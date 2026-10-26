# Database design

Part 5 defines the persistence and API contract for Parts 6, 7 and 9. It does not add
database code. The machine-readable table design is in `docs/schema.json`.

## Scope and decisions

- SQLite is the local database.
- The schema supports multiple users, but the MVP seeds and authenticates only `user`.
- A unique constraint on `boards.user_id` enforces one board per user.
- Columns are fixed: they can be renamed, but the API does not create, delete or reorder
  them.
- Column and card public IDs remain strings so the current frontend IDs can be preserved.
  Their primary keys include `board_id`, allowing different users to receive the same
  seed IDs without collisions.
- Authentication credentials remain hardcoded in the application. No password or session
  data is stored in SQLite.

## Tables and relationships

`users` contains an integer primary key and a unique username. `boards` belongs to a user,
and `UNIQUE(user_id)` limits that user to one board. `board_columns` belongs to a board and
uses `(board_id, id)` as its primary key. `cards` uses `(board_id, id)` as its primary key
and a composite foreign key to `(board_id, column_id)` in `board_columns`. This prevents a
card from referring to a column on another user's board.

Board, column and card relationships use cascading deletes. Part 6 will enable SQLite
foreign-key enforcement on every connection with `PRAGMA foreign_keys = ON`.

## Ordering

`board_columns.position` and `cards.position` are zero-based integers. Reads use
`ORDER BY position`; card IDs are used only as identifiers, never as ordering keys. Unique
constraints prevent two columns on a board or two cards in a column from sharing a
position.

A card move is handled in one transaction. The service builds the desired ordered ID
lists for the affected source and destination columns, moves their current positions above
the normal range with a safe positive offset, and then writes consecutive positions
starting at zero. This avoids transient unique-constraint collisions. Adding and deleting
a card uses the same reindex helper, so positions remain contiguous.

## Creation, storage and seeding

Part 6 will create the parent directory and SQLite file when they do not exist, then run
idempotent `CREATE TABLE IF NOT EXISTS` statements. The database path will come from
`DATABASE_PATH`, defaulting to `/data/pm.db` in the container and a repository-local data
path during development.

The Docker start scripts will mount a named volume at `/data`. The stop scripts remove the
container but not the volume, so data survives normal stop/start and image rebuilds. No
database file or credentials will be baked into the image or committed.

Initialization inserts the hardcoded `user` row if it is missing. When an authenticated
user first requests a board and has none, one transaction creates the board and seeds the
five columns and eight cards from `frontend/src/lib/kanban.ts`. Repeated requests do not
reseed or overwrite an existing board.

## Frontend mapping

The API returns the existing frontend `BoardData` shape without database-only fields:

```json
{
  "columns": [
    {
      "id": "col-backlog",
      "title": "Backlog",
      "cardIds": ["card-1", "card-2"]
    }
  ],
  "cards": {
    "card-1": {
      "id": "card-1",
      "title": "Align roadmap themes",
      "details": "Draft quarterly themes with impact statements and metrics."
    }
  }
}
```

Rows in `board_columns` are read by column position. For each column, card rows are read by
card position to form `cardIds`. The same card rows are keyed by ID to form the `cards`
object. The database therefore preserves every field and ordering relationship in the
current `initialData` without adding database details to the frontend model.

## Part 6 API

All board routes require the Part 4 session. The backend resolves the session username to
a user and restricts every query by that user's board ID. Anonymous requests return `401`;
IDs not found on that board return `404`; invalid bodies return `422`.

| Method | Route | Request body | Success response |
| --- | --- | --- | --- |
| `GET` | `/api/board` | none | `200` with `BoardData` |
| `PATCH` | `/api/columns/{column_id}` | `{ "title": string }` | `200` with updated `BoardData` |
| `POST` | `/api/cards` | `{ "columnId": string, "title": string, "details": string }` | `201` with updated `BoardData` |
| `PATCH` | `/api/cards/{card_id}` | `{ "title": string, "details": string }` | `200` with updated `BoardData` |
| `POST` | `/api/cards/{card_id}/move` | `{ "columnId": string, "position": integer }` | `200` with updated `BoardData` |
| `DELETE` | `/api/cards/{card_id}` | none | `200` with updated `BoardData` |

Titles are trimmed and must not be empty. Details are strings and may be empty. A move's
`position` is the card's desired zero-based index in the final target-column list after
the moving card has been removed from its previous position. It may equal the final list's
last index, which covers dropping at the end.

Returning the complete board after each mutation keeps Part 7 simple: the frontend can
replace its local state with the server result and cannot drift from server ordering.

## Part 9 AI updates

Board mutations will live in service functions that accept the authenticated board ID and
a database transaction. HTTP routes call these functions; the AI route will call the same
functions directly rather than making internal HTTP requests.

The structured AI result may contain an ordered list of create, edit and move operations.
Part 9 will validate the entire result first, then apply all operations in one transaction.
If an operation references an unknown card or column, or any operation fails, the
transaction rolls back and the existing board remains unchanged. A successful response
returns the assistant reply, a board-changed flag and the freshly serialized `BoardData`.

