import json
import requests
from typing import Dict, Optional, Any


class HTTPLLMProvider:
    """HTTP-based LLM provider for OpenAI-compatible endpoints"""

    def __init__(
        self,
        base_url: str,
        model: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ):
        """
        Initialize HTTP LLM provider

        Args:
            base_url: Base URL for the HTTP endpoint
            model: Model identifier
            headers: Additional HTTP headers
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

        self.headers = {"Content-Type": "application/json"}

        if headers:
            self.headers.update(headers)

    def invoke(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Process prompt using HTTP endpoint

        Args:
            prompt: Input prompt string
            max_tokens: Max response tokens
            temperature: Creativity control (0-1)
            timeout: Optional request timeout override in seconds

        Returns:
            Parsed JSON response or error dictionary
        """
        url = f"{self.base_url}/chat/completions"

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
                url, headers=self.headers, json=payload, timeout=effective_timeout
            )

            if response.status_code != 200:
                return {
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "response": None,
                }

            response_data = response.json()

            if "choices" in response_data and len(response_data["choices"]) > 0:
                content = response_data["choices"][0]["message"].get("content", "")

                try:
                    parsed_content = json.loads(content)

                    result = parsed_content
                    if "usage" in response_data:
                        result["_token_usage"] = response_data["usage"]

                    return result

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
                        try:
                            parsed_content = json.loads(candidate)
                            result = parsed_content
                            if "usage" in response_data:
                                result["_token_usage"] = response_data["usage"]
                            return result
                        except json.JSONDecodeError:
                            pass
                    return {
                        "error": "Invalid JSON in response content",
                        "response": content,
                    }
            else:
                return {
                    "error": "Unexpected response format - missing choices",
                    "response": response_data,
                }

        except requests.exceptions.Timeout:
            return {
                "error": f"Request timeout after {self.timeout} seconds",
                "response": None,
            }
        except requests.exceptions.ConnectionError:
            return {"error": f"Connection error to {url}", "response": None}
        except json.JSONDecodeError:
            return {
                "error": "Invalid JSON response from server",
                "response": response.text if "response" in locals() else None,
            }
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}", "response": None}
