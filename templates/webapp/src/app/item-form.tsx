"use client";
import { useActionState } from "react";
import { createItem } from "./actions";

export function ItemForm() {
  const [state, action, pending] = useActionState(createItem, {});
  return (
    <form action={action}>
      <input name="title" placeholder="New item" aria-label="Title" />
      <button type="submit" disabled={pending}>Add</button>
      {state.error ? <p className="error" role="alert">{state.error}</p> : null}
    </form>
  );
}
