from celery import Celery
from datetime import datetime
from app.db.session import SessionLocal
from app.db.models import Company, OrganizationDetails, Person, PersonDetails, CompanyPeople, CompanySearchResults, CompanySearchRun
from app.apollo.client import ApolloClient
from sqlalchemy import select
from app.core.settings import get_settings
import uuid, logging

celery = Celery("tasks", broker=get_settings().redis_url)
celery.conf.task_default_queue = "enrich"
apollo = ApolloClient()
log = logging.getLogger("worker")

from urllib.parse import urljoin
settings = get_settings()
WEBHOOK_URL = urljoin(settings.public_base_url, "/webhook/apollo_phone")

# TITLES_FILTER = [
#     "owner", "founder", "c_suite", "partner", "vp",
#     "head", "director", "manager", "senior"
# ]

TITLES_FILTER = [
    "owner", "founder"
]

# @celery.task(bind=True, max_retries=None, autoretry_for=(Exception,),
#              retry_backoff=True, retry_jitter=True)
@celery.task(bind=True, max_retries=0)
def enrich_company(self, task_id: str, company_name: str, domain_entered: str | None):
    log.info("START %s – %s", task_id, company_name)

    # 0) Search by name if no domain supplied --------------------------------
    # ---------------------------------------------------------------------
    # A) SEARCH   (save the entire search response immediately)
    # ---------------------------------------------------------------------
    domain_for_enrich = domain_entered
    if domain_for_enrich is None:
        sr_json   = apollo.company_search(name=company_name, per_page=5)   # now returns "accounts"
        log.info("DOMAIN SEARCH", sr_json)
        accounts  = sr_json.get("accounts", [])

        # 1. store the RUN metadata + full JSON
        with SessionLocal() as db:
            run = CompanySearchRun(
                query_name      = company_name,
                partial_results = sr_json.get("partial_results_only"),
                page            = sr_json["pagination"]["page"],
                per_page        = sr_json["pagination"]["per_page"],
                total_entries   = sr_json["pagination"]["total_entries"],
                total_pages     = sr_json["pagination"]["total_pages"],
                raw_json        = sr_json,
            )
            db.add(run); db.flush()                   # run.id now available

            # 2. store EACH account hit
            for hit in accounts:
                db.add(CompanySearchResults(
                    run_id         = run.id,
                    apollo_org_id  = hit["id"],
                    name           = hit["name"],
                    primary_domain = hit.get("primary_domain") or hit.get("domain"),
                    website_url    = hit.get("website_url"),
                    phone          = hit.get("phone"),
                    logo_url       = hit.get("logo_url"),
                    alexa_ranking  = hit.get("alexa_ranking"),
                    raw_json       = hit,
                ))
            db.commit()

        # 3. pick the first hit we’ll enrich
        if not accounts:
            log.warning("No accounts found for %s; aborting task %s", company_name, task_id)
            return

        first_hit = accounts[0]

        log.info("First hit: %s", first_hit)

        # 4. derive domain
        from urllib.parse import urlparse
        domain_for_enrich = (
            first_hit.get("primary_domain")
            or first_hit.get("domain")
            or urlparse(first_hit.get("website_url", "")).netloc
        )

        log.info("Domain for enrich: %s", domain_for_enrich)

        if not domain_for_enrich:
            log.warning("No domain found in first hit for %s", company_name)
            return
    # ---------------------------------------------------------------------
    # B) COMPANY UPSERT shell row (before enrich)
    # ---------------------------------------------------------------------
    with SessionLocal() as db:
        comp = db.scalars(
            select(Company).where(
                Company.name == company_name, Company.domain_entered == domain_entered
            )
        ).first()
        if not comp:
            comp = Company(name=company_name, domain_entered=domain_entered)
            db.add(comp); db.commit(); db.refresh(comp)

    domain = domain_entered if domain_entered is not None else domain_for_enrich
    log.info("Domain trying for: %s", domain)

    # ---------- 1) organization enrichment  -------------------------------
    org_json = apollo.enrich_org(name=company_name, domain=domain)["organization"]

    with SessionLocal() as db:
        comp = db.get(Company, comp.id)                      # re-attach
        comp.apollo_org_id    = org_json["id"]
        comp.domain_resolved  = domain
        comp.employee_count   = org_json.get("estimated_num_employees")
        comp.industry         = org_json.get("industry")
        comp.location_city    = org_json.get("city")
        comp.location_country = org_json.get("country")
        comp.revenue          = org_json.get("annual_revenue")
        comp.enriched_at      = datetime.utcnow()
        comp.is_enriched      = True

        det = OrganizationDetails(
            company_id=comp.id,
            raw_json=org_json
        )
        db.merge(det)
        db.commit()

    # ---------- 2) people search -----------------------------------------
    search = apollo.people_search(
        domain=domain,
        seniorities=TITLES_FILTER,   # e.g. ["owner","founder","c_suite",…]
        page=1,
        per_page=10,
    )
    log.info("People search: %s", search)
    # for stub in search.get("people", []):
    hits = search.get("people", [])[:1]   # only the first person

    for stub in hits:
        person_id   = stub["id"]
        person_json = apollo.enrich_person_async(
            person_id      = person_id,
            webhook_url    = WEBHOOK_URL,
            webhook_secret = settings.apollo_webhook_secret,
            reveal_email   = True,
            reveal_phone   = True,
            domain         = domain,   # ← critical!
        )["person"]

        log.info("Person JSON: %s", person_json)

        with SessionLocal() as db:
            # 2.1 Upsert core Person
            existing = db.scalars(
                select(Person).where(Person.apollo_person_id == person_id)
            ).first()

            if existing:
                person = existing
            else:
                person = Person(apollo_person_id=person_id, 
                            first_name = person_json.get("first_name") or "",
                            last_name = person_json.get("last_name")  or "",
                            is_enriched = False, 
                )
                db.add(person)
                db.commit()
                db.refresh(person)

            # 2.2 Update scalar fields
            person.first_name       = person_json.get("first_name")
            person.last_name        = person_json.get("last_name")
            person.title            = person_json.get("title")
            person.seniority        = person_json.get("seniority")
            person.email            = person_json.get("email")
            person.phone            = (
                person_json.get("number") or [{}]
            )[0].get("sanitized_number")
            person.linkedin_url     = person_json.get("linkedin_url")
            person.location_city    = person_json.get("city")
            person.location_country = person_json.get("country")
            person.enriched_at      = datetime.utcnow()
            person.is_enriched      = True
            # person.personal_email = person_json.get("email_personal") or person_json.get("personal_emails", [None])[0]

            person = db.merge(person)
            db.commit()
            db.refresh(person)

            # link to company
            link = CompanyPeople(company_id=comp.id, person_id=person.id)
            db.merge(link)
            db.commit()

            pdet = PersonDetails(person_id=person.id, raw_json=person_json)
            db.merge(pdet)
            db.commit()

    log.info("DONE %s", task_id)
