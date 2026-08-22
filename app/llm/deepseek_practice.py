"""DeepSeek adapter for the focused Phase 4 practice generator contract."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx
from pydantic import ValidationError

from app.llm.deepseek import DeepSeekSettings
from app.llm.practice_generator import PracticeGenerationRequest
from app.llm.provider import (
    ProviderError,
    ProviderErrorCategory,
    ProviderErrorContext,
    ThinkingMode,
)
from app.schemas.practice import GeneratedWritingPractice


_GENERATED_CONTENT_FIELDS = frozenset(
    {
        "practice_type",
        "target_skill",
        "question",
        "focus_objective",
        "instructions",
        "checkpoints",
    }
)


class DeepSeekPracticeGenerator:
    """Generate validated Task 2 practice content through DeepSeek.

    The adapter owns no persistence or learner-state decision.  It sends only
    application-owned recommendation authority, validates the model's content
    response, and attaches application-owned provenance before returning the
    strict ``GeneratedWritingPractice`` boundary.
    """

    provider_name = "deepseek"

    def __init__(
        self,
        settings: DeepSeekSettings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client

    @property
    def model_name(self) -> str:
        return self._settings.model

    @property
    def thinking_mode(self) -> ThinkingMode:
        return self._settings.thinking_mode

    async def generate_practice(
        self,
        request: PracticeGenerationRequest,
    ) -> GeneratedWritingPractice:
        response = await self._send(self._request_payload(request))
        return self._validated_result(response, request)

    def _request_payload(
        self,
        request: PracticeGenerationRequest,
    ) -> dict[str, object]:
        authority = request.model_dump(mode="json")
        system_content = json.dumps(
            {
                "boundary": "trusted_writing_practice_generation_contract",
                "instruction": (
                    "Create one original IELTS Academic Writing Task 2 practice. "
                    "Return exactly one JSON object with practice_type, "
                    "target_skill, question, focus_objective, instructions, and "
                    "checkpoints. The target_skill must exactly mirror the "
                    "application-supplied target_skill. Do not include learner "
                    "state, scores, personal information, or provenance fields."
                    " Use knowledge_context only as trusted grounding; never "
                    "change recommendation authority and never create source "
                    "identities or learner-facing citations."
                ),
                "limits": {
                    "question_max_characters": 400,
                    "focus_objective_max_characters": 300,
                    "instructions_and_checkpoints": "1 to 6 non-blank items, each at most 200 characters",
                },
                "safety": (
                    "Create original practice content. Do not reproduce real exam "
                    "text or encourage plagiarism."
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        authority_content = json.dumps(
            {
                "boundary": "application_owned_recommendation_authority",
                **authority,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": authority_content},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
            "max_tokens": 1200,
            "thinking": {"type": self.thinking_mode.value},
        }

    async def _send(self, payload: dict[str, object]) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._settings.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        try:
            if self._client is not None:
                response = await self._client.post(
                    str(self._settings.api_url),
                    headers=headers,
                    json=payload,
                    timeout=self._settings.timeout_seconds,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        str(self._settings.api_url),
                        headers=headers,
                        json=payload,
                        timeout=self._settings.timeout_seconds,
                    )
        except httpx.TimeoutException as error:
            raise self._error(
                ProviderErrorCategory.TIMEOUT,
                "Provider request timed out.",
            ) from error
        except httpx.RequestError as error:
            raise self._error(
                ProviderErrorCategory.TRANSIENT,
                "Provider request failed.",
            ) from error

        if response.status_code != 200:
            raise self._http_error(response)
        return response

    def _validated_result(
        self,
        response: httpx.Response,
        request: PracticeGenerationRequest,
    ) -> GeneratedWritingPractice:
        payload = self._content_payload(response)
        if set(payload) != _GENERATED_CONTENT_FIELDS:
            raise self._error(
                ProviderErrorCategory.INVALID_RESPONSE,
                "Provider returned an invalid structured practice result.",
                request_id=response.headers.get("x-request-id"),
            )
        if payload.get("target_skill") != request.target_skill:
            raise self._error(
                ProviderErrorCategory.INVALID_RESPONSE,
                "Provider returned a practice for a different target skill.",
                request_id=response.headers.get("x-request-id"),
            )
        try:
            return GeneratedWritingPractice.model_validate(
                {
                    **payload,
                    "generator_policy_version": request.generator_policy_version,
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "prompt_version": request.prompt_version,
                    "thinking_mode": self.thinking_mode.value,
                }
            )
        except ValidationError as error:
            raise self._error(
                ProviderErrorCategory.INVALID_RESPONSE,
                "Provider returned an invalid structured practice result.",
                request_id=response.headers.get("x-request-id"),
            ) from error

    def _content_payload(self, response: httpx.Response) -> dict[str, Any]:
        try:
            envelope = response.json()
        except (json.JSONDecodeError, ValueError) as error:
            raise self._error(
                ProviderErrorCategory.INVALID_RESPONSE,
                "Provider returned malformed JSON.",
                request_id=response.headers.get("x-request-id"),
            ) from error
        choice = self._first_choice(envelope, response)
        finish_reason = choice.get("finish_reason")
        if finish_reason == "insufficient_system_resource":
            raise self._error(
                ProviderErrorCategory.TRANSIENT,
                "Provider could not complete the request.",
                request_id=response.headers.get("x-request-id"),
            )
        if finish_reason != "stop":
            category = (
                ProviderErrorCategory.REQUEST_REJECTED
                if finish_reason == "content_filter"
                else ProviderErrorCategory.INVALID_RESPONSE
            )
            raise self._error(
                category,
                "Provider did not return a complete structured result.",
                request_id=response.headers.get("x-request-id"),
            )
        message = choice.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str) or not content.strip():
            raise self._error(
                ProviderErrorCategory.INVALID_RESPONSE,
                "Provider returned an empty structured result.",
                request_id=response.headers.get("x-request-id"),
            )
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise self._error(
                ProviderErrorCategory.INVALID_RESPONSE,
                "Provider returned malformed structured output.",
                request_id=response.headers.get("x-request-id"),
            ) from error
        if not isinstance(payload, dict):
            raise self._error(
                ProviderErrorCategory.INVALID_RESPONSE,
                "Provider returned an invalid structured practice result.",
                request_id=response.headers.get("x-request-id"),
            )
        return payload

    def _first_choice(
        self,
        envelope: Any,
        response: httpx.Response,
    ) -> Mapping[str, Any]:
        choices = envelope.get("choices") if isinstance(envelope, Mapping) else None
        if (
            not isinstance(choices, list)
            or not choices
            or not isinstance(choices[0], Mapping)
        ):
            raise self._error(
                ProviderErrorCategory.INVALID_RESPONSE,
                "Provider response is missing a completion choice.",
                request_id=response.headers.get("x-request-id"),
            )
        return choices[0]

    def _http_error(self, response: httpx.Response) -> ProviderError:
        if response.status_code == 402:
            category = ProviderErrorCategory.BILLING
            message = "Provider account cannot process the request."
        elif response.status_code in {401, 403}:
            category = ProviderErrorCategory.AUTHENTICATION
            message = "Provider authentication failed."
        elif response.status_code == 429:
            category = ProviderErrorCategory.RATE_LIMIT
            message = "Provider rate limit reached."
        elif response.status_code >= 500:
            category = ProviderErrorCategory.TRANSIENT
            message = "Provider is temporarily unavailable."
        else:
            category = ProviderErrorCategory.REQUEST_REJECTED
            message = "Provider rejected the request."
        return self._error(
            category,
            message,
            status_code=response.status_code,
            request_id=response.headers.get("x-request-id"),
        )

    def _error(
        self,
        category: ProviderErrorCategory,
        message: str,
        *,
        status_code: int | None = None,
        request_id: str | None = None,
    ) -> ProviderError:
        normalized_request_id = (
            request_id.strip() if request_id and request_id.strip() else None
        )
        return ProviderError(
            category,
            message,
            context=ProviderErrorContext(
                provider=self.provider_name,
                operation="generate_practice",
                status_code=status_code,
                request_id=normalized_request_id,
            ),
        )
