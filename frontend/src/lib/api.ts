import type { BoardData } from "@/lib/kanban";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
  }
}

const request = async (path: string, method = "GET", body?: object) => {
  const response = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw new ApiError(response.status, `${method} ${path} failed with ${response.status}`);
  }
  return (await response.json()) as BoardData;
};

export const boardApi = {
  get: () => request("/api/board"),
  renameColumn: (columnId: string, title: string) =>
    request(`/api/columns/${encodeURIComponent(columnId)}`, "PATCH", { title }),
  createCard: (columnId: string, title: string, details: string) =>
    request("/api/cards", "POST", { columnId, title, details }),
  updateCard: (cardId: string, title: string, details: string) =>
    request(`/api/cards/${encodeURIComponent(cardId)}`, "PATCH", { title, details }),
  moveCard: (cardId: string, columnId: string, position: number) =>
    request(`/api/cards/${encodeURIComponent(cardId)}/move`, "POST", {
      columnId,
      position,
    }),
  deleteCard: (cardId: string) =>
    request(`/api/cards/${encodeURIComponent(cardId)}`, "DELETE"),
};

export type ChatMessage = { role: "user" | "assistant"; content: string };

export type ChatResult =
  | { reply: string; boardChanged: false }
  | { reply: string; boardChanged: true; board: BoardData };

const isString = (value: unknown): value is string => typeof value === "string";

const isBoardData = (value: unknown): value is BoardData => {
  if (typeof value !== "object" || value === null) return false;
  const { columns, cards } = value as Record<string, unknown>;
  if (!Array.isArray(columns) || typeof cards !== "object" || cards === null) return false;
  const cardMap = cards as Record<string, unknown>;
  return columns.every((column) => {
    const { id, title, cardIds } = (column ?? {}) as Record<string, unknown>;
    return (
      isString(id) &&
      isString(title) &&
      Array.isArray(cardIds) &&
      cardIds.every((cardId) => {
        const card = (isString(cardId) ? cardMap[cardId] : null) as Record<string, unknown> | null;
        return (
          card !== null &&
          typeof card === "object" &&
          card.id === cardId &&
          isString(card.title) &&
          isString(card.details)
        );
      })
    );
  });
};

// Any response that does not match {reply, boardChanged, board} is treated as a failed
// request: the caller shows an error and keeps its current board and history.
const parseChatResult = (data: unknown): ChatResult => {
  const { reply, boardChanged, board } = (data ?? {}) as Record<string, unknown>;
  if (!isString(reply) || !reply.trim()) {
    throw new ApiError(0, "Malformed AI response");
  }
  if (boardChanged === false) {
    return { reply, boardChanged };
  }
  if (boardChanged === true && isBoardData(board)) {
    return { reply, boardChanged, board };
  }
  throw new ApiError(0, "Malformed AI response");
};

export const aiApi = {
  chat: async (message: string, history: ChatMessage[]): Promise<ChatResult> => {
    const response = await fetch("/api/ai/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });
    if (!response.ok) {
      throw new ApiError(response.status, `POST /api/ai/chat failed with ${response.status}`);
    }
    return parseChatResult(await response.json().catch(() => null));
  },
};
