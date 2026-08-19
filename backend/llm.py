from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from config import Settings


class LLMNotConfigured(RuntimeError):
    pass


def create_model(settings: Settings) -> OpenAIChatModel:
    if not settings.llm_configured:
        raise LLMNotConfigured("El proveedor LLM no esta configurado")
    client = AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=1,
    )
    return OpenAIChatModel(
        settings.llm_model,
        provider=OpenAIProvider(openai_client=client),
    )
