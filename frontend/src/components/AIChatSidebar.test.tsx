import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData, type BoardData } from "@/lib/kanban";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

type ChatBody = { message: string; history: { role: string; content: string }[] };

// GET /api/board returns the initial board; POST /api/ai/chat calls `respond`, which may
// return a promise so a test can hold the request open.
const mockApi = (respond: (body: ChatBody) => Response | Promise<Response>) => {
  const chats: ChatBody[] = [];
  let boardLoads = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/board" && (init?.method ?? "GET") === "GET") {
        boardLoads += 1;
        return json(200, initialData);
      }
      if (url === "/api/ai/chat" && init?.method === "POST") {
        const body = JSON.parse(init.body as string) as ChatBody;
        chats.push(body);
        return respond(body);
      }
      throw new Error(`Unexpected request ${init?.method} ${url}`);
    })
  );
  return { chats, boardLoads: () => boardLoads };
};

const replyOnly = (reply: string) => json(200, { reply, boardChanged: false, board: null });

const withNewCard: BoardData = {
  columns: initialData.columns.map((column) =>
    column.id === "col-backlog"
      ? { ...column, cardIds: [...column.cardIds, "card-ai"] }
      : column
  ),
  cards: {
    ...initialData.cards,
    "card-ai": { id: "card-ai", title: "Write release notes", details: "" },
  },
};

const renderBoard = async () => {
  render(<KanbanBoard username="user" onLogout={() => {}} />);
  await screen.findAllByTestId(/^column-/);
};

const chat = () => screen.getByRole("complementary", { name: "AI assistant" });
const input = () => within(chat()).getByLabelText("Message");
const sendButton = () => within(chat()).getByRole("button", { name: /Send/ });
const log = () => within(chat()).getByRole("log", { name: "Conversation" });

const send = async (message: string) => {
  await userEvent.clear(input());
  await userEvent.type(input(), message);
  await userEvent.click(sendButton());
};

