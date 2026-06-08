from __future__ import annotations

from abc import ABC, abstractmethod

from openai import APIError, AsyncOpenAI

from app.core.config import settings


class EmbeddingProviderError(Exception):
    """Raised when an embedding provider cannot generate a vector."""


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return a single embedding vector for the given text."""


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key or settings.openai_api_key)
        self._model_name = model_name or settings.embedding_model_name

    async def embed(self, text: str) -> list[float]:
        try:
            response = await self._client.embeddings.create(
                model=self._model_name,
                input=text,
            )
        except APIError as exc:
            raise EmbeddingProviderError("OpenAI embedding request failed") from exc
        except Exception as exc:
            raise EmbeddingProviderError("Unexpected embedding provider failure") from exc

        if not response.data:
            raise EmbeddingProviderError("Embedding provider returned no data")

        return list(response.data[0].embedding)


class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider | None = None) -> None:
        self._provider = provider or OpenAIEmbeddingProvider()

    async def embed_text(self, text: str) -> list[float]:
        return await self._provider.embed(text)
