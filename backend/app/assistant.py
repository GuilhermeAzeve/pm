"""Part 9 AI board assistant: prompt building, the Structured Outputs schema, local
validation of the model result and applying its operations through the board services."""

import json
import sqlite3
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints

from app import board

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class InvalidOutputError(Exception):
    """The model returned content that is not a valid result for this board."""


class CreateOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["create"]
    column_id: Text = Field(alias="columnId")
    title: Text
    details: str


class EditOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["edit"]
    card_id: Text = Field(alias="cardId")
    title: Text
    details: str


class MoveOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["move"]
    card_id: Text = Field(alias="cardId")
    column_id: Text = Field(alias="columnId")
    position: Annotated[StrictInt, Field(ge=0)]


Operation = Annotated[
    CreateOperation | EditOperation | MoveOperation, Field(discriminator="type")
]


class AssistantResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply: Text
    operations: list[Operation]


def _object(description: str, properties: dict) -> dict:
    return {
        "type": "object",
        "description": description,
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _type(name: str) -> dict:
    return {"type": "string", "enum": [name], "description": f"Always \"{name}\"."}


_TITLE = {"type": "string", "description": "Card title; must not be empty."}
_DETAILS = {"type": "string", "description": "Card details; may be an empty string."}
_CARD_ID = {"type": "string", "description": "ID of an existing card on the board."}
_COLUMN_ID = {"type": "string", "description": "ID of an existing column on the board."}

SCHEMA = _object(
    "Reply to the user and the ordered board operations to apply.",
    {
        "reply": {"type": "string", "description": "Message shown to the user; not empty."},
        "operations": {
            "type": "array",
            "description": "Operations applied in order. Empty when the board should not change.",
            "items": {
                "anyOf": [
                    _object(
                        "Create a card at the end of a column.",
                        {
                            "type": _type("create"),
                            "columnId": _COLUMN_ID,
                            "title": _TITLE,
                            "details": _DETAILS,
                        },
                    ),
                    _object(
                        "Replace the title and details of a card.",
                        {
                            "type": _type("edit"),
                            "cardId": _CARD_ID,
                            "title": _TITLE,
                            "details": _DETAILS,
                        },
                    ),
                    _object(
                        "Move a card to a column and position.",
                        {
                            "type": _type("move"),
                            "cardId": _CARD_ID,
                            "columnId": _COLUMN_ID,
                            "position": {
                                "type": "integer",
                                "description": "Zero-based index in the target column, counted"
                                " after removing the card from its current place.",
                            },
                        },
                    ),
                ]
            },
        },
    },
)

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {"name": "board_assistant_result", "strict": True, "schema": SCHEMA},
}

INSTRUCTIONS = """You are the assistant for a single user's Kanban board. Answer the \
user's latest message using the conversation and the current board below.

You may change the board only with these operations, applied in order:
- create: add a card with title and details to the end of column columnId.
- edit: replace the title and details of card cardId.
- move: move card cardId to column columnId at a zero-based position, counted after \
removing the card from its current place.

Use only column and card IDs that appear in the board. Deleting cards and renaming \
columns are not supported. Leave operations empty when no change is needed, and always \
say in reply what you did or why you could not.

Current board as JSON (columns in order, each with its ordered cardIds; cards by ID):
"""


def build_messages(
    board_data: dict, history: list[dict[str, str]], message: str
) -> list[dict[str, str]]:
    system = INSTRUCTIONS + json.dumps(board_data, ensure_ascii=False)
    return [{"role": "system", "content": system}, *history, {"role": "user", "content": message}]


def parse_result(content: str) -> AssistantResult:
    try:
        return AssistantResult.model_validate(json.loads(content), strict=True)
    except ValueError:
        # Covers JSON decode errors and pydantic ValidationError; details are not exposed.
        raise InvalidOutputError("AI output did not match the schema") from None


def apply_operations(
    conn: sqlite3.Connection, board_id: int, operations: list[Operation]
) -> None:
    """Apply operations in order. Raises InvalidOutputError on the first failure; the
    caller's transaction must then be rolled back."""
    try:
        for op in operations:
            match op:
                case CreateOperation():
                    board.create_card(conn, board_id, op.column_id, op.title, op.details)
                case EditOperation():
                    board.update_card(conn, board_id, op.card_id, op.title, op.details)
                case MoveOperation():
                    board.move_card(conn, board_id, op.card_id, op.column_id, op.position)
    except (board.NotFoundError, board.InvalidMoveError, sqlite3.IntegrityError):
        raise InvalidOutputError("AI operation could not be applied") from None
