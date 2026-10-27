import { execSync } from "node:child_process";
import { expect, test, type Locator, type Page } from "@playwright/test";
import type { BoardData } from "../src/lib/kanban";
import { mockApi } from "./mockApi";

// With PLAYWRIGHT_BASE_URL the tests use the real FastAPI API and its database; otherwise
// the API is mocked. E2E_RESTART_COMMAND (optional, external only) restarts the container
// during the persistence test, for example "docker restart pm-app".
const usesExternalServer = Boolean(process.env.PLAYWRIGHT_BASE_URL);
const restartCommand = process.env.E2E_RESTART_COMMAND;

const signIn = async (page: Page) => {
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
};

const openAuthenticatedBoard = async (page: Page) => {
  if (!usesExternalServer) {
    await mockApi(page, true);
  }
  await page.goto("/");
  if (usesExternalServer) {
    await signIn(page);
  }
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
};

const cardByTitle = (page: Page, title: string) =>
  page.locator('[data-testid^="card-"]').filter({ hasText: title });

const dragTo = async (page: Page, card: Locator, column: Locator) => {
  const cardBox = await card.boundingBox();
  const columnBox = await column.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }
  await page.mouse.move(cardBox.x + cardBox.width / 2, cardBox.y + cardBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(columnBox.x + columnBox.width / 2, columnBox.y + 120, {
    steps: 12,
  });
  await page.mouse.up();
};

const apiDone = (page: Page, method: string, path: string) =>
  page.waitForResponse(
    (response) =>
      response.request().method() === method && response.url().includes(path) && response.ok()
  );

test("signs in, keeps the session on reload, and logs out", async ({ page }) => {
  if (!usesExternalServer) {
    await mockApi(page, false);
  }
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("wrong");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Invalid username or password.")).toBeVisible();

  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();

  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("loads the kanban board from the API", async ({ page }) => {
  await openAuthenticatedBoard(page);
  await expect(page.getByLabel("Column title")).toHaveCount(5);
});

test("persists column rename and card add, edit, move and delete", async ({ page }) => {
  test.setTimeout(300_000);
  const suffix = Date.now().toString(36);
  const columnTitle = `E2E column ${suffix}`;
  const cardTitle = `E2E card ${suffix}`;
  const editedTitle = `E2E edited ${suffix}`;
  const tempTitle = `E2E temp ${suffix}`;

  await openAuthenticatedBoard(page);
  const discovery = page.getByTestId("column-col-discovery");
  const originalTitle = await discovery.getByLabel("Column title").inputValue();
  const backlog = page.getByTestId("column-col-backlog");
  const review = page.getByTestId("column-col-review");

  try {
    const titleInput = discovery.getByLabel("Column title");
    await titleInput.fill(columnTitle);
    await Promise.all([apiDone(page, "PATCH", "/api/columns/"), titleInput.press("Enter")]);

    for (const title of [cardTitle, tempTitle]) {
      await backlog.getByRole("button", { name: /add a card/i }).click();
      await backlog.getByPlaceholder("Card title").fill(title);
      await backlog.getByPlaceholder("Details").fill("Added via e2e.");
      await backlog.getByRole("button", { name: /add card/i }).click();
      await expect(cardByTitle(page, title)).toBeVisible();
    }

    const cardTestId = (await cardByTitle(page, cardTitle).getAttribute("data-testid"))!;
    const card = page.getByTestId(cardTestId);
    await card.getByRole("button", { name: `Edit ${cardTitle}` }).click();
    await card.getByLabel("Card title").fill(editedTitle);
    await card.getByLabel("Card details").fill("Edited via e2e.");
    await card.getByRole("button", { name: "Save" }).click();
    await expect(card.getByText(editedTitle)).toBeVisible();

    await Promise.all([apiDone(page, "POST", "/move"), dragTo(page, card, review)]);
    await expect(review.getByTestId(cardTestId)).toBeVisible();

    await page.getByRole("button", { name: `Delete ${tempTitle}`, exact: true }).click();
    await expect(cardByTitle(page, tempTitle)).toHaveCount(0);

    const verify = async () => {
      await expect(discovery.getByLabel("Column title")).toHaveValue(columnTitle);
      await expect(review.getByTestId(cardTestId)).toContainText(editedTitle);
      await expect(review.getByTestId(cardTestId)).toContainText("Edited via e2e.");
      await expect(backlog.getByTestId(cardTestId)).toHaveCount(0);
      await expect(cardByTitle(page, tempTitle)).toHaveCount(0);
    };

    await page.reload();
    await verify();

    if (usesExternalServer && restartCommand) {
      execSync(restartCommand, { stdio: "inherit" });
      await expect
        .poll(
          async () => (await page.request.get("/api/health").catch(() => null))?.status(),
          { timeout: 120_000 }
        )
        .toBe(200);
      await page.reload();
      await verify();
    }
  } finally {
    // Remove test cards and restore the column so a real database is left as found.
    if (usesExternalServer) {
      const board = (await (await page.request.get("/api/board")).json()) as BoardData;
      for (const { id, title } of Object.values(board.cards)) {
        if (title.endsWith(suffix)) {
          await page.request.delete(`/api/cards/${id}`);
        }
      }
      await page.request.patch("/api/columns/col-discovery", {
        data: { title: originalTitle },
      });
    }
  }
});
