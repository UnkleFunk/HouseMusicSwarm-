"""Drafting guards, the demo pipeline end to end, the worker, and the live draft path with a fake client."""

import pytest

from resale_app import db, drafting, pipeline, worker
from resale_app.models import DraftsWire, DraftWire

from conftest import add_photos
from test_vision_live import wire


def make_item(conn, settings, names, **fields):
    fields.setdefault("category", "board")
    item = db.create_item(conn, **fields)
    add_photos(conn, settings, item, names)
    return db.get_item(conn, item["id"])


BOARD_SHOTS = ["front.jpg", "socket.jpg", "io.jpg", "back.jpg", "serial_sticker.jpg"]


# --- functional status and the untested guard --------------------------------------------


@pytest.mark.parametrize(
    "notes,expected",
    [
        ("Tested: boots to BIOS.", "tested_working"),
        ("Works fine, posts every time", "tested_working"),
        ("Came out of a parts lot.", "untested"),
        ("", "untested"),
        ("Does not POST. Selling for parts.", "not_working"),
        ("Does not POST.", "not_working"),
        ("Tested: fails to boot after the logo", "not_working"),
        ("Won't boot", "not_working"),
        ("dead board", "not_working"),
    ],
)
def test_functional_status_from_seller_notes(notes, expected):
    assert drafting.functional_status("board", notes) == expected


def test_functional_status_only_applies_to_boards():
    assert drafting.functional_status("clothing", "tested") == "n/a"


def test_testing_notes_keep_the_sellers_words_and_drop_price_talk():
    notes = "Tested: boots to BIOS. I paid $40 and it works great! Bought for cheap, tested twice."
    assert drafting.testing_notes("board", notes) == ["Tested: boots to BIOS."]


# --- demo pipeline ------------------------------------------------------------------------


def test_demo_pipeline_drafts_every_platform_and_reaches_review(conn, settings):
    item = make_item(conn, settings, BOARD_SHOTS, brand="ASUS", model="TUF GAMING X570-PLUS",
                     notes="Tested: boots to BIOS. Small scratch near the M.2 heatsink. Serial: K1MB0123456.")
    pipeline.run_analysis(conn, item["id"], settings)
    item = db.get_item(conn, item["id"])
    listings = {l["platform"]: l for l in db.list_listings(conn, item_id=item["id"])}

    assert set(listings) == {"ebay", "mercari", "facebook"}  # no Poshmark for a board
    for plat_id, l in listings.items():
        assert l["state"] == "draft"
        assert l["title"] and l["description"]
        assert l["condition_grade"] == "good"
        assert "K1MB0123456" not in l["description"] + str(l["specs"]) + l["title"]  # serials stay private
        assert "Small scratch near the M.2 heatsink" in l["description"]
        assert "\nTested: boots to BIOS.\n" in l["description"]  # the seller's words, verbatim
        assert "haven't tested" not in l["description"]


def test_flaws_without_a_closeup_keep_the_item_in_needs_photos(conn, settings):
    item = make_item(conn, settings, BOARD_SHOTS, brand="ASUS", model="X570", notes="Small scratch near the M.2 heatsink.")
    pipeline.run_analysis(conn, item["id"], settings)
    assert db.get_item(conn, item["id"])["status"] == "needs_photos"
    analysis = pipeline.stored_analysis(conn, item["id"])
    missing = pipeline.missing_for(db.get_item(conn, item["id"]), db.list_photos(conn, item["id"]), analysis)
    assert [m.id for m in missing if m.required] == ["flaw_closeup"]


def test_untested_board_always_says_so(conn, settings):
    item = make_item(conn, settings, BOARD_SHOTS, brand="Gigabyte", model="B450 AORUS M", notes="Came out of a parts lot.")
    pipeline.run_analysis(conn, item["id"], settings)
    for l in db.list_listings(conn, item_id=item["id"]):
        assert "untested" in l["description"].lower()
    assert db.get_item(conn, item["id"])["status"] == "review"


def test_missing_and_blurry_photos_block_review_status(conn, settings):
    item = make_item(conn, settings, ["front.jpg", "socket_blurry.jpg", "io.jpg", "back.jpg"], brand="ASUS", model="X570")
    pipeline.run_analysis(conn, item["id"], settings)
    item = db.get_item(conn, item["id"])
    assert item["status"] == "needs_photos"
    missing = pipeline.missing_for(item, db.list_photos(conn, item["id"]), pipeline.stored_analysis(conn, item["id"]))
    needed = {m.id: m for m in missing if m.required}
    assert set(needed) == {"socket", "serial_sticker"}
    assert needed["socket"].issue == "blurry"


