"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Legacy route — profile lives at /profile. */
export default function OnboardingRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/profile");
  }, [router]);
  return null;
}
