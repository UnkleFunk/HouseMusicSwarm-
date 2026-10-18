"""The web flows, the export packs, the demo data and the CLI."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from resale_app import __main__ as cli
from resale_app import db, demo, worker
from resale_app.app import create_app


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def seeded(settings, conn):
    assert demo.seed_demo(conn, settings) == 5
    return conn


def upload(client, jpeg, names, **form):
    files = [("files", (n, jpeg(seed=i + 1 + sum(map(ord, n))), "image/jpeg")) for i, n in enumerate(names)]
    return client.post("/upload", data=form, files=files, follow_redirects=False)


# --- upload ---------------------------------------------------------------------------------


def test_upload_page_accepts_several_photos_and_creates_one_item(client, conn, settings, jpeg):
    page = client.get("/upload")
    assert 'type="file"' in page.text and "multiple" in page.text and 'accept="image/*"' in page.text
    r = upload(client, jpeg, ["front.jpg", "socket.jpg", "back.jpg"], category="board", brand="ASUS", model="X570",
               notes="Tested: boots.", cost="85", analyze="1")
    assert r.status_code == 303 and r.headers["location"].startswith("/items/1")
    (item,) = db.list_items(conn)
    assert (item["photo_count"], item["category"], item["cost_basis_cents"], item["analysis_status"]) == (3, "board", 8500, "queued")
    assert worker.process_one(settings) is True
    assert db.get_item(conn, 1)["status"] in ("review", "needs_photos")


def test_upload_to_an_existing_item_updates_it(client, conn, jpeg):
    item = db.create_item(conn, category="unknown", notes="first note")
    upload(client, jpeg, ["a.jpg"], item_id=str(item["id"]), category="sneakers", brand="Nike", notes="second note")
    upload(client, jpeg, ["b.jpg"], item_id=str(item["id"]), brand="")
    after = db.get_item(conn, item["id"])
    assert after["category"] == "sneakers" and after["brand"] == "Nike"
    assert after["notes"] == "first note\nsecond note"
    assert len(db.list_photos(conn, item["id"])) == 2 and len(db.list_items(conn)) == 1


def test_upload_without_analyze_does_not_queue(client, conn, jpeg):
    upload(client, jpeg, ["a.jpg"], category="board")
    assert db.get_item(conn, 1)["analysis_status"] == "idle"


def test_bad_files_are_skipped_not_fatal(client, conn, jpeg):
    files = [("files", ("ok.jpg", jpeg(), "image/jpeg")), ("files", ("bad.jpg", b"nope", "image/jpeg"))]
    r = client.post("/upload", data={"category": "board"}, files=files, follow_redirects=True)
    assert "1 photo added" in r.text and "bad.jpg" in r.text
    assert db.list_items(conn)[0]["photo_count"] == 1


def test_upload_with_no_files_is_a_400(client):
    assert client.post("/upload", data={"category": "board"}).status_code == 400


def test_json_upload_api(client, conn, jpeg):
    r = client.post("/api/upload", data={"category": "clothing", "brand": "Carhartt"},
                    files=[("files", ("a.jpg", jpeg(), "image/jpeg")), ("files", ("b.jpg", jpeg(seed=9), "image/jpeg"))])
    body = r.json()
    assert body == {"sku": "RS-0001", "id": 1, "created": True, "added": 2, "duplicates": 0, "errors": []}
    again = client.post("/api/upload", data={"item_id": "1"}, files=[("files", ("a.jpg", jpeg(), "image/jpeg"))]).json()
    assert again["added"] == 0 and again["duplicates"] == 1
    assert client.get("/api/items").json()[0]["sku"] == "RS-0001"


def test_upload_page_shows_the_missing_photo_prompts_for_an_item(client, seeded):
    page = client.get("/upload?item=1&shot=socket")
    assert "Photos still wanted" in page.text and "CPU socket close-up" in page.text and "retake" in page.text.lower()


# --- review ---------------------------------------------------------------------------------


def test_review_shows_cards_with_the_required_parts(client, seeded):
    page = client.get("/review").text
    for must in ("Approve", "Edit", "Skip", "Photos still needed", "What I read from the photos", "Photo order", "Item specifics", "Keywords"):
        assert must in page
    assert page.count('class="card"') == 4  # four items waiting; the garage-lot item has not been read
    assert "Serial number" not in page and "K1MB0123456" not in page.split("What I read")[0]


def test_missing_photo_prompts_on_the_card_name_the_shots(client, seeded):
    sneaker = client.get("/items/4").text
    for label in ("Box label", "Flaw close-ups"):
        assert label in sneaker
    assert "Not applicable" in sneaker and "/upload?item=4&amp;shot=box_label" in sneaker
    board = client.get("/items/1").text
    assert "CPU socket close-up" in board and "Serial / model sticker" in board and "is blurry" in board


def test_approve_edit_skip_flow(client, seeded):
    ebay = db.get_listing_for(seeded, 3, "ebay")
    r = client.post(f"/listings/{ebay['id']}/approve", data={"next": "/review#item-3"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/review?msg=Approved.#item-3")
    assert db.get_listing(seeded, ebay["id"])["state"] == "approved"

    client.post(f"/listings/{ebay['id']}/edit", data={
        "title": "Carhartt WIP hoodie, size L", "description": "Plain and honest.\n\nStrong, stunning!", "condition_grade": "fair",
        "specs": "Size: L\nColor: Heather grey\nnot a spec line", "keywords": "carhartt, hoodie,\nwip", "price": "$32.50",
    })
    after = db.get_listing(seeded, ebay["id"])
    assert after["state"] == "draft" and after["edited"] == 1  # editing an approval re-opens it
    assert after["title"] == "Carhartt WIP hoodie, size L" and after["condition_grade"] == "fair"
    assert after["specs"] == [{"name": "Size", "value": "L"}, {"name": "Color", "value": "Heather grey"}]
    assert after["keywords"] == ["carhartt", "hoodie", "wip"] and after["price_cents"] == 3250
    assert any("Hype wording" in w for w in after["warnings"])

    mercari = db.get_listing_for(seeded, 3, "mercari")
    client.post(f"/listings/{mercari['id']}/skip")
    assert db.get_listing(seeded, mercari["id"])["state"] == "skipped"
    client.post(f"/listings/{mercari['id']}/reopen")
    assert db.get_listing(seeded, mercari["id"])["state"] == "draft"


def test_approve_all_and_skip_item_move_the_item_through_statuses(client, seeded):
    client.post("/items/3/approve-all")
    assert {l["state"] for l in db.list_listings(seeded, item_id=3)} == {"approved"}
    assert db.get_item(seeded, 3)["status"] == "approved"
    client.post("/items/2/skip")
    assert db.get_item(seeded, 2)["status"] == "skipped"
    review = client.get("/review").text
    assert 'id="item-3"' not in review and 'id="item-2"' not in review  # decided items leave the queue


def test_not_applicable_clears_a_required_photo_and_restores(client, seeded):
    assert db.get_item(seeded, 4)["status"] == "needs_photos"
    client.post("/items/4/waive", data={"shot": "box_label"})
    assert db.get_item(seeded, 4)["waived_shots"] == ["box_label"]
    client.post("/items/4/waive", data={"shot": "box_label", "undo": "1"})
    assert db.get_item(seeded, 4)["waived_shots"] == []


def test_item_details_and_redraft_via_the_ui(client, seeded):
    client.post("/items/2/update", data={"category": "board", "brand": "Gigabyte", "model": "B450 AORUS M", "title": "B450", "condition": "like_new",
                                         "cost": "30", "notes": "Tested: boots to BIOS."})
    client.post("/items/2/redraft")
    ebay = db.get_listing_for(seeded, 2, "ebay")
    assert ebay["condition_grade"] == "like_new" and "Tested: boots to BIOS." in ebay["description"]
    assert "untested" not in ebay["description"]


def test_photo_delete_and_item_delete_remove_files(client, seeded, settings):
    photo = db.list_photos(seeded, 1)[0]
    path = settings.media_dir / "RS-0001" / "orig" / photo["filename"]
    assert path.exists()
    client.post(f"/items/1/photos/{photo['id']}/delete")
    assert not path.exists() and len(db.list_photos(seeded, 1)) == 3
    client.post("/items/1/delete")
    assert db.get_item(seeded, 1) is None
    assert list((settings.media_dir / "RS-0001" / "orig").iterdir()) == []


def test_redirect_targets_are_local_only(client, seeded):
    r = client.post("/items/3/approve-all", data={"next": "//evil.example/x"}, follow_redirects=False)
    assert r.headers["location"] == "/?msg=Approved."


# --- other pages, media, auth ---------------------------------------------------------------


def test_pages_render(client, seeded):
    for path in ("/", "/items", "/items?status=review&category=board&q=ASUS", "/items/5", "/export", "/healthz"):
        assert client.get(path).status_code == 200, path
    assert client.get("/items/999").status_code == 404
    assert client.get("/export/nope").status_code == 404
    assert "Demo mode" in client.get("/").text


def test_media_is_served_and_traversal_is_refused(client, seeded):
    photo = db.list_photos(seeded, 1)[0]
    assert client.get(f"/media/RS-0001/thumb/{photo['filename']}").headers["content-type"] == "image/jpeg"
    assert client.get(f"/media/RS-0001/orig/{photo['filename']}").status_code == 200
    assert client.get("/media/RS-0001/orig/..%2F..%2Fresale.sqlite3").status_code == 404
    assert client.get("/media/RS-0001/secret/x.jpg").status_code == 404


def test_access_token_gate(settings, monkeypatch, conn):
    monkeypatch.setenv("RESALE_ACCESS_TOKEN", "s3cret")
    from resale_app.config import get_settings

    with TestClient(create_app(get_settings())) as c:
        assert c.get("/").status_code == 401
        assert c.get("/healthz").status_code == 200
        assert c.get("/", headers={"x-resale-token": "wrong"}).status_code == 401
        ok = c.get("/?token=s3cret")
        assert ok.status_code == 200 and "resale_token" in ok.headers["set-cookie"]
        assert c.get("/items").status_code == 200  # cookie carries the session


# --- export ---------------------------------------------------------------------------------


def approve_all(conn):
    for l in db.list_listings(conn):
        db.update_listing(conn, l["id"], state="approved")


def test_export_pack_text_has_every_field(client, seeded):
    approve_all(seeded)
    text = client.get("/export/ebay/listings.txt").text
    for section in ("TITLE (", "CONDITION", "DESCRIPTION (", "ITEM SPECIFICS", "KEYWORDS", "PHOTO ORDER"):
        assert section in text
    assert "01_whole-board-top-down.jpg" in text and text.count("===") >= 8
    assert "Poshmark" not in text


def test_export_only_includes_approved_listings(client, seeded):
    assert "No approved eBay listings yet" in client.get("/export/ebay/listings.txt").text
    ebay = db.get_listing_for(seeded, 3, "ebay")
    db.update_listing(seeded, ebay["id"], state="approved")
    text = client.get("/export/ebay/listings.txt").text
    assert "RS-0003" in text and "RS-0002" not in text
    page = client.get("/export/ebay")
    assert "data-copy" in page.text and "Download pack" in page.text


def test_export_zip_has_text_and_photos_in_upload_order(client, seeded):
    db.update_listing(seeded, db.get_listing_for(seeded, 3, "poshmark")["id"], state="approved")
    r = client.get("/export/poshmark/pack.zip")
    assert r.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert "README.txt" in names and "all_listings.txt" in names
    folder = next(n for n in names if n.endswith("listing.txt")).rsplit("/", 1)[0]
    photos = sorted(n for n in names if "/photos/" in n)
    assert [p.split("/")[-1][:2] for p in photos] == ["01", "02", "03", "04", "05"]
    assert photos[0].endswith("front.jpg") or "front" in photos[0]
    assert "Carhartt" in zf.read(f"{folder}/listing.txt").decode()
    first = zf.read(photos[0])
    assert first[:2] == b"\xff\xd8"


def test_mark_posted_moves_listing_out_of_the_pack(client, seeded):
    ebay = db.get_listing_for(seeded, 3, "ebay")
    db.update_listing(seeded, ebay["id"], state="approved")
    client.post(f"/listings/{ebay['id']}/posted", data={"url": "https://ebay.example/1", "next": "/export/ebay"})
    after = db.get_listing(seeded, ebay["id"])
    assert after["state"] == "posted" and after["external_url"] == "https://ebay.example/1" and after["posted_at"]
    assert "RS-0003" not in client.get("/export/ebay/listings.txt").text


# --- demo data and CLI ----------------------------------------------------------------------


def test_demo_data_covers_each_review_state(seeded):
    statuses = {i["title"]: i["status"] for i in db.list_items(seeded)}
    assert statuses["ASUS TUF GAMING X570-PLUS"] == "needs_photos"  # blurry socket, no serial sticker
    assert statuses["Gigabyte B450 AORUS M"] == "review"
    assert statuses["Carhartt WIP Hooded Sweatshirt"] == "review"
    assert statuses["Nike Air Max 90"] == "needs_photos"
    assert statuses["Garage lot find"] == "intake"
    assert demo.seed_demo(seeded, __import__("resale_app.config", fromlist=["get_settings"]).get_settings()) == 0  # does not double up


def test_cli_seed_ingest_analyze_export(settings, jpeg, tmp_path, capsys):
    assert cli.main(["seed"]) == 0
    assert "created 8" in capsys.readouterr().out
    assert cli.main(["seed"]) == 0 and "unchanged 8" in capsys.readouterr().out

    pic = tmp_path / "RS-0001_front.jpg"
    pic.write_bytes(jpeg())
    assert cli.main(["ingest", "--keep", str(pic)]) == 0
    assert "RS-0001  added" in capsys.readouterr().out
    assert cli.main(["ingest", str(tmp_path / "nothing")]) == 1

    assert cli.main(["analyze"]) == 0
    assert "Analysed 1 item(s) in demo mode." in capsys.readouterr().out

    conn = db.connect(settings)
    for l in db.list_listings(conn, item_id=1):
        db.update_listing(conn, l["id"], state="approved")
    conn.close()
    out = tmp_path / "pack"
    assert cli.main(["export", "ebay", "--out", str(out)]) == 0
    assert (out / "all_listings.txt").read_text().count("TITLE") == 1
    assert cli.main(["export", "nope"]) == 2


def test_cli_seed_reports_a_bad_file_and_a_missing_one(settings, tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("category,brand\nspaceship,Nope\n")
    assert cli.main(["seed", "--file", str(bad)]) == 1
    assert "unknown category" in capsys.readouterr().err
    assert cli.main(["seed", "--file", str(tmp_path / "missing.csv")]) == 2


def test_cli_watch_once(settings, jpeg, capsys):
    drop = settings.drop_dir / "boards" / "Test board"
    drop.mkdir(parents=True)
    (drop / "front.jpg").write_bytes(jpeg())
    import os, time

    old = time.time() - 60
    os.utime(drop / "front.jpg", (old, old))
    assert cli.main(["watch", "--once", "--stable", "0"]) == 0
    assert "ok" in capsys.readouterr().out
