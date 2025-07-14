
# app/api/webhooks.py
from fastapi import APIRouter, Request, HTTPException, status
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import Person, PersonDetails
from app.core.settings import get_settings
from typing import Any
import logging
log = logging.getLogger(__name__)
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(prefix="/webhook")

@router.post("/apollo_phone")
async def apollo_phone(request: Request):
    print("Apollo phone webhook received", request, request.headers)
    settings = get_settings()

    # secret = (
    #     request.headers.get("Webhook-Secret")
    #     or request.headers.get("X-Apollo-Webhook-Secret")
    # )
    # if secret != settings.apollo_webhook_secret:
    #     raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid secret")

    # ── 1. parse JSON body ─────────────────────────────────────────────────
    payload = await request.json()

    print("Incoming Apollo phone payload: %r", payload)

    # keep a copy for storage
    full_blob = payload

    # Apollo always returns an *array* of people; we only ever request one
    first_person: dict[str, Any] = (payload.get("people") or [{}])[0]

    person_id: str | None = first_person.get("id")
    if not person_id:
        raise HTTPException(400, "No person id in payload")

    # prefer first sanitized_number, fall back to raw if sanitised missing
    phones: list[dict[str, Any]] = first_person.get("phone_numbers") or []
    sanitized_number: str | None = (
        phones[0].get("sanitized_number") if phones else None
    ) or (phones[0].get("raw_number") if phones else None)

    if not sanitized_number:
        raise HTTPException(400, "No phone number found")

    phone_status: str = first_person.get("status", "verified")

    # ── 2. save to DB ──────────────────────────────────────────────────────
    try:
        with SessionLocal() as db, db.begin():
            # 2-a. Person (must exist – inserted during import phase)
            person: Person | None = db.scalars(
                select(Person).where(Person.apollo_person_id == person_id)
            ).first()

            if person is None:
                raise HTTPException(404, f"Person '{person_id}' not found")

            person.personal_phone            = sanitized_number
            person.phone_verification_status = phone_status
            person.phones_raw_json           = phones
            person.updated_at                = datetime.utcnow()

            # 2-b. PersonDetails (create if missing – race-safe)
            details: PersonDetails | None = db.scalars(
                select(PersonDetails).where(PersonDetails.person_id == person.id)
            ).first()

            if details is None:
                details = PersonDetails(person_id=person.id)
                db.add(details)

            # store the *same* info in details for analytics / BI users
            details.webhook_phone_number  = sanitized_number
            details.webhook_respomse_json       = full_blob
            details.updated_at     = datetime.utcnow()

            # optional: also keep status if you want it per-number / per-payload
            details.contact_blob   = first_person   # ← freeform JSON column

            # commit happens automatically at context-exit
    except SQLAlchemyError as exc:
        # make sure we roll back so the connection returns to pool clean
        log.error("DB error while saving Apollo phone webhook: %s", exc, exc_info=True)
        raise HTTPException(500, "DB error")
    except HTTPException:
        # re-raise specific HTTP errors (404, 400, 401…)
        raise

    # ── 3. ACK to Apollo ───────────────────────────────────────────────────
    return {
        "status": "ok",
        "person_id": person_id,
        "personal_phone": sanitized_number,
    }
