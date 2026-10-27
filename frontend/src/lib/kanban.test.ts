import { moveCard, planMove, type Column } from "@/lib/kanban";

describe("moveCard", () => {
  const baseColumns: Column[] = [
    { id: "col-a", title: "A", cardIds: ["card-1", "card-2"] },
    { id: "col-b", title: "B", cardIds: ["card-3"] },
  ];

  it("reorders cards in the same column", () => {
    const result = moveCard(baseColumns, "card-2", "card-1");
    expect(result[0].cardIds).toEqual(["card-2", "card-1"]);
  });

  it("moves cards to another column", () => {
    const result = moveCard(baseColumns, "card-2", "card-3");
    expect(result[0].cardIds).toEqual(["card-1"]);
    expect(result[1].cardIds).toEqual(["card-2", "card-3"]);
  });

  it("drops cards to the end of a column", () => {
    const result = moveCard(baseColumns, "card-1", "col-b");
    expect(result[0].cardIds).toEqual(["card-2"]);
    expect(result[1].cardIds).toEqual(["card-3", "card-1"]);
  });
});

describe("planMove", () => {
  const baseColumns: Column[] = [
    { id: "col-a", title: "A", cardIds: ["card-1", "card-2"] },
    { id: "col-b", title: "B", cardIds: ["card-3"] },
  ];

  it("maps a same-column reorder to its final index", () => {
    const plan = planMove(baseColumns, "card-2", "card-1");
    expect(plan).toMatchObject({ columnId: "col-a", position: 0 });
    expect(plan?.columns[0].cardIds).toEqual(["card-2", "card-1"]);
  });

  it("maps a drop before a card in another column", () => {
    expect(planMove(baseColumns, "card-1", "card-3")).toMatchObject({
      columnId: "col-b",
      position: 0,
    });
  });

  it("maps a drop on a column to its last index", () => {
    expect(planMove(baseColumns, "card-1", "col-b")).toMatchObject({
      columnId: "col-b",
      position: 1,
    });
  });

  it("returns null when nothing changes", () => {
    expect(planMove(baseColumns, "card-1", "card-1")).toBeNull();
    expect(planMove(baseColumns, "card-1", "missing")).toBeNull();
  });
});
