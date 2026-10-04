import { sql } from "drizzle-orm";
import { db, ready } from "@/db";

export const dynamic = "force-dynamic";

// Liveness + database check. The platform's checks and the deploy probe call this.
export async function GET() {
  try {
    await ready();
    await db.execute(sql`select 1`);
    return Response.json({ ok: true });
  } catch {
    return Response.json({ ok: false }, { status: 503 });
  }
}
