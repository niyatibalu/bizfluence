"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { login, loginDemo } from "@/lib/api";
import { Wordmark } from "@/components/Wordmark";

function useReveal<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setOn(true);
      return;
    }
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setOn(true);
          obs.disconnect();
        }
      },
      { threshold: 0.18, rootMargin: "0px 0px -8% 0px" }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return { ref, on };
}

export default function LandingPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState<"login" | "demo" | null>(null);
  const [error, setError] = useState("");
  const [heroReady, setHeroReady] = useState(false);
  const [heroLeaving, setHeroLeaving] = useState(false);
  const heroRef = useRef<HTMLElement | null>(null);

  const pillars = useReveal<HTMLElement>();
  const steps = useReveal<HTMLElement>();
  const cta = useReveal<HTMLElement>();

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setHeroReady(true);
      return;
    }
    const t = window.setTimeout(() => setHeroReady(true), 40);
    return () => window.clearTimeout(t);
  }, []);

  useEffect(() => {
    const el = heroRef.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        setHeroLeaving(!entry.isIntersecting || entry.intersectionRatio < 0.55);
      },
      { threshold: [0.45, 0.55, 0.7] }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  async function afterAuth(isNew: boolean) {
    router.push(isNew ? "/profile?welcome=1" : "/home");
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    const cleanEmail = email.trim().toLowerCase();
    const cleanName = name.trim();
    if (!cleanName) {
      setError("Please enter your name.");
      return;
    }
    if (!cleanEmail || !cleanEmail.includes("@")) {
      setError("Please enter a valid email.");
      return;
    }
    setLoading("login");
    try {
      const user = await login(cleanEmail, cleanName);
      await afterAuth(Boolean(user.is_new));
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "message" in err
          ? String((err as { message?: string }).message)
          : "";
      setError(
        msg.includes("Network") || msg.includes("ECONNREFUSED")
          ? "Cannot reach the server. Start the backend, then try again."
          : "Sign in failed. Check the server is running, then try again."
      );
    } finally {
      setLoading(null);
    }
  }

  async function onGuest() {
    setError("");
    setLoading("demo");
    try {
      const user = await loginDemo();
      await afterAuth(Boolean(user.is_new));
    } catch {
      setError("Could not continue as guest. Start the backend first.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="bg-[var(--paper)] text-[var(--ink)]">
      {/*
        Hero moment (ink slab + heat line):
        On load the ink slab rises into place under the wordmark and a heat rule draws full-width under the tagline.
        On scroll out of the hero the slab eases upward and fades while later sections reveal with the same fade-up.
      */}
      <section
        ref={heroRef}
        className="flex min-h-[100svh] flex-col overflow-hidden"
      >
        {/* Text lives fully above the ink slab so nothing crops the wordmark */}
        <div className="relative z-10 mx-auto flex w-full max-w-6xl flex-1 flex-col justify-center px-4 py-16 sm:px-8 sm:py-20">
          <Wordmark className="max-w-full text-[clamp(2.75rem,7.2vw,5.75rem)] text-[var(--ink)]" />
          <p className="mt-5 max-w-xl text-base text-[var(--ink)]/70 sm:text-lg">
            Brand deals without a manager on payroll. Find fit. Pitch. Decide.
          </p>
          <div className={`heat-line mt-7 ${heroReady ? "is-ready" : ""}`} />
          <a
            href="#get-in"
            className="mt-8 inline-block text-sm font-semibold uppercase tracking-[0.14em] text-[var(--heat)] transition hover:text-[var(--heat-deep)]"
          >
            Get in ↓
          </a>
        </div>
        <div
          className={`hero-slab h-[min(28vh,220px)] w-full shrink-0 bg-[var(--ink)] ${
            heroReady ? "is-ready" : ""
          } ${heroLeaving ? "is-leaving" : ""}`}
          aria-hidden
        />
      </section>

      <section
        ref={pillars.ref}
        className={`reveal border-t border-[var(--line)] px-4 py-24 sm:px-8 ${pillars.on ? "is-in" : ""}`}
      >
        <div className="mx-auto grid max-w-6xl gap-12 md:grid-cols-2 md:gap-16">
          <div>
            <h2 className="font-display text-4xl uppercase leading-none tracking-tight sm:text-5xl">
              Find brands that fit you
            </h2>
            <p className="mt-5 max-w-md text-base leading-relaxed text-[var(--ink)]/65">
              Stop guessing who might take a collab. Bizfluence builds a target list around your niche
              and opens a workspace to pitch the right people.
            </p>
          </div>
          <div>
            <h2 className="font-display text-4xl uppercase leading-none tracking-tight sm:text-5xl">
              Know if an offer is worth it
            </h2>
            <p className="mt-5 max-w-md text-base leading-relaxed text-[var(--ink)]/65">
              Paste the email. Get a straight call: take it, negotiate, or pass. Plus talking points
              and a reply you can send.
            </p>
          </div>
        </div>
      </section>

      <section
        ref={steps.ref}
        className={`reveal border-t border-[var(--line)] bg-[var(--ink)] px-4 py-24 text-[var(--paper)] sm:px-8 ${
          steps.on ? "is-in" : ""
        }`}
      >
        <div className="mx-auto max-w-6xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--heat)]">How it works</p>
          <div className="mt-10 grid gap-10 md:grid-cols-3">
            {[
              ["Set your profile", "Niche, links, rates. Once. So everything downstream sounds like you."],
              ["Chase targets", "Brand ideas, contacts, LinkedIn and email pitches ready to send."],
              ["Judge offers", "Inbound briefs that tell you what to do next, not a vanity score."],
            ].map(([title, body]) => (
              <div key={title}>
                <h3 className="font-display text-3xl uppercase tracking-tight">{title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-[var(--paper)]/65">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section
        id="get-in"
        ref={cta.ref}
        className={`reveal border-t border-[var(--line)] px-4 py-24 sm:px-8 ${cta.on ? "is-in" : ""}`}
      >
        <div className="mx-auto grid max-w-6xl items-start gap-12 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <h2 className="font-display text-5xl uppercase leading-none tracking-tight sm:text-6xl">
              Get in
            </h2>
            <p className="mt-4 max-w-md text-[var(--ink)]/65">
              Sign in to keep your board. Or continue as a guest and start clean.
            </p>
          </div>
          <div className="border border-[var(--line)] bg-[var(--surface)] p-6">
            <form onSubmit={onSubmit} className="space-y-3" noValidate>
              <div>
                <label className="label" htmlFor="bf-name">
                  Name
                </label>
                <input
                  id="bf-name"
                  className="input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  autoComplete="name"
                />
              </div>
              <div>
                <label className="label" htmlFor="bf-email">
                  Email
                </label>
                <input
                  id="bf-email"
                  className="input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@email.com"
                  autoComplete="email"
                />
              </div>
              {error && (
                <p className="text-sm text-[var(--danger)]" role="alert">
                  {error}
                </p>
              )}
              <button className="btn w-full" disabled={loading !== null} type="submit">
                {loading === "login" ? "Signing in…" : "Sign in"}
              </button>
            </form>
            <div className="relative my-4 flex items-center gap-3 text-xs uppercase tracking-wide text-[var(--ink)]/35">
              <span className="h-px flex-1 bg-[var(--line)]" />
              or
              <span className="h-px flex-1 bg-[var(--line)]" />
            </div>
            <button
              className="btn-ghost w-full"
              type="button"
              disabled={loading !== null}
              onClick={onGuest}
            >
              {loading === "demo" ? "Starting…" : "Continue as a guest"}
            </button>
            <p className="mt-2 text-center text-xs text-[var(--ink)]/45">
              Guest sessions start fresh. Nothing from past visits is kept.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
