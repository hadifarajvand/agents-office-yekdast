// Runs once when the server starts: apply database migrations before the first request.
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { ready } = await import("./db");
    await ready();
  }
}
