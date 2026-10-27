import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData, type BoardData } from "@/lib/kanban";

type Call = { method: string; url: string; body: unknown };

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

// Mocks fetch: GET /api/board returns `board`; mutations call `respond` (default: echo
// the board) so each test controls the server result.
const mockApi = (
  respond: (call: Call) => Response = () => json(200, initialData),
  board: () => Response = () => json(200, initialData)
) => {
  const calls: Call[] = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const call = {
      method: init?.method ?? "GET",
      url,
      body: init?.body ? JSON.parse(init.body as string) : undefined,
    };
    if (call.method === "GET" && url === "/api/board") {
      return board();
    }
    calls.push(call);
    return respond(call);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
};

const withColumnTitle = (title: string): BoardData => ({
  ...initialData,
  columns: initialData.columns.map((column, index) =>
    index === 0 ? { ...column, title } : column
  ),
});

const renderBoard = async () => {
  render(<KanbanBoard username="user" onLogout={() => {}} />);
  await screen.findAllByTestId(/^column-/);
};

const firstColumn = () => screen.getAllByTestId(/^column-/)[0];

describe("KanbanBoard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows a loading state, then the board from the API", async () => {
    mockApi();
    render(<KanbanBoard username="user" onLogout={() => {}} />);
    expect(screen.getByText("Loading board...")).toBeInTheDocument();
    expect(await screen.findAllByTestId(/^column-/)).toHaveLength(5);
    expect(screen.getByText("Align roadmap themes")).toBeInTheDocument();
  });

  it("shows an error when loading fails and recovers on reload", async () => {
    let fail = true;
    mockApi(undefined, () => (fail ? json(500, {}) : json(200, initialData)));
    render(<KanbanBoard username="user" onLogout={() => {}} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load the board.");
    expect(screen.queryAllByTestId(/^column-/)).toHaveLength(0);

    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Reload board" }));
    expect(await screen.findAllByTestId(/^column-/)).toHaveLength(5);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renames a column on blur with a trimmed title", async () => {
    const { calls } = mockApi(() => json(200, withColumnTitle("New Name")));
    await renderBoard();
    const input = within(firstColumn()).getByLabelText("Column title");

    await userEvent.clear(input);
    await userEvent.type(input, "  New Name  ");
    expect(calls).toHaveLength(0);
    await userEvent.tab();

    expect(calls).toEqual([
      { method: "PATCH", url: "/api/columns/col-backlog", body: { title: "New Name" } },
    ]);
    await waitFor(() =>
      expect(within(firstColumn()).getByLabelText("Column title")).toHaveValue("New Name")
    );
  });

  it("renames a column on Enter", async () => {
    const { calls } = mockApi(() => json(200, withColumnTitle("Ideas")));
    await renderBoard();
    const input = within(firstColumn()).getByLabelText("Column title");

    await userEvent.clear(input);
    await userEvent.type(input, "Ideas{Enter}");
    expect(calls).toHaveLength(1);
  });

  it("does not send an empty or unchanged column title", async () => {
    const { calls } = mockApi();
    await renderBoard();
    const input = within(firstColumn()).getByLabelText("Column title");

    await userEvent.clear(input);
    await userEvent.tab();
    expect(input).toHaveValue("Backlog");

    await userEvent.click(input);
    await userEvent.tab();
    expect(calls).toHaveLength(0);
  });

  it("restores the column title and shows an error when rename fails", async () => {
    mockApi(() => json(500, {}));
    await renderBoard();
    const input = within(firstColumn()).getByLabelText("Column title");

    await userEvent.clear(input);
    await userEvent.type(input, "Broken{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save your change.");
    expect(within(firstColumn()).getByLabelText("Column title")).toHaveValue("Backlog");
  });

  it("adds a card through the API and shows the returned board", async () => {
    const created: BoardData = {
      columns: initialData.columns.map((column, index) =>
        index === 0 ? { ...column, cardIds: [...column.cardIds, "card-new"] } : column
      ),
      cards: {
        ...initialData.cards,
        "card-new": { id: "card-new", title: "New card", details: "Notes" },
      },
    };
    const { calls } = mockApi(() => json(201, created));
    await renderBoard();
    const column = firstColumn();

    await userEvent.click(within(column).getByRole("button", { name: /add a card/i }));
    await userEvent.type(within(column).getByPlaceholderText(/card title/i), " New card ");
    await userEvent.type(within(column).getByPlaceholderText(/details/i), "Notes");
    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(calls).toEqual([
      {
        method: "POST",
        url: "/api/cards",
        body: { columnId: "col-backlog", title: "New card", details: "Notes" },
      },
    ]);
    expect(await within(column).findByText("New card")).toBeInTheDocument();
    expect(within(column).queryByPlaceholderText(/card title/i)).not.toBeInTheDocument();
  });

  it("keeps the new card form open when adding fails", async () => {
    mockApi(() => json(500, {}));
    await renderBoard();
    const column = firstColumn();

    await userEvent.click(within(column).getByRole("button", { name: /add a card/i }));
    await userEvent.type(within(column).getByPlaceholderText(/card title/i), "New card");
    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(within(column).getByPlaceholderText(/card title/i)).toHaveValue("New card");
  });

  it("edits a card inline", async () => {
    const edited: BoardData = {
      ...initialData,
      cards: {
        ...initialData.cards,
        "card-1": { id: "card-1", title: "Edited title", details: "" },
      },
    };
    const { calls } = mockApi(() => json(200, edited));
    await renderBoard();
    const card = screen.getByTestId("card-card-1");

    await userEvent.click(within(card).getByRole("button", { name: "Edit Align roadmap themes" }));
    const title = within(card).getByLabelText("Card title");
    await userEvent.clear(title);
    await userEvent.type(title, " Edited title ");
    await userEvent.clear(within(card).getByLabelText("Card details"));
    await userEvent.click(within(card).getByRole("button", { name: "Save" }));

    expect(calls).toEqual([
      {
        method: "PATCH",
        url: "/api/cards/card-1",
        body: { title: "Edited title", details: "" },
      },
    ]);
    expect(await within(card).findByText("Edited title")).toBeInTheDocument();
    expect(within(card).queryByLabelText("Card title")).not.toBeInTheDocument();
  });

  it("does not save an empty card title and cancels without a request", async () => {
    const { calls } = mockApi();
    await renderBoard();
    const card = screen.getByTestId("card-card-1");

    await userEvent.click(within(card).getByRole("button", { name: "Edit Align roadmap themes" }));
    await userEvent.clear(within(card).getByLabelText("Card title"));
    await userEvent.click(within(card).getByRole("button", { name: "Save" }));
    await userEvent.click(within(card).getByRole("button", { name: "Cancel" }));

    expect(calls).toHaveLength(0);
    expect(within(card).getByText("Align roadmap themes")).toBeInTheDocument();
  });

  it("deletes a card through the API", async () => {
    const deleted: BoardData = {
      columns: initialData.columns.map((column, index) =>
        index === 0 ? { ...column, cardIds: ["card-2"] } : column
      ),
      cards: Object.fromEntries(
        Object.entries(initialData.cards).filter(([id]) => id !== "card-1")
      ),
    };
    const { calls } = mockApi(() => json(200, deleted));
    await renderBoard();

    await userEvent.click(screen.getByRole("button", { name: "Delete Align roadmap themes" }));

    expect(calls).toEqual([{ method: "DELETE", url: "/api/cards/card-1", body: undefined }]);
    await waitFor(() =>
      expect(screen.queryByText("Align roadmap themes")).not.toBeInTheDocument()
    );
  });

  it("reloads the server board when a mutation fails", async () => {
    const { fetchMock } = mockApi(() => json(500, {}));
    await renderBoard();

    await userEvent.click(screen.getByRole("button", { name: "Delete Align roadmap themes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save your change.");
    expect(screen.getByText("Align roadmap themes")).toBeInTheDocument();
    const boardLoads = fetchMock.mock.calls.filter((call: unknown[]) => call[0] === "/api/board");
    expect(boardLoads.length).toBeGreaterThanOrEqual(2);
  });
});
