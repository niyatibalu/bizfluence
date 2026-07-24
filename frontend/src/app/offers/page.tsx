"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Company, getStoredUser, Offer } from "@/lib/api";

export default function OffersPage() {
  const router = useRouter();
  const [offers, setOffers] = useState<Offer[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [raw, setRaw] = useState("");
  const [companyId, setCompanyId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<Offer | null>(null);
  const [error, setError] = useState("");
  const [showArchive, setShowArchive] = useState(false);

  const load = useCallback(async () => {
    const [o, c] = await Promise.all([
      api.get<Offer[]>("/offers"),
      api.get<Company[]>("/companies"),
    ]);
    setOffers(o.data);
    setCompanies(c.data);
    return o.data;
  }, []);

  useEffect(() => {
    if (!getStoredUser()) {
      router.replace("/");
      return;
    }
    load().catch(() => setError("Failed to load offers."));
  }, [router, load]);

  const active = useMemo(
    () => offers.filter((o) => o.status === "new" || o.status === "negotiating"),
    [offers]
  );
  const archived = useMemo(
    () => offers.filter((o) => o.status === "accepted" || o.status === "passed"),
    [offers]
  );

  // Keep selected in sync if it still belongs to the visible list; never auto-open first item
  useEffect(() => {
    if (!selected) return;
    const list = showArchive ? archived : active;
    const still = list.find((o) => o.id === selected.id);
    if (!still) {
      setSelected(null);
      return;
    }
    if (still !== selected) setSelected(still);
  }, [offers, active, archived, showArchive, selected]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post<Offer>("/offers", {
        raw_text: raw,
        company_id: companyId ? Number(companyId) : null,
        source: "paste",
      });
      setRaw("");
      await load();
      setShowArchive(false);
      setSelected(data);
    } catch {
      setError("Could not evaluate offer.");
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(status: string) {
    if (!selected) return;
    await api.patch<Offer>(`/offers/${selected.id}`, { status });
    await load();
    // Collapse detail back to list after any decision
    setSelected(null);
    if (status === "accepted" || status === "passed") {
      setShowArchive(true);
    } else {
      setShowArchive(false);
    }
  }

  let factors: Record<string, string> = {};
  try {
    factors = selected?.brief?.factors_json ? JSON.parse(selected.brief.factors_json) : {};
  } catch {
    factors = {};
  }

  const list = showArchive ? archived : active;

  return (
    <div>
      <h1 className="font-display text-5xl tracking-tight sm:text-6xl">Offers</h1>
      <p className="mt-3 max-w-2xl text-[var(--ink)]/60">
        Paste a brand email or DM. We’ll tell you if it’s worth taking, negotiating, or passing,
        and draft a reply.
      </p>

      <form onSubmit={submit} className="panel mt-8 space-y-3">
        <div>
          <label className="label">Related brand (optional)</label>
          <select className="input" value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
            <option value="">None</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Paste the offer</label>
          <textarea
            className="input min-h-[140px]"
            required
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            placeholder="Paste the brand’s email or DM here…"
          />
        </div>
        {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
        <button className="btn" disabled={busy} type="submit">
          {busy ? "Reading offer…" : "Check this offer"}
        </button>
      </form>

      <div className="mt-8 grid gap-6 lg:grid-cols-[240px_1fr]">
        <aside className="space-y-3">
          <div className="flex gap-2">
            <button
              type="button"
              className={!showArchive ? "btn text-xs" : "btn-ghost text-xs"}
              onClick={() => {
                setShowArchive(false);
                setSelected(null);
              }}
            >
              Active ({active.length})
            </button>
            <button
              type="button"
              className={showArchive ? "btn text-xs" : "btn-ghost text-xs"}
              onClick={() => {
                setShowArchive(true);
                setSelected(null);
              }}
            >
              Decided ({archived.length})
            </button>
          </div>
          {list.map((o) => (
            <button
              key={o.id}
              type="button"
              onClick={() => setSelected(o)}
              className={`w-full rounded-sm border px-3 py-2 text-left text-sm transition ${
                selected?.id === o.id
                  ? "border-[var(--ink)] bg-[var(--mist)]"
                  : "border-[var(--line)] bg-white hover:border-[var(--ink)]/40"
              }`}
            >
              <span className="font-semibold capitalize">{o.status}</span>
              <span className="mt-1 block line-clamp-2 text-[var(--ink)]/55">
                {o.raw_text.slice(0, 80)}
                {o.raw_text.length > 80 ? "…" : ""}
              </span>
            </button>
          ))}
          {list.length === 0 && (
            <p className="text-sm text-[var(--ink)]/50">
              {showArchive ? "No decided offers yet." : "No active offers. Paste one above."}
            </p>
          )}
        </aside>

        {selected?.brief ? (
          <article className="panel space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span
                className={`rounded-sm px-3 py-1 text-sm font-semibold uppercase tracking-wide stance-${selected.brief.recommended_stance}`}
              >
                {selected.brief.recommended_stance}
              </span>
              <div className="flex flex-wrap gap-2">
                {[
                  ["negotiating", "Negotiating"],
                  ["accepted", "Accepted"],
                  ["passed", "Passed"],
                ].map(([s, label]) => (
                  <button key={s} type="button" className="btn-ghost capitalize" onClick={() => setStatus(s)}>
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <section className="border-b border-[var(--line)] pb-5">
              <h2 className="font-display text-2xl tracking-tight">Summary</h2>
              <p className="mt-2 text-[var(--ink)]/80">{selected.brief.fit_summary}</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-sm bg-[rgba(143,169,140,0.18)] px-3 py-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-[#3f5c3d]">
                    Why it could help
                  </h3>
                  <p className="mt-1 text-sm text-[var(--ink)]/80">{selected.brief.reputation_upsides}</p>
                </div>
                <div className="rounded-sm bg-[rgba(244,184,174,0.35)] px-3 py-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-[#8a3a32]">
                    What to watch
                  </h3>
                  <p className="mt-1 text-sm text-[var(--ink)]/80">{selected.brief.reputation_risks}</p>
                </div>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <div>
                  <h3 className="label">Money / value</h3>
                  <p className="text-sm">{selected.brief.pay_value_clarity}</p>
                </div>
                <div>
                  <h3 className="label">Workload</h3>
                  <p className="text-sm">{selected.brief.deliverable_load}</p>
                </div>
                <div>
                  <h3 className="label">Red flags</h3>
                  <p className="text-sm">{selected.brief.red_flags}</p>
                </div>
              </div>
            </section>

            <details className="group">
              <summary className="cursor-pointer list-none text-sm font-semibold text-[var(--heat)] marker:content-none">
                <span className="group-open:hidden">Show full breakdown →</span>
                <span className="hidden group-open:inline">Hide full breakdown</span>
              </summary>
              <div className="mt-4 space-y-4 border-t border-[var(--line)] pt-4">
                {Object.keys(factors).length > 0 && (
                  <section>
                    <h3 className="label">Factors</h3>
                    <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                      {Object.entries(factors).map(([k, v]) => (
                        <div key={k} className="rounded-sm bg-[var(--mist)] px-3 py-2 text-sm">
                          <dt className="font-semibold capitalize">{k.replaceAll("_", " ")}</dt>
                          <dd className="text-[var(--ink)]/70">{String(v)}</dd>
                        </div>
                      ))}
                    </dl>
                  </section>
                )}
                <section>
                  <h3 className="label">Talking points</h3>
                  <pre className="mt-1 whitespace-pre-wrap font-sans text-sm">{selected.brief.talking_points}</pre>
                </section>
                <section>
                  <h3 className="label">Reply draft</h3>
                  <textarea className="input mt-1 min-h-[120px]" readOnly value={selected.brief.reply_draft} />
                </section>
                <details>
                  <summary className="cursor-pointer text-sm font-medium text-[var(--ink)]/70">
                    Original offer text
                  </summary>
                  <pre className="mt-2 whitespace-pre-wrap rounded-sm bg-[var(--mist)] p-3 text-sm">
                    {selected.raw_text}
                  </pre>
                </details>
              </div>
            </details>
          </article>
        ) : (
          <div className="panel flex min-h-[12rem] items-center justify-center text-sm text-[var(--ink)]/50">
            Select an offer from the list to review it.
          </div>
        )}
      </div>
    </div>
  );
}
