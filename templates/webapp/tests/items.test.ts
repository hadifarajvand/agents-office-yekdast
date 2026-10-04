import { describe, expect, it } from "vitest";
import { addItem, listItems } from "@/lib/items";

// Runs against an in-process PGlite database with the real migrations.
describe("items", () => {
  it("adds an item and lists newest first", async () => {
    await addItem({ title: "first" });
    await addItem({ title: "second" });
    const rows = await listItems();
    expect(rows.map((r) => r.title).slice(0, 2)).toEqual(["second", "first"]);
  });

  it("rejects an empty title", async () => {
    await expect(addItem({ title: "  " })).rejects.toThrow();
  });
});
