
# app/api/webhooks.py
from fastapi import APIRouter, Request, HTTPException, status
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import Person
from app.core.settings import get_settings

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

    payload = await request.json()
    print(payload)
    # 1) get the first person object
    first_person = (payload.get("people") or [{}])[0]
    person_id    = first_person.get("id")
    if not person_id:
        raise HTTPException(400, "No person ID in payload")

    # 2) get the sanitized phone
    sanitized = (
        first_person
        .get("phone_numbers", [{}])[0]
        .get("sanitized_number")
    )
    if not sanitized:
        raise HTTPException(400, "No sanitized_number found")

    # 3) update your DB
    with SessionLocal() as db:
        person = db.scalars(
            select(Person).where(Person.apollo_person_id == person_id)
        ).first()

        if not person:
            raise HTTPException(404, "Person not found")

        person.personal_phone            = sanitized
        person.phone_verification_status = first_person.get("status", "verified")
        person.phones_raw_json           = first_person.get("phone_numbers")
        db.commit()

    return {"status": "ok", "personal_phone": sanitized}

