import { toNextJsHandler } from "better-auth/next-js";
import { ready } from "@/db";
import { auth } from "@/lib/auth";

const handler = toNextJsHandler(auth.handler);

export async function GET(req: Request) {
  await ready();
  return handler.GET(req);
}

export async function POST(req: Request) {
  await ready();
  return handler.POST(req);
}
