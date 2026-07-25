from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Company, Contact, User
from app.schemas import (
    ContactCreate,
    ContactFindResult,
    ContactOut,
    EmailGuessOut,
    EmailGuessRequest,
)
from app.services.contact_find import find_marketing_contacts
from app.services.email_guess import guess_corporate_email

router = APIRouter(tags=["contacts"])


def _company_for_user(db: Session, user: User, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/companies/{company_id}/contacts", response_model=list[ContactOut])
def list_contacts(
    company_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _company_for_user(db, user, company_id)
    return db.query(Contact).filter(Contact.company_id == company_id).all()


@router.post("/companies/{company_id}/contacts", response_model=ContactOut)
def create_contact(
    company_id: int,
    payload: ContactCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _company_for_user(db, user, company_id)
    data = payload.model_dump()
    if not (data.get("notes") or "").strip():
        data["notes"] = "Added manually."
    if not (data.get("email_confidence") or "").strip() and data.get("email"):
        data["email_confidence"] = "manual"
    contact = Contact(company_id=company_id, **data)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.post("/companies/{company_id}/contacts/find", response_model=ContactFindResult)
def find_and_save_contacts(
    company_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hunter Domain Search. Clears previous auto-found contacts so stale junk doesn't linger."""
    company = _company_for_user(db, user, company_id)
    found, source, message = find_marketing_contacts(company)

    # Drop prior auto-discovered rows; keep contacts explicitly added by the user
    existing = db.query(Contact).filter(Contact.company_id == company_id).all()
    for c in existing:
        if _is_auto_contact(c):
            db.delete(c)
    db.flush()

    saved: list[Contact] = []
    seen_emails: set[str] = set()
    seen_names: set[str] = set()
    for row in found:
        name_l = row["name"].lower()
        email_l = (row.get("email") or "").lower()
        if name_l in seen_names:
            continue
        if email_l and email_l in seen_emails:
            continue
        contact = Contact(company_id=company_id, **row)
        db.add(contact)
        saved.append(contact)
        seen_names.add(name_l)
        if email_l:
            seen_emails.add(email_l)
    db.commit()
    for c in saved:
        db.refresh(c)

    return ContactFindResult(contacts=saved, message=message, source=source)


def _is_auto_contact(c: Contact) -> bool:
    notes = (c.notes or "").strip()
    notes_l = notes.lower()
    if notes_l.startswith("added manually"):
        return False
    conf = (c.email_confidence or "").lower()
    if conf == "manual":
        return False

    markers = (
        "found via hunter",
        "hunter ·",
        "hunter only found",
        "found via public web",
        "parsed from linkedin",
        "hunter unavailable",
        "verify before outreach",
        "brand inbox",
        "no named marketing",
    )
    if any(m in notes_l for m in markers):
        return True

    # Legacy web-search junk: guessed/high confidence without a manual note
    if conf in {"guessed", "hunter", "generic"}:
        return True
    if conf in {"high", "medium", "low"} and not notes:
        return True
    if not notes and conf:
        return True
    return False


@router.delete("/contacts/{contact_id}")
def delete_contact(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    company = db.get(Company, contact.company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"ok": True}


@router.post("/email/guess", response_model=EmailGuessOut)
def email_guess(payload: EmailGuessRequest, user: User = Depends(get_current_user)):
    _ = user
    return guess_corporate_email(payload.first_name, payload.last_name, payload.domain)
