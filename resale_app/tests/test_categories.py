from typing import get_args

from resale_app import categories as c
from resale_app.models import ShotId


def required_ids(category, flaws=False):
    return {m.id for m in c.missing_shots(category, set(), has_flaws=flaws) if m.required}


def test_board_prompts_cover_socket_back_io_serial():
    assert {"socket", "back", "io", "serial_sticker"} <= required_ids("board")


def test_clothing_prompts_cover_tags_size_and_flaws():
    assert {"brand_tag", "size_tag"} <= required_ids("clothing")
    assert "flaw_closeup" not in required_ids("clothing")  # only when flaws were seen
    assert "flaw_closeup" in required_ids("clothing", flaws=True)


def test_sneaker_prompts_cover_box_label_soles_insoles():
    assert {"box_label", "soles", "insoles"} <= required_ids("sneakers")


def test_covered_shots_drop_out():
    remaining = required_ids("board") - {"socket"}
    got = {m.id for m in c.missing_shots("board", {"socket", "front"}) if m.required}
    assert got == remaining - {"front"}


def test_blurry_photo_asks_for_a_retake():
    (socket,) = [m for m in c.missing_shots("board", set(), bad={"socket": "blurry"}) if m.id == "socket"]
    assert socket.required and socket.issue == "blurry"
    assert socket.prompt.startswith("The cpu socket close-up photo is blurry. Please retake it.")


def test_waived_shot_is_not_requested():
    assert "box_label" in required_ids("sneakers")
    got = {m.id for m in c.missing_shots("sneakers", set(), waived=["box_label"])}
    assert "box_label" not in got


def test_recommended_shots_are_optional():
    optional = {m.id for m in c.missing_shots("board", set()) if not m.required}
    assert {"ram_slots", "accessories"} <= optional


def test_unknown_category_has_no_prompts():
    assert c.missing_shots("unknown", set()) == []


def test_photo_order_follows_the_category_checklist():
    photos = [(1, "back"), (2, "other"), (3, "front"), (4, "socket"), (5, None), (6, "io")]
    assert c.photo_order("board", photos) == [3, 4, 6, 1, 2, 5]


def test_photo_order_is_stable_for_equal_shots():
    assert c.photo_order("clothing", [(1, "front"), (2, "front"), (3, "back")]) == [1, 2, 3]


def test_waived_facts_are_stated_for_waived_shots_only():
    assert c.waived_facts("sneakers", ["box_label"]) == [("No original box.", "box")]
    assert c.waived_facts("sneakers", ["soles"]) == []


def test_every_category_shot_is_a_valid_model_shot_id():
    valid = set(get_args(ShotId))
    for cat in c.CATEGORIES.values():
        assert {s.id for s in cat.shots} <= valid
    assert "other" in valid


def test_every_grade_has_a_definition():
    assert set(c.GRADES) == {"new", "like_new", "good", "fair", "for_parts"}
    assert all(g.definition for g in c.GRADES.values())
