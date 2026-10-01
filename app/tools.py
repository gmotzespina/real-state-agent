"""Custom tools for Real Estate Listing Extraction and Irish Property Price Register (PPR) analysis."""

import json
import re
import time
import urllib.parse
from typing import Any

import httpx
from bs4 import BeautifulSoup
from google.adk.tools import ToolContext
from opentelemetry import trace

from app.app_utils import telemetry
from app.property_memory import (
    list_reviewed_properties_memories,
    record_property_review_memory,
    save_reviewed_property_record,
)

__all__ = [
    "fetch_listing_page",
    "list_reviewed_properties_memories",
    "query_property_price_register",
    "record_property_review_memory",
    "save_reviewed_property_record",
]


def fetch_listing_page(
    url: str, tool_context: ToolContext | None = None
) -> dict[str, Any]:
    """Fetches a real estate property listing page and extracts its property details.

    Use this tool to extract property details from a house listing URL (such as Daft.ie,
    MyHome.ie, or other estate agent websites). It extracts the property title, description,
    address, asking price, bedrooms, bathrooms, property type, and Eircode if present.

    Args:
        url: The web URL of the property listing (must start with http:// or https://).

    Returns:
        A dictionary containing:
        - status: "success" or "error"
        - url: The requested URL
        - title: Webpage title or property headline
        - meta_description: Extracted meta description
        - asking_price: Stated asking price if detectable
        - address: Estimated address or location
        - eircode: Detected Eircode (e.g. D04HV00) if found
        - bedrooms: Detected number of bedrooms
        - property_type: Detected property type (e.g. apartment, terraced house, semi-detached)
        - text_content: Cleaned readable text of the listing
    """
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.set_attribute("real_estate.listing.url", url)

    if not url.startswith("http://") and not url.startswith("https://"):
        telemetry.listing_fetch_counter.add(1, {"status": "error_invalid_url"})
        return {
            "status": "error",
            "message": "Invalid URL format. URL must start with http:// or https://",
        }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IE,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        with httpx.Client(
            headers=headers, follow_redirects=True, timeout=20.0
        ) as client:
            resp = client.get(url)

        if resp.status_code != 200:
            telemetry.listing_fetch_counter.add(
                1, {"status": f"http_{resp.status_code}"}
            )
            return {
                "status": "error",
                "status_code": resp.status_code,
                "message": f"Failed to fetch listing URL: HTTP status {resp.status_code}",
                "url": url,
            }

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        # Strip scripts and styles
        for tag in soup(
            ["script", "style", "noscript", "svg", "header", "footer", "nav"]
        ):
            if tag.name != "script" or tag.get("type") != "application/ld+json":
                tag.decompose()

        title = soup.title.get_text(strip=True) if soup.title else ""
        meta_desc = ""
        meta_desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
            "meta", attrs={"property": "og:description"}
        )
        if meta_desc_tag and meta_desc_tag.get("content"):
            meta_desc = meta_desc_tag["content"].strip()

        # Check JSON-LD for rich structured real estate schemas
        json_ld_data = []
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            if script.string:
                try:
                    data = json.loads(script.string)
                    json_ld_data.append(data)
                except Exception:
                    pass

        # Extract text content
        body_text = soup.get_text(separator=" ", strip=True)
        # Collapse whitespace
        clean_text = re.sub(r"\s+", " ", body_text)

        # Detect Eircode (format: A65 F4E2, D04 HV00, etc.)
        eircode_match = re.search(
            r"\b([AC-FHKNPRTV-Y]\d{2})\s?([0-9AC-FHKNPRTV-Y]{4})\b",
            clean_text,
            re.IGNORECASE,
        )
        detected_eircode = None
        if eircode_match:
            detected_eircode = (
                f"{eircode_match.group(1).upper()}{eircode_match.group(2).upper()}"
            )

        # Detect price (e.g. €750,000 or €750k or EUR 750,000)
        price_match = re.search(
            r"(?:€|EUR|\bEUR\b)\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{2})?|[0-9]{2,3}(?:,[0-9]{3})*)",
            clean_text,
        )
        asking_price = price_match.group(0).strip() if price_match else None

        # Detect beds
        beds_match = re.search(
            r"\b(\d+)\s*(?:bed|bedroom|bed\s+rooms)\b", clean_text, re.IGNORECASE
        )
        beds = beds_match.group(1) if beds_match else None

        result = {
            "status": "success",
            "url": url,
            "title": title,
            "meta_description": meta_desc,
            "detected_eircode": detected_eircode,
            "detected_asking_price": asking_price,
            "detected_beds": beds,
            "json_ld_metadata": json_ld_data[:3] if json_ld_data else None,
            "text_excerpt": clean_text[:3500],
        }

        if tool_context and hasattr(tool_context, "state"):
            tool_context.state["session:current_listing"] = {
                "url": url,
                "title": title,
                "asking_price": asking_price,
                "eircode": detected_eircode,
            }
            analyzed = tool_context.state.get("session:analyzed_properties", [])
            if title and title not in analyzed:
                analyzed.append(title)
                tool_context.state["session:analyzed_properties"] = analyzed

        # Automatically store structured property JSON memory
        try:
            prop_type = "residential"
            lower_title = (title or "").lower()
            if "apartment" in lower_title or "flat" in lower_title:
                prop_type = "apartment"
            elif "semi-detached" in lower_title:
                prop_type = "semi-detached"
            elif "detached" in lower_title:
                prop_type = "detached"
            elif "terraced" in lower_title or "townhouse" in lower_title:
                prop_type = "terraced"

            prop_memory_data = {
                "url": url,
                "title": title,
                "address": title or url,
                "eircode": detected_eircode,
                "asking_price": asking_price,
                "bedrooms": int(beds) if beds and beds.isdigit() else None,
                "property_type": prop_type,
            }
            save_reviewed_property_record(prop_memory_data, tool_context=tool_context)
        except Exception:
            pass

        telemetry.listing_fetch_counter.add(1, {"status": "success"})
        if current_span and current_span.is_recording():
            if asking_price:
                current_span.set_attribute(
                    "real_estate.listing.asking_price", str(asking_price)
                )
            if detected_eircode:
                current_span.set_attribute(
                    "real_estate.listing.eircode", str(detected_eircode)
                )

        return result

    except Exception as exc:
        telemetry.listing_fetch_counter.add(1, {"status": "error_exception"})
        return {
            "status": "error",
            "url": url,
            "message": f"Error fetching or parsing URL: {exc!s}",
        }


