import requests, time, logging
from settings import get_settings

settings = get_settings()
log = logging.getLogger("apollo")

class ApolloClient:
    BASE = "https://api.apollo.io/v1"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"Api-Key": settings.apollo_api_key})

    # --- internal helpers --------------------------------------------------
    def _call(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.BASE}{path}"
        retries = 0
        while True:
            resp = self.session.request(method, url, timeout=30, **kwargs)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 2 ** retries))
                log.warning("Rate-limited, sleeping %s s", wait)
                time.sleep(wait)
                retries += 1
                continue
            resp.raise_for_status()
            return resp.json()

    # --- public API --------------------------------------------------------
    def enrich_org(self, *, name: str | None = None, domain: str | None = None):
        return self._call("GET", "/organizations/enrich", params={
            "organization_name": name,
            "domain": domain
        })

    def people_search(self, *, domain: str, titles: list[str]):
        titles_qs = [("person_titles[]", t) for t in titles]
        return self._call("POST", "/mixed_people/search", params=dict(titles_qs), json={
            "organization_domains": [domain],
            "page": 1, "per_page": 10
        })

    def enrich_person(self, person_id: str):
        return self._call("POST", "/people/match", json={"id": person_id})
