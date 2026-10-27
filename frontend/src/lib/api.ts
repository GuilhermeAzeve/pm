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
