from celery import Celery
from datetime import datetime
from db import SessionLocal
from models import Company, OrganizationDetails, Person, PersonDetails, CompanyPeople
from apollo_client import ApolloClient
from sqlalchemy import select
import uuid, logging

celery = Celery("tasks", broker=get_settings().redis_url)
celery.conf.task_default_queue = "enrich"
apollo = ApolloClient()
log = logging.getLogger("worker")

TITLES_FILTER = [
    "owner", "founder", "c_suite", "partner", "vp",
    "head", "director", "manager", "senior"
]

@celery.task(bind=True, max_retries=None, autoretry_for=(Exception,),
             retry_backoff=True, retry_jitter=True)
def enrich_company(self, task_id: str, company_name: str, domain_entered: str | None):
    log.info("START %s – %s", task_id, company_name)
    with SessionLocal() as db:
        # idempotent upsert
        stmt = select(Company).where(
            Company.name == company_name,
            Company.domain_entered == domain_entered
        )
        comp = db.scalars(stmt).first()
        if not comp:
            comp = Company(name=company_name, domain_entered=domain_entered)
            db.add(comp); db.commit(); db.refresh(comp)

    # ---------- 1) organization enrichment  -------------------------------
    org_json = apollo.enrich_org(name=company_name, domain=domain_entered)["organization"]

    with SessionLocal() as db:
        comp = db.get(Company, comp.id)                      # re-attach
        comp.apollo_org_id    = org_json["id"]
        comp.domain_resolved  = org_json["primary_domain"]
        comp.employee_count   = org_json.get("estimated_num_employees")
        comp.industry         = org_json.get("industry")
        comp.location_city    = org_json.get("city")
        comp.location_country = org_json.get("country")
        comp.revenue          = org_json.get("annual_revenue")
        comp.enriched_at      = datetime.utcnow()
        comp.is_enriched      = True

        det = OrganizationDetails(company_id=comp.id, **org_json)  # 1-to-1
        db.merge(det)                                              # upsert
        db.commit()

    # ---------- 2) people search -----------------------------------------
    search = apollo.people_search(domain=comp.domain_resolved, titles=TITLES_FILTER)
    for stub in search.get("people", []):
        person_id = stub["id"]
        person_json = apollo.enrich_person(person_id)["person"]

        with SessionLocal() as db:
            # upsert core row
            person = db.scalars(
                select(Person).where(Person.apollo_person_id == person_id)
            ).first()
            if not person:
                person = Person(apollo_person_id=person_id)
            person.first_name = person_json["first_name"]
            person.last_name  = person_json["last_name"]
            person.title      = person_json.get("title")
            person.seniority  = person_json.get("seniority")
            person.email      = person_json.get("email")
            person.phone      = (
                person_json.get("phone_numbers") or [{}]
            )[0].get("sanitized_number")
            person.linkedin_url     = person_json.get("linkedin_url")
            person.location_city    = person_json.get("city")
            person.location_country = person_json.get("country")
            person.enriched_at      = datetime.utcnow()
            person.is_enriched      = True

            db.merge(person)
            db.commit(); db.refresh(person)

            # link to company
            link = CompanyPeople(company_id=comp.id, person_id=person.id)
            db.merge(link)

            # save 1-to-1 detail blob
            unwanted = {"organization", "employment_history"}
            filtered = {k: v for k, v in person_json.items() if k not in unwanted}
            pdet = PersonDetails(person_id=person.id, **filtered)
            db.merge(pdet)
            db.commit()

    log.info("DONE %s", task_id)
