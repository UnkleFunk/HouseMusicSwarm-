"""Run the live path through the real Anthropic SDK, with the HTTP layer mocked.

This proves what the fake-client tests cannot: that the request the SDK builds from our pydantic
models is well formed (JSON-schema structured output, model, system prompt, image blocks) and that
a structured response is parsed back into our models. No network and no API key are involved.
"""

import json

import pytest

anthropic = pytest.importorskip("anthropic")
httpx2 = pytest.importorskip("httpx2")

from resale_app import db, llm, pipeline
from resale_app.models import AnalysisWire, DraftsWire

from conftest import add_photos
from test_vision_live import wire


def sdk_client(responses, seen):
    """A real anthropic.Anthropic whose HTTP calls are answered from `responses` (a list of text payloads)."""

    def handler(request):
        seen.append(json.loads(request.content))
        text = responses.pop(0)
        return httpx2.Response(200, json={
            "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": text}], "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 10},
        })

    return anthropic.Anthropic(api_key="test-key", base_url="http://mock.invalid", max_retries=0,
                               http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))


def test_structured_request_and_response_round_trip(conn, live_settings):
    item = db.create_item(conn, category="board", brand="ASUS", model="X570", notes="Tested: boots.")
    add_photos(conn, live_settings, item, ["front.jpg", "socket.jpg", "io.jpg", "back.jpg", "serial_sticker.jpg"])
    seen = []
    analysis = wire(photos=[{"photo_number": i, "shot": s, "quality": "ok", "note": ""} for i, s in
                            enumerate(["front", "socket", "io", "back", "serial_sticker"], start=1)], flaws=[])
    drafts = {"drafts": [
        {"platform": p, "title": f"ASUS X570 board {p}", "description": "ASUS X570 motherboard.\n\nHappy to answer questions.",
         "specs": [{"name": "Socket", "value": "AM4"}], "keywords": ["asus", "x570"]}
        for p in ("ebay", "mercari", "facebook")]}
    client = sdk_client([analysis.model_dump_json(), json.dumps(drafts)], seen)

    pipeline.run_analysis(conn, item["id"], live_settings, client)

    vision_req, draft_req = seen
    assert vision_req["model"] == live_settings.vision_model and vision_req["max_tokens"] == 16000
    schema = vision_req["output_config"]["format"]["schema"]
    assert vision_req["output_config"]["format"]["type"] == "json_schema" and schema["additionalProperties"] is False
    assert {"category", "photos", "flaws", "suggested_condition"} <= set(schema["properties"])
    blocks = vision_req["messages"][0]["content"]
    assert sum(b["type"] == "image" and b["source"]["media_type"] == "image/jpeg" for b in blocks) == 5
    assert "Read, do not guess" in vision_req["system"]
    assert set(draft_req["output_config"]["format"]["schema"]["properties"]) == {"drafts"}
    assert db.get_item(conn, item["id"])["status"] == "review"
    assert db.get_listing_for(conn, item["id"], "ebay")["title"] == "ASUS X570 board ebay"


def test_sdk_parses_into_our_models():
    seen = []
    client = sdk_client([wire().model_dump_json()], seen)
    out = llm.parse_structured(client, model="claude-opus-5-5", system="s", content="c", output_format=AnalysisWire)
    assert isinstance(out, AnalysisWire) and out.photos[1].shot == "socket"


def test_malformed_model_output_is_an_error_not_a_crash():
    client = sdk_client(["this is not json"], [])
    with pytest.raises(llm.LLMError, match="Claude call failed"):
        llm.parse_structured(client, model="claude-opus-5-5", system="s", content="c", output_format=DraftsWire)
