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

"""Unit tests for Memory Bank configuration and reviewed property JSON memory storage."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from app.agent import generate_memories_callback, root_agent
from app.app_utils.memory_config import memory_bank_config
from app.property_memory import (
    list_reviewed_properties_memories,
    record_property_review_memory,
    save_reviewed_property_record,
)


def test_memory_bank_config_structure():
    """Validates that Memory Bank configuration has managed topics and real estate custom topics."""
    assert memory_bank_config is not None
    assert len(memory_bank_config.customization_configs) > 0

    topics = memory_bank_config.customization_configs[0].memory_topics or []
    topic_labels = []
    for t in topics:
        if t.managed_memory_topic:
            topic_labels.append(t.managed_memory_topic.managed_topic_enum.value)
        elif t.custom_memory_topic:
            topic_labels.append(t.custom_memory_topic.label)

    assert "USER_PERSONAL_INFO" in topic_labels
    assert "USER_PREFERENCES" in topic_labels
    assert "EXPLICIT_INSTRUCTIONS" in topic_labels
    assert "PROPERTY_PREFERENCES_AND_REVIEWED_HOMES" in topic_labels


def test_save_reviewed_property_record_creates_json(tmp_path, monkeypatch):
    """Validates that saving a property creates a valid structured JSON file and updates index."""
    test_dir = tmp_path / "memories" / "reviewed_properties"
    monkeypatch.setattr("app.property_memory.MEMORIES_DIR", test_dir)

    prop_data = {
        "address": "45 Grand Canal Dock, Dublin 2",
        "area": "Grand Canal Dock",
        "county": "Dublin",
        "eircode": "D02XY99",
        "asking_price_eur": 525000,
        "size_sqm": 78.5,
        "bedrooms": 2,
        "bathrooms": 2,
        "property_type": "apartment",
        "ber_rating": "A3",
        "url": "https://www.daft.ie/for-sale/apartment-45-grand-canal-dock-dublin-2",
        "notes": "Spacious waterfront apartment for tech professional buyer",
    }

    result = save_reviewed_property_record(prop_data)
    assert result["status"] == "success"
    assert result["property_id"].startswith("d02xy99")

    json_file = test_dir / f"{result['property_id']}.json"
    assert json_file.exists()

    with open(json_file, encoding="utf-8") as f:
        saved_content = json.load(f)

    assert saved_content["address"] == "45 Grand Canal Dock, Dublin 2"
    assert saved_content["asking_price_eur"] == 525000
    assert saved_content["size_sqm"] == 78.5
    assert saved_content["bedrooms"] == 2
    assert saved_content["eircode"] == "D02XY99"
    assert saved_content["ber_rating"] == "A3"

    # Check index.json
    index_file = test_dir / "index.json"
    assert index_file.exists()
    with open(index_file, encoding="utf-8") as f:
        index_content = json.load(f)
    assert len(index_content["properties"]) == 1
    assert index_content["properties"][0]["property_id"] == result["property_id"]


def test_record_property_review_memory_tool(tmp_path, monkeypatch):
    """Validates tool execution for record_property_review_memory."""
    test_dir = tmp_path / "memories" / "reviewed_properties"
    monkeypatch.setattr("app.property_memory.MEMORIES_DIR", test_dir)

    res = record_property_review_memory(
        address="10 Sandymount Green, Dublin 4",
        asking_price_eur=875000,
        area="Sandymount",
        bedrooms=3,
        bathrooms=2,
        size_sqm=125.0,
        property_type="terraced house",
        eircode="D04E8P2",
        ber_rating="B2",
        notes="Victorian redbrick close to the Dart station",
    )

    assert res["status"] == "success"
    assert "d04e8p2" in res["property_id"]

    # Verify query tool
    listed = list_reviewed_properties_memories()
    assert listed["status"] == "success"
    assert listed["count"] == 1
    assert listed["properties"][0]["area"] == "Sandymount"


def test_root_agent_has_memory_tools_and_callback():
    """Validates that root_agent is wired with PreloadMemoryTool and memory callbacks."""
    tool_types = [type(t) for t in root_agent.tools]
    assert PreloadMemoryTool in tool_types
    assert root_agent.after_agent_callback == generate_memories_callback


@pytest.mark.asyncio
async def test_generate_memories_callback_invokes_add_session():
    """Validates that generate_memories_callback delegates to callback_context."""
    mock_context = MagicMock()
    mock_context.add_session_to_memory = AsyncMock()

    await generate_memories_callback(mock_context)
    mock_context.add_session_to_memory.assert_awaited_once()
