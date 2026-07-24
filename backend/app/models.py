from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["CreatorProfile | None"] = relationship(back_populates="user", uselist=False)
    companies: Mapped[list["Company"]] = relationship(back_populates="user")
    offers: Mapped[list["Offer"]] = relationship(back_populates="user")


class CreatorProfile(Base):
    __tablename__ = "creator_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    niche: Mapped[str] = mapped_column(String(255), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    platforms: Mapped[str] = mapped_column(Text, default="")  # comma-separated
    instagram_url: Mapped[str] = mapped_column(String(512), default="")
    youtube_url: Mapped[str] = mapped_column(String(512), default="")
    linkedin_url: Mapped[str] = mapped_column(String(512), default="")
    other_links: Mapped[str] = mapped_column(Text, default="")
    research_notes: Mapped[str] = mapped_column(Text, default="")
    audience_geo: Mapped[str] = mapped_column(String(255), default="India")
    audience_size: Mapped[str] = mapped_column(String(64), default="")
    audience_description: Mapped[str] = mapped_column(Text, default="")
    rate_card_hints: Mapped[str] = mapped_column(Text, default="")
    exclusions: Mapped[str] = mapped_column(Text, default="")
    collab_goals: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="profile")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(128), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    fit_rationale: Mapped[str] = mapped_column(Text, default="")
    suggested_angle: Mapped[str] = mapped_column(Text, default="")
    priority_narrative: Mapped[str] = mapped_column(Text, default="")
    research_notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(64), default="discovered")  # discovered|researching|outreach|closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="companies")
    contacts: Mapped[list["Contact"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    messages: Mapped[list["OutreachMessage"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    offers: Mapped[list["Offer"]] = relationship(back_populates="company")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255), default="")
    linkedin_url: Mapped[str] = mapped_column(String(512), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    email_confidence: Mapped[str] = mapped_column(String(32), default="")  # high|medium|low|guessed
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship(back_populates="contacts")
    messages: Mapped[list["OutreachMessage"]] = relationship(back_populates="contact")


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(32))  # linkedin|email
    subject: Mapped[str] = mapped_column(String(512), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="drafted")  # drafted|sent|replied|closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship(back_populates="messages")
    contact: Mapped["Contact | None"] = relationship(back_populates="messages")


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="paste")  # paste|email|dm
    raw_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="new")  # new|negotiating|accepted|passed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="offers")
    company: Mapped["Company | None"] = relationship(back_populates="offers")
    brief: Mapped["OfferBrief | None"] = relationship(
        back_populates="offer", uselist=False, cascade="all, delete-orphan"
    )


class OfferBrief(Base):
    __tablename__ = "offer_briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), unique=True)
    fit_summary: Mapped[str] = mapped_column(Text, default="")
    reputation_upsides: Mapped[str] = mapped_column(Text, default="")
    reputation_risks: Mapped[str] = mapped_column(Text, default="")
    pay_value_clarity: Mapped[str] = mapped_column(Text, default="")
    deliverable_load: Mapped[str] = mapped_column(Text, default="")
    red_flags: Mapped[str] = mapped_column(Text, default="")
    factors_json: Mapped[str] = mapped_column(Text, default="{}")
    recommended_stance: Mapped[str] = mapped_column(String(32), default="negotiate")  # accept|negotiate|pass
    talking_points: Mapped[str] = mapped_column(Text, default="")
    reply_draft: Mapped[str] = mapped_column(Text, default="")
    generation_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    offer: Mapped["Offer"] = relationship(back_populates="brief")
