import os
import json
import requests
from typing import Dict, Any, Optional

from ..providers.llm_http import HTTPLLMProvider


class SafetyLLM:
    """LLM Provider Router for multiple backends (openrouter|http|local)"""

    def __init__(
        self,
        model: Optional[str] = None,
        backend: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the safety LLM router

        Args:
            model: Model identifier (defaults to ANALYSIS_LLM_MODEL env var)
            backend: Backend type (defaults to ANALYSIS_LLM_BACKEND env var)
            api_key: API key for cloud providers
            **kwargs: Additional provider-specific arguments
        """
        self.backend = backend or os.getenv("ANALYSIS_LLM_BACKEND", "openrouter")
        self.model = model or os.getenv("ANALYSIS_LLM_MODEL", "SafeLens/llama-3-8b")
        self.timeout = int(os.getenv("ANALYSIS_LLM_TIMEOUT_SEC", "30"))

        if self.backend == "openrouter":
            self.provider = self._init_openrouter_provider(api_key)
        elif self.backend == "http":
            self.provider = self._init_http_provider()
        elif self.backend == "local":
            self.provider = self._init_local_provider()
        else:
            raise ValueError(
                f"Unsupported backend: {self.backend}. "
                f"Supported backends: openrouter, http, local"
            )

    def _init_openrouter_provider(self, api_key: Optional[str]):
        """Initialize OpenRouter provider (existing implementation)"""
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")

        if not self.api_key:
            return MockLLMProvider()

        return OpenRouterProvider(self.api_url, self.model, self.api_key, self.timeout)

    def _init_http_provider(self):
        """Initialize HTTP provider"""
        base_url = os.getenv("ANALYSIS_LLM_HTTP_URL")
        if not base_url:
            raise ValueError("ANALYSIS_LLM_HTTP_URL is required for HTTP backend")

        headers = {}
        headers_str = os.getenv("ANALYSIS_LLM_HTTP_HEADERS")
        if headers_str:
            try:
                headers = json.loads(headers_str)
            except json.JSONDecodeError:
                raise ValueError("ANALYSIS_LLM_HTTP_HEADERS must be valid JSON")

        return HTTPLLMProvider(base_url, self.model, headers, self.timeout)

    def _init_local_provider(self):
        """Initialize local provider.

        Tries to import an optional LocalLLMProvider from web/providers/llm_local.py.
        If it is missing, fall back to a lightweight mock so the server can run
        without local LLM dependencies.
        """
        try:
            from ..providers.llm_local import LocalLLMProvider  # type: ignore
            return LocalLLMProvider(self.model)
        except Exception:
            # Graceful fallback when local provider is not available
            return MockLLMProvider()

    def invoke(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Process prompt using the configured provider

        Args:
            prompt: Input prompt string
            max_tokens: Max response tokens
            temperature: Creativity control (0-1)
            timeout: Optional timeout override in seconds

        Returns:
            Parsed JSON response or error dictionary
        """
        effective_timeout = timeout if timeout is not None else self.timeout
        return self.provider.invoke(prompt, max_tokens, temperature, effective_timeout)


class OpenRouterProvider:
    """OpenRouter API provider (original implementation)"""

    def __init__(self, api_url: str, model: str, api_key: str, timeout: int):
        self.api_url = api_url
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def invoke(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        timeout: int = None,
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": "Video Safety Agent",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a content safety analyst. Return responses in JSON format.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        try:
            effective_timeout = timeout if timeout is not None else self.timeout
            response = requests.post(
                self.api_url, headers=headers, json=payload, timeout=effective_timeout
            )

            if response.status_code != 200:
                return {
                    "error": f"API error {response.status_code}",
                    "response": response.text,
                }

            response_data = response.json()
            content = response_data["choices"][0]["message"].get("content", "")

            try:
                parsed_content = json.loads(content)
            except json.JSONDecodeError:
                cleaned = content.strip() if isinstance(content, str) else ""
                if cleaned.startswith("```"):
                    nl = cleaned.find("\n")
                    if nl != -1:
                        cleaned = cleaned[nl + 1 :]
                    fence = cleaned.rfind("```")
                    if fence != -1:
                        cleaned = cleaned[:fence]
                    cleaned = cleaned.strip()
                start = cleaned.find("{")
                end = cleaned.rfind("}")
                if start != -1 and end != -1 and end > start:
                    candidate = cleaned[start : end + 1]
                    parsed_content = json.loads(candidate)
                else:
                    return {
                        "error": "Invalid JSON response from API",
                        "response": content,
                    }

            if "usage" in response_data:
                parsed_content["_token_usage"] = response_data["usage"]

            return parsed_content

        except json.JSONDecodeError:
            return {"error": "Invalid JSON response from API"}
        except KeyError:
            return {"error": "Unexpected API response format"}
        except Exception as e:
            return {"error": str(e)}


class MockLLMProvider:
    """Mock provider for development when no API keys are available"""

    def invoke(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        timeout: int = None,
    ) -> Dict[str, Any]:
        return {
            "safety_assessment": "mock_analysis",
            "confidence": 0.5,
            "explanation": "This is a mock response for development purposes",
            "_mock": True,
        }
