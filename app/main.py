import logging

from fastapi import FastAPI
from app.api.enrich import router as enrich_router
from app.api.webhook import router as webhooks

# optional: configure logging here or in a separate app/core/logging.py
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")

app = FastAPI(title="Apollo-Zoho Enricher")

# mount the enrich endpoint
app.include_router(enrich_router)

app.include_router(webhooks)