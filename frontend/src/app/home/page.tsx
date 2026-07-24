"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, Company, getStoredUser, Offer, User } from "@/lib/api";

const tools = [
  {
    href: "/targets",
    title: "Targets",
    blurb: "Brand list, contacts, pitches.",
  },
  {
    href: "/offers",
    title: "Offers",
    blurb: "Paste an inbound. Get a call.",
  },
  {
    href: "/profile",
    title: "Profile",
    blurb: "Niche, links, rates.",
  },
];

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [targetCount, setTargetCount] = useState(0);
  const [pendingOffers, setPendingOffers] = useState(0);
  const [decidedOffers, setDecidedOffers] = useState(0);

  useEffect(() => {
    const u = getStoredUser();
    if (!u) {
      router.replace("/");
      return;
    }
    setUser(u);
    Promise.all([api.get<Company[]>("/companies"), api.get<Offer[]>("/offers")])
      .then(([c, o]) => {
        setTargetCount(c.data.length);
        setPendingOffers(o.data.filter((x) => x.status === "new" || x.status === "negotiating").length);
        setDecidedOffers(o.data.filter((x) => x.status === "accepted" || x.status === "passed").length);
      })
      .catch(() => undefined);
  }, [router]);

  if (!user) {
    return <p className="text-[var(--ink)]/50">Loading…</p>;
  }

  const stats = [
    { label: "Targets found", value: targetCount, href: "/targets" },
    { label: "Offers pending", value: pendingOffers, href: "/offers" },
    { label: "Decided", value: decidedOffers, href: "/offers" },
  ];

  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--heat)]">Home</p>
      <h1 className="font-display mt-2 text-4xl tracking-tight sm:text-5xl">
        Hey {user.name?.split(" ")[0] || "there"}
      </h1>
      <p className="mt-2 text-[var(--ink)]/60">Pick a lane and move.</p>

      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {tools.map((t) => (
          <Link key={t.href} href={t.href} className="panel panel-interactive block min-h-[11rem]">
            <h2 className="font-display text-2xl tracking-tight sm:text-3xl">{t.title}</h2>
            <p className="mt-3 text-sm leading-relaxed text-[var(--ink)]/60">{t.blurb}</p>
            <span className="mt-6 inline-block text-sm font-semibold text-[var(--heat)]">Open →</span>
          </Link>
        ))}
      </div>

      <div className="mt-6 grid gap-3 border border-[var(--line)] bg-[var(--surface)] p-4 sm:grid-cols-3">
        {stats.map((s) => (
          <Link
            key={s.label}
            href={s.href}
            className="rounded-sm px-3 py-3 transition hover:bg-[var(--mist)]"
          >
            <p className="font-display text-3xl tracking-tight text-[var(--ink)]">{s.value}</p>
            <p className="mt-1 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--ink)]/50">
              {s.label}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