def test_waiving_a_shot_clears_it_and_the_listing_states_the_fact(conn, settings):
    item = make_item(conn, settings, ["side.jpg", "soles.jpg", "insoles.jpg"], category="sneakers", brand="Nike", model="Air Max 90",
                     notes="Size: 10. Colorway: White/Black.")
    pipeline.run_analysis(conn, item["id"], settings)
    assert db.get_item(conn, item["id"])["status"] == "needs_photos"
    db.update_item(conn, item["id"], waived_shots=["box_label"])
    pipeline.redraft(conn, item["id"], settings)
    item = db.get_item(conn, item["id"])
    assert item["status"] == "review"
    assert all("No original box." in l["description"] for l in db.list_listings(conn, item_id=item["id"]))


def test_unknown_category_is_filled_from_the_analysis_but_seller_values_win(conn, settings):
    item = make_item(conn, settings, ["front.jpg", "tag.jpg"], category="unknown", title="Hoodie lot", notes="Size: M. Color: navy hoodie.")
    pipeline.run_analysis(conn, item["id"], settings)
    after = db.get_item(conn, item["id"])
    assert after["category"] == "clothing" and after["title"] == "Hoodie lot"
    # A category the seller chose is never overwritten by the photos' opinion.
    other = make_item(conn, settings, ["front.jpg"], category="sneakers", notes="Size: 9 hoodie")
    pipeline.run_analysis(conn, other["id"], settings)
    assert db.get_item(conn, other["id"])["category"] == "sneakers"


def test_titles_respect_each_platforms_limit(conn, settings):
    item = make_item(conn, settings, BOARD_SHOTS, brand="ASUS", model="ROG MAXIMUS Z790 HERO EVA-02 EDITION WITH EXTRA LONG NAME",
                     notes="socket: LGA1700. chipset: Z790. form factor: Extended ATX Special Edition")
    pipeline.run_analysis(conn, item["id"], settings)
    for l in db.list_listings(conn, item_id=item["id"]):
        limit = {"ebay": 80, "mercari": 80, "facebook": 100, "poshmark": 80}[l["platform"]]
        assert len(l["title"]) <= limit and not l["title"].endswith(" ")


def test_photo_order_follows_the_checklist_and_uses_photo_ids(conn, settings):
    item = make_item(conn, settings, ["back.jpg", "io.jpg", "socket.jpg", "front.jpg", "serial_sticker.jpg"], brand="ASUS", model="X570")
    pipeline.run_analysis(conn, item["id"], settings)
    by_name = {p["original_name"]: p["id"] for p in db.list_photos(conn, item["id"])}
    want = [by_name[n] for n in ("front.jpg", "socket.jpg", "io.jpg", "back.jpg", "serial_sticker.jpg")]
    assert db.get_listing_for(conn, item["id"], "ebay")["photo_order"] == want


def test_photo_order_is_cut_to_the_platform_photo_limit(conn, settings):
    names = ["front.jpg", "socket.jpg", "io.jpg", "back.jpg", "serial_sticker.jpg"] + [f"extra{i}.jpg" for i in range(8)]
    item = make_item(conn, settings, names, brand="ASUS", model="X570")
    pipeline.run_analysis(conn, item["id"], settings)
    assert len(db.get_listing_for(conn, item["id"], "ebay")["photo_order"]) == 13
    fb = db.get_listing_for(conn, item["id"], "facebook")
    assert len(fb["photo_order"]) == 10 and any("13 photos" in w for w in fb["warnings"])


# --- drafts survive the seller's edits -----------------------------------------------------


def test_redraft_keeps_edited_and_decided_listings_unless_forced(conn, settings):
    item = make_item(conn, settings, BOARD_SHOTS, brand="ASUS", model="X570", notes="Tested: boots.")
    pipeline.run_analysis(conn, item["id"], settings)
    ebay = db.get_listing_for(conn, item["id"], "ebay")
    db.update_listing(conn, ebay["id"], title="My own title", edited=1)
    db.update_listing(conn, db.get_listing_for(conn, item["id"], "mercari")["id"], state="approved")

    counts = pipeline.redraft(conn, item["id"], settings)
    assert counts == {"created": 0, "updated": 1, "kept": 2}
    assert db.get_listing_for(conn, item["id"], "ebay")["title"] == "My own title"
    assert db.get_listing_for(conn, item["id"], "mercari")["state"] == "approved"

    pipeline.redraft(conn, item["id"], settings, force=True)
    ebay = db.get_listing_for(conn, item["id"], "ebay")
    assert ebay["title"] != "My own title" and ebay["edited"] == 0 and ebay["state"] == "draft"


