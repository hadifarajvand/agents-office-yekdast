"use server";
import { revalidatePath } from "next/cache";
import { addItem } from "@/lib/items";

export async function createItem(_prev: { error?: string }, form: FormData): Promise<{ error?: string }> {
  try {
    await addItem({ title: form.get("title") });
  } catch (e) {
    return { error: e instanceof Error && "issues" in e ? "Title is required" : "Could not save" };
  }
  revalidatePath("/");
  return {};
}
