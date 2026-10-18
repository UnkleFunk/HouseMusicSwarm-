from resale_app import platforms as p
from resale_app import voice


def test_fit_title_cuts_on_a_word_boundary():
    title = "ASUS TUF GAMING X570-PLUS Motherboard AM4 ATX DDR4 Used"
    out = p.fit_title(title, 40)
    assert out == "ASUS TUF GAMING X570-PLUS Motherboard"  # "AM4" would have cut at 41
    assert len(out) <= 40


def test_fit_title_leaves_no_dangling_separator():
    assert p.fit_title("Nike Air Max 90 - Size 10 - White", 18) == "Nike Air Max 90"


def test_fit_title_short_titles_pass_through_and_whitespace_is_tidied():
    assert p.fit_title("  Nike   Air Max  ", 80) == "Nike Air Max"


def test_fit_description_drops_detail_bullets_first_and_keeps_flaws():
    text = "Opener.\n\nWhat to know:\n- Scuff on the toe.\n\nDetails:\n- Size: 10\n- Color: White\n- Style: CN8490\n\nHappy to help."
    out = p.fit_description(text, len(text) - 20)
    assert "Scuff on the toe" in out
    assert "Style: CN8490" not in out
    assert len(out) <= len(text) - 20


def test_fit_description_hard_limit_never_exceeded():
    long = ("A sentence that goes on. " * 100).strip()
    assert len(p.fit_description(long, 200)) <= 200


def test_poshmark_is_offered_for_clothing_and_sneakers_only():
    assert {x.id for x in p.platforms_for("board")} == {"ebay", "mercari", "facebook"}
    assert "poshmark" in {x.id for x in p.platforms_for("clothing")}
    assert "poshmark" in {x.id for x in p.platforms_for("sneakers")}


def test_every_platform_labels_every_grade():
    for plat in p.PLATFORMS.values():
        assert set(plat.condition_labels) == {"new", "like_new", "good", "fair", "for_parts"}


def test_check_draft_flags_overlong_text_and_extra_photos():
    ebay = p.PLATFORMS["facebook"]
    warnings = p.check_draft(ebay, "x" * 120, "", 12)
    assert any("Title is 120" in w for w in warnings)
    assert any("Description is empty" in w for w in warnings)
    assert any("12 photos" in w for w in warnings)


def test_voice_flags_hype():
    out = voice.lint("A stunning, rare find. Must have!")
    assert any("Hype wording: rare, stunning" in x or "stunning" in x for x in out)
    assert "Exclamation mark." in out


def test_voice_flags_emoji_and_price_paid():
    out = voice.lint("Great board \U0001F525 I paid $80 for it")
    assert "Emoji." in out and "Mentions what was paid." in out


def test_voice_flags_shouting_but_allows_model_names():
    assert any("ALL CAPS" in x for x in voice.lint("BRAND NEW AMAZING PIECE"))
    assert voice.lint("ASUS TUF GAMING X570-PLUS board", allow=["TUF GAMING X570-PLUS"]) == []


def test_voice_passes_plain_honest_text():
    text = "Used, with normal light wear. Small scratch near the M.2 heatsink. I haven't tested it, so it's sold as untested."
    assert voice.lint(text) == []
