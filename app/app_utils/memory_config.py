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

"""Memory Bank configuration for Real Estate Agent.

Defines the managed and custom memory topics extracted and persisted by
Vertex AI Memory Bank across user sessions.
"""

from vertexai._genai.types import (
    ManagedTopicEnum,
)
from vertexai._genai.types import (
    MemoryBankCustomizationConfig as CustomizationConfig,
)
from vertexai._genai.types import (
    MemoryBankCustomizationConfigMemoryTopic as MemoryTopic,
)
from vertexai._genai.types import (
    MemoryBankCustomizationConfigMemoryTopicCustomMemoryTopic as CustomMemoryTopic,
)
from vertexai._genai.types import (
    MemoryBankCustomizationConfigMemoryTopicManagedMemoryTopic as ManagedMemoryTopic,
)
from vertexai._genai.types import (
    ReasoningEngineContextSpecMemoryBankConfig as MemoryBankConfig,
)

# --- Memory Bank Configuration ---
# Configures Vertex AI Memory Bank to extract:
# 1. USER_PERSONAL_INFO: User name, location, family constraints, first-time buyer status.
# 2. USER_PREFERENCES: Preferred areas (e.g. Dublin 4, Ranelagh), property types (apartments, houses),
#    budget ceilings, size requirements, garden/parking needs.
# 3. EXPLICIT_INSTRUCTIONS: Things the user explicitly asked the agent to remember or focus on.
# 4. KEY_CONVERSATION_DETAILS: Milestones, properties reviewed, bidding decisions.
# 5. PROPERTY_PREFERENCES_AND_REVIEWED_HOMES (Custom): Structured facts on property criteria,
#    searched locations, floor areas, asking prices, and reviewed listings.
memory_bank_config = MemoryBankConfig(
    customization_configs=[
        CustomizationConfig(
            memory_topics=[
                MemoryTopic(
                    managed_memory_topic=ManagedMemoryTopic(
                        managed_topic_enum=ManagedTopicEnum.USER_PERSONAL_INFO,
                    ),
                ),
                MemoryTopic(
                    managed_memory_topic=ManagedMemoryTopic(
                        managed_topic_enum=ManagedTopicEnum.USER_PREFERENCES,
                    ),
                ),
                MemoryTopic(
                    managed_memory_topic=ManagedMemoryTopic(
                        managed_topic_enum=ManagedTopicEnum.EXPLICIT_INSTRUCTIONS,
                    ),
                ),
                MemoryTopic(
                    managed_memory_topic=ManagedMemoryTopic(
                        managed_topic_enum=ManagedTopicEnum.KEY_CONVERSATION_DETAILS,
                    ),
                ),
                MemoryTopic(
                    custom_memory_topic=CustomMemoryTopic(
                        label="PROPERTY_PREFERENCES_AND_REVIEWED_HOMES",
                        description=(
                            "User property preferences, reviewed real estate listings, target areas in Ireland, "
                            "desired bedrooms, bathrooms, floor area, budget constraints, and property characteristics."
                        ),
                    ),
                ),
            ],
        ),
    ],
)
