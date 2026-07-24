from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import CreatorProfile, User
from app.schemas import HealthOut, LoginRequest, ProfileIn, ProfileOut, UserOut
from app.services.seed import create_fresh_demo_user
from app.services.web_research import research_creator

router = APIRouter(tags=["auth"])


@router.get("/health", response_model=HealthOut)
def health():
    get_settings.cache_clear()
    settings = get_settings()
    from app.services.llm import last_llm_status

    st = last_llm_status()
    live = "unknown"
    detail = ""
    if not settings.gemini_api_key:
        live = "offline"
        detail = "No API key in backend/.env"
    elif st.get("mode") == "gemini":
        live = "ok"
    elif "429" in (st.get("detail") or "") or "quota" in (st.get("detail") or "").lower():
        live = "quota"
        detail = "Free-tier quota hit — app uses offline writers until Google resets limits."
    elif st.get("detail"):
        live = "offline"
        detail = (st.get("detail") or "")[:200]
    return HealthOut(
        status="ok",
        app=settings.app_name,
        gemini_configured=bool(settings.gemini_api_key),
        resend_configured=bool(settings.resend_api_key),
        gemini_live=live,
        gemini_detail=detail,
    )


@router.post("/auth/login", response_model=UserOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    is_new = False
    if not user:
        user = User(email=payload.email.lower(), name=payload.name or payload.email.split("@")[0])
        db.add(user)
        db.commit()
        db.refresh(user)
        is_new = True
    elif payload.name and user.name != payload.name:
        user.name = payload.name
        db.commit()
        db.refresh(user)
    return UserOut(id=user.id, email=user.email, name=user.name, is_new=is_new)


@router.post("/auth/demo", response_model=UserOut)
def login_demo(db: Session = Depends(get_db)):
    """Always returns a fresh empty workspace — no shared/leftover test data."""
    user = create_fresh_demo_user(db)
    return UserOut(id=user.id, email=user.email, name=user.name, is_new=True)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/profile", response_model=ProfileOut | None)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(CreatorProfile).filter(CreatorProfile.user_id == user.id).first()


@router.put("/profile", response_model=ProfileOut)
def upsert_profile(
    payload: ProfileIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(CreatorProfile).filter(CreatorProfile.user_id == user.id).first()
    data = payload.model_dump()
    if not profile:
        profile = CreatorProfile(user_id=user.id, **data)
        db.add(profile)
    else:
        for key, value in data.items():
            setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    # Always refresh internal research on save (not shown in the UI)
    try:
        research_creator(profile, force=True)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    except Exception:  # noqa: BLE001
        pass
    return profile


@router.post("/profile/research", response_model=ProfileOut)
def refresh_creator_research(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(CreatorProfile).filter(CreatorProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Save your profile first")
    research_creator(profile, force=True)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile
