import { listItems } from "@/lib/items";
import { ItemForm } from "./item-form";

export const dynamic = "force-dynamic";

export default async function Home() {
  const rows = await listItems();
  return (
    <>
      <h1>Items</h1>
      <ItemForm />
      {rows.length === 0 ? <p className="muted">Nothing yet.</p> : (
        <ul>{rows.map((r) => <li key={r.id}>{r.title}</li>)}</ul>
      )}
    </>
  );
}
