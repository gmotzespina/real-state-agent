# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Memory store for reviewed property JSON files and user search criteria.

Persists structured metadata (size, asking price, area, bedrooms, BER, Eircode,
valuation notes) into JSON files under `memories/reviewed_properties/` and maintains
an index so the agent can learn and recall the types of properties the user explores.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)

# Base directory for storing reviewed property memory JSON files
MEMORIES_DIR = Path("memories") / "reviewed_properties"


def _sanitize_slug(text: str) -> str:
    """Creates a filesystem-friendly slug for a property address or ID."""
    clean = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text.strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean[:80] or "property"


def save_reviewed_property_record(
    property_data: dict[str, Any],
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Saves a structured property metadata JSON file to the memory repository.

    Args:
        property_data: Dictionary containing property metadata.
        tool_context: Optional ADK ToolContext for session state and artifact storage.

    Returns:
        A dictionary containing the save status, file path, and property ID.
    """
    MEMORIES_DIR.mkdir(parents=True, exist_ok=True)

    raw_address = (
        property_data.get("address") or property_data.get("title") or "Unnamed Property"
    )
    eircode = property_data.get("eircode") or ""
    area = property_data.get("area") or property_data.get("county") or "Ireland"
    asking_price = property_data.get("asking_price_eur") or property_data.get(
        "asking_price"
    )

    # Generate deterministic identifier
    slug_base = f"{eircode}_{raw_address}" if eircode else raw_address
    property_id = _sanitize_slug(slug_base)

    timestamp = property_data.get("review_timestamp") or datetime.now(UTC).isoformat()

    record: dict[str, Any] = {
        "property_id": property_id,
        "address": raw_address,
        "eircode": eircode,
        "area": area,
        "county": property_data.get("county", "Dublin"),
        "asking_price_eur": asking_price,
        "size_sqm": property_data.get("size_sqm"),
        "size_sqft": property_data.get("size_sqft"),
        "bedrooms": property_data.get("bedrooms"),
        "bathrooms": property_data.get("bathrooms"),
        "property_type": property_data.get("property_type", "residential"),
        "ber_rating": property_data.get("ber_rating"),
        "url": property_data.get("url"),
        "review_timestamp": timestamp,
        "valuation_estimate": property_data.get("valuation_estimate"),
        "bidding_strategy": property_data.get("bidding_strategy"),
        "user_notes": property_data.get("notes") or property_data.get("user_notes"),
    }

    # Write JSON file
    file_path = MEMORIES_DIR / f"{property_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    # Update index.json
    index_path = MEMORIES_DIR / "index.json"
    index_data: dict[str, Any] = {"properties": [], "last_updated": timestamp}
    if index_path.exists():
        try:
            with open(index_path, encoding="utf-8") as f:
                index_data = json.load(f)
        except Exception:
            index_data = {"properties": [], "last_updated": timestamp}

    # Deduplicate in index
    existing = [
        p
        for p in index_data.get("properties", [])
        if p.get("property_id") != property_id
    ]
    summary_entry = {
        "property_id": property_id,
        "address": raw_address,
        "eircode": eircode,
        "area": area,
        "asking_price_eur": asking_price,
        "bedrooms": record["bedrooms"],
        "size_sqm": record["size_sqm"],
        "property_type": record["property_type"],
        "reviewed_at": timestamp,
        "file": str(file_path),
    }
    existing.append(summary_entry)
    index_data["properties"] = existing
    index_data["last_updated"] = timestamp

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)

    # Store in session state if tool context is available
    if tool_context and hasattr(tool_context, "state"):
        tool_context.state["session:last_saved_property_memory"] = property_id
        reviewed_list = tool_context.state.get(
            "session:reviewed_properties_history", []
        )
        if property_id not in reviewed_list:
            reviewed_list.append(property_id)
            tool_context.state["session:reviewed_properties_history"] = reviewed_list

    return {
        "status": "success",
        "property_id": property_id,
        "file_path": str(file_path),
        "record": record,
    }


def record_property_review_memory(
    address: str,
    asking_price_eur: float | None = None,
    area: str = "",
    bedrooms: int | None = None,
    bathrooms: int | None = None,
    size_sqm: float | None = None,
    property_type: str = "residential",
    eircode: str = "",
    ber_rating: str = "",
    notes: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Stores a structured JSON memory file for a property the user asked to review.

    Use this tool whenever the user discusses or requests an analysis of a specific real estate
    property. This persists the property metadata (address, asking price, area, size, bedrooms,
    and notes) so the agent remembers what types of properties the user is interested in across chats.

    Args:
        address: Full address or headline of the property.
        asking_price_eur: Stated asking price in Euros (€).
        area: Locality, neighborhood, or postal district (e.g. 'Ballsbridge', 'Dublin 4').
        bedrooms: Number of bedrooms (e.g. 2).
        bathrooms: Number of bathrooms (e.g. 1).
        size_sqm: Floor area in square meters.
        property_type: Type of property (e.g. 'apartment', 'terraced', 'semi-detached', 'detached').
        eircode: Irish Eircode if known (e.g. 'D04RY76').
        ber_rating: Building Energy Rating (e.g. 'B2', 'C1').
        notes: User search preferences, budget constraints, or valuation highlights.

    Returns:
        A dictionary confirming memory persistence with file path and property ID.
    """
    prop_data = {
        "address": address,
        "asking_price_eur": asking_price_eur,
        "area": area,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "size_sqm": size_sqm,
        "property_type": property_type,
        "eircode": eircode,
        "ber_rating": ber_rating,
        "notes": notes,
    }
    return save_reviewed_property_record(prop_data, tool_context=tool_context)


def list_reviewed_properties_memories(
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Retrieves all stored property review memories and past user inquiries.

    Use this tool to see the full list of properties the user has asked to review across past chats,
    including their areas, sizes, asking prices, and bedrooms.

    Returns:
        A dictionary containing the list of reviewed property records.
    """
    index_path = MEMORIES_DIR / "index.json"
    if not index_path.exists():
        return {
            "status": "empty",
            "count": 0,
            "properties": [],
            "message": "No property memories have been recorded yet.",
        }

    try:
        with open(index_path, encoding="utf-8") as f:
            index_data = json.load(f)
        return {
            "status": "success",
            "count": len(index_data.get("properties", [])),
            "properties": index_data.get("properties", []),
            "last_updated": index_data.get("last_updated"),
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed to read property memory index: {exc!s}",
        }
