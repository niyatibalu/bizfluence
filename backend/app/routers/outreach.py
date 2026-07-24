from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Company, Contact, CreatorProfile, OutreachMessage, User
from app.schemas import (
    OutreachCreate,
    OutreachOut,
    OutreachUpdate,
    PitchGenerateRequest,
    PitchPack,
    SendEmailOut,
    SendEmailRequest,
)
from app.services.pitch import generate_pitch_pack
from app.services.resend_mail import send_outreach_email

router = APIRouter(tags=["outreach"])


def _company_for_user(db: Session, user: User, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/companies/{company_id}/outreach", response_model=list[OutreachOut])
def list_outreach(
    company_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _company_for_user(db, user, company_id)
    return (
        db.query(OutreachMessage)
        .filter(OutreachMessage.company_id == company_id)
        .order_by(OutreachMessage.created_at.desc())
        .all()
    )


@router.post("/companies/{company_id}/outreach/pitch", response_model=PitchPack)
def create_pitch(
    company_id: int,
    payload: PitchGenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company = _company_for_user(db, user, company_id)
    profile = db.query(CreatorProfile).filter(CreatorProfile.user_id == user.id).first()
    contact = db.get(Contact, payload.contact_id) if payload.contact_id else None
    if contact and contact.company_id != company_id:
        raise HTTPException(status_code=400, detail="Contact does not belong to company")
    pack = generate_pitch_pack(
        profile,
        company,
        contact,
        contact_name=payload.contact_name,
        contact_title=payload.contact_title,
    )
    if profile is not None:
        db.add(profile)
    db.add(company)
    db.commit()
    return pack


@router.post("/companies/{company_id}/outreach", response_model=OutreachOut)
def save_outreach(
    company_id: int,
    payload: OutreachCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _company_for_user(db, user, company_id)
    msg = OutreachMessage(company_id=company_id, **payload.model_dump())
    db.add(msg)
    company = db.get(Company, company_id)
    if company and company.status == "discovered":
        company.status = "outreach"
    db.commit()
    db.refresh(msg)
    return msg


@router.patch("/outreach/{message_id}", response_model=OutreachOut)
def update_outreach(
    message_id: int,
    payload: OutreachUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg = db.get(OutreachMessage, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    company = db.get(Company, msg.company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(status_code=404, detail="Message not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(msg, key, value)
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/outreach/send-email", response_model=SendEmailOut)
def send_email(
    payload: SendEmailRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    result = send_outreach_email(payload.to_email, payload.subject, payload.body)
    if payload.outreach_id and result.ok and result.mode == "resend":
        msg = db.get(OutreachMessage, payload.outreach_id)
        if msg:
            msg.status = "sent"
            db.commit()
    return result
