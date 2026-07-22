import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin

import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))

DEFAULT_COMPANIES_PATH = Path(__file__).resolve().parents[1] / "applyflow_data" / "remote_companies.json"
DEFAULT_CONTACTS_PATH = Path(__file__).resolve().parents[1] / "applyflow_data" / "company_contacts.json"

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
COMMON_PATHS = ["", "/contact", "/careers", "/jobs", "/about"]
COMMON_ALIASES = ["careers", "jobs", "talent", "recruiting", "hr", "internships", "people", "hello", "contact"]
REJECT_LOCALS = {"abuse", "security", "suspicious", "privacy", "legal", "support", "help", "sales", "press", "media", "noreply", "no-reply"}

KNOWN_COMPANY_DOMAINS = {
    "10up": "10up.com",
    "37signals": "37signals.com",
    "42 Technologies": "42technologies.com",
    "90 Seconds": "90seconds.com",
    "Abstract API": "abstractapi.com",
    "Acquia": "acquia.com",
    "Adzuna": "adzuna.com",
    "Akka": "akka.io",
    "Alight Solutions": "alight.com",
    "Amazon": "amazon.jobs",
    "Andela": "andela.com",
    "Appcues": "appcues.com",
    "Appwrite": "appwrite.io",
    "Articulate": "articulate.com",
    "Asana": "asana.com",
    "Auth0": "auth0.com",
    "Automattic": "automattic.com",
    "Bairesdev": "bairesdev.com",
    "Balena": "balena.io",
    "Balsamiq": "balsamiq.com",
    "Bandcamp": "bandcamp.com",
    "Basecamp": "basecamp.com",
    "Bitovi": "bitovi.com",
    "Buffer": "buffer.com",
    "Canonical": "canonical.com",
    "Capgemini": "capgemini.com",
    "Chess": "chess.com",
    "CircleCI": "circleci.com",
    "ClickUp": "clickup.com",
    "Close": "close.com",
    "CodePen": "codepen.io",
    "CodeSandbox": "codesandbox.io",
    "Coinbase": "coinbase.com",
    "Customer.io": "customer.io",
    "Datadog": "datadoghq.com",
    "Deel": "deel.com",
    "DigitalOcean": "digitalocean.com",
    "Discourse": "discourse.org",
    "Docker": "docker.com",
    "DuckDuckGo": "duckduckgo.com",
    "Elastic": "elastic.co",
    "Etsy": "etsy.com",
    "Fastly": "fastly.com",
    "Fleetio": "fleetio.com",
    "Fly.io": "fly.io",
    "GitHub": "github.com",
    "GitLab": "gitlab.com",
    "Glitch": "glitch.com",
    "GoDaddy": "godaddy.com",
    "Harvest": "getharvest.com",
    "Heap": "heap.io",
    "Help Scout": "helpscout.com",
    "Honeybadger": "honeybadger.io",
    "Hotjar": "hotjar.com",
    "Hubspot": "hubspot.com",
    "IBM": "ibm.com",
    "Intercom": "intercom.com",
    "Kaggle": "kaggle.com",
    "Kinsta": "kinsta.com",
    "Komoot": "komoot.com",
    "Kraken": "kraken.com",
    "Labelbox": "labelbox.com",
    "MailerLite": "mailerlite.com",
    "Mapbox": "mapbox.com",
    "MetaMask": "metamask.io",
    "Microsoft": "microsoft.com",
    "MongoDB": "mongodb.com",
    "Mux": "mux.com",
    "Namecheap": "namecheap.com",
    "Netguru": "netguru.com",
    "Nvidia": "nvidia.com",
    "Okta": "okta.com",
    "Oracle": "oracle.com",
    "Parabol": "parabol.co",
    "PayU": "payu.com",
    "Percona": "percona.com",
    "Plex": "plex.tv",
    "Prisma": "prisma.io",
    "Quora": "quora.com",
    "Rackspace": "rackspace.com",
    "Red Hat": "redhat.com",
    "Replit": "replit.com",
    "Rocket.Chat": "rocket.chat",
    "Salesforce": "salesforce.com",
    "Scopic Software": "scopicsoftware.com",
    "Shopify": "shopify.com",
    "Sonatype": "sonatype.com",
    "Spotify": "spotify.com",
    "Stack Exchange": "stackoverflow.com",
    "Sticker Mule": "stickermule.com",
    "Stripe": "stripe.com",
    "Toptal": "toptal.com",
    "Twilio": "twilio.com",
    "Udacity": "udacity.com",
    "Vercel": "vercel.com",
    "VMware": "vmware.com",
    "Wikimedia Foundation": "wikimediafoundation.org",
    "X-Team": "x-team.com",
    "Yahoo!": "yahoo.com",
    "Zapier": "zapier.com",
}


