"""Scraper for local.ch based on the public sitemap structure.

This module discovers relevant search and detail pages through the
``https://www.local.ch/sitemaps/sitemap_index.xml`` entry point and then
collects structured data for businesses that match the provided keyword
and postal codes.

The script can be invoked from the command line::

    python sitemap_scraper.py --keyword plombier --input input.txt \
        --output plombiers_geneve.csv

The input file must contain one postal code per line. The keyword is
matched against the textual content of the business detail page. The
result is written to a CSV file with the columns requested by the user:
source URL, name, address, zip code, city, telephone, email and website.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Set, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


SITEMAP_INDEX_URL = "https://www.local.ch/sitemaps/sitemap_index.xml"


def _strip_namespace(tag: str) -> str:
    """Return the tag name without the XML namespace prefix."""

    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _load_xml_document(content: bytes) -> ET.Element:
    """Load XML document handling potential byte-order marks."""

    # xml.etree cannot handle byte-order marks when parsing from bytes
    # directly, so we decode using UTF-8 and re-encode.
    text = content.decode("utf-8", errors="replace")
    return ET.fromstring(text)


def _is_local_domain(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.lower().endswith("local.ch")


def _normalise_postal_code(value: str) -> str:
    return re.sub(r"\s+", "", value).strip()


def _ensure_list(value):
    if isinstance(value, list):
        return value
    return [value]


@dataclass
class BusinessRecord:
    """Structure holding the information to be written to CSV."""

    source_url: str
    name: Optional[str] = None
    address: Optional[str] = None
    zipcode: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None

    def to_row(self) -> dict:
        return {
            "source_url": self.source_url,
            "name": self.name or "",
            "address": self.address or "",
            "zipcode": self.zipcode or "",
            "city": self.city or "",
            "phone": self.phone or "",
            "email": self.email or "",
            "website": self.website or "",
        }


class LocalChSitemapScraper:
    """Scrape business detail pages discovered via the sitemap system."""

    def __init__(
        self,
        keyword: str,
        postal_codes: Sequence[str],
        language: str = "fr",
        session: Optional[requests.Session] = None,
        logger: Optional[logging.Logger] = None,
        max_retries: int = 3,
        retry_delay: float = 1.5,
    ) -> None:
        self.keyword = keyword.lower()
        self.postal_codes: Set[str] = {
            _normalise_postal_code(code) for code in postal_codes if code
        }
        self.language = language
        self.base_url = "https://www.local.ch"
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/116.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            }
        )

        self.logger = logger or logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def fetch_bytes(self, url: str) -> Optional[bytes]:
        """Retrieve raw bytes from a URL with retry support."""

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=30)
                if response.status_code == 200:
                    return response.content
                if response.status_code == 404:
                    self.logger.debug("URL not found: %s", url)
                    return None
                self.logger.warning(
                    "Unexpected status %s while fetching %s", response.status_code, url
                )
            except requests.RequestException as exc:
                self.logger.warning("Request error for %s: %s", url, exc)

            if attempt < self.max_retries:
                time.sleep(self.retry_delay * attempt)

        self.logger.error("Failed to fetch %s after %s attempts", url, self.max_retries)
        return None

    def fetch_text(self, url: str) -> Optional[str]:
        content = self.fetch_bytes(url)
        if content is None:
            return None
        return content.decode("utf-8", errors="replace")

    # ------------------------------------------------------------------
    # Sitemap discovery
    # ------------------------------------------------------------------
    def discover_relevant_urls(self) -> tuple[Set[str], Set[str]]:
        """Return tuples of (search_page_urls, detail_page_urls)."""

        queue = [SITEMAP_INDEX_URL]
        visited: Set[str] = set()
        search_pages: Set[str] = set()
        detail_pages: Set[str] = set()

        while queue:
            sitemap_url = queue.pop(0)
            if sitemap_url in visited:
                continue
            visited.add(sitemap_url)

            if not _is_local_domain(sitemap_url):
                continue

            self.logger.debug("Fetching sitemap: %s", sitemap_url)
            content = self.fetch_bytes(sitemap_url)
            if content is None:
                continue

            if sitemap_url.endswith(".gz"):
                try:
                    content = gzip.decompress(content)
                except OSError:
                    self.logger.warning("Unable to decompress sitemap: %s", sitemap_url)
                    continue

            try:
                root = _load_xml_document(content)
            except ET.ParseError as exc:
                self.logger.warning("Failed to parse sitemap %s: %s", sitemap_url, exc)
                continue

            tag = _strip_namespace(root.tag)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            if tag == "sitemapindex":
                for loc_node in root.findall("sm:sitemap/sm:loc", ns):
                    loc_text = (loc_node.text or "").strip()
                    if loc_text:
                        queue.append(loc_text)
                continue

            if tag != "urlset":
                continue

            for loc_node in root.findall("sm:url/sm:loc", ns):
                loc_text = (loc_node.text or "").strip()
                if not loc_text:
                    continue

                lowered = loc_text.lower()
                if not _is_local_domain(loc_text):
                    continue

                if self._is_search_page(loc_text, lowered):
                    search_pages.add(loc_text)
                elif self._is_detail_page(loc_text, lowered):
                    detail_pages.add(loc_text)

        if not search_pages:
            self.logger.warning(
                "No search pages discovered via sitemap. Fallback to detail pages only."
            )
        return search_pages, detail_pages

    def _is_search_page(self, url: str, lowered: str) -> bool:
        parsed = urlparse(url)
        if "/q" not in parsed.path and "search" not in parsed.path:
            return False

        query = parse_qs(parsed.query)
        if query:
            if self.keyword and all(self.keyword not in value.lower() for value in query.get("what", [])):
                keyword_present = any(
                    self.keyword in value.lower() for value in query.get("what", [])
                )
                if not keyword_present:
                    return False

            if self.postal_codes:
                for code in self.postal_codes:
                    if any(code in value for value in query.get("where", [])):
                        return True
                return any(code in lowered for code in self.postal_codes)

        return self.keyword in lowered and (
            not self.postal_codes or any(code in lowered for code in self.postal_codes)
        )

    def _is_detail_page(self, url: str, lowered: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path
        parts = [part for part in path.split("/") if part]
        if len(parts) < 3:
            return False

        # Example detail path: /fr/d/geneve/societe-xyz-abcde
        if parts[1] != "d":
            return False

        # The postal code is usually not present in the path, so we only
        # check for the keyword to avoid downloading every single listing.
        if self.keyword and self.keyword not in lowered:
            return False

        return True

    # ------------------------------------------------------------------
    # Search result parsing
    # ------------------------------------------------------------------
    def iter_search_result_pages(self, url: str) -> Iterator[Tuple[str, str]]:
        seen: Set[str] = set()
        next_url = url

        while next_url and next_url not in seen:
            seen.add(next_url)
            html = self.fetch_text(next_url)
            if not html:
                break
            yield next_url, html

            soup = BeautifulSoup(html, "html.parser")
            link_tag = soup.find("link", attrs={"rel": "next"})
            if link_tag and link_tag.get("href"):
                next_href = link_tag["href"]
                next_url = urljoin(next_url, next_href)
                continue

            next_link = soup.find("a", attrs={"rel": "next"})
            if not next_link:
                # Look for button/link containing "Suivant" in French UI.
                candidates = soup.select("a, button")
                next_link = None
                for candidate in candidates:
                    text = candidate.get_text(strip=True).lower()
                    if text in {"suivant", "next"}:
                        next_link = candidate
                        break

            if next_link and next_link.get("href"):
                next_url = urljoin(next_url, next_link.get("href"))
            else:
                next_url = None

    def extract_listing_urls(self, search_page_url: str, html: str) -> Set[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls: Set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href:
                continue
            absolute = urljoin(search_page_url, href)
            parsed = urlparse(absolute)
            path = parsed.path
            parts = [part for part in path.split("/") if part]
            if len(parts) >= 3 and parts[0] in {"fr", "de", "en", "it"} and parts[1] == "d":
                urls.add(urljoin(self.base_url, path))

        return urls

    # ------------------------------------------------------------------
    # Detail page parsing
    # ------------------------------------------------------------------
    def parse_detail_page(self, url: str) -> Optional[BusinessRecord]:
        html = self.fetch_text(url)
        if not html:
            return None

        lowered_html = html.lower()
        if self.keyword and self.keyword not in lowered_html:
            # Keyword not present anywhere in the page content.
            return None

        soup = BeautifulSoup(html, "html.parser")

        record = BusinessRecord(source_url=url)

        # Attempt to parse JSON-LD blocks that usually store structured data.
        structured_data = self._extract_structured_data(soup)
        if structured_data:
            address = structured_data.get("address") or {}
            if isinstance(address, dict):
                street = address.get("streetAddress")
                if street:
                    record.address = str(street)
                postal = address.get("postalCode")
                if postal:
                    record.zipcode = str(postal)
                locality = address.get("addressLocality")
                if locality:
                    record.city = str(locality)

            name = structured_data.get("name")
            if name:
                record.name = str(name)
            telephone = structured_data.get("telephone")
            if telephone:
                record.phone = str(telephone)
            email = structured_data.get("email")
            if email:
                record.email = str(email)
            url_value = structured_data.get("url")
            if url_value:
                record.website = str(url_value)

        if not record.name:
            title_node = soup.find("h1")
            if title_node:
                record.name = title_node.get_text(strip=True)

        if not record.address or not record.zipcode or not record.city:
            self._extract_address_from_html(soup, record)

        if not record.phone:
            record.phone = self._extract_phone_from_html(soup)

        if not record.email:
            record.email = self._extract_email_from_html(soup)

        if not record.website:
            record.website = self._extract_website_from_html(soup)

        if self.postal_codes:
            if record.zipcode:
                if _normalise_postal_code(str(record.zipcode)) not in self.postal_codes:
                    return None
            else:
                return None

        return record

    def _extract_structured_data(self, soup: BeautifulSoup) -> Optional[dict]:
        scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        for script in scripts:
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue

            for entry in _ensure_list(data):
                if not isinstance(entry, dict):
                    continue
                entry_type = entry.get("@type")
                if isinstance(entry_type, list):
                    types = {value.lower() for value in entry_type}
                elif isinstance(entry_type, str):
                    types = {entry_type.lower()}
                else:
                    types = set()

                if types & {
                    "localbusiness",
                    "professionalservice",
                    "organization",
                    "dentist",
                    "physician",
                    "store",
                }:
                    return entry
        return None

    def _extract_address_from_html(self, soup: BeautifulSoup, record: BusinessRecord) -> None:
        address_node = soup.find("address")
        if address_node:
            text = address_node.get_text(" ", strip=True)
            record.address = record.address or text
            match = re.search(r"(\d{4,5})\s+([A-Za-zÀ-ÿ\-\s]+)", text)
            if match:
                record.zipcode = record.zipcode or match.group(1)
                record.city = record.city or match.group(2).strip()

    def _extract_phone_from_html(self, soup: BeautifulSoup) -> Optional[str]:
        phone_link = soup.find("a", href=re.compile(r"^tel:"))
        if phone_link:
            return phone_link["href"].replace("tel:", "").strip()
        phone_span = soup.find(string=re.compile(r"\+?\d[\d\s\.\-]{6,}"))
        if phone_span:
            return re.sub(r"[^\d\+]", "", phone_span)
        return None

    def _extract_email_from_html(self, soup: BeautifulSoup) -> Optional[str]:
        mail_link = soup.find("a", href=re.compile(r"^mailto:"))
        if mail_link:
            return mail_link["href"].replace("mailto:", "").strip()
        return None

    def _extract_website_from_html(self, soup: BeautifulSoup) -> Optional[str]:
        website_link = soup.find("a", attrs={"data-testid": re.compile("website", re.I)})
        if website_link and website_link.get("href"):
            return website_link["href"].strip()

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if href.startswith("http") and "local.ch" not in href:
                return href
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> List[BusinessRecord]:
        search_pages, detail_pages = self.discover_relevant_urls()

        records: List[BusinessRecord] = []
        processed_detail_urls: Set[str] = set()

        for search_page in sorted(search_pages):
            self.logger.info("Scraping search results: %s", search_page)
            for page_url, html in self.iter_search_result_pages(search_page):
                listing_urls = self.extract_listing_urls(page_url, html)
                for listing_url in listing_urls:
                    detail_pages.add(listing_url)

        for detail_url in sorted(detail_pages):
            if detail_url in processed_detail_urls:
                continue
            processed_detail_urls.add(detail_url)
            self.logger.info("Scraping detail page: %s", detail_url)
            record = self.parse_detail_page(detail_url)
            if record:
                records.append(record)

        return records


def read_postal_codes(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        codes = [line.strip() for line in handle if line.strip()]

    return codes


def write_csv(path: Path, records: Iterable[BusinessRecord]) -> None:
    fieldnames = [
        "source_url",
        "name",
        "address",
        "zipcode",
        "city",
        "phone",
        "email",
        "website",
    ]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_row())


def parse_arguments(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape local.ch using the sitemap structure.")
    parser.add_argument(
        "--keyword",
        "-k",
        required=True,
        help="Keyword used to filter businesses (e.g. 'plombier').",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("input.txt"),
        help="Path to the file containing postal codes (one per line).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("local_ch_results.csv"),
        help="Destination CSV file.",
    )
    parser.add_argument(
        "--language",
        "-l",
        default="fr",
        help="Preferred local.ch language (fr, de, it, en).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging for debugging purposes.",
    )

    return parser.parse_args(argv)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_arguments(argv)
    configure_logging(args.verbose)

    try:
        postal_codes = read_postal_codes(args.input)
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        return 1

    scraper = LocalChSitemapScraper(
        keyword=args.keyword,
        postal_codes=postal_codes,
        language=args.language,
        logger=logging.getLogger("localch"),
    )

    records = scraper.run()
    if not records:
        logging.warning("No matching businesses found.")

    write_csv(args.output, records)
    logging.info("Saved %s records to %s", len(records), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
