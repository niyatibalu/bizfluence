"use client";

import { Suspense } from "react";
import ProfileInner from "./ProfileInner";

export default function ProfilePage() {
  return (
    <Suspense fallback={<p className="text-[var(--ink)]/50">Loading profile…</p>}>
      <ProfileInner />
    </Suspense>
  );
}