@dataclass
class ContactResult:
    company: str
    domain: str
    verified_emails: list[str]
    possible_emails: list[str]
    sources: list[str]
    confidence: str
    notes: str


def load_contacts(path: Path = DEFAULT_CONTACTS_PATH) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_contacts(contacts: dict, path: Path = DEFAULT_CONTACTS_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=2, ensure_ascii=True)
    return path


def load_companies(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [str(item).strip() for item in data if str(item).strip()]


def best_email_for_company(company: str, contacts: dict | None = None) -> str:
    contacts = contacts if contacts is not None else load_contacts()
    item = contacts.get(company) or {}
    verified = item.get("verified_emails") or []
    possible = item.get("possible_emails") or []
    return (verified or possible or [""])[0]


def discover_company_contact(company: str, timeout: float = 5.0) -> ContactResult:
    domain = domain_for_company(company)
    sources = []
    verified = set()

    if domain:
        session = requests.Session()
        session.headers.update({"User-Agent": "ezApply contact finder (personal internship outreach)"})
        for base in _candidate_base_urls(domain):
            for path in COMMON_PATHS:
                url = urljoin(base, path)
                try:
                    response = session.get(url, timeout=timeout, allow_redirects=True)
                except requests.RequestException:
                    continue
                if response.status_code >= 400 or not response.text:
                    continue
                sources.append(response.url)
                verified.update(_extract_emails(response.text, domain))
                if len(sources) >= 4:
                    break
            if verified or len(sources) >= 4:
                break

    possible = _possible_emails(domain) if domain else []
    confidence = "verified" if verified else ("guessed-domain" if domain else "unknown")
    notes = "Emails found on company pages." if verified else "No public email found; possible emails are guesses from the domain."
    return ContactResult(
        company=company,
        domain=domain,
        verified_emails=sorted(verified),
        possible_emails=possible,
        sources=sources[:6],
        confidence=confidence,
        notes=notes,
    )


def discover_contacts(limit: int, companies_path: Path = DEFAULT_COMPANIES_PATH, output_path: Path = DEFAULT_CONTACTS_PATH, refresh: bool = False) -> Path:
    companies = load_companies(companies_path)[:limit]
    existing = load_contacts(output_path)
    for company in companies:
        if not refresh and company in existing and existing[company].get("confidence") == "verified":
            continue
        existing[company] = asdict(discover_company_contact(company))
        save_contacts(existing, output_path)
    return save_contacts(existing, output_path)


def domain_for_company(company: str) -> str:
    if company in KNOWN_COMPANY_DOMAINS:
        return KNOWN_COMPANY_DOMAINS[company]
    slug = re.sub(r"[^a-z0-9]+", "", company.lower())
    if not slug:
        return ""
    return f"{slug}.com"


def _candidate_base_urls(domain: str) -> list[str]:
    if domain.startswith("http://") or domain.startswith("https://"):
        return [domain]
    return [f"https://{domain}", f"https://www.{domain}"]


def _extract_emails(text: str, domain: str) -> list[str]:
    emails = set()
    for email in EMAIL_RE.findall(text):
        cleaned = email.strip(".,;:()[]{}<>").lower()
        if _is_good_email(cleaned, domain):
            emails.add(cleaned)
    return sorted(emails)


def _is_good_email(email: str, domain: str) -> bool:
    bad_fragments = ("example.", "sentry.", "wixpress.", "schema.", "domain.com", "yourcompany")
    if any(fragment in email for fragment in bad_fragments):
        return False
    local = email.split("@", 1)[0]
    email_domain = email.split("@", 1)[1]
    if local in REJECT_LOCALS:
        return False
    return bool(domain and email_domain == domain)


def _possible_emails(domain: str) -> list[str]:
    return [f"{alias}@{domain}" for alias in COMMON_ALIASES]


def main():
    parser = argparse.ArgumentParser(description="Discover possible company emails.")
    parser.add_argument("--companies", type=Path, default=DEFAULT_COMPANIES_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_CONTACTS_PATH)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--company", default="")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    if args.company:
        contacts = load_contacts(args.output)
        contacts[args.company] = asdict(discover_company_contact(args.company))
        save_contacts(contacts, args.output)
        print(json.dumps(contacts[args.company], indent=2))
        return

    output = discover_contacts(args.limit, args.companies, args.output, refresh=args.refresh)
    print(f"Wrote contact dictionary to {output}")


if __name__ == "__main__":
    main()