def query_property_price_register(
    address: str,
    county: str = "Dublin",
    year: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Queries the Irish Property Price Register (PPR) for historical sale transactions.

    Use this tool to find real historical sold prices of properties in Ireland.
    You can search by:
    1. Exact Eircode (e.g. 'D04HV00') to check if the specific property was previously sold.
    2. Street or development name (e.g. 'Shelbourne Village', 'Morehampton Road') to find comparable sales nearby.
    3. Postal district or area (e.g. 'Dublin 4', 'Ballsbridge') with County='Dublin'.

    Args:
        address: The address, street name, housing development, or Eircode to search for.
        county: The Irish county (default is 'Dublin'). Options include Dublin, Cork, Galway, etc.
        year: Optional 4-digit year filter (e.g. '2025', '2026'). Leave empty for all years.

    Returns:
        A dictionary containing:
        - status: "success", "not_found", or "error"
        - query: The address string searched
        - county: The county searched
        - count: Total number of matching transactions found
        - transactions: List of transaction records with:
            - date: Date of sale (DD/MM/YYYY)
            - price_raw: Original formatted price string (e.g. '€450,000.00')
            - price_eur: Numerical price in Euros (e.g. 450000.0)
            - address: Sold property address including postal code/Eircode
    """
    address_clean = address.strip()
    if not address_clean:
        return {"status": "error", "message": "Search address cannot be empty."}

    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.set_attribute("real_estate.ppr.query", address)
        current_span.set_attribute("real_estate.ppr.county", county)

    # Detect if search term is an Eircode
    eircode_match = re.search(
        r"\b([AC-FHKNPRTV-Y]\d{2})\s?([0-9AC-FHKNPRTV-Y]{4})\b",
        address_clean,
        re.IGNORECASE,
    )

    if eircode_match:
        code = f"{eircode_match.group(1).upper()}{eircode_match.group(2).upper()}"
        query_str = f"([address]=*{code}* OR [eircode]={code})"
        addr_param = code
    else:
        query_str = f"([address]=*{address_clean}*)"
        addr_param = address_clean

    encoded_query = urllib.parse.quote(query_str)
    encoded_addr = urllib.parse.quote(addr_param)
    url = (
        f"https://www.propertypriceregister.ie/website/npsra/PPR/npsra-ppr.nsf/PPR-By-Date"
        f"&Start=1&Query={encoded_query}&County={urllib.parse.quote(county)}&Year={year}"
        f"&StartMonth=&EndMonth=&Address={encoded_addr}"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    start_time = time.perf_counter()
    try:
        with httpx.Client(
            headers=headers, follow_redirects=True, timeout=20.0
        ) as client:
            resp = client.get(url)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        telemetry.ppr_query_duration_ms.record(
            elapsed_ms, {"county": county, "status": str(resp.status_code)}
        )

        if resp.status_code != 200:
            return {
                "status": "error",
                "message": f"PPR returned HTTP status {resp.status_code}",
                "query": address,
            }

        match = re.search(
            r"var\s+dataSearchResults\s*=\s*(\[.*?\]);", resp.text, re.DOTALL
        )
        if not match:
            if "bobcmn" in resp.text or "TSPD" in resp.text:
                return {
                    "status": "error",
                    "query": address,
                    "county": county,
                    "message": "PPR request rate-limited or challenged by bot protection. Please retry shortly.",
                }
            return {
                "status": "not_found",
                "query": address,
                "county": county,
                "count": 0,
                "transactions": [],
                "message": f"No records found for query '{address}'. Consider broadening the query to street name or area.",
            }

        raw_list = match.group(1)
        matches = re.findall(
            r"\[\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*\]", raw_list
        )

        transactions = []
        for date_str, price_str, raw_addr in matches:
            clean_addr = re.sub(r"<.*?>", "", raw_addr).strip()
            num_str = re.sub(r"[^\d.]", "", price_str)
            price_val = float(num_str) if num_str else None
            transactions.append(
                {
                    "date": date_str,
                    "price_raw": price_str,
                    "price_eur": price_val,
                    "address": clean_addr,
                }
            )

        if not transactions:
            telemetry.ppr_comps_retrieved.record(0, {"county": county})
            if current_span and current_span.is_recording():
                current_span.set_attribute("real_estate.ppr.comps_count", 0)
            return {
                "status": "not_found",
                "query": address,
                "county": county,
                "count": 0,
                "transactions": [],
                "message": f"No transactions returned for query '{address}'.",
            }

        telemetry.ppr_comps_retrieved.record(len(transactions), {"county": county})
        if current_span and current_span.is_recording():
            current_span.set_attribute("real_estate.ppr.comps_count", len(transactions))

        result = {
            "status": "success",
            "query": address,
            "county": county,
            "count": len(transactions),
            "transactions": transactions[:25],  # Top 25 most recent sales
        }

        if tool_context and hasattr(tool_context, "state") and transactions:
            tool_context.state["session:last_ppr_comps"] = transactions[:10]

        return result

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        telemetry.ppr_query_duration_ms.record(
            elapsed_ms, {"county": county, "status": "exception"}
        )
        return {
            "status": "error",
            "message": f"Error querying Property Price Register: {exc!s}",
            "query": address,
        }
