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

"""OpenTelemetry instrumentation, outbound HTTP tracing, and custom domain metrics."""

import logging

from opentelemetry import metrics, trace
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

logger = logging.getLogger(__name__)

# Initialize outbound HTTP client instrumentation for granular network spans in Cloud Trace
try:
    _httpx_inst = HTTPXClientInstrumentor()
    if not _httpx_inst.is_instrumented_by_opentelemetry:
        _httpx_inst.instrument()

    _aiohttp_inst = AioHttpClientInstrumentor()
    if not _aiohttp_inst.is_instrumented_by_opentelemetry:
        _aiohttp_inst.instrument()
except Exception as e:  # pragma: no cover
    logger.warning(
        "Failed to initialize OpenTelemetry HTTP client instrumentation: %s", e
    )

# Dedicated Tracer & Meter for Real Estate domain observability
tracer = trace.get_tracer("real-estate-agent.tools")
meter = metrics.get_meter("real-estate-agent.metrics")

# 1. Latency Histogram for Irish Property Price Register Lookups
ppr_query_duration_ms = meter.create_histogram(
    name="real_estate.ppr.query_duration_ms",
    description="Duration of Irish Property Price Register (PPR) HTTP queries in milliseconds",
    unit="ms",
)

# 2. Number of Comparable Transactions Retrieved
ppr_comps_retrieved = meter.create_histogram(
    name="real_estate.ppr.comps_retrieved",
    description="Number of comparable transactions retrieved per Property Price Register search",
    unit="1",
)

# 3. Property Listing Pages Fetched Counter
listing_fetch_counter = meter.create_counter(
    name="real_estate.listing.fetches_total",
    description="Total count of property listing pages fetched and parsed",
    unit="1",
)

# 4. Bidding Strategies Synthesized Counter
bidding_strategy_counter = meter.create_counter(
    name="real_estate.bidding.strategies_total",
    description="Total count of tactical bidding strategies synthesized",
    unit="1",
)
