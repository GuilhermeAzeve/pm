"use client";

import { useEffect, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { boardApi } from "@/lib/api";
import { planMove, type BoardData } from "@/lib/kanban";

const LOAD_ERROR = "Could not load the board.";
const SAVE_ERROR = "Could not save your change. The board shows the last saved state.";

type KanbanBoardProps = {
  username: string;
  onLogout: () => void;
};

export const KanbanBoard = ({ username, onLogout }: KanbanBoardProps) => {
  const [board, setBoard] = useState<BoardData | null>(null);
  const [error, setError] = useState("");
  const [activeCardId, setActiveCardId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  useEffect(() => {
    let active = true;
    boardApi
      .get()
      .then((data) => {
        if (active) setBoard(data);
      })
      .catch(() => {
        if (active) setError(LOAD_ERROR);
      });
    return () => {
      active = false;
    };
  }, []);

  const reload = async () => {
    try {
      setBoard(await boardApi.get());
      setError("");
    } catch {
      setError(LOAD_ERROR);
    }
  };

  // Every change is saved through the API and the returned board replaces local state.
  // On failure the board is reloaded from the server so it never silently diverges.
  const save = async (request: () => Promise<BoardData>) => {
    try {
      setBoard(await request());
      setError("");
      return true;
    } catch {
      setError(SAVE_ERROR);
      try {
        setBoard(await boardApi.get());
      } catch {
        setError(LOAD_ERROR);
      }
      return false;
    }
  };

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!board || !over || active.id === over.id) {
      return;
    }

    const cardId = active.id as string;
    const plan = planMove(board.columns, cardId, over.id as string);
    if (!plan) {
      return;
    }

    // Show the drop immediately; the server response then replaces it.
    setBoard({ ...board, columns: plan.columns });
    void save(() => boardApi.moveCard(cardId, plan.columnId, plan.position));
  };

  const handleRenameColumn = (columnId: string, title: string) =>
    save(() => boardApi.renameColumn(columnId, title));

  const handleAddCard = (columnId: string, title: string, details: string) =>
    save(() => boardApi.createCard(columnId, title, details));

  const handleEditCard = (cardId: string, title: string, details: string) =>
    save(() => boardApi.updateCard(cardId, title, details));

  const handleDeleteCard = (cardId: string) => {
    void save(() => boardApi.deleteCard(cardId));
  };

  const activeCard = activeCardId && board ? board.cards[activeCardId] : null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="flex items-center gap-4 rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                  Signed in as
                </p>
                <p className="mt-1 font-semibold text-[var(--primary-blue)]">{username}</p>
              </div>
              <button
                type="button"
                onClick={onLogout}
                className="rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
              >
                Log out
              </button>
            </div>
          </div>
          {board ? (
            <div className="flex flex-wrap items-center gap-4">
              {board.columns.map((column) => (
                <div
                  key={column.id}
                  className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
                >
                  <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                  {column.title}
                </div>
              ))}
            </div>
          ) : null}
        </header>

        {error ? (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[var(--stroke)] bg-white px-5 py-4 text-sm font-semibold text-red-700"
          >
            {error}
            <button
              type="button"
              onClick={reload}
              className="rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--primary-blue)] transition hover:border-[var(--primary-blue)]"
            >
              Reload board
            </button>
          </div>
        ) : null}

        {board ? (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <section className="grid gap-6 lg:grid-cols-5">
              {board.columns.map((column) => (
                <KanbanColumn
                  key={column.id}
                  column={column}
                  cards={column.cardIds.map((cardId) => board.cards[cardId])}
                  onRename={handleRenameColumn}
                  onAddCard={handleAddCard}
                  onEditCard={handleEditCard}
                  onDeleteCard={handleDeleteCard}
                />
              ))}
            </section>
            <DragOverlay>
              {activeCard ? (
                <div className="w-[260px]">
                  <KanbanCardPreview card={activeCard} />
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>
        ) : !error ? (
          <p className="text-sm font-semibold text-[var(--gray-text)]">Loading board...</p>
        ) : null}
      </main>
    </div>
  );
};
