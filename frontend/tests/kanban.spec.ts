import { expect, test, type Page } from "@playwright/test";

const usesExternalServer = Boolean(process.env.PLAYWRIGHT_BASE_URL);

const mockAuthApi = async (page: Page, initiallySignedIn: boolean) => {
  let signedIn = initiallySignedIn;

  await page.route("**/api/me", async (route) => {
    await route.fulfill({
      status: signedIn ? 200 : 401,
      contentType: "application/json",
      body: JSON.stringify(
        signedIn ? { username: "user" } : { detail: "Not authenticated" }
      ),
    });
  });

  await page.route("**/api/login", async (route) => {
    const credentials = route.request().postDataJSON() as {
      username: string;
      password: string;
    };
    signedIn =
      credentials.username === "user" && credentials.password === "password";
    await route.fulfill({
      status: signedIn ? 200 : 401,
      contentType: "application/json",
      body: JSON.stringify(
        signedIn
          ? { username: "user" }
          : { detail: "Invalid username or password" }
      ),
    });
  });

  await page.route("**/api/logout", async (route) => {
    signedIn = false;
    await route.fulfill({ status: 204, body: "" });
  });
};

const openAuthenticatedBoard = async (page: Page) => {
  if (!usesExternalServer) {
    await mockAuthApi(page, true);
  }
  await page.goto("/");
  if (usesExternalServer) {
    await page.getByLabel("Username").fill("user");
    await page.getByLabel("Password").fill("password");
    await page.getByRole("button", { name: "Sign in" }).click();
  }
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
};

test("signs in, keeps the session on reload, and logs out", async ({ page }) => {
  if (!usesExternalServer) {
    await mockAuthApi(page, false);
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

test("loads the kanban board", async ({ page }) => {
  await openAuthenticatedBoard(page);
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("adds a card to a column", async ({ page }) => {
  await openAuthenticatedBoard(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText("Playwright card")).toBeVisible();
});

test("moves a card between columns", async ({ page }) => {
  await openAuthenticatedBoard(page);
  const card = page.getByTestId("card-card-1");
  const targetColumn = page.getByTestId("column-col-review");
  const cardBox = await card.boundingBox();
  const columnBox = await targetColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }

  await page.mouse.move(
    cardBox.x + cardBox.width / 2,
    cardBox.y + cardBox.height / 2
  );
  await page.mouse.down();
  await page.mouse.move(
    columnBox.x + columnBox.width / 2,
    columnBox.y + 120,
    { steps: 12 }
  );
  await page.mouse.up();
  await expect(targetColumn.getByTestId("card-card-1")).toBeVisible();
});