def test_item_status_follows_listing_decisions(conn, settings):
    item = make_item(conn, settings, BOARD_SHOTS, brand="ASUS", model="X570", notes="Tested: boots.")
    pipeline.run_analysis(conn, item["id"], settings)
    ls = db.list_listings(conn, item_id=item["id"])
    status = lambda: pipeline.refresh_status(conn, item["id"])["status"]
    assert status() == "review"
    db.update_listing(conn, ls[0]["id"], state="approved")
    assert status() == "review"  # two drafts still pending
    for l in ls[1:]:
        db.update_listing(conn, l["id"], state="skipped")
    assert status() == "approved"
    db.update_listing(conn, ls[0]["id"], state="posted")
    assert status() == "listed"
    db.update_listing(conn, ls[0]["id"], state="sold")
    assert status() == "sold"


def test_all_skipped_means_skipped(conn, settings):
    item = make_item(conn, settings, BOARD_SHOTS, brand="ASUS", model="X570", notes="Tested: boots.")
    pipeline.run_analysis(conn, item["id"], settings)
    for l in db.list_listings(conn, item_id=item["id"]):
        db.update_listing(conn, l["id"], state="skipped")
    assert pipeline.refresh_status(conn, item["id"])["status"] == "skipped"


# --- worker ---------------------------------------------------------------------------------


def test_worker_processes_queued_items_after_their_settle_delay(conn, settings):
    item = make_item(conn, settings, BOARD_SHOTS, brand="ASUS", model="X570")
    db.queue_analysis(conn, item["id"], delay=3600)
    assert worker.process_one(settings) is False  # not due yet
    db.queue_analysis(conn, item["id"], delay=0)
    assert worker.process_one(settings) is True
    after = db.get_item(conn, item["id"])
    assert after["analysis_status"] == "done" and after["status"] in ("review", "needs_photos")
    assert worker.process_one(settings) is False


def test_worker_records_failures_on_the_item_and_keeps_going(conn, live_settings, fake_client):
    item = make_item(conn, live_settings, BOARD_SHOTS, brand="ASUS", model="X570")
    db.queue_analysis(conn, item["id"])
    assert worker.process_one(live_settings, fake_client(("refusal", "general_harms"))) is True
    after = db.get_item(conn, item["id"])
    assert after["analysis_status"] == "error" and "declined" in after["analysis_error"]
    assert db.list_listings(conn, item_id=item["id"]) == []


def test_worker_requeues_when_photos_arrive_mid_analysis(conn, settings, monkeypatch):
    item = make_item(conn, settings, BOARD_SHOTS, brand="ASUS", model="X570")
    db.queue_analysis(conn, item["id"])
    real = pipeline.run_analysis

    def run_and_add_photo(c, item_id, s, client=None):
        out = real(c, item_id, s, client)
        add_photos(c, s, db.get_item(c, item_id), ["late.jpg"])
        return out

    monkeypatch.setattr(pipeline, "run_analysis", run_and_add_photo)
    worker.process_one(settings)
    assert db.get_item(conn, item["id"])["analysis_status"] == "queued"


def test_crashed_running_items_go_back_in_the_queue(conn):
    item = db.create_item(conn)
    db.update_item(conn, item["id"], analysis_status="running")
    db.recover_running(conn)
    assert db.get_item(conn, item["id"])["analysis_status"] == "queued"


# --- live drafting with a fake client -------------------------------------------------------


def live_item(conn, live_settings, notes="", category="board", names=None):
    item = make_item(conn, live_settings, names or BOARD_SHOTS, category=category, brand="ASUS", model="X570", notes=notes)
    return item


def draft(platform, **over):
    d = dict(platform=platform, title="ASUS X570 Motherboard AM4", description="ASUS X570 motherboard.\n\nHappy to answer questions.",
             specs=[{"name": "Socket", "value": "AM4"}], keywords=["asus", "x570", "am4"])
    d.update(over)
    return DraftWire(**d)


