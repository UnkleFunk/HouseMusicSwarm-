import os
import time

from resale_app import db, ingest, watcher


def drop_file(settings, rel, jpeg, seed=0, age=0.0):
    path = settings.drop_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jpeg(seed=seed))
    if age:
        t = time.time() - age
        os.utime(path, (t, t))
    return path


def test_folder_per_item_creates_one_item_with_all_its_photos(settings, conn, jpeg):
    files = [drop_file(settings, f"ASUS TUF X570/IMG_{n}.jpg", jpeg, seed=n) for n in range(3)]
    results = ingest.ingest_paths(files, settings)
    assert [r.error for r in results] == ["", "", ""]
    (item,) = db.list_items(conn)
    assert item["title"] == "ASUS TUF X570" and item["photo_count"] == 3 and item["category"] == "unknown"
    assert sum(r.created for r in results) == 1


def test_category_folder_sets_the_category(settings, conn, jpeg):
    f = drop_file(settings, "boards/Gigabyte B450/front.jpg", jpeg)
    ingest.ingest_paths([f], settings)
    (item,) = db.list_items(conn)
    assert item["category"] == "board" and item["title"] == "Gigabyte B450"


def test_sku_in_filename_or_folder_adds_to_the_existing_item(settings, conn, jpeg):
    item = db.create_item(conn, category="board", brand="ASUS")
    a = drop_file(settings, "RS-0001_socket.jpg", jpeg, seed=1)
    b = drop_file(settings, "RS-0001/back.jpg", jpeg, seed=2)
    results = ingest.ingest_paths([a, b], settings)
    assert all(r.sku == "RS-0001" and not r.created for r in results)
    assert len(db.list_photos(conn, item["id"])) == 2


def test_unknown_sku_is_a_failure_not_a_new_item(settings, conn, jpeg):
    f = drop_file(settings, "RS-0099_front.jpg", jpeg)
    (r,) = ingest.ingest_paths([f], settings)
    assert "RS-0099" in r.error and db.list_items(conn) == []
    assert (settings.drop_dir / "_failed" / "RS-0099_front.jpg").exists()
    assert "RS-0099" in (settings.drop_dir / "_failed" / "RS-0099_front.jpg.error.txt").read_text()


def test_loose_photos_taken_together_become_one_item(settings, conn, jpeg):
    files = [drop_file(settings, f"IMG_{n}.jpg", jpeg, seed=n) for n in range(4)]
    for f in files:  # one at a time, the way Hazel hands them over
        ingest.ingest_paths([f], settings)
    (item,) = db.list_items(conn)
    assert item["photo_count"] == 4 and item["intake_key"].startswith("drop:batch:unknown:")


def test_loose_photos_after_a_long_gap_start_a_new_item(settings, conn, jpeg, monkeypatch):
    monkeypatch.setenv("RESALE_BATCH_GAP_SECONDS", "0")
    from resale_app.config import get_settings

    s = get_settings()
    ingest.ingest_paths([drop_file(s, "a.jpg", jpeg, seed=1)], s)
    time.sleep(0.05)
    ingest.ingest_paths([drop_file(s, "b.jpg", jpeg, seed=2)], s)
    assert len(db.list_items(conn)) == 2


def test_files_are_moved_to_processed_and_duplicates_are_noted(settings, conn, jpeg):
    first = drop_file(settings, "Hoodie/a.jpg", jpeg, seed=5)
    (r1,) = ingest.ingest_paths([first], settings)
    assert not first.exists() and "_processed" in r1.moved_to
    again = drop_file(settings, "Hoodie/a-copy.jpg", jpeg, seed=5)  # identical bytes
    (r2,) = ingest.ingest_paths([again], settings)
    assert r2.duplicate and not r2.added and not again.exists()
    assert db.list_items(conn)[0]["photo_count"] == 1


