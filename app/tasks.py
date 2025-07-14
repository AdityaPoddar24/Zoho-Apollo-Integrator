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

# TITLES_FILTER = [
#     "owner", "founder", "manager", "director"
# ]

TITLES_FILTER = ["vp", "director", "head", "manager", "owner", "partner", "founder"],

def _primary_phone(stub: dict) -> str | None:
    """Return the best single phone number for either payload type."""
    # 1) person‐level
    if stub.get("sanitized_phone"):
        return stub["sanitized_phone"]
    if stub.get("phone_numbers"):
        return stub["phone_numbers"][0].get("sanitized_number")

    # 2) fallback to the nested org‐block, if present
    org = stub.get("organization", {})
    # Apollo sometimes gives both "sanitized_phone" *and*
    # "primary_phone":{…}, so check both
    if org.get("sanitized_phone"):
        return org["sanitized_phone"]
    if isinstance(org.get("primary_phone"), dict):
        return org["primary_phone"].get("sanitized_number")

    # 3) legacy
    if stub.get("number"):
        return (stub["number"] or [{}])[0].get("sanitized_number")



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
    org_enrich = apollo.enrich_org(name=company_name, domain=domain)
    print("Enrich response for %s: %r", company_name, org_enrich)
    if "organization" not in org_enrich:
        log.error("Missing 'organization' key in response; full payload: %r", org_enrich)
        return  # or raise a custom error
    org_json = org_enrich["organization"]

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
        det.website_url              = org_json.get("website_url")          or det.website_url
        det.blog_url                 = org_json.get("blog_url")             or det.blog_url
        det.angellist_url            = org_json.get("angellist_url")        or det.angellist_url
        det.linkedin_url             = org_json.get("linkedin_url")         or det.linkedin_url
        det.twitter_url              = org_json.get("twitter_url")          or det.twitter_url
        det.facebook_url             = org_json.get("facebook_url")         or det.facebook_url
        det.alexa_ranking            = org_json.get("alexa_ranking")        or det.alexa_ranking
        det.phone                    = (
            org_json.get("sanitized_phone")
            or org_json.get("phone")
            or det.phone
        )
        det.primary_phone            = org_json.get("primary_phone")        or det.primary_phone
        det.languages                = org_json.get("languages")            or det.languages or []
        det.linkedin_uid             = org_json.get("linkedin_uid")         or det.linkedin_uid
        det.founded_year             = org_json.get("founded_year")         or det.founded_year
        det.publicly_traded_symbol   = org_json.get("publicly_traded_symbol")   or det.publicly_traded_symbol
        det.publicly_traded_exchange = org_json.get("publicly_traded_exchange") or det.publicly_traded_exchange
        det.logo_url                 = org_json.get("logo_url")             or det.logo_url
        det.crunchbase_url           = org_json.get("crunchbase_url")       or det.crunchbase_url
        det.primary_domain           = org_json.get("primary_domain")       or det.primary_domain
        det.keywords                 = org_json.get("keywords")             or det.keywords or []
        det.estimated_num_employees  = org_json.get("estimated_num_employees") or det.estimated_num_employees
        det.industries               = org_json.get("industries")           or det.industries or []
        det.secondary_industries     = org_json.get("secondary_industries") or det.secondary_industries or []
        det.snippets_loaded          = org_json.get("snippets_loaded", det.snippets_loaded)
        det.industry_tag_id          = org_json.get("industry_tag_id")      or det.industry_tag_id
        det.industry_tag_hash        = org_json.get("industry_tag_hash")    or det.industry_tag_hash
        det.retail_location_count    = org_json.get("retail_location_count")    or det.retail_location_count
        det.raw_address              = org_json.get("raw_address")          or det.raw_address
        det.street_address           = org_json.get("street_address")       or det.street_address
        det.city                     = org_json.get("city")                 or det.city
        det.state                    = org_json.get("state")                or det.state
        det.postal_code              = org_json.get("postal_code")          or det.postal_code
        det.country                  = org_json.get("country")              or det.country
        det.owned_by_organization_id = org_json.get("owned_by_organization_id") or det.owned_by_organization_id
        det.seo_description          = org_json.get("seo_description")      or det.seo_description
        det.short_description        = org_json.get("short_description")    or det.short_description
        det.suborganizations         = org_json.get("suborganizations")     or det.suborganizations or []
        det.num_suborganizations     = org_json.get("num_suborganizations") or det.num_suborganizations
        det.annual_revenue_printed   = org_json.get("annual_revenue_printed")   or det.annual_revenue_printed
        det.annual_revenue           = org_json.get("annual_revenue")       or det.annual_revenue
        det.total_funding            = org_json.get("total_funding")        or det.total_funding
        det.total_funding_printed    = org_json.get("total_funding_printed")    or det.total_funding_printed
        det.latest_funding_round_date= org_json.get("latest_funding_round_date") or det.latest_funding_round_date
        det.latest_funding_stage     = org_json.get("latest_funding_stage") or det.latest_funding_stage
        det.funding_events           = org_json.get("funding_events")       or det.funding_events or []
        det.technology_names         = (
            org_json.get("technology_names")
            or [t.get("name") for t in org_json.get("current_technologies", [])]
            or det.technology_names
            or []
        )
        det.org_chart_root_people_ids = org_json.get("org_chart_root_people_ids") or det.org_chart_root_people_ids or []
        det.org_chart_sector         = org_json.get("org_chart_sector")     or det.org_chart_sector
        det.org_chart_removed        = org_json.get("org_chart_removed", det.org_chart_removed)
        det.org_chart_show_department_filter = org_json.get(
            "org_chart_show_department_filter", det.org_chart_show_department_filter
        )
        det.account_id               = org_json.get("account_id")          or det.account_id
        det.departmental_head_count  = org_json.get("departmental_head_count") or det.departmental_head_count
        det.primary_phone            = org_json.get("primary_phone")       or det.primary_phone

        det.updated_at = datetime.utcnow()

        db.merge(det)
        db.commit()

    # ---------- 2) people search -----------------------------------------
    search = apollo.people_search(
        domain      = domain,
        seniorities = TITLES_FILTER,
        titles      = ["hr", "people", "talent", "cfo", "finance", "founder", "owner", "ceo", "coo", "chro"],
        page        = 1,
        per_page    = 5,
    )
    # ── 1. normalise the list of “stubs” ──────────────────────────
    stubs: list[dict] = search.get("people", []) + search.get("contacts", [])
    log.info("People search returned %d stubs for %s", len(stubs), domain)

    for stub in stubs:
         # ── 2. figure out which identifier we can enrich with ─────
        apollo_id: str | None = stub.get("person_id") or stub.get("id")
        if not apollo_id:          # extremely rare, but be safe
            log.warning("Skipping stub without person/contact id: %s", stub)
            continue

        # ────────────────────────────── start tx for ONE person ────────────
        with SessionLocal() as db, db.begin():
            # 1. stub insert / update (guarantees PK for FK linkage)
            person = db.scalars(
                select(Person).where(Person.apollo_person_id == apollo_id)
            ).first()

            if person is None:
                person = Person(apollo_person_id=apollo_id)
                db.add(person)

            # fill stub data first
            person.first_name        = stub.get("first_name")
            person.last_name         = stub.get("last_name")
            person.title             = stub.get("title")
            person.seniority         = stub.get("seniority")
            person.email             = stub.get("email")                 # redacted placeholder
            person.linkedin_url      = stub.get("linkedin_url")
            person.location_city     = stub.get("city")
            person.location_country  = stub.get("country")
            person.updated_at        = datetime.utcnow()
            person.company_name      = company_name

            db.flush()

            # 1-a. PersonDetails stub
            details = db.get(PersonDetails, person.id)
            if details is None:
                details = PersonDetails()
                details.person = person     # <— binds person_id for us
                db.add(details)
            
            details.photo_url         = stub.get("photo_url")
            details.linkedin_url_full = stub.get("linkedin_url")
            details.headline          = stub.get("headline")
            details.email_status      = stub.get("email_status")
            details.departments       = stub.get("departments")    or []
            details.subdepartments    = stub.get("subdepartments") or []
            details.functions         = stub.get("functions")      or []
            details.raw_json          = stub                       # keep the search snapshot
            details.updated_at        = datetime.utcnow()
            details.phone_numbers     = _primary_phone(stub)

            db.flush()          # person.id now available for FK

            # 1-b. company-person link (idempotent merge)
            link = CompanyPeople(company_id=comp.id, person_id=person.id)
            db.merge(link)

            # 2. trigger enrichment and capture the immediate response
            try:
                enrich_resp = apollo.enrich_person_async(
                    person_id      = apollo_id,
                    webhook_url    = WEBHOOK_URL,
                    webhook_secret = settings.apollo_webhook_secret,
                    reveal_email   = True,
                    reveal_phone   = True,
                    domain         = domain,
                )
                log.info("Enrich instant response: ", enrich_resp)
                print("Enrich instant response: ", enrich_resp)
                enriched = enrich_resp.get("person", {})

            except Exception as exc:
                log.warning("Enrich call failed for %s: %s", apollo_id, exc)
                enriched = {}

            # 3. overlay enriched fields (only if returned)
            if enriched:
                person.first_name        = enriched.get("first_name", person.first_name)
                person.last_name         = enriched.get("last_name",  person.last_name)
                person.title             = enriched.get("title",      person.title)
                person.seniority         = enriched.get("seniority",  person.seniority)
                person.email             = enriched.get("email",      person.email)
                person.phone            = _primary_phone(enriched)

                # write extra details
                details.headline                      = enriched.get("headline", details.headline)
                details.twitter_url                   = enriched.get("twitter_url", details.twitter_url)
                details.github_url                    = enriched.get("github_url",  details.github_url)
                details.facebook_url                  = enriched.get("facebook_url", details.facebook_url)
                details.extrapolated_email_confidence = enriched.get(
                    "extrapolated_email_confidence", details.extrapolated_email_confidence
                )
                details.intent_strength               = enriched.get("intent_strength", details.intent_strength)
                details.show_intent                   = enriched.get("show_intent", details.show_intent)
                details.revealed_for_current_team     = enriched.get(
                    "revealed_for_current_team", details.revealed_for_current_team
                )

                # Overwrite raw_json with the latest full blob
                details.raw_json = enriched

                # mark person as enriched
                person.is_enriched = True
                person.enriched_at = datetime.utcnow()

            log.info("Upserted & enriched person %s (%s)", person.id, apollo_id)
        # ────────────────────────────── end tx for ONE person ───────────────

    log.info("Finished import for %s – processed %d people", domain, len(stubs))