def test_live_pipeline_uses_the_draft_model_and_sends_facts_not_cost(conn, live_settings, fake_client):
    item = live_item(conn, live_settings, notes="Tested: boots to BIOS.")
    db.update_item(conn, item["id"], cost_basis_cents=424242)
    client = fake_client(wire(photos=[{"photo_number": i, "shot": s, "quality": "ok", "note": ""} for i, s in
                                      enumerate(["front", "socket", "io", "back", "serial_sticker"], start=1)], flaws=[]),
                         DraftsWire(drafts=[draft("ebay"), draft("mercari"), draft("facebook")]))
    pipeline.run_analysis(conn, item["id"], live_settings, client)
    vision_call, draft_call = client.messages.calls
    assert draft_call["output_format"] is DraftsWire and draft_call["model"] == live_settings.draft_model
    brief = draft_call["messages"][0]["content"]
    assert '"title_max_chars": 80' in brief and "testing_notes" in brief and "Tested: boots to BIOS." in brief
    assert "4242" not in brief and "cost" not in brief.lower()
    assert "Write as the seller" in draft_call["system"] and "no hype" in draft_call["system"].lower()
    assert db.get_item(conn, item["id"])["status"] == "review"


def test_guards_fix_what_the_model_gets_wrong(conn, live_settings, fake_client):
    item = live_item(conn, live_settings, notes="")
    long_title = "ASUS TUF GAMING X570-PLUS ATX AM4 Motherboard for Ryzen 3000 4000 5000 Series DDR4 USB 3.2 Wi-Fi HDMI Excellent"
    hype = draft("ebay", title=long_title, description="A stunning, rare board!\n\nDetails:\n- Serial: K1MB0123456\n- Socket: AM4",
                 specs=[{"name": "Socket", "value": "AM4"}, {"name": "Serial Number", "value": "K1MB0123456"}])
    client = fake_client(wire(), DraftsWire(drafts=[hype]))  # the model forgot mercari and facebook
    pipeline.run_analysis(conn, item["id"], live_settings, client)

    ebay = db.get_listing_for(conn, item["id"], "ebay")
    assert len(ebay["title"]) <= 80
    assert "untested" in ebay["description"]  # added: notes never said it was tested
    assert [s["name"] for s in ebay["specs"]] == ["Socket"]  # the serial spec is dropped
    assert any("Hype wording" in w for w in ebay["warnings"]) and any("Exclamation" in w for w in ebay["warnings"])
    assert {l["platform"] for l in db.list_listings(conn, item_id=item["id"])} == {"ebay", "mercari", "facebook"}
    assert db.get_listing_for(conn, item["id"], "mercari")["title"]  # filled by the template fallback


def test_not_working_boards_are_sold_for_parts(conn, live_settings, fake_client):
    item = live_item(conn, live_settings, notes="Does not post.")
    client = fake_client(wire(), DraftsWire(drafts=[draft("ebay"), draft("mercari"), draft("facebook")]))
    pipeline.run_analysis(conn, item["id"], live_settings, client)
    assert "sold for parts or repair" in db.get_listing_for(conn, item["id"], "ebay")["description"]


def test_description_guard_text_survives_the_length_limit(conn, live_settings, fake_client):
    item = live_item(conn, live_settings, notes="")
    padding = "\n".join(f"- Detail {i}: {'x' * 60}" for i in range(30))
    long = draft("mercari", description="ASUS board.\n\nDetails:\n" + padding)
    client = fake_client(wire(), DraftsWire(drafts=[draft("ebay"), long, draft("facebook")]))
    pipeline.run_analysis(conn, item["id"], live_settings, client)
    merc = db.get_listing_for(conn, item["id"], "mercari")
    assert len(merc["description"]) <= 1000 and merc["description"].endswith("sold as untested.")


def test_a_failed_draft_call_leaves_the_analysis_saved_and_the_error_visible(conn, live_settings, fake_client):
    item = live_item(conn, live_settings)
    db.queue_analysis(conn, item["id"])
    client = fake_client(wire(), RuntimeError("network down"))
    worker.process_one(live_settings, client)
    after = db.get_item(conn, item["id"])
    assert after["analysis_status"] == "error" and "network down" in after["analysis_error"]
    assert pipeline.stored_analysis(conn, item["id"]) is not None  # redraft can retry without re-reading photos
    client2 = fake_client(DraftsWire(drafts=[draft("ebay"), draft("mercari"), draft("facebook")]))
    pipeline.redraft(conn, item["id"], live_settings, client2)
    assert len(db.list_listings(conn, item_id=item["id"])) == 3
