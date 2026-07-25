import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export const api = axios.create({
  baseURL: API_BASE,
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const userId = localStorage.getItem("bf_user_id");
    if (userId) {
      config.headers["X-User-Id"] = userId;
    }
  }
  return config;
});

export type User = { id: number; email: string; name: string; is_new?: boolean };

export type Profile = {
  id: number;
  user_id: number;
  niche: string;
  bio: string;
  platforms: string;
  instagram_url?: string;
  youtube_url?: string;
  linkedin_url?: string;
  other_links?: string;
  research_notes?: string;
  audience_geo: string;
  audience_size: string;
  audience_description?: string;
  rate_card_hints: string;
  exclusions: string;
  collab_goals: string;
};

export type Company = {
  id: number;
  user_id: number;
  name: string;
  domain: string;
  category: string;
  notes: string;
  fit_rationale: string;
  suggested_angle: string;
  priority_narrative: string;
  status: string;
};

export type Contact = {
  id: number;
  company_id: number;
  name: string;
  title: string;
  linkedin_url: string;
  email: string;
  email_confidence: string;
  notes: string;
};

export type ContactFindResult = {
  contacts: Contact[];
  message: string;
  source: string;
};

export type PitchPack = {
  linkedin_dm: string;
  email_subject: string;
  email_body: string;
  subject_alternatives: string[];
  generation_note?: string;
};

export type OutreachMessage = {
  id: number;
  company_id: number;
  contact_id: number | null;
  channel: string;
  subject: string;
  body: string;
  status: string;
};

export type OfferBrief = {
  id: number;
  offer_id: number;
  fit_summary: string;
  reputation_upsides: string;
  reputation_risks: string;
  pay_value_clarity: string;
  deliverable_load: string;
  red_flags: string;
  factors_json: string;
  recommended_stance: string;
  talking_points: string;
  reply_draft: string;
  generation_note?: string;
};

export type Offer = {
  id: number;
  user_id: number;
  company_id: number | null;
  source: string;
  raw_text: string;
  status: string;
  brief: OfferBrief | null;
};

export async function login(email: string, name: string) {
  const { data } = await api.post<User>("/auth/login", { email, name });
  localStorage.setItem("bf_user_id", String(data.id));
  localStorage.setItem("bf_user", JSON.stringify(data));
  return data;
}

export async function loginDemo() {
  const { data } = await api.post<User>("/auth/demo");
  localStorage.setItem("bf_user_id", String(data.id));
  localStorage.setItem("bf_user", JSON.stringify(data));
  return data;
}

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("bf_user");
  return raw ? (JSON.parse(raw) as User) : null;
}

export function logout() {
  localStorage.removeItem("bf_user_id");
  localStorage.removeItem("bf_user");
}
