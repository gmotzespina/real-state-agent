"""Unit tests for Real Estate tools and agent configuration."""

from unittest.mock import patch

import httpx
import pytest

from app.agent import (
    init_session_and_user_state,
    property_researcher,
    root_agent,
    valuation_strategist,
)
from app.tools import fetch_listing_page, query_property_price_register


def test_agent_hierarchy():
    """Verify multi-agent coordinator and specialist configuration."""
    assert root_agent.name == "root_agent"
    assert len(root_agent.sub_agents) == 2
    subagent_names = [sub.name for sub in root_agent.sub_agents]
    assert "property_researcher" in subagent_names
    assert "valuation_strategist" in subagent_names
    assert property_researcher.name == "property_researcher"
    assert valuation_strategist.name == "valuation_strategist"


def test_invalid_listing_url():
    """Verify tool rejects invalid URLs cleanly without crashing."""
    result = fetch_listing_page("ftp://invalid-url.com")
    assert result["status"] == "error"
    assert "Invalid URL" in result["message"]


def test_empty_address_query():
    """Verify PPR query handles empty input gracefully."""
    result = query_property_price_register("")
    assert result["status"] == "error"


def test_ppr_html_parsing():
    """Verify PPR parsing correctly extracts dates, prices, and addresses."""
    mock_html = (
        "<html><script>"
        "var dataSearchResults = [["
        "'28/10/2021','€345,000.00',"
        "'<a href=\"/link\">65 SHELBOURNE VILLAGE, RINGSEND RD, DUBLIN 4, Dublin</a>'"
        "]];"
        "</script></html>"
    )
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = httpx.Response(
            200, text=mock_html, request=httpx.Request("GET", "https://mock")
        )
        result = query_property_price_register("D04HV00")
        assert result["status"] == "success"
        assert result["count"] == 1
        assert result["transactions"][0]["date"] == "28/10/2021"
        assert result["transactions"][0]["price_eur"] == 345000.0
        assert "65 SHELBOURNE VILLAGE" in result["transactions"][0]["address"]


def test_ppr_rate_limit_handling():
    """Verify PPR tool handles WAF bot challenges gracefully."""
    mock_challenge_html = (
        "<html><script>window['bobcmn'] = '/TSPD/3000';</script></html>"
    )
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = httpx.Response(
            200, text=mock_challenge_html, request=httpx.Request("GET", "https://mock")
        )
        result = query_property_price_register("D04HV00")
        assert result["status"] == "error"
        assert "bot protection" in result["message"]


@pytest.mark.asyncio
async def test_session_and_user_state_callback():
    """Verify callback initializes user-scoped and session-scoped state."""

    class DummyContext:
        def __init__(self):
            self.state = {}

    ctx = DummyContext()
    await init_session_and_user_state(ctx)  # type: ignore[arg-type]
    assert "user:buyer_profile" in ctx.state
    assert ctx.state["user:buyer_profile"]["target_counties"] == ["Dublin"]
    assert "session:analyzed_properties" in ctx.state


def test_tool_context_state_capture():
    """Verify tools populate session state when ToolContext is passed."""

    class DummyToolContext:
        def __init__(self):
            self.state = {}

    ctx = DummyToolContext()
    mock_html = (
        "<html><script>"
        "var dataSearchResults = [["
        "'28/10/2021','€345,000.00',"
        "'<a href=\"/link\">65 SHELBOURNE VILLAGE, RINGSEND RD, DUBLIN 4, Dublin</a>'"
        "]];"
        "</script></html>"
    )
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = httpx.Response(
            200, text=mock_html, request=httpx.Request("GET", "https://mock")
        )
        res = query_property_price_register("D04HV00", tool_context=ctx)  # type: ignore[arg-type]
        assert res["status"] == "success"
        assert "session:last_ppr_comps" in ctx.state
        assert len(ctx.state["session:last_ppr_comps"]) == 1
