"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getStoredUser, logout, User } from "@/lib/api";
import { Wordmark } from "@/components/Wordmark";

const links = [
  { href: "/home", label: "Home" },
  { href: "/targets", label: "Targets" },
  { href: "/offers", label: "Offers" },
  { href: "/profile", label: "Profile" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    setUser(getStoredUser());
  }, [pathname]);

  const isAuthPage = pathname === "/" || pathname === "/login";

  if (isAuthPage) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-[var(--paper)]">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[var(--ink)] text-[var(--paper)]">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3.5">
          <Link href="/home" className="transition hover:opacity-90">
            <Wordmark
              compact
              className="text-[var(--paper)] [&_.wordmark-block]:bg-[var(--heat)] [&_.wordmark-block]:text-[var(--ink)]"
            />
          </Link>
          <nav className="flex flex-wrap items-center gap-1 text-sm" aria-label="Main">
            {links.map((l) => {
              const active = pathname === l.href || (l.href !== "/home" && pathname.startsWith(l.href));
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  className={`rounded-sm px-3 py-1.5 font-medium transition ${
                    active
                      ? "bg-[var(--heat)] text-white"
                      : "text-[var(--paper)]/70 hover:bg-white/10 hover:text-[var(--paper)]"
                  }`}
                >
                  {l.label}
                </Link>
              );
            })}
            {user && (
              <span className="ml-2 hidden max-w-[10rem] truncate text-[var(--paper)]/40 sm:inline">
                {user.name || user.email}
              </span>
            )}
            {user && (
              <button
                type="button"
                className="ml-1 rounded-sm px-2 py-1.5 text-[var(--paper)]/55 transition hover:text-[var(--heat)]"
                onClick={() => {
                  logout();
                  router.push("/");
                }}
              >
                Log out
              </button>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