describe("AIChatSidebar", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the heading, empty state, labeled input and a disabled Send button", async () => {
    mockApi(() => replyOnly("Hi"));
    await renderBoard();

    expect(within(chat()).getByRole("heading", { name: "AI assistant" })).toBeInTheDocument();
    expect(within(log()).getByText(/No messages yet/)).toBeInTheDocument();
    expect(input()).toHaveValue("");
    expect(sendButton()).toBeDisabled();
  });

  it("does not send an empty or whitespace message", async () => {
    const { chats } = mockApi(() => replyOnly("Hi"));
    await renderBoard();

    await userEvent.type(input(), "   ");
    expect(sendButton()).toBeDisabled();
    await userEvent.type(input(), "{Enter}");
    expect(chats).toHaveLength(0);
    expect(within(log()).getByText(/No messages yet/)).toBeInTheDocument();
  });

  it("sends trimmed messages with the exact prior history and renders both sides", async () => {
    const replies = ["First reply", "Second reply", "Third reply"];
    const { chats } = mockApi(() => replyOnly(replies[chats.length - 1]));
    await renderBoard();

    await send("  Hello  ");
    expect(await within(log()).findByText("First reply")).toBeInTheDocument();
    await send("What is on the board?");
    expect(await within(log()).findByText("Second reply")).toBeInTheDocument();
    await send("Thanks");
    expect(await within(log()).findByText("Third reply")).toBeInTheDocument();

    expect(chats).toEqual([
      { message: "Hello", history: [] },
      {
        message: "What is on the board?",
        history: [
          { role: "user", content: "Hello" },
          { role: "assistant", content: "First reply" },
        ],
      },
      {
        message: "Thanks",
        history: [
          { role: "user", content: "Hello" },
          { role: "assistant", content: "First reply" },
          { role: "user", content: "What is on the board?" },
          { role: "assistant", content: "Second reply" },
        ],
      },
    ]);
    const texts = within(log())
      .getAllByText(/^(You|Assistant)$/)
      .map((label) => label.textContent);
    expect(texts).toEqual(["You", "Assistant", "You", "Assistant", "You", "Assistant"]);
    expect(input()).toHaveValue("");
  });

  it("shows the user message and a pending state, and blocks duplicate sends", async () => {
    let resolve: (response: Response) => void = () => {};
    const { chats } = mockApi(
      () => new Promise<Response>((done) => (resolve = done))
    );
    await renderBoard();

    await send("Add a card");
    expect(within(log()).getByText("Add a card")).toBeInTheDocument();
    expect(within(chat()).getByRole("status")).toHaveTextContent("Assistant is thinking...");
    expect(sendButton()).toBeDisabled();
    expect(sendButton()).toHaveTextContent("Sending...");
    expect(input()).toBeDisabled();
    await userEvent.click(sendButton());
    expect(chats).toHaveLength(1);

    resolve(replyOnly("Done"));
    expect(await within(log()).findByText("Done")).toBeInTheDocument();
    expect(within(chat()).queryByRole("status")).not.toBeInTheDocument();
    expect(input()).toBeEnabled();
  });

  it("keeps the board unchanged for a reply-only response", async () => {
    const { boardLoads } = mockApi(() => replyOnly("Nothing to change."));
    await renderBoard();

    await send("Hello");
    expect(await within(log()).findByText("Nothing to change.")).toBeInTheDocument();
    expect(within(screen.getByTestId("column-col-backlog")).getAllByTestId(/^card-/)).toHaveLength(2);
    expect(boardLoads()).toBe(1);
  });

  it("replaces the board with the returned board when it changed, without reloading", async () => {
    const { boardLoads } = mockApi(() =>
      json(200, { reply: "Added it.", boardChanged: true, board: withNewCard })
    );
    await renderBoard();

    await send("Add a card called Write release notes");
    expect(await within(log()).findByText("Added it.")).toBeInTheDocument();
    const backlog = screen.getByTestId("column-col-backlog");
    expect(within(backlog).getByText("Write release notes")).toBeInTheDocument();
    expect(within(backlog).getAllByTestId(/^card-/)).toHaveLength(3);
    expect(boardLoads()).toBe(1);
  });

  it("shows an error on failure, keeps the board and history, and recovers on retry", async () => {
    let fail = true;
    const { chats } = mockApi(() =>
      fail
        ? json(502, { detail: "AI provider request failed" })
        : json(200, { reply: "Added it.", boardChanged: true, board: withNewCard })
    );
    await renderBoard();

    await send("Add a card");
    expect(await within(chat()).findByRole("alert")).toHaveTextContent(
      "The assistant could not respond."
    );
    expect(within(log()).getByText(/No messages yet/)).toBeInTheDocument();
    expect(input()).toHaveValue("Add a card");
    expect(screen.queryByText("Write release notes")).not.toBeInTheDocument();

    fail = false;
    await userEvent.click(sendButton());
    expect(await within(log()).findByText("Added it.")).toBeInTheDocument();
    expect(within(chat()).queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("Write release notes")).toBeInTheDocument();
    expect(chats[1]).toEqual({ message: "Add a card", history: [] });
  });

  it("treats a network error as a failure", async () => {
    mockApi(() => Promise.reject(new TypeError("Failed to fetch")));
    await renderBoard();

    await send("Hello");
    expect(await within(chat()).findByRole("alert")).toBeInTheDocument();
    expect(sendButton()).toBeEnabled();
  });

  it.each([
    ["non-JSON body", () => new Response("oops", { status: 200 })],
    ["missing reply", () => json(200, { boardChanged: false, board: null })],
    ["empty reply", () => json(200, { reply: "  ", boardChanged: false, board: null })],
    ["missing boardChanged", () => json(200, { reply: "Hi", board: null })],
    ["changed without a board", () => json(200, { reply: "Hi", boardChanged: true, board: null })],
    [
      "changed with an invalid board",
      () => json(200, { reply: "Hi", boardChanged: true, board: { columns: "x", cards: {} } }),
    ],
    [
      "changed with a card missing from cards",
      () =>
        json(200, {
          reply: "Hi",
          boardChanged: true,
          board: { columns: [{ id: "c", title: "C", cardIds: ["gone"] }], cards: {} },
        }),
    ],
  ])("rejects a malformed response (%s) without changing the board", async (_: string, respond: () => Response) => {
    const { chats } = mockApi(respond);
    await renderBoard();

    await send("Hello");
    expect(await within(chat()).findByRole("alert")).toBeInTheDocument();
    expect(within(log()).queryByText("Hi")).not.toBeInTheDocument();
    expect(screen.getAllByTestId(/^column-/)).toHaveLength(5);
    expect(within(screen.getByTestId("column-col-backlog")).getAllByTestId(/^card-/)).toHaveLength(2);

    await send("Again");
    await waitFor(() => expect(chats).toHaveLength(2));
    expect(chats[1].history).toEqual([]);
  });
});
