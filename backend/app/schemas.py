from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


# ---- Auth / User ----


class LoginRequest(BaseModel):
    email: EmailStr
    name: str = ""


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    is_new: bool = False

    model_config = {"from_attributes": True}


# ---- Profile ----


class ProfileIn(BaseModel):
    niche: str = ""
    bio: str = ""
    platforms: str = ""
    instagram_url: str = ""
    youtube_url: str = ""
    linkedin_url: str = ""
    other_links: str = ""
    audience_geo: str = "India"
    audience_size: str = ""
    audience_description: str = ""
    rate_card_hints: str = ""
    exclusions: str = ""
    collab_goals: str = ""


class ProfileOut(ProfileIn):
    id: int
    user_id: int
    research_notes: str = ""

    model_config = {"from_attributes": True}


class SuggestBrandsRequest(BaseModel):
    field: str | None = None
    extra_hints: str = ""
    refresh_research: bool = False
    replace_existing: bool = True  # wipe prior discovered targets for this user
    tier: str = "micro_mid"  # micro_mid | any



# ---- Companies ----


class CompanyCreate(BaseModel):
    name: str
    domain: str = ""
    category: str = ""
    notes: str = ""
    fit_rationale: str = ""
    suggested_angle: str = ""
    priority_narrative: str = ""
    status: str = "discovered"


class CompanyUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    category: str | None = None
    notes: str | None = None
    fit_rationale: str | None = None
    suggested_angle: str | None = None
    priority_narrative: str | None = None
    status: str | None = None


class CompanyOut(BaseModel):
    id: int
    user_id: int
    name: str
    domain: str
    category: str
    notes: str
    fit_rationale: str
    suggested_angle: str
    priority_narrative: str
    research_notes: str = ""
    status: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SuggestedBrand(BaseModel):
    name: str
    domain: str = ""
    category: str = ""
    fit_rationale: str
    suggested_angle: str
    priority_narrative: str


# ---- Contacts ----


class ContactCreate(BaseModel):
    name: str
    title: str = ""
    linkedin_url: str = ""
    email: str = ""
    email_confidence: str = ""
    notes: str = ""


class ContactOut(ContactCreate):
    id: int
    company_id: int

    model_config = {"from_attributes": True}


class EmailGuessRequest(BaseModel):
    first_name: str
    last_name: str
    domain: str


class EmailGuessOut(BaseModel):
    email: str
    confidence: Literal["high", "medium", "low", "guessed"]
    pattern: str
    alternatives: list[str] = []


# ---- Outreach ----


class PitchGenerateRequest(BaseModel):
    contact_id: int | None = None
    contact_name: str = ""
    contact_title: str = ""
    channel_preference: Literal["both", "linkedin", "email"] = "both"


class PitchPack(BaseModel):
    linkedin_dm: str = ""
    email_subject: str = ""
    email_body: str = ""
    subject_alternatives: list[str] = []
    generation_note: str = ""


class OutreachCreate(BaseModel):
    contact_id: int | None = None
    channel: Literal["linkedin", "email"]
    subject: str = ""
    body: str
    status: str = "drafted"


class OutreachUpdate(BaseModel):
    status: str | None = None
    subject: str | None = None
    body: str | None = None


class OutreachOut(BaseModel):
    id: int
    company_id: int
    contact_id: int | None
    channel: str
    subject: str
    body: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SendEmailRequest(BaseModel):
    to_email: EmailStr
    subject: str
    body: str
    outreach_id: int | None = None


class SendEmailOut(BaseModel):
    ok: bool
    message: str
    mode: Literal["resend", "mailto"]


# ---- Offers ----


class OfferCreate(BaseModel):
    raw_text: str
    company_id: int | None = None
    source: str = "paste"


class OfferUpdate(BaseModel):
    status: str | None = None
    company_id: int | None = None


class OfferBriefOut(BaseModel):
    id: int
    offer_id: int
    fit_summary: str
    reputation_upsides: str
    reputation_risks: str
    pay_value_clarity: str
    deliverable_load: str
    red_flags: str
    factors_json: str
    recommended_stance: str
    talking_points: str
    reply_draft: str
    generation_note: str = ""

    model_config = {"from_attributes": True}


class OfferOut(BaseModel):
    id: int
    user_id: int
    company_id: int | None
    source: str
    raw_text: str
    status: str
    created_at: datetime | None = None
    brief: OfferBriefOut | None = None

    model_config = {"from_attributes": True}


class HealthOut(BaseModel):
    status: str
    app: str
    gemini_configured: bool
    resend_configured: bool
    gemini_live: str = ""  # ok | quota | offline | unknown
    gemini_detail: str = ""
