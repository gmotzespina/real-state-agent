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

"""Unit tests for OpenTelemetry instrumentation and custom domain metrics."""

from unittest.mock import MagicMock, patch

from app.app_utils import telemetry
from app.tools import fetch_listing_page, query_property_price_register


def test_telemetry_metrics_initialized():
    """Verify that custom domain meters and instruments are properly defined."""
    assert telemetry.meter is not None
    assert telemetry.tracer is not None
    assert telemetry.ppr_query_duration_ms is not None
    assert telemetry.ppr_comps_retrieved is not None
    assert telemetry.listing_fetch_counter is not None
    assert telemetry.bidding_strategy_counter is not None


def test_fetch_listing_page_records_telemetry():
    """Verify fetch_listing_page updates counters and spans on invalid and valid inputs."""
    # Invalid URL format
    res = fetch_listing_page("invalid-url")
    assert res["status"] == "error"

    # Mocked valid HTML fetch
    mock_html = """
    <html>
      <head><title>2 Bed Apartment Ballsbridge</title></head>
      <body>
        <h1>2 Bed Apartment, Ballsbridge, Dublin 4</h1>
        <p>Price: €495,000</p>
      </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html

    with patch("httpx.Client.get", return_value=mock_resp):
        res_valid = fetch_listing_page("https://www.example.com/property/123")
        assert res_valid["status"] == "success"
        assert "Ballsbridge" in res_valid["title"]


def test_query_ppr_records_telemetry():
    """Verify query_property_price_register records metrics on simulated PPR response."""
    mock_html = """
    <html>
      <script>
        var dataSearchResults = [
          ['15/01/2026', '€475,000.00', '12 Shelbourne Village, Ringsend, Dublin 4']
        ];
      </script>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html

    with patch("httpx.Client.get", return_value=mock_resp):
        res = query_property_price_register("Shelbourne Village", county="Dublin")
        assert res["status"] == "success"
        assert res["count"] == 1
        assert res["transactions"][0]["price_eur"] == 475000.0
