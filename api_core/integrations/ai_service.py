"""
AI Service Integration Facade — api_core.integrations.ai_service
Re-exports AIServiceClient and singletons from api_core.ai_client.
"""

from api_core.ai_client import (
    AIServiceClient,
    SyncAIServiceClient,
    ai_client,
    ai_client_sync,
)

__all__ = [
    "AIServiceClient",
    "SyncAIServiceClient",
    "ai_client",
    "ai_client_sync",
]
