import { FormEvent, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { aiApi, type ChatMessage } from "@/lib/api";
import type { BoardData } from "@/lib/kanban";

const CHAT_ERROR = "The assistant could not respond. Your board was not changed. Please try again.";

type AIChatSidebarProps = {
  onBoardChange: (board: BoardData) => void;
};

// Conversation history lives only in this component and holds successful turns only.
export const AIChatSidebar = ({ onBoardChange }: AIChatSidebarProps) => {
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const logRef = useRef<HTMLDivElement>(null);

  const messages: ChatMessage[] = pendingMessage
    ? [...history, { role: "user", content: pendingMessage }]
    : history;
  const pending = pendingMessage !== null;
  const canSend = !pending && draft.trim() !== "";

  useEffect(() => {
    logRef.current?.scrollTo?.({ top: logRef.current.scrollHeight });
  }, [messages.length]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message || pending) return;

    setPendingMessage(message);
    setDraft("");
    setError("");
    try {
      const result = await aiApi.chat(message, history);
      setHistory([
        ...history,
        { role: "user", content: message },
        { role: "assistant", content: result.reply },
      ]);
      if (result.boardChanged) {
        onBoardChange(result.board);
      }
    } catch {
      setError(CHAT_ERROR);
      setDraft(message);
    } finally {
      setPendingMessage(null);
    }
  };

  return (
    <aside
      aria-labelledby="ai-chat-heading"
      className="flex flex-col rounded-3xl border border-[var(--stroke)] bg-[var(--surface-strong)] p-5 shadow-[var(--shadow)] 2xl:sticky 2xl:top-6 2xl:max-h-[calc(100vh-3rem)]"
    >
      <div className="h-2 w-10 rounded-full bg-[var(--accent-yellow)]" />
      <h2
        id="ai-chat-heading"
        className="mt-3 font-display text-lg font-semibold text-[var(--navy-dark)]"
      >
        AI assistant
      </h2>
      <p className="mt-1 text-xs leading-5 text-[var(--gray-text)]">
        Ask about your board or ask it to create, edit or move cards.
      </p>

      <div
        ref={logRef}
        role="log"
        aria-label="Conversation"
        className="mt-4 flex min-h-[200px] max-h-[420px] flex-1 flex-col gap-3 overflow-y-auto rounded-2xl bg-[var(--surface)] p-3 2xl:max-h-none"
      >
        {messages.length === 0 ? (
          <p className="m-auto max-w-[240px] text-center text-sm leading-6 text-[var(--gray-text)]">
            No messages yet. Try &quot;Add a card to Backlog called Write release notes&quot;.
          </p>
        ) : (
          messages.map((message, index) => (
            <div
              key={index}
              className={clsx(
                "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6",
                message.role === "user"
                  ? "self-end bg-[var(--primary-blue)] text-white"
                  : "self-start border border-[var(--stroke)] bg-white text-[var(--navy-dark)]"
              )}
            >
              <p
                className={clsx(
                  "text-[10px] font-semibold uppercase tracking-[0.2em]",
                  message.role === "user" ? "text-white/80" : "text-[var(--gray-text)]"
                )}
              >
                {message.role === "user" ? "You" : "Assistant"}
              </p>
              <p className="mt-1 whitespace-pre-wrap break-words">{message.content}</p>
            </div>
          ))
        )}
        {pending ? (
          <p role="status" className="self-start text-sm font-semibold text-[var(--gray-text)]">
            Assistant is thinking...
          </p>
        ) : null}
      </div>

      {error ? (
        <p role="alert" className="mt-3 text-sm font-semibold text-red-700">
          {error}
        </p>
      ) : null}

      <form className="mt-4 flex flex-col gap-3" onSubmit={handleSubmit}>
        <label className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
          Message
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={pending}
            placeholder="Ask the assistant"
            className="mt-2 w-full rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 text-sm font-normal normal-case tracking-normal text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)] disabled:opacity-60"
          />
        </label>
        <button
          type="submit"
          disabled={!canSend}
          className="rounded-2xl bg-[var(--secondary-purple)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {pending ? "Sending..." : "Send"}
        </button>
      </form>
    </aside>
  );
};
