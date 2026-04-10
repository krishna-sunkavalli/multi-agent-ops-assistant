"""
Native Foundry IQ knowledge integration via AzureAISearchContextProvider.
Provides grounding context to agents automatically.
"""
from agent_framework.azure import AzureAISearchContextProvider
from azure.identity import DefaultAzureCredential
from config.settings import (
    SEARCH_ENDPOINT,
    KNOWLEDGE_BASE_NAME,
    AZURE_AI_PROJECT_ENDPOINT,
    MODEL_DEPLOYMENT_NAME,
)


def build_knowledge_provider() -> AzureAISearchContextProvider:
    """Create the native Foundry IQ context provider."""
    # Extract the Azure OpenAI resource URL from the project endpoint
    # Project endpoint: https://<resource>.services.ai.azure.com/api/projects/<project>
    # Azure OpenAI URL:  https://<resource>.services.ai.azure.com
    resource_url = AZURE_AI_PROJECT_ENDPOINT.split("/api/projects")[0]

    return AzureAISearchContextProvider(
        endpoint=SEARCH_ENDPOINT,
        credential=DefaultAzureCredential(),
        knowledge_base_name=KNOWLEDGE_BASE_NAME,
        mode="agentic",
        azure_openai_resource_url=resource_url,
        model_deployment_name=MODEL_DEPLOYMENT_NAME,
    )
