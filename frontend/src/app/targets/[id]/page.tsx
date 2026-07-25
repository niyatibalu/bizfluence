"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  api,
  Company,
  Contact,
  ContactFindResult,
  getStoredUser,
  OutreachMessage,
  PitchPack,
} from "@/lib/api";

export default function CompanyWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const companyId = Number(params.id);

  const [company, setCompany] = useState<Company | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [messages, setMessages] = useState<OutreachMessage[]>([]);
  const [pitch, setPitch] = useState<PitchPack | null>(null);
  const [selectedContact, setSelectedContact] = useState<number | null>(null);
  const [busy, setBusy] = useState("");
  const [toast, setToast] = useState("");

  const [cName, setCName] = useState("");
  const [cTitle, setCTitle] = useState("Influencer Marketing Manager");
  const [cLinkedIn, setCLinkedIn] = useState("");
  const [cEmail, setCEmail] = useState("");

  const load = useCallback(async () => {
    const [co, cts, msgs] = await Promise.all([
      api.get<Company>(`/companies/${companyId}`),
      api.get<Contact[]>(`/companies/${companyId}/contacts`),
      api.get<OutreachMessage[]>(`/companies/${companyId}/outreach`),
    ]);
    setCompany(co.data);
    setContacts(cts.data);
    setMessages(msgs.data);
    setSelectedContact((prev) => prev ?? (cts.data[0]?.id ?? null));
  }, [companyId]);

  useEffect(() => {
    if (!getStoredUser()) {
      router.replace("/");
      return;
    }
    load().catch(() => setToast("Failed to load company workspace."));
  }, [router, load]);

  async function addContact(e: FormEvent) {
    e.preventDefault();
    setBusy("contact");
    try {
      let email = cEmail;
      let confidence = email ? "manual" : "";
      if (!email && cName && company?.domain) {
        const parts = cName.trim().split(/\s+/);
        const guess = await api.post("/email/guess", {
          first_name: parts[0] || "",
          last_name: parts.slice(1).join(" ") || parts[0] || "",
          domain: company.domain,
        });
        email = guess.data.email;
        confidence = guess.data.confidence;
      }
      const { data } = await api.post<Contact>(`/companies/${companyId}/contacts`, {
        name: cName,
        title: cTitle,
        linkedin_url: cLinkedIn,
        email,
        email_confidence: confidence || (email ? "manual" : ""),
        notes: "Added manually.",
      });
      setCName("");
      setCLinkedIn("");
      setCEmail("");
      setSelectedContact(data.id);
      await load();
      setToast(email ? `Contact saved. Email: ${email} (${confidence})` : "Contact saved.");
    } catch {
      setToast("Could not save contact.");
    } finally {
      setBusy("");
    }
  }

  async function generatePitch() {
    setBusy("pitch");
    try {
      const contact = contacts.find((c) => c.id === selectedContact);
      const { data } = await api.post<PitchPack>(`/companies/${companyId}/outreach/pitch`, {
        contact_id: selectedContact,
        contact_name: contact?.name || cName,
        contact_title: contact?.title || cTitle,
        channel_preference: "both",
      });
      setPitch(data);
      setToast("Pitch ready. Edit anything before you send.");
    } catch {
      setToast("Pitch generation failed.");
    } finally {
      setBusy("");
    }
  }

  async function saveDraft(channel: "linkedin" | "email") {
    if (!pitch) return;
    setBusy("save");
    try {
      await api.post(`/companies/${companyId}/outreach`, {
        contact_id: selectedContact,
        channel,
        subject: channel === "email" ? pitch.email_subject : "",
        body: channel === "email" ? pitch.email_body : pitch.linkedin_dm,
        status: "drafted",
      });
      await load();
      setToast(`${channel} draft saved.`);
    } catch {
      setToast("Could not save draft.");
    } finally {
      setBusy("");
    }
  }

  async function findContacts() {
    setBusy("find");
    setToast("Looking for people to pitch…");
    try {
      const { data } = await api.post<ContactFindResult>(`/companies/${companyId}/contacts/find`);
      await load();
      setToast(data.message || (data.contacts.length ? `Found ${data.contacts.length}.` : "No contacts found."));
    } catch {
      setToast("Contact search failed.");
    } finally {
      setBusy("");
    }
  }

  async function removeContact(id: number) {
    try {
      await api.delete(`/contacts/${id}`);
      if (selectedContact === id) setSelectedContact(null);
      await load();
      setToast("Contact removed.");
    } catch {
      setToast("Could not remove contact.");
    }
  }

  async function enrichBrand() {
    setBusy("enrich");
    setToast("Researching this brand for your niche…");
    try {
      const { data } = await api.post<Company>(`/companies/${companyId}/enrich`);
      setCompany(data);
      setToast("Fit note updated.");
    } catch {
      setToast("Could not enrich brand.");
    } finally {
      setBusy("");
    }
  }

  async function copyLinkedIn() {
    if (!pitch) return;
    try {
      await navigator.clipboard.writeText(pitch.linkedin_dm);
    } catch {
      /* ignore */
    }
    const contact = contacts.find((c) => c.id === selectedContact);
    // Always log to outreach (same as email path)
    try {
      const saved = await api.post<OutreachMessage>(`/companies/${companyId}/outreach`, {
        contact_id: selectedContact,
        channel: "linkedin",
        subject: "",
        body: pitch.linkedin_dm,
        status: "sent",
      });
      await load();
      setToast(`LinkedIn DM copied and logged (#${saved.data.id}). Paste it in LinkedIn and send.`);
    } catch {
      setToast("Copied DM, but could not write outreach log.");
    }
    if (contact?.linkedin_url) {
      window.open(contact.linkedin_url, "_blank", "noopener,noreferrer");
    } else {
      window.open("https://www.linkedin.com/messaging/", "_blank", "noopener,noreferrer");
    }
  }

  async function sendOrMailto() {
    if (!pitch) return;
    const contact = contacts.find((c) => c.id === selectedContact);
    if (!contact?.email) {
      setToast("Add an email on the contact first.");
      return;
    }
    setBusy("email");
    try {
      const saved = await api.post<OutreachMessage>(`/companies/${companyId}/outreach`, {
        contact_id: selectedContact,
        channel: "email",
        subject: pitch.email_subject,
        body: pitch.email_body,
        status: "sent",
      });
      // Open Gmail compose in browser (avoids Mac Mail app glitches)
      const gmail = new URL("https://mail.google.com/mail/");
      gmail.searchParams.set("view", "cm");
      gmail.searchParams.set("fs", "1");
      gmail.searchParams.set("to", contact.email);
      gmail.searchParams.set("su", pitch.email_subject);
      gmail.searchParams.set("body", pitch.email_body.slice(0, 8000));
      window.open(gmail.toString(), "_blank", "noopener,noreferrer");
      try {
        await navigator.clipboard.writeText(pitch.email_body);
      } catch {
        /* ignore */
      }
      await load();
      setToast(
        `Logged email (#${saved.data.id}). Opened Gmail compose in a new tab — body also copied if you need to paste.`
      );
    } catch {
      setToast("Could not prepare email.");
    } finally {
      setBusy("");
    }
  }

  if (!company) {
    return <p className="text-[var(--ink)]/50">Loading workspace…</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <Link href="/targets" className="text-sm text-[var(--teal)] hover:underline">
          ← Targets
        </Link>
        <h1 className="font-display mt-2 text-4xl">{company.name}</h1>
        <p className="text-[var(--ink)]/55">
          {company.domain} · {company.category} · {company.status}
        </p>
        <p className="mt-3 max-w-3xl text-[var(--ink)]/80">{company.fit_rationale}</p>
        {company.suggested_angle && (
          <p className="mt-2 text-sm font-medium text-[var(--teal)]">Angle: {company.suggested_angle}</p>
        )}
        <button className="btn-ghost mt-3" type="button" disabled={busy === "enrich"} onClick={enrichBrand}>
          {busy === "enrich" ? "Researching…" : "Refresh fit note"}
        </button>
      </div>

      {toast && <p className="rounded-xl bg-[var(--mist)] px-3 py-2 text-sm">{toast}</p>}

      <section className="panel space-y-4">
        <h2 className="font-display text-2xl">Contacts</h2>
        <p className="text-sm text-[var(--ink)]/60">
          Find people to pitch, or paste a LinkedIn profile yourself. Always double-check before you reach out.
        </p>
        <button className="btn" type="button" disabled={busy === "find"} onClick={findContacts}>
          {busy === "find" ? "Searching…" : "Find contacts"}
        </button>
        <ul className="space-y-2">
          {contacts.map((c) => (
            <li key={c.id} className="flex gap-2">
              <div
                role="button"
                tabIndex={0}
                onClick={() => setSelectedContact(c.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelectedContact(c.id);
                  }
                }}
                className={`min-w-0 flex-1 cursor-pointer rounded-xl border px-3 py-2 text-left text-sm transition ${
                  selectedContact === c.id
                    ? "border-[var(--teal)] bg-[var(--mist)]"
                    : "border-[var(--line)] bg-white/50"
                }`}
              >
                <span className="font-semibold">{c.name}</span> — {c.title}
                {c.email && (
                  <a
                    href={`mailto:${c.email}`}
                    className="block truncate text-[var(--ink)]/55 hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {c.email}
                    {c.email_confidence ? ` (${c.email_confidence})` : ""}
                  </a>
                )}
                {c.linkedin_url && (
                  <a
                    href={c.linkedin_url.startsWith("http") ? c.linkedin_url : `https://${c.linkedin_url}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-0.5 block truncate text-[var(--teal)] underline-offset-2 hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {c.linkedin_url}
                  </a>
                )}
                {c.notes && <span className="mt-1 block text-xs text-[var(--ink)]/45">{c.notes}</span>}
              </div>
              <button
                type="button"
                className="btn-ghost shrink-0 self-start px-2 text-xs"
                onClick={() => removeContact(c.id)}
                aria-label={`Remove ${c.name}`}
              >
                Remove
              </button>
            </li>
          ))}
          {contacts.length === 0 && <p className="text-sm text-[var(--ink)]/50">No contacts yet.</p>}
        </ul>

        <form onSubmit={addContact} className="grid gap-3 border-t border-[var(--line)] pt-4 md:grid-cols-2">
          <div>
            <label className="label">Name</label>
            <input className="input" required value={cName} onChange={(e) => setCName(e.target.value)} />
          </div>
          <div>
            <label className="label">Title</label>
            <input className="input" value={cTitle} onChange={(e) => setCTitle(e.target.value)} />
          </div>
          <div>
            <label className="label">LinkedIn URL</label>
            <input className="input" value={cLinkedIn} onChange={(e) => setCLinkedIn(e.target.value)} placeholder="https://linkedin.com/in/…" />
          </div>
          <div>
            <label className="label">Email (optional — guessed from domain)</label>
            <input className="input" value={cEmail} onChange={(e) => setCEmail(e.target.value)} />
          </div>
          <button className="btn md:col-span-2" disabled={busy === "contact"} type="submit">
            {busy === "contact" ? "Saving…" : "Add contact"}
          </button>
        </form>
      </section>

      <section className="panel space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-2xl">Pitch pack</h2>
          <button className="btn" type="button" disabled={busy === "pitch"} onClick={generatePitch}>
            {busy === "pitch" ? "Drafting…" : "Generate pitch"}
          </button>
        </div>
        {pitch ? (
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="label">LinkedIn DM</label>
              <textarea
                className="input min-h-[140px]"
                value={pitch.linkedin_dm}
                onChange={(e) => setPitch({ ...pitch, linkedin_dm: e.target.value })}
              />
              <div className="mt-2 flex flex-wrap gap-2">
                <button className="btn" type="button" onClick={copyLinkedIn}>
                  Copy DM & open LinkedIn
                </button>
                <button className="btn-ghost" type="button" onClick={() => saveDraft("linkedin")}>
                  Save draft
                </button>
              </div>
            </div>
            <div>
              <label className="label">Cold email</label>
              <input
                className="input mb-2"
                value={pitch.email_subject}
                onChange={(e) => setPitch({ ...pitch, email_subject: e.target.value })}
              />
              <textarea
                className="input min-h-[140px]"
                value={pitch.email_body}
                onChange={(e) => setPitch({ ...pitch, email_body: e.target.value })}
              />
              <div className="mt-2 flex flex-wrap gap-2">
                <button className="btn" type="button" disabled={busy === "email"} onClick={sendOrMailto}>
                  Open in Gmail
                </button>
                <button className="btn-ghost" type="button" onClick={() => saveDraft("email")}>
                  Save draft
                </button>
              </div>
              {pitch.subject_alternatives?.length > 0 && (
                <p className="mt-2 text-xs text-[var(--ink)]/50">
                  Alt subjects: {pitch.subject_alternatives.join(" · ")}
                </p>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-[var(--ink)]/55">Generate a LinkedIn DM + cold email tailored to this brand and contact.</p>
        )}
      </section>

      <section className="panel">
        <h2 className="font-display text-2xl">Outreach log</h2>
        <ul className="mt-3 space-y-2">
          {messages.map((m) => (
            <li key={m.id} className="rounded-xl border border-[var(--line)] bg-white/60 px-3 py-2 text-sm">
              <div className="flex justify-between gap-2">
                <span className="font-semibold uppercase tracking-wide">{m.channel}</span>
                <span className="text-[var(--ink)]/50">{m.status}</span>
              </div>
              {m.subject && <p className="font-medium">{m.subject}</p>}
              <p className="mt-1 whitespace-pre-wrap text-[var(--ink)]/75">{m.body}</p>
            </li>
          ))}
          {messages.length === 0 && <p className="text-sm text-[var(--ink)]/50">No outreach yet.</p>}
        </ul>
      </section>
    </div>
  );
}
