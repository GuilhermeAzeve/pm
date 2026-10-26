"use client";

import { FormEvent, useEffect, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";

type AuthState =
  | { status: "loading" }
  | { status: "signedOut" }
  | { status: "signedIn"; username: string };

export const AuthenticatedApp = () => {
  const [auth, setAuth] = useState<AuthState>({ status: "loading" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;

    fetch("/api/me")
      .then(async (response) => {
        if (!active) return;
        if (!response.ok) {
          setAuth({ status: "signedOut" });
          return;
        }
        const data = (await response.json()) as { username: string };
        if (active) setAuth({ status: "signedIn", username: data.username });
      })
      .catch(() => {
        if (active) setAuth({ status: "signedOut" });
      });

    return () => {
      active = false;
    };
  }, []);

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: form.get("username"),
          password: form.get("password"),
        }),
      });

      if (!response.ok) {
        setError("Invalid username or password.");
        return;
      }

      const data = (await response.json()) as { username: string };
      setAuth({ status: "signedIn", username: data.username });
    } catch {
      setError("Unable to sign in. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleLogout = async () => {
    await fetch("/api/logout", { method: "POST" }).catch(() => undefined);
    setAuth({ status: "signedOut" });
  };

  if (auth.status === "loading") {
    return (
      <main className="grid min-h-screen place-items-center px-6">
        <p className="text-sm font-semibold text-[var(--gray-text)]">Loading...</p>
      </main>
    );
  }

  if (auth.status === "signedIn") {
    return <KanbanBoard username={auth.username} onLogout={handleLogout} />;
  }

  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden px-6 py-12">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <section className="relative w-full max-w-md rounded-[32px] border border-[var(--stroke)] bg-white/90 p-8 shadow-[var(--shadow)] backdrop-blur">
        <div className="mb-8 h-1 w-16 rounded-full bg-[var(--accent-yellow)]" />
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--primary-blue)]">
          Kanban Studio
        </p>
        <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
          Sign in
        </h1>
        <p className="mt-3 text-sm leading-6 text-[var(--gray-text)]">
          Enter your credentials to open your project board.
        </p>

        <form className="mt-8 space-y-5" onSubmit={handleLogin}>
          <label className="block text-sm font-semibold text-[var(--navy-dark)]">
            Username
            <input
              name="username"
              autoComplete="username"
              required
              className="mt-2 w-full rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 font-normal outline-none transition focus:border-[var(--primary-blue)]"
            />
          </label>
          <label className="block text-sm font-semibold text-[var(--navy-dark)]">
            Password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              className="mt-2 w-full rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 font-normal outline-none transition focus:border-[var(--primary-blue)]"
            />
          </label>
          {error ? (
            <p role="alert" className="text-sm font-semibold text-red-700">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-2xl bg-[var(--secondary-purple)] px-5 py-3 font-semibold text-white transition hover:opacity-90 disabled:cursor-wait disabled:opacity-60"
          >
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
};
