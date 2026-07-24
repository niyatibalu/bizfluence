"""Fresh demo workspaces — never reuse prior test data."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import CreatorProfile, User


def create_fresh_demo_user(db: Session) -> User:
    """Each 'Try demo' click gets a brand-new empty user (no leftover brands/offers)."""
    token = uuid.uuid4().hex[:10]
    user = User(email=f"demo-{token}@bizfluence.local", name="Demo Creator")
    db.add(user)
    db.flush()
    profile = CreatorProfile(
        user_id=user.id,
        niche="",
        bio="",
        platforms="Instagram",
        audience_geo="India",
        audience_size="10K–50K",
        exclusions="",
        collab_goals="Paid collabs and thoughtful PR with India D2C brands",
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return user
