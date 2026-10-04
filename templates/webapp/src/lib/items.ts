import { desc } from "drizzle-orm";
import { z } from "zod";
import { db, ready } from "@/db";
import { items } from "@/db/schema";

// Example resource: server-side functions that pages and tests call. Validate every input.
export const NewItem = z.object({ title: z.string().trim().min(1, "Title is required").max(200) });

export async function listItems() {
  await ready();
  return db.select().from(items).orderBy(desc(items.id)).limit(100);
}

export async function addItem(input: unknown) {
  const data = NewItem.parse(input);
  await ready();
  const [row] = await db.insert(items).values(data).returning();
  return row;
}
