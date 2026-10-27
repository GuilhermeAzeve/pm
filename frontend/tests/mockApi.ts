import type { Page, Route } from "@playwright/test";
import { initialData, type BoardData } from "../src/lib/kanban";

// Stateful stand-in for the FastAPI auth and board API, used when Playwright runs against
// the standalone Next.js dev server. State lives for the test, so it survives reloads.
export const mockApi = async (page: Page, initiallySignedIn: boolean) => {
  let signedIn = initiallySignedIn;
  const board: BoardData = structuredClone(initialData);
  let nextId = 1;

  const reply = (route: Route, status: number, body?: unknown) =>
    route.fulfill({
      status,
      contentType: "application/json",
      body: body === undefined ? "" : JSON.stringify(body),
    });

  const columnOf = (cardId: string) =>
    board.columns.find((column) => column.cardIds.includes(cardId));

  await page.route("**/api/me", (route) =>
    signedIn
      ? reply(route, 200, { username: "user" })
      : reply(route, 401, { detail: "Not authenticated" })
  );

  await page.route("**/api/login", (route) => {
    const credentials = route.request().postDataJSON() as {
      username: string;
      password: string;
    };
    signedIn = credentials.username === "user" && credentials.password === "password";
    return signedIn
      ? reply(route, 200, { username: "user" })
      : reply(route, 401, { detail: "Invalid username or password" });
  });

  await page.route("**/api/logout", (route) => {
    signedIn = false;
    return route.fulfill({ status: 204, body: "" });
  });

  await page.route(/\/api\/(board|columns|cards)/, (route) => {
    if (!signedIn) {
      return reply(route, 401, { detail: "Not authenticated" });
    }
    const request = route.request();
    const method = request.method();
    const path = new URL(request.url()).pathname;
    const body = request.postDataJSON() ?? {};
    const [, , resource, id, action] = path.split("/");

    if (method === "GET" && resource === "board") {
      return reply(route, 200, board);
    }

    if (method === "PATCH" && resource === "columns") {
      board.columns = board.columns.map((column) =>
        column.id === id ? { ...column, title: body.title.trim() } : column
      );
      return reply(route, 200, board);
    }

    if (method === "POST" && resource === "cards" && !id) {
      const cardId = `card-mock-${nextId++}`;
      board.cards[cardId] = { id: cardId, title: body.title.trim(), details: body.details };
      board.columns = board.columns.map((column) =>
        column.id === body.columnId
          ? { ...column, cardIds: [...column.cardIds, cardId] }
          : column
      );
      return reply(route, 201, board);
    }

    if (method === "PATCH" && resource === "cards") {
      board.cards[id] = { id, title: body.title.trim(), details: body.details };
      return reply(route, 200, board);
    }

    if (method === "POST" && action === "move") {
      const columns = board.columns.map((column) => ({
        ...column,
        cardIds: column.cardIds.filter((cardId) => cardId !== id),
      }));
      const target = columns.find((column) => column.id === body.columnId)!;
      target.cardIds.splice(body.position, 0, id);
      board.columns = columns;
      return reply(route, 200, board);
    }

    if (method === "DELETE" && resource === "cards") {
      const column = columnOf(id)!;
      column.cardIds = column.cardIds.filter((cardId) => cardId !== id);
      delete board.cards[id];
      return reply(route, 200, board);
    }

    return reply(route, 404, { detail: "Not Found" });
  });
};
