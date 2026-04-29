import json
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from broker_api.data.resource_catalog import Resource
from broker_api.llm.prompts import system_prompt, user_prompt
from broker_api.policy.schemas import AccessDecision
from broker_api.policy.validate_decision import validate_decision


class ApprovalFailed(RuntimeError):
    pass


def _parse_response(parsed_or_text: Any) -> AccessDecision:
    if isinstance(parsed_or_text, AccessDecision):
        return parsed_or_text
    if isinstance(parsed_or_text, str):
        return AccessDecision.model_validate_json(parsed_or_text)
    return AccessDecision.model_validate(parsed_or_text)


def approve_user_request(
    *,
    openai_api_key: str,
    catalog: dict[str, Resource],
    policy_text: str,
    reason: str,
    max_attempts: int = 3,
) -> AccessDecision:
    client = OpenAI(api_key=openai_api_key)
    feedback = ""
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        prompt = user_prompt(policy_text=policy_text, reason=reason)
        if feedback:
            prompt = (
                f"{prompt}\n\nYour previous output was rejected by validation. "
                f"Fix the decision. Validation error: {feedback}"
            )

        try:
            response = client.responses.parse(
                model="gpt-5.5",
                reasoning={"effort": "low"},
                input=[
                    {"role": "system", "content": system_prompt(catalog)},
                    {"role": "user", "content": prompt},
                ],
                text_format=AccessDecision,
            )
            parsed = response.output_parsed
            decision = _parse_response(parsed)
            return validate_decision(
                decision=decision,
                policy_text=policy_text,
                reason=reason,
            )
        except (ValidationError, ValueError) as error:
            last_error = error
            feedback = str(error)
        except AttributeError:
            response = client.responses.create(
                model="gpt-5.5",
                reasoning={"effort": "low"},
                input=[
                    {"role": "system", "content": system_prompt(catalog)},
                    {"role": "user", "content": prompt},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "AccessDecision",
                        "schema": AccessDecision.model_json_schema(),
                        "strict": True,
                    }
                },
            )
            try:
                text = response.output_text
                decision = _parse_response(text)
                return validate_decision(
                    decision=decision,
                    policy_text=policy_text,
                    reason=reason,
                )
            except (ValidationError, ValueError, json.JSONDecodeError) as error:
                last_error = error
                feedback = str(error)

    raise ApprovalFailed(f"LLM decision failed validation: {last_error}")
