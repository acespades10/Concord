"use client";
import { useState, useSyncExternalStore, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, Shapes, ShieldCheck } from "lucide-react";
import { Logo } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { api, setCsrf, type Session } from "@/lib/api";

const subscribe = () => () => {};

export default function LoginPage() {
  const ready = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  const [email, setEmail] = useState("admin@concord.demo"),
    [password, setPassword] = useState("concord-demo-2026"),
    [pending, setPending] = useState(false),
    [error, setError] = useState("");
  const router = useRouter(),
    client = useQueryClient();
  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const session = await api<Session>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setCsrf(session.csrf);
      client.clear();
      client.setQueryData(["session"], session);
      router.push("/projects");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <main className="login-page">
      <section className="login-story">
        <Logo />
        <div className="login-story-content">
          <span className="eyebrow">
            <span className="status-dot" /> HUMAN JUDGMENT. SHARED CONFIDENCE.
          </span>
          <h1>
            Better data.
            <br />
            <span>Built together.</span>
          </h1>
          <p>
            A little more agreement.
            <br />A lot more confidence in what comes next.
          </p>
          <div className="login-art" aria-hidden="true">
            <div className="art-orbit orbit-one" />
            <div className="art-orbit orbit-two" />
            <div className="art-label art-label-one">
              <span className="art-icon lavender">
                <Shapes size={24} />
              </span>
              <div>
                Thoughtful annotation<small>One label at a time</small>
              </div>
              <Check size={20} />
            </div>
            <div className="art-label art-label-two">
              <span className="art-icon sage">
                <ShieldCheck size={24} />
              </span>
              <div>
                Shared understanding<small>Agreement you can measure</small>
              </div>
              <Check size={20} />
            </div>
            <span className="art-spark">✳</span>
          </div>
        </div>
        <small>THE HUMAN SIDE OF MACHINE LEARNING</small>
      </section>
      <section className="login-form-panel">
        <div className="login-form">
          <span className="eyebrow">WELCOME TO CONCORD</span>
          <h2>Make good work count.</h2>
          <p className="muted">Sign in to your annotation workspace.</p>
          <form onSubmit={submit}>
            <label>
              Email address
              <input
                type="email"
                disabled={!ready || pending}
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                disabled={!ready || pending}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <Button
              disabled={!ready || pending}
              type="submit"
              className="full-width"
            >
              {pending ? "Signing in…" : "Enter workspace"}
              <ArrowRight size={17} />
            </Button>
          </form>
          <div className="demo-accounts">
            <div className="divider-label">EXPLORE THE DEMO</div>
            <p>
              Choose a perspective. The demo credentials are filled in for you.
            </p>
            <div className="demo-role-grid">
              {[
                ["admin", "Admin"],
                ["reviewer", "Reviewer"],
                ["annotator1", "Annotator 1"],
                ["annotator2", "Annotator 2"],
                ["annotator3", "Annotator 3"],
              ].map(([id, label]) => (
                <button
                  key={id}
                  disabled={!ready || pending}
                  className={email === `${id}@concord.demo` ? "selected" : ""}
                  onClick={() => {
                    setEmail(`${id}@concord.demo`);
                    setPassword("concord-demo-2026");
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <small>
              Demo password: <code>concord-demo-2026</code>
            </small>
          </div>
          <p className="login-footnote">
            <ShieldCheck size={15} /> Your role determines what you can see and
            do.
          </p>
        </div>
      </section>
    </main>
  );
}
