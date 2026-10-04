"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authClient } from "@/lib/auth-client";

export default function SignIn() {
  const router = useRouter();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [error, setError] = useState("");

  async function submit(form: FormData) {
    setError("");
    const email = String(form.get("email") || "");
    const password = String(form.get("password") || "");
    const res = mode === "up"
      ? await authClient.signUp.email({ email, password, name: email.split("@")[0] })
      : await authClient.signIn.email({ email, password });
    if (res.error) setError(res.error.message || "Could not sign in");
    else router.push("/admin");
  }

  return (
    <>
      <h1>{mode === "up" ? "Create account" : "Sign in"}</h1>
      <form action={submit}>
        <input name="email" type="email" placeholder="Email" aria-label="Email" required />
        <input name="password" type="password" placeholder="Password (8+ characters)" aria-label="Password" minLength={8} required />
        <button type="submit">{mode === "up" ? "Create account" : "Sign in"}</button>
      </form>
      {error ? <p className="error" role="alert">{error}</p> : null}
      <p className="muted">
        <a href="#" onClick={(e) => { e.preventDefault(); setMode(mode === "up" ? "in" : "up"); }}>
          {mode === "up" ? "I already have an account" : "Create an account"}
        </a>
      </p>
    </>
  );
}
