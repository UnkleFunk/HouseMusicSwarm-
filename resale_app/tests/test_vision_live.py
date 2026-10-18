"""The live vision path, exercised against a fake client so no network or key is needed."""

import base64

import pytest

from resale_app import db, llm, vision
from resale_app.models import AnalysisWire

from conftest import add_photos


def wire(**over):
    base = dict(
        category="board", brand="ASUS", model="TUF GAMING X570-PLUS", product_name="ATX motherboard",
        identification_confidence="high", identification_evidence="Silk-screen near the PCIe slot reads TUF GAMING X570-PLUS.",
        model_numbers=[{"value": "TUF GAMING X570-PLUS", "kind": "model", "photo_number": 1}],
        label_text=["TUF GAMING X570-PLUS"],
        photos=[
            {"photo_number": 1, "shot": "front", "quality": "ok", "note": ""},
            {"photo_number": 2, "shot": "socket", "quality": "blurry", "note": "Pins not sharp."},
        ],
        flaws=[{"description": "Scratch near the M.2 heatsink", "severity": "minor", "photo_number": 1}],
        attributes=[{"name": "Socket", "value": "AM4"}],
        suggested_condition="good", condition_rationale="Light cosmetic wear only.",
        unknowns=["Socket pins are not sharp enough to judge."],
    )
    base.update(over)
    return AnalysisWire(**base)


def item_with_photos(conn, settings, n=2, **fields):
    item = db.create_item(conn, category="board", notes="Tested: boots.", **fields)
    photos = add_photos(conn, settings, item, [f"p{i}.jpg" for i in range(n)])
    return item, photos


def test_live_analysis_sends_labelled_images_and_returns_normalised_analysis(conn, live_settings, fake_client):
    item, photos = item_with_photos(conn, live_settings)
    client = fake_client(wire())
    result = vision.analyze(item, db.list_photos(conn, item["id"]), live_settings, client)

    (call,) = client.messages.calls
    assert call["model"] == live_settings.vision_model
    assert call["output_format"] is AnalysisWire
    content = call["messages"][0]["content"]
    images = [b for b in content if b["type"] == "image"]
    assert len(images) == 2
    assert [b["text"] for b in content if b["type"] == "text" and b["text"].startswith("Photo")] == ["Photo 1:", "Photo 2:"]
    assert base64.b64decode(images[0]["source"]["data"])[:2] == b"\xff\xd8"  # a JPEG
    assert images[0]["source"]["media_type"] == "image/jpeg"
    assert "Tested: boots." in content[0]["text"]  # seller notes are passed through
    assert "socket" in call["system"] and "bent, missing or pushed-in" in call["system"]

    assert result.mode == "live" and result.photo_ids == [p["id"] for p in photos]
    assert result.photos[1].quality == "blurry"


def test_cost_basis_is_never_sent_to_the_model(conn, live_settings, fake_client):
    item, _ = item_with_photos(conn, live_settings, cost_basis_cents=987654)
    item = db.get_item(conn, item["id"])
    client = fake_client(wire())
    vision.analyze(item, db.list_photos(conn, item["id"]), live_settings, client)
    sent = str(client.messages.calls[0]["messages"]) + client.messages.calls[0]["system"]
    assert "9876" not in sent


def test_only_the_first_n_photos_are_sent(conn, live_settings, fake_client):
    import dataclasses

    settings = dataclasses.replace(live_settings, max_vision_photos=3)
    item, photos = item_with_photos(conn, settings, n=5)
    client = fake_client(wire(photos=[]))
    result = vision.analyze(item, db.list_photos(conn, item["id"]), settings, client)
    content = client.messages.calls[0]["messages"][0]["content"]
    assert sum(b["type"] == "image" for b in content) == 3
    assert "the first 3 are attached" in content[0]["text"]
    assert result.photo_ids == [p["id"] for p in photos[:3]]


def test_normalize_fills_missing_photo_reads_and_clamps_bad_numbers(conn, live_settings, fake_client):
    item, _ = item_with_photos(conn, live_settings)
    bad = wire(
        photos=[{"photo_number": 9, "shot": "io", "quality": "ok", "note": ""}],
        flaws=[{"description": "Dent", "severity": "minor", "photo_number": 7}],
    )
    result = vision.analyze(item, db.list_photos(conn, item["id"]), live_settings, fake_client(bad))
    assert [(p.photo_number, p.shot) for p in result.photos] == [(1, "other"), (2, "other")]
    assert result.flaws[0].photo_number == 0


def test_refusal_and_truncation_become_clear_errors(conn, live_settings, fake_client):
    item, _ = item_with_photos(conn, live_settings)
    photos = db.list_photos(conn, item["id"])
    with pytest.raises(llm.LLMError, match="declined.*cyber"):
        vision.analyze(item, photos, live_settings, fake_client(("refusal", "cyber")))
    with pytest.raises(llm.LLMError, match="ran out of room"):
        vision.analyze(item, photos, live_settings, fake_client("max_tokens"))
    with pytest.raises(llm.LLMError, match="Claude call failed: RuntimeError"):
        vision.analyze(item, photos, live_settings, fake_client(RuntimeError("boom")))


def test_no_photos_is_an_error(conn, live_settings, fake_client):
    item = db.create_item(conn, category="board")
    with pytest.raises(llm.LLMError, match="no photos"):
        vision.analyze(item, [], live_settings, fake_client())


def test_wire_schema_is_flat_enough_for_structured_outputs():
    schema = AnalysisWire.model_json_schema()
    assert "attributes" in schema["properties"] and schema["properties"]["attributes"]["type"] == "array"
    assert "shot" in schema["$defs"]["PhotoRead"]["properties"]
    assert "enum" in schema["$defs"]["PhotoRead"]["properties"]["shot"]
