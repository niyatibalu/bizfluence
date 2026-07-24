"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

/** Legacy route — redirects to /targets/[id]. */
export default function MoneyTalksCompanyRedirect() {
  const router = useRouter();
  const params = useParams();
  useEffect(() => {
    const id = params?.id;
    router.replace(id ? `/targets/${id}` : "/targets");
  }, [router, params]);
  return null;
}
