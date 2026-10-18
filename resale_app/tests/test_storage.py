import io

import pytest
from PIL import Image

from resale_app import db, images, seed


def test_money_parsing_and_formatting():
    assert db.parse_money("$1,234.50") == 123450
    assert db.parse_money("12") == 1200
    assert db.parse_money("") is None and db.parse_money("abc") is None and db.parse_money(None) is None
    assert db.format_money(1250) == "$12.50" and db.format_money(None) == ""


def test_items_get_sequential_skus(conn):
    a = db.create_item(conn, category="board", brand="ASUS")
    b = db.create_item(conn, category="clothing")
    assert (a["sku"], b["sku"]) == ("RS-0001", "RS-0002")
    assert db.get_item_by_sku(conn, "rs-0002")["id"] == b["id"]


def test_unknown_fields_are_rejected(conn):
    with pytest.raises(ValueError):
        db.create_item(conn, colour="red")


def test_store_photo_writes_three_variants_and_dedupes(conn, settings, jpeg):
    item = db.create_item(conn, category="board")
    data = jpeg("blue", size=(3000, 2000))
    first = images.store_photo(conn, settings, item, "IMG_1.jpg", data)
    assert not first.duplicate
    for variant in images.VARIANTS:
        assert images.media_path(settings, item["sku"], variant, first.photo["filename"]).is_file()
    with Image.open(images.media_path(settings, item["sku"], "vision", first.photo["filename"])) as v:
        assert max(v.size) == images.VISION_EDGE
    with Image.open(images.media_path(settings, item["sku"], "orig", first.photo["filename"])) as o:
        assert o.size == (3000, 2000)  # the original is kept as shot
    again = images.store_photo(conn, settings, item, "copy.jpg", data)
    assert again.duplicate and len(db.list_photos(conn, item["id"])) == 1


def test_non_images_are_rejected(conn, settings):
    item = db.create_item(conn)
    with pytest.raises(images.ImageError):
        images.store_photo(conn, settings, item, "notes.jpg", b"this is not a picture")
    with pytest.raises(images.ImageError):
        images.store_photo(conn, settings, item, "empty.jpg", b"")


def test_png_is_kept_as_png(conn, settings):
    item = db.create_item(conn)
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), "green").save(buf, "PNG")
    stored = images.store_photo(conn, settings, item, "x.png", buf.getvalue())
    assert stored.photo["filename"].endswith(".png")


def test_media_path_refuses_traversal_and_junk(settings, conn):
    item = db.create_item(conn)
    assert images.media_path(settings, item["sku"], "orig", "../../resale.sqlite3") is None
    assert images.media_path(settings, "../etc", "orig", "x.jpg") is None
    assert images.media_path(settings, item["sku"], "secret", "x.jpg") is None


def test_seed_is_idempotent_and_reports_bad_rows(conn, settings, tmp_path):
    csv_path = tmp_path / "inv.csv"
    csv_path.write_text(
        "ref,category,brand,model,title,condition,status,cost,notes,photos\n"
        "a,board,ASUS,X570,,good,intake,$85.00,tested,\n"
        "b,clothing,Carhartt,Hoodie,,,listed,14,,\n"
        "c,spaceship,Nope,,,,,,,\n"
        "d,board,,,,,,,,\n"
        "e,board,MSI,B550,,mint,,,,\n"
    )
    rows = seed.load_rows(csv_path)
    first = seed.seed(conn, settings, rows, tmp_path)
    assert (first.created, first.skipped) == (2, 0)
    assert len(first.errors) == 3
    assert any("row 4" in e and "category" in e for e in first.errors)
    assert any("row 5" in e for e in first.errors)
    assert any("row 6" in e and "condition" in e for e in first.errors)
    second = seed.seed(conn, settings, rows, tmp_path)
    assert (second.created, second.skipped) == (0, 2)
    assert len(db.list_items(conn)) == 2
    a = db.get_item_by_key(conn, "seed:a")
    assert (a["cost_basis_cents"], a["condition"], a["title"]) == (8500, "good", "ASUS X570")
    assert db.get_item_by_key(conn, "seed:b")["status"] == "listed"


def test_seed_update_flag_changes_existing_rows(conn, settings, tmp_path):
    p = tmp_path / "inv.csv"
    p.write_text("ref,category,brand,model,cost\nx,board,ASUS,X570,10\n")
    seed.seed(conn, settings, seed.load_rows(p), tmp_path)
    p.write_text("ref,category,brand,model,cost\nx,board,ASUS,X570,25\n")
    s = seed.seed(conn, settings, seed.load_rows(p), tmp_path, update=True)
    assert s.updated == 1 and db.get_item_by_key(conn, "seed:x")["cost_basis_cents"] == 2500


def test_seed_attaches_photos_relative_to_the_csv(conn, settings, tmp_path, jpeg):
    (tmp_path / "pics").mkdir()
    (tmp_path / "pics" / "front.jpg").write_bytes(jpeg())
    p = tmp_path / "inv.csv"
    p.write_text("ref,category,brand,photos\nx,board,ASUS,pics/front.jpg|pics/missing.jpg\n")
    s = seed.seed(conn, settings, seed.load_rows(p), tmp_path)
    assert s.photos_added == 1 and len(s.errors) == 1 and "missing.jpg" in s.errors[0]


def test_bundled_sample_inventory_loads_cleanly(conn, settings):
    rows = seed.load_rows(seed.DEFAULT_FILE)
    out = seed.seed(conn, settings, rows, seed.DEFAULT_FILE.parent)
    assert out.errors == [] and out.created == len(rows) >= 6
