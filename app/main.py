import logging

from fastapi import FastAPI
from enrich import router as enrich_router

# optional: configure logging here or in a separate app/core/logging.py
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")

app = FastAPI(title="Apollo-Zoho Enricher")

# mount the enrich endpoint
app.include_router(enrich_router)
