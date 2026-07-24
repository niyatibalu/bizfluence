"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, getStoredUser, Profile, User } from "@/lib/api";

const empty = {
  niche: "",
  bio: "",
  platforms: "",
  instagram_url: "",
  youtube_url: "",
  linkedin_url: "",
  other_links: "",
  audience_geo: "India",
  audience_size: "",
  audience_description: "",
  rate_card_hints: "",
  exclusions: "",
  collab_goals: "",
};

function isGuestUser(user: User | null) {
  const email = (user?.email || "").toLowerCase();
  return email.endsWith("@bizfluence.local") || email.startsWith("demo-");
}

export default function ProfileInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const welcome = searchParams.get("welcome") === "1";
  const [user, setUser] = useState<User | null>(null);
  const [form, setForm] = useState(empty);
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const guest = isGuestUser(user);
  const totalSteps = 3;

  useEffect(() => {
    const u = getStoredUser();
    if (!u) {
      router.replace("/");
      return;
    }
    setUser(u);
    api
      .get<Profile | null>("/profile")
      .then((res) => {
        if (res.data) {
          setForm({
            niche: res.data.niche || "",
            bio: res.data.bio || "",
            platforms: res.data.platforms || "",
            instagram_url: res.data.instagram_url || "",
            youtube_url: res.data.youtube_url || "",
            linkedin_url: res.data.linkedin_url || "",
            other_links: res.data.other_links || "",
            audience_geo: res.data.audience_geo || "India",
            audience_size: res.data.audience_size || "",
            audience_description: res.data.audience_description || "",
            rate_card_hints: res.data.rate_card_hints || "",
            exclusions: res.data.exclusions || "",
            collab_goals: res.data.collab_goals || "",
          });
        }
      })
      .catch(() => undefined);
  }, [router]);

  const stepTitle = useMemo(() => {
    if (step === 1) return "Creator basics";
    if (step === 2) return "Audience basics";
    return guest ? "More detail (sign in to unlock)" : "More about you";
  }, [step, guest]);

  async function saveAndFinish() {
    setSaving(true);
    setMessage("");
    try {
      const payload = guest
        ? {
            ...form,
            bio: "",
            audience_description: "",
            collab_goals: "",
            exclusions: "",
            other_links: "",
          }
        : form;
      await api.put<Profile>("/profile", payload);
      setMessage("Saved. Taking you home…");
      router.push("/home");
    } catch {
      setMessage("Could not save profile. Try again.");
    } finally {
      setSaving(false);
    }
  }

  function onNext(e: FormEvent) {
    e.preventDefault();
    if (step < totalSteps) {
      setStep((s) => s + 1);
      return;
    }
    void saveAndFinish();
  }

  function field(
    key: keyof typeof empty,
    label: string,
    textarea = false,
    placeholder = "",
    locked = false
  ) {
    const props = {
      className: `input ${locked ? "opacity-60" : ""}`,
      value: form[key],
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
        setForm((f) => ({ ...f, [key]: e.target.value })),
      placeholder,
      disabled: locked,
      readOnly: locked,
    };
    return (
      <div>
        <label className="label">{label}</label>
        {textarea ? <textarea rows={3} {...props} /> : <input {...props} />}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--heat)]">
        Step {step} of {totalSteps}
      </p>
      <h1 className="font-display mt-2 text-3xl tracking-tight sm:text-4xl">
        {welcome ? "Set up your profile" : "Your profile"}
      </h1>
      <p className="mt-2 text-[var(--ink)]/60">{stepTitle}</p>

      <form onSubmit={onNext} className="panel mt-6 space-y-4">
        {step === 1 && (
          <>
            {field("niche", "What you create", false, "e.g. skincare & clean beauty")}
            {field("platforms", "Main platforms", false, "Instagram, YouTube")}
            {field("instagram_url", "Instagram", false, "https://instagram.com/you")}
            {field("youtube_url", "YouTube", false, "https://youtube.com/@you")}
            {field("linkedin_url", "LinkedIn", false, "https://linkedin.com/in/you")}
          </>
        )}
        {step === 2 && (
          <>
            {field("audience_size", "Audience size", false, "45K IG")}
            {field("audience_geo", "Where is your audience from?", false, "India")}
            {field("rate_card_hints", "Your rates (optional)", true, "Reel from ₹15k…")}
          </>
        )}
        {step === 3 && (
          <>
            {guest && (
              <div className="rounded-sm border border-[var(--line)] bg-[var(--mist)] px-3 py-3 text-sm text-[var(--ink)]/75">
                You’re in as a guest. Sign in to fill these fields — they unlock richer brand matches and
                pitches.
                <div className="mt-3">
                  <Link href="/" className="btn text-sm">
                    Sign in to unlock
                  </Link>
                </div>
              </div>
            )}
            {field(
              "bio",
              "Bio",
              true,
              "A short paragraph about your content and how you show up online",
              guest
            )}
            {field(
              "audience_description",
              "Describe your audience",
              true,
              "Who they are, what they care about — e.g. Gen Z · skincare curious · metro India",
              guest
            )}
            {field("collab_goals", "What you want from brands", true, "Paid deals, thoughtful PR…", guest)}
            {field("exclusions", "Hard no-gos", true, "alcohol, gambling…", guest)}
            {field("other_links", "Other links", true, "Website, Linktree…", guest)}
          </>
        )}

        {message && <p className="text-sm text-[var(--ok)]">{message}</p>}

        <div className="flex flex-wrap gap-2 pt-1">
          {step > 1 && (
            <button className="btn-ghost" type="button" onClick={() => setStep((s) => s - 1)}>
              Back
            </button>
          )}
          <button className="btn" disabled={saving} type="submit">
            {step < totalSteps
              ? "Next"
              : saving
                ? "Saving…"
                : guest
                  ? "Save basics & continue"
                  : "Save & continue"}
          </button>
          {!welcome && step === totalSteps && (
            <button className="btn-ghost" type="button" onClick={() => router.push("/home")}>
              Cancel
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
