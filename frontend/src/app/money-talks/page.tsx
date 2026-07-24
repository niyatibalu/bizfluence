"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Legacy route — Money Talks naming removed. */
export default function MoneyTalksRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/targets");
  }, [router]);
  return null;
}
