"""One thin wrapper around the Anthropic SDK so the rest of the app, and the tests, share a seam."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model call failed or came back unusable. The message is safe to show the user."""


def get_client() -> Any:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - depends on the install
        raise LLMError("The 'anthropic' package is not installed. Run: pip install -r resale_app/requirements.txt") from exc
    # Credentials come from ANTHROPIC_API_KEY or an `ant auth login` profile.
    return anthropic.Anthropic(max_retries=3)


def parse_structured(
    client: Any,
    *,
    model: str,
    system: str,
    content: list[dict[str, Any]] | str,
    output_format: type[T],
    max_tokens: int = 16000,
) -> T:
    """Ask for output matching a pydantic model. Refusals and truncation become LLMError."""
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_format=output_format,
        )
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError(f"Claude call failed: {type(exc).__name__}: {exc}") from exc

    stop = getattr(response, "stop_reason", None)
    if stop == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None) if details else None
        raise LLMError(f"The model declined this request{f' ({category})' if category else ''}. Try again, or re-shoot the photos.")
    if stop == "max_tokens":
        raise LLMError("The model ran out of room before it finished. Try again with fewer photos.")
    parsed = getattr(response, "parsed_output", None)
    if parsed is None:
        raise LLMError("The model returned nothing in the expected format.")
    return parsed
