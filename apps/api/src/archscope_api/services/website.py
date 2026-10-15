"""Read a client's public homepage for the business analysis: its title,
description, visible text and the technology seen in its source (HubSpot,
Shopify, a booking widget…), condensed into a short excerpt.

The URL comes from a user, so fetching it is guarded: http(s) only, the
host must resolve to public internet addresses (never localhost or a
private network — that would let the server be used to probe internal
systems), redirects are re-checked, and time and size are capped. A site
that can't be read is reported, never fatal to the draft.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

TIMEOUT_SECONDS = 8.0
MAX_BYTES = 1_500_000
MAX_REDIRECTS = 3
MAX_TEXT_CHARS = 5000
USER_AGENT = "Mozilla/5.0 (compatible; ArchitectureScope/1.0; discovery research)"

# Page-source fingerprints of tools worth knowing about before a HubSpot engagement.
TECH_SIGNATURES = {
    "HubSpot": ("js.hs-scripts.com", "js.hsforms.net", "hs-banner.com", "hubspot"),
    "Salesforce": ("salesforce.com", "force.com", "pardot"),
    "Marketo": ("marketo", "munchkin"),
    "Mailchimp": ("mailchimp", "list-manage.com"),
    "Klaviyo": ("klaviyo",),
    "Shopify": ("cdn.shopify.com", "shopify"),
    "WooCommerce": ("woocommerce",),
    "WordPress": ("wp-content", "wp-includes"),
    "Wix": ("wix.com", "wixstatic"),
    "Squarespace": ("squarespace",),
    "Webflow": ("webflow",),
    "Intercom": ("intercom",),
    "Drift": ("drift.com", "js.driftt.com"),
    "Zendesk": ("zendesk", "zdassets"),
    "Calendly": ("calendly",),
    "Google Analytics / Tag Manager": ("googletagmanager.com", "google-analytics.com", "gtag("),
    "Meta Pixel": ("connect.facebook.net", "fbq("),
    "LinkedIn Insight": ("snap.licdn.com",),
    "Stripe": ("js.stripe.com",),
}


class WebsiteError(Exception):
    """The website couldn't be read; the message is safe to show."""


@dataclass
class WebsiteSnapshot:
    url: str
    title: str = ""
    description: str = ""
    headings: list[str] = field(default_factory=list)
    text: str = ""
    technologies: list[str] = field(default_factory=list)

    def excerpt(self) -> str:
        """What the model receives about the website."""
        parts = [f"URL: {self.url}"]
        if self.title:
            parts.append(f"Title: {self.title}")
        if self.description:
            parts.append(f"Description: {self.description}")
        if self.technologies:
            parts.append("Technology seen in the page source: " + ", ".join(self.technologies))
        if self.headings:
            parts.append("Headings: " + " | ".join(self.headings[:20]))
        if self.text:
            parts.append("Page text: " + self.text)
        return "\n".join(parts)


def normalize_url(raw: str) -> str:
    """``acme.com`` → ``https://acme.com``; refuses anything but http(s)."""
    url = raw.strip()
    if not url:
        raise WebsiteError("No website given.")
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise WebsiteError("Enter a web address like acme.com or https://acme.com.")
    return url


def _check_public(host: str) -> None:
    """Refuse hosts that are, or resolve to, non-public addresses."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise WebsiteError(f"The website {host} couldn't be found.") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise WebsiteError("That address isn't a public website.")


class _TextExtractor(HTMLParser):
    _SKIP = frozenset({"script", "style", "noscript", "svg", "template", "iframe"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.headings: list[str] = []
        self.chunks: list[str] = []
        self._skip_depth = 0
        self._in_title = False
        self._heading: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in ("h1", "h2", "h3"):
            self._heading = []
        elif tag == "meta":
            a = {k.lower(): (v or "") for k, v in attrs}
            if a.get("name", "").lower() == "description" or a.get("property", "").lower() == "og:description":
                self.description = self.description or a.get("content", "").strip()

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in ("h1", "h2", "h3") and self._heading is not None:
            heading = " ".join("".join(self._heading).split())
            if heading and heading not in self.headings:
                self.headings.append(heading)
            self._heading = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
            return
        if self._heading is not None:
            self._heading.append(data)
        text = " ".join(data.split())
        if len(text) > 1:
            self.chunks.append(text)


def parse_homepage(url: str, html: str) -> WebsiteSnapshot:
    """The useful parts of a homepage's HTML."""
    extractor = _TextExtractor()
    extractor.feed(html)
    seen: set[str] = set()
    lines = []
    for chunk in extractor.chunks:
        if chunk not in seen:
            seen.add(chunk)
            lines.append(chunk)
    text = re.sub(r"\s+", " ", " · ".join(lines))[:MAX_TEXT_CHARS]
    source = html.lower()
    tech = [name for name, marks in TECH_SIGNATURES.items() if any(m in source for m in marks)]
    return WebsiteSnapshot(
        url=url,
        title=" ".join(extractor.title.split())[:200],
        description=extractor.description[:500],
        headings=extractor.headings,
        text=text,
        technologies=tech,
    )


def read_homepage(raw_url: str, *, client: httpx.Client | None = None, check_host: bool = True) -> WebsiteSnapshot:
    """Fetch and condense a public homepage. Raises :class:`WebsiteError`."""
    url = normalize_url(raw_url)
    own = client is None
    http = client or httpx.Client(timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
    try:
        for _ in range(MAX_REDIRECTS + 1):
            host = urlsplit(url).hostname or ""
            if check_host:
                _check_public(host)
            try:
                with http.stream("GET", url) as response:
                    if response.is_redirect and response.headers.get("location"):
                        url = urljoin(url, response.headers["location"])
                        if urlsplit(url).scheme not in ("http", "https"):
                            raise WebsiteError("The website redirected somewhere that can't be read.")
                        continue
                    if response.status_code >= 400:
                        raise WebsiteError(f"The website answered with an error ({response.status_code}).")
                    if "html" not in response.headers.get("content-type", "html"):
                        raise WebsiteError("The address isn't a web page.")
                    body = b""
                    for chunk in response.iter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            break
                    return parse_homepage(url, body.decode(response.encoding or "utf-8", errors="replace"))
            except httpx.TimeoutException as exc:
                raise WebsiteError("The website took too long to answer.") from exc
            except httpx.HTTPError as exc:
                raise WebsiteError("The website couldn't be reached.") from exc
        raise WebsiteError("The website redirected too many times.")
    finally:
        if own:
            http.close()
