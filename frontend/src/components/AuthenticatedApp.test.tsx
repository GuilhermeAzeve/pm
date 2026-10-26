import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthenticatedApp } from "@/components/AuthenticatedApp";

const response = (status: number, body: object = {}) =>
  Promise.resolve(
    new Response(status === 204 ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    })
  );

describe("AuthenticatedApp", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the login form for an anonymous visitor", async () => {
    vi.stubGlobal("fetch", vi.fn(() => response(401)));
    render(<AuthenticatedApp />);

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByText("Single Board Kanban")).not.toBeInTheDocument();
  });

  it("shows an error for invalid credentials", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => response(401))
      .mockImplementationOnce(() =>
        response(401, { detail: "Invalid username or password" })
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<AuthenticatedApp />);

    await userEvent.type(await screen.findByLabelText("Username"), "user");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid username or password."
    );
  });

  it("shows the board after sign in and returns to login after logout", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => response(401))
      .mockImplementationOnce(() => response(200, { username: "user" }))
      .mockImplementationOnce(() => response(204));
    vi.stubGlobal("fetch", fetchMock);
    render(<AuthenticatedApp />);

    await userEvent.type(await screen.findByLabelText("Username"), "user");
    await userEvent.type(screen.getByLabelText("Password"), "password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Single Board Kanban")).toBeInTheDocument();
    expect(screen.getByText("user")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Log out" }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument()
    );
  });
});
