# enrich.py
import uuid
import logging

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from tasks import enrich_company

log = logging.getLogger("api")
router = APIRouter()

class EnrichPayload(BaseModel):
    company_name: str
    domain_entered: str | None = None

class TaskAck(BaseModel):
    task_id: str

@router.post("/enrich", response_model=TaskAck, status_code=202)
async def enqueue(payload: EnrichPayload, bg: BackgroundTasks):
    task_id = str(uuid.uuid4())
    bg.add_task(
        enrich_company.delay,
        task_id,
        payload.company_name,
        payload.domain_entered
    )
    log.info("QUEUED %s – %s", task_id, payload.company_name)
    return TaskAck(task_id=task_id)
