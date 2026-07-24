"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Company, getStoredUser } from "@/lib/api";

export default function TargetsPage() {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [suggesting, setSuggesting] = useState(false);
  const [autoTried, setAutoTried] = useState(false);
  const [field, setField] = useState("");
  const [hints, setHints] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [error, setError] = useState("");
  const [statusMsg, setStatusMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<Company[]>("/companies");
      setCompanies(data);
    } catch {
      setError("Couldn’t load your brands.");
    } finally {
      setLoading(false);
    }
  }, []);

  const runSuggest = useCallback(
    async (opts?: { field?: string; hints?: string }) => {
      setSuggesting(true);
      setError("");
      setStatusMsg("Finding brands for you. This can take about half a minute…");
      try {
        await api.post("/companies/suggest/save", {
          field: opts?.field || field || null,
          extra_hints: opts?.hints ?? hints,
          refresh_research: true,
          replace_existing: true,
          tier: "micro_mid",
        });
        await load();
        setStatusMsg("Here’s a fresh set of brand ideas for you.");
      } catch {
        setError("Couldn’t suggest brands right now. Try again in a moment.");
        setStatusMsg("");
      } finally {
        setSuggesting(false);
      }
    },
    [field, hints, load]
  );

  useEffect(() => {
    if (!getStoredUser()) {
      router.replace("/");
      return;
    }
    load();
  }, [router, load]);

  useEffect(() => {
    if (loading || autoTried || suggesting) return;
    if (companies.length > 0) {
      setAutoTried(true);
      return;
    }
    setAutoTried(true);
    runSuggest({ field: "", hints: "emerging India D2C micro influencer friendly" });
  }, [loading, autoTried, companies.length, suggesting, runSuggest]);

  async function addCompany(e: FormEvent) {
    e.preventDefault();
    setStatusMsg("Adding this brand for you…");
    try {
      await api.post("/companies", {
        name,
        domain,
        fit_rationale: "",
        suggested_angle: "",
        priority_narrative: "",
        status: "discovered",
      });
      setName("");
      setDomain("");
      setAddOpen(false);
      await load();
      setStatusMsg("Brand added.");
    } catch {
      setError("Couldn’t add that company.");
      setStatusMsg("");
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl">
          <h1 className="font-display text-5xl tracking-tight text-[var(--ink)] sm:text-6xl">
            Target brands
          </h1>
          <p className="mt-3 text-[var(--ink)]/60">
            Brands that fit what you create. Open one to find contacts and send a pitch.
          </p>
        </div>
        <button className="btn-ghost" type="button" onClick={() => setAddOpen((v) => !v)}>
          {addOpen ? "Cancel" : "Add a brand"}
        </button>
      </div>

      <div className="panel mt-8 space-y-3">
        <h2 className="text-base font-semibold text-[var(--ink)]/80">Get brand ideas</h2>
        <p className="text-sm text-[var(--ink)]/60">
          Tell us a category if you want, then refresh. We’ll replace older unused suggestions
          with a new list.
        </p>
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <label className="label">Category</label>
            <input
              className="input"
              value={field}
              onChange={(e) => setField(e.target.value)}
              placeholder="beauty, fitness, tech, food…"
            />
          </div>
          <div>
            <label className="label">Anything else?</label>
            <input
              className="input"
              value={hints}
              onChange={(e) => setHints(e.target.value)}
              placeholder="D2C, skincare, sustainable…"
            />
          </div>
        </div>
        <button className="btn" type="button" disabled={suggesting} onClick={() => runSuggest()}>
          {suggesting ? "Searching…" : "Suggest brands"}
        </button>
        {statusMsg && <p className="text-sm text-[var(--ok)]">{statusMsg}</p>}
      </div>

      {addOpen && (
        <form onSubmit={addCompany} className="panel mt-4 grid gap-3 md:grid-cols-3">
          <div>
            <label className="label">Brand name</label>
            <input className="input" required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="label">Website</label>
            <input
              className="input"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="brand.com"
            />
          </div>
          <div className="flex items-end">
            <button className="btn w-full" type="submit">
              Add brand
            </button>
          </div>
        </form>
      )}

      {error && <p className="mt-4 text-sm text-[var(--danger)]">{error}</p>}

      <div className="mt-8 grid gap-4 md:grid-cols-2">
        {(loading || suggesting) && companies.length === 0 && (
          <p className="text-[var(--ink)]/50 md:col-span-2">Loading brands…</p>
        )}
        {!loading && !suggesting && companies.length === 0 && (
          <div className="panel md:col-span-2">
            <p className="text-[var(--ink)]/70">No targets yet. Suggest brands or add one yourself.</p>
          </div>
        )}
        {companies.map((c) => (
          <Link
            key={c.id}
            href={`/targets/${c.id}`}
            className="panel panel-interactive block"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-display text-xl tracking-tight sm:text-2xl">{c.name}</h3>
                <p className="text-sm text-[var(--ink)]/50">
                  {c.domain || "no website"} · {c.category || "general"}
                </p>
              </div>
              <span className="rounded-sm bg-[var(--mist)] px-2.5 py-1 text-xs font-semibold uppercase tracking-wide">
                {c.status}
              </span>
            </div>
            <p className="mt-3 text-sm text-[var(--ink)]/80">
              {c.fit_rationale || "Open to see how this brand could fit you."}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
