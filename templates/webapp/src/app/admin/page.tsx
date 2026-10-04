import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { ready } from "@/db";
import { auth } from "@/lib/auth";
import { listItems } from "@/lib/items";

export const dynamic = "force-dynamic";

// Signed-in users only. Put owner/staff screens under /admin.
export default async function Admin() {
  await ready();
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) redirect("/sign-in");
  const rows = await listItems();
  return (
    <>
      <h1>Admin</h1>
      <p>Signed in as {session.user.email}.</p>
      <p className="muted">{rows.length} items.</p>
    </>
  );
}