def test_non_images_and_files_outside_the_drop_folder(settings, conn, jpeg, tmp_path):
    junk = settings.drop_dir / "notes.txt"
    junk.parent.mkdir(parents=True)
    junk.write_text("hi")
    (r,) = ingest.ingest_paths([junk], settings)
    assert "not an image" in r.error and (settings.drop_dir / "_failed" / "notes.txt").exists()
    outside = tmp_path / "camera" / "IMG_9.jpg"
    outside.parent.mkdir()
    outside.write_bytes(jpeg())
    (r2,) = ingest.ingest_paths([outside], settings)
    assert not r2.error and outside.exists() and not r2.moved_to  # not ours to move


def test_keep_flag_leaves_files_in_place(settings, jpeg):
    f = drop_file(settings, "Thing/a.jpg", jpeg)
    ingest.ingest_paths([f], settings, move=False)
    assert f.exists()


def test_ingest_queues_analysis_with_the_settle_delay(settings, conn, jpeg, monkeypatch):
    monkeypatch.setenv("RESALE_SETTLE_SECONDS", "600")
    from resale_app.config import get_settings

    s = get_settings()
    ingest.ingest_paths([drop_file(s, "Thing/a.jpg", jpeg)], s)
    (item,) = db.list_items(conn)
    assert item["analysis_status"] == "queued" and item["analyze_after"] > time.time() + 500
    assert db.claim_next_analysis(conn) is None  # still settling
    ingest.ingest_paths([drop_file(s, "Thing/b.jpg", jpeg, seed=2)], s, analyze=False)
    assert db.claim_next_analysis(conn, now=time.time() + 700) == item["id"]


def test_listed_items_are_not_requeued(settings, conn, jpeg):
    item = db.create_item(conn, status="listed")
    ingest.ingest_paths([drop_file(settings, "RS-0001_extra.jpg", jpeg)], settings)
    assert db.get_item(conn, item["id"])["analysis_status"] == "idle"


def test_directories_are_expanded_but_processed_folders_are_skipped(settings, conn, jpeg):
    drop_file(settings, "Thing/a.jpg", jpeg, seed=1)
    drop_file(settings, "_processed/2020-01-01/old.jpg", jpeg, seed=2)
    results = ingest.ingest_paths([settings.drop_dir], settings)
    assert len(results) == 1


# --- watcher ---------------------------------------------------------------------------------


def test_watcher_waits_for_a_file_to_stop_changing(settings, conn, jpeg):
    w = watcher.Watcher(settings, stable_seconds=5)
    path = drop_file(settings, "Thing/a.jpg", jpeg, age=60)
    assert w.scan() == []  # first sighting
    assert w.scan() == [path]  # unchanged on the second scan
    path.unlink()  # what ingest does: move it out of the drop folder
    path2 = drop_file(settings, "Thing/b.jpg", jpeg, seed=2, age=60)
    w.scan()
    path2.write_bytes(jpeg(seed=3) + b"more")  # still growing
    assert w.scan() == []


def test_watcher_ignores_fresh_hidden_partial_and_non_image_files(settings, jpeg):
    w = watcher.Watcher(settings, stable_seconds=5)
    drop_file(settings, "Thing/fresh.jpg", jpeg, seed=1, age=0)  # too new
    drop_file(settings, ".hidden.jpg", jpeg, seed=2, age=60)
    drop_file(settings, "Thing/dl.jpg.crdownload", jpeg, seed=3, age=60)
    (settings.drop_dir / "readme.txt").write_text("x")
    drop_file(settings, "_failed/old.jpg", jpeg, seed=4, age=60)
    w.scan()
    assert w.scan() == []


def test_watcher_run_once_ingests_ready_files_and_moves_them(settings, conn, jpeg):
    w = watcher.Watcher(settings, stable_seconds=0)
    drop_file(settings, "boards/Board A/front.jpg", jpeg, seed=1, age=30)
    drop_file(settings, "boards/Board A/socket.jpg", jpeg, seed=2, age=30)
    assert w.run_once() == []
    results = w.run_once()
    assert len(results) == 2 and all(not r.error for r in results)
    (item,) = db.list_items(conn)
    assert item["photo_count"] == 2 and item["category"] == "board"
    assert w.run_once() == []  # moved out, nothing left to do


def test_watcher_with_no_drop_folder_is_a_no_op(settings):
    assert watcher.Watcher(settings).scan() == []
