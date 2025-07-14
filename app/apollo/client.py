import requests, time, logging
from app.core.settings import get_settings

settings = get_settings()
log = logging.getLogger("apollo")

class ApolloClient:
    BASE = "https://api.apollo.io/v1"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": settings.apollo_api_key,
            "Content-Type": "application/json"
        })


    # --- internal helpers --------------------------------------------------
    def _call(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.BASE}{path}"
        resp = self.session.request(method, url, timeout=30, **kwargs)
        if resp.status_code >= 400:
            log.error("Apollo %s → %s returned %s\nPayload: %s\nBody: %s",
                    method, url, resp.status_code, kwargs.get("json"), resp.text)
            resp.raise_for_status()
        return resp.json()

    # --- public API --------------------------------------------------------
    # app/apollo/client.py
    def company_search(self, *, name: str, page: int = 1, per_page: int = 5):
        payload = {
            "q_organization_name": name,
            "page": page,
            "per_page": per_page,
            "display_mode": "explorer_mode",   # ← mandatory
        }
        return self._call("POST", "/mixed_companies/search", json=payload)

    
    def enrich_org(self, *, name: str | None = None, domain: str | None = None):
        return self._call("GET", "/organizations/enrich", params={
            "organization_name": name,
            "domain": domain
        })

    def people_search(
        self,
        *,
        domain: str,
        seniorities: list[str],
        titles: list[str] | None = None,
        page: int = 1,
        per_page: int = 100,
    ) -> dict:
        """
        POST /mixed_people/search but send filters as repeated query-params:
          - person_seniorities[]=...
          - q_organization_domains_list[]=...
        """
        # build a list of 2-tuples so requests will repeat the key
        params: list[tuple[str,str]] = []
        # Title filters
        if titles:
            for t in titles:
                params.append(("person_titles[]", t))

        for s in seniorities:
            params.append(("person_seniorities[]", s))
        
        params.append(("q_organization_domains_list[]", domain))

        # pagination
        params.append(("page", str(page)))
        params.append(("per_page", str(per_page)))

        print("Params for people search api call",params)

        return self._call("POST", "/mixed_people/search", params=params)

    def enrich_person_async(
        self,
        *,
        person_id: str,
        webhook_url: str,
        webhook_secret: str,
        reveal_email: bool = True,
        reveal_phone: bool = True,
        domain: str | None = None,
    ):
        payload = {
            "id": person_id,
            "reveal_personal_emails": reveal_email,
            "reveal_phone_number": reveal_phone,
            "webhook_url": webhook_url,
            "webhook_secret": webhook_secret,
        }

        # **scope by your company’s domain**  
        if domain:
            payload["domain"] = domain
        
        print(payload)

        return self._call("POST", "/people/match", json=payload)
    
    
