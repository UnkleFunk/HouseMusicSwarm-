"""FastAPI app: dashboard, phone upload, review cards, edit/approve/skip, export packs.

Routes are plain sync functions (FastAPI runs them in a thread pool), because photo handling
with Pillow is CPU work and sqlite3 is synchronous.
"""

from __future__ import annotations

import hmac
import re
import sqlite3
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db, export, images, pipeline, voice, worker
from .categories import (
    CATEGORIES, GRADES, ITEM_CATEGORY_CHOICES, photo_order, required_missing, shot_label,
)
from .config import PACKAGE_DIR, Settings, get_settings
from .platforms import PLATFORMS, check_draft

NEXT_RE = re.compile(r"^/[^/\\]")


def create_app(settings: Settings | None = None, llm_client: Any = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stop = None
        if settings.worker_enabled:
            _thread, stop = worker.start_thread(settings, llm_client)
        yield
        if stop is not None:
            stop.set()

    app = FastAPI(title="Resale", lifespan=lifespan)
    app.state.settings = settings
    app.state.llm_client = llm_client
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
    templates.env.filters["money"] = db.format_money
    templates.env.filters["dollars"] = lambda cents: "" if cents is None else f"{cents / 100:.2f}"
    templates.env.globals.update(
        GRADES=GRADES, PLATFORMS=PLATFORMS, CATEGORIES=CATEGORIES, CATEGORY_CHOICES=ITEM_CATEGORY_CHOICES,
        ITEM_STATUSES=db.ITEM_STATUSES, shot_label=shot_label,
    )

    # --- plumbing ---------------------------------------------------------------------

    @app.middleware("http")
    async def token_gate(request: Request, call_next):
        token = settings.access_token
        if not token or request.url.path == "/healthz":
            return await call_next(request)
        supplied = request.query_params.get("token") or request.headers.get("x-resale-token") or request.cookies.get("resale_token") or ""
        if not hmac.compare_digest(supplied.encode(), token.encode()):
            return PlainTextResponse("Unauthorized. Open the app with ?token=<your RESALE_ACCESS_TOKEN> once.", status_code=401)
        response = await call_next(request)
        if request.query_params.get("token"):
            response.set_cookie("resale_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 90)
        return response

    def get_conn(request: Request):
        conn = db.connect(request.app.state.settings)
        try:
            yield conn
        finally:
            conn.close()

    def render(request: Request, name: str, **ctx: Any) -> Response:
        ctx.setdefault("mode", settings.mode)
        ctx.setdefault("msg", request.query_params.get("msg", ""))
        return templates.TemplateResponse(request, name, ctx)

    def go(url: str, msg: str = "") -> RedirectResponse:
        if not NEXT_RE.match(url):
            url = "/"
        base, hash_, frag = url.partition("#")
        if msg:
            base += ("&" if "?" in base else "?") + "msg=" + quote(msg)
        return RedirectResponse(base + (hash_ + frag), status_code=303)

    def require_item(conn: sqlite3.Connection, item_id: int) -> dict[str, Any]:
        item = db.get_item(conn, item_id)
        if item is None:
            raise HTTPException(404, "No such item")
        return item

    def build_entry(conn: sqlite3.Connection, item: dict[str, Any]) -> dict[str, Any]:
        photos = db.list_photos(conn, item["id"])
        analysis = pipeline.stored_analysis(conn, item["id"])
        missing = pipeline.missing_for(item, photos, analysis)
        by_id = {p["id"]: p for p in photos}
        listings = []
        for listing in db.list_listings(conn, item_id=item["id"]):
            listing["platform_obj"] = PLATFORMS.get(listing["platform"])
            listing["ordered_photos"] = [by_id[i] for i in listing["photo_order"] if i in by_id]
            listings.append(listing)
        category = item["category"]
        strip_ids = photo_order(category, [(p["id"], p.get("shot")) for p in photos])
        return {
            "item": item,
            "photos": photos,
            "strip": [by_id[i] for i in strip_ids],
            "analysis": analysis,
            "missing": missing,
            "required_gaps": bool(required_missing(missing)),
            "listings": listings,
            "pending": sum(1 for l in listings if l["state"] == "draft"),
        }

    # --- pages ------------------------------------------------------------------------

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "mode": settings.mode}

    @app.get("/")
    def dashboard(request: Request, conn=Depends(get_conn)):
        counts = db.counts_by_status(conn)
        busy = conn.execute("SELECT COUNT(*) FROM items WHERE analysis_status IN ('queued','running')").fetchone()[0]
        errors = conn.execute("SELECT COUNT(*) FROM items WHERE analysis_status = 'error'").fetchone()[0]
        approved = {p: len(db.list_listings(conn, platform=p, state="approved")) for p in PLATFORMS}
        return render(request, "dashboard.html", counts=counts, busy=busy, errors=errors, approved=approved, total=sum(counts.values()))

    @app.get("/items")
    def items_page(request: Request, status: str = "", category: str = "", q: str = "", conn=Depends(get_conn)):
        items = db.list_items(conn, status=status or None, category=category or None, q=q or None)
        return render(request, "items.html", items=items, status=status, category=category, q=q)

    @app.get("/items/{item_id}")
    def item_page(request: Request, item_id: int, conn=Depends(get_conn)):
        item = require_item(conn, item_id)
        return render(request, "item.html", e=build_entry(conn, item), next_url=f"/items/{item_id}")

    @app.get("/review")
    def review_page(request: Request, conn=Depends(get_conn)):
        items = db.list_items(conn, status="review") + db.list_items(conn, status="needs_photos")
        entries = [build_entry(conn, i) for i in items]
        busy = conn.execute("SELECT COUNT(*) FROM items WHERE analysis_status IN ('queued','running')").fetchone()[0]
        return render(request, "review.html", entries=entries, busy=busy)

    @app.get("/upload")
    def upload_page(request: Request, item: int = 0, shot: str = "", conn=Depends(get_conn)):
        current = db.get_item(conn, item) if item else None
        entry = build_entry(conn, current) if current else None
        choices = [i for i in db.list_items(conn, limit=200) if i["status"] not in ("sold",)]
        return render(request, "upload.html", current=current, entry=entry, shot=shot, choices=choices)

    # --- upload (HTML form and JSON API share one handler) ----------------------------

    def receive_photos(
        conn: sqlite3.Connection, files: list[UploadFile], item_id: str, category: str, brand: str, model: str,
        notes: str, cost: str, analyze: bool,
    ) -> dict[str, Any]:
        files = [f for f in files if f.filename]
        if not files:
            raise HTTPException(400, "Choose at least one photo.")
        if item_id.strip():
            item = require_item(conn, int(item_id))
            changes = {k: v.strip() for k, v in (("brand", brand), ("model", model)) if v.strip()}
            if category in CATEGORIES and item["category"] == "unknown":
                changes["category"] = category
            if notes.strip():
                changes["notes"] = (item["notes"] + "\n" + notes.strip()).strip()
            if db.parse_money(cost) is not None and item["cost_basis_cents"] is None:
                changes["cost_basis_cents"] = db.parse_money(cost)
            item = db.update_item(conn, item["id"], **changes) if changes else item
            created = False
        else:
            cat = category if category in CATEGORIES else "unknown"
            title = " ".join(p for p in (brand.strip(), model.strip()) if p) or "New item"
            item = db.create_item(conn, category=cat, brand=brand.strip(), model=model.strip(), title=title,
                                  notes=notes.strip(), cost_basis_cents=db.parse_money(cost))
            created = True
        added, duplicates, errors = 0, 0, []
        for f in files:
            try:
                stored = images.store_photo(conn, settings, item, f.filename or "photo", f.file.read())
                added += 0 if stored.duplicate else 1
                duplicates += 1 if stored.duplicate else 0
            except images.ImageError as exc:
                errors.append(str(exc))
        if added and analyze:
            db.queue_analysis(conn, item["id"], delay=0)
        return {"item": db.get_item(conn, item["id"]), "created": created, "added": added, "duplicates": duplicates, "errors": errors}

    @app.post("/upload")
    def upload_submit(
        conn=Depends(get_conn), files: list[UploadFile] = File(default=[]), item_id: str = Form(""),
        category: str = Form("unknown"), brand: str = Form(""), model: str = Form(""), notes: str = Form(""),
        cost: str = Form(""), analyze: str = Form(""),
    ):
        r = receive_photos(conn, files, item_id, category, brand, model, notes, cost, bool(analyze))
        bits = [f"{r['added']} photo{'s' if r['added'] != 1 else ''} added"]
        if r["duplicates"]:
            bits.append(f"{r['duplicates']} already there")
        if r["errors"]:
            bits.append("skipped: " + "; ".join(r["errors"]))
        if r["added"] and analyze:
            bits.append("reading them now")
        return go(f"/items/{r['item']['id']}", ". ".join(bits) + ".")

    @app.post("/api/upload")
    def api_upload(
        conn=Depends(get_conn), files: list[UploadFile] = File(default=[]), item_id: str = Form(""),
        category: str = Form("unknown"), brand: str = Form(""), model: str = Form(""), notes: str = Form(""),
        cost: str = Form(""), analyze: str = Form("1"),
    ):
        """Same as the upload page, but returns JSON. Handy for an Apple Shortcut or a script."""
        r = receive_photos(conn, files, item_id, category, brand, model, notes, cost, analyze not in ("", "0", "false"))
        return {"sku": r["item"]["sku"], "id": r["item"]["id"], "created": r["created"], "added": r["added"],
                "duplicates": r["duplicates"], "errors": r["errors"]}

    @app.get("/api/items")
    def api_items(status: str = "", conn=Depends(get_conn)):
        return [{k: i[k] for k in ("id", "sku", "category", "brand", "model", "title", "status", "condition", "photo_count")}
                for i in db.list_items(conn, status=status or None)]

    # --- item actions -----------------------------------------------------------------

    @app.post("/items/{item_id}/update")
    def item_update(
        item_id: int, conn=Depends(get_conn), category: str = Form("unknown"), brand: str = Form(""), model: str = Form(""),
        title: str = Form(""), condition: str = Form(""), cost: str = Form(""), notes: str = Form(""), next: str = Form(""),
    ):
        require_item(conn, item_id)
        db.update_item(
            conn, item_id,
            category=category if category in CATEGORIES else "unknown", brand=brand.strip(), model=model.strip(),
            title=title.strip(), condition=condition if condition in GRADES else None,
            cost_basis_cents=db.parse_money(cost), notes=notes.strip(),
        )
        pipeline.refresh_status(conn, item_id)
        return go(next or f"/items/{item_id}", "Details saved. Use Redraft to rewrite the listings with them.")

    @app.post("/items/{item_id}/analyze")
    def item_analyze(item_id: int, conn=Depends(get_conn), next: str = Form("")):
        item = require_item(conn, item_id)
        if not db.list_photos(conn, item_id):
            return go(next or f"/items/{item_id}", "Add photos first.")
        db.queue_analysis(conn, item["id"], delay=0)
        return go(next or f"/items/{item_id}", "Reading the photos.")

    @app.post("/items/{item_id}/redraft")
    def item_redraft(item_id: int, request: Request, conn=Depends(get_conn), force: str = Form(""), next: str = Form("")):
        require_item(conn, item_id)
        try:
            counts = pipeline.redraft(conn, item_id, settings, request.app.state.llm_client, force=bool(force))
        except Exception as exc:
            return go(next or f"/items/{item_id}", f"Could not redraft: {exc}")
        msg = f"Redrafted {counts['created'] + counts['updated']} listing(s)."
        if counts["kept"]:
            msg += f" Kept {counts['kept']} you already edited or decided."
        return go(next or f"/items/{item_id}", msg)

    @app.post("/items/{item_id}/waive")
    def item_waive(item_id: int, conn=Depends(get_conn), shot: str = Form(...), undo: str = Form(""), next: str = Form("")):
        item = require_item(conn, item_id)
        waived = set(item["waived_shots"])
        waived.discard(shot) if undo else waived.add(shot)
        db.update_item(conn, item_id, waived_shots=sorted(waived))
        pipeline.refresh_status(conn, item_id)
        return go(next or f"/items/{item_id}", "Marked not applicable. Redraft to put it in the listing." if not undo else "Photo request restored.")

    @app.post("/items/{item_id}/approve-all")
    def item_approve_all(item_id: int, conn=Depends(get_conn), next: str = Form("")):
        require_item(conn, item_id)
        for l in db.list_listings(conn, item_id=item_id, state="draft"):
            db.update_listing(conn, l["id"], state="approved")
        pipeline.refresh_status(conn, item_id)
        return go(next or f"/items/{item_id}", "Approved.")

    @app.post("/items/{item_id}/skip")
    def item_skip(item_id: int, conn=Depends(get_conn), next: str = Form("")):
        require_item(conn, item_id)
        for l in db.list_listings(conn, item_id=item_id, state="draft"):
            db.update_listing(conn, l["id"], state="skipped")
        pipeline.refresh_status(conn, item_id)
        return go(next or "/review", "Skipped.")

    @app.post("/items/{item_id}/delete")
    def item_delete(item_id: int, conn=Depends(get_conn)):
        item = require_item(conn, item_id)
        for p in db.list_photos(conn, item_id):
            images.remove_photo_files(settings, item["sku"], p["filename"])
        db.delete_item(conn, item_id)
        return go("/items", f"Deleted {item['sku']}.")

    @app.post("/items/{item_id}/photos/{photo_id}/delete")
    def photo_delete(item_id: int, photo_id: int, conn=Depends(get_conn)):
        item = require_item(conn, item_id)
        photo = db.get_photo(conn, photo_id)
        if photo is None or photo["item_id"] != item_id:
            raise HTTPException(404, "No such photo")
        images.remove_photo_files(settings, item["sku"], photo["filename"])
        db.delete_photo(conn, photo_id)
        return go(f"/items/{item_id}", "Photo removed. Re-read the photos to refresh the drafts.")

    # --- listing actions --------------------------------------------------------------

    def require_listing(conn: sqlite3.Connection, listing_id: int) -> dict[str, Any]:
        listing = db.get_listing(conn, listing_id)
        if listing is None:
            raise HTTPException(404, "No such listing")
        return listing

    def set_state(conn: sqlite3.Connection, listing_id: int, state: str, **extra: Any) -> dict[str, Any]:
        listing = require_listing(conn, listing_id)
        db.update_listing(conn, listing_id, state=state, **extra)
        pipeline.refresh_status(conn, listing["item_id"])
        return listing

    @app.post("/listings/{listing_id}/approve")
    def listing_approve(listing_id: int, conn=Depends(get_conn), next: str = Form("")):
        l = set_state(conn, listing_id, "approved")
        return go(next or f"/items/{l['item_id']}", "Approved.")

    @app.post("/listings/{listing_id}/skip")
    def listing_skip(listing_id: int, conn=Depends(get_conn), next: str = Form("")):
        l = set_state(conn, listing_id, "skipped")
        return go(next or f"/items/{l['item_id']}", "Skipped.")

    @app.post("/listings/{listing_id}/reopen")
    def listing_reopen(listing_id: int, conn=Depends(get_conn), next: str = Form("")):
        l = set_state(conn, listing_id, "draft")
        return go(next or f"/items/{l['item_id']}", "Back in the review queue.")

    @app.post("/listings/{listing_id}/posted")
    def listing_posted(listing_id: int, conn=Depends(get_conn), url: str = Form(""), next: str = Form("")):
        l = set_state(conn, listing_id, "posted", external_url=url.strip(), posted_at=db.now_iso())
        return go(next or f"/items/{l['item_id']}", "Marked as posted.")

    @app.post("/listings/{listing_id}/edit")
    def listing_edit(
        listing_id: int, conn=Depends(get_conn), title: str = Form(""), description: str = Form(""),
        condition_grade: str = Form(""), specs: str = Form(""), keywords: str = Form(""), price: str = Form(""),
        next: str = Form(""),
    ):
        listing = require_listing(conn, listing_id)
        platform = PLATFORMS[listing["platform"]]
        item = db.get_item(conn, listing["item_id"])
        spec_list = []
        for line in specs.splitlines():
            name, sep, value = line.partition(":")
            if sep and name.strip() and value.strip():
                spec_list.append({"name": name.strip(), "value": value.strip()})
        kw = [k.strip() for k in re.split(r"[,\n]", keywords) if k.strip()]
        warnings = check_draft(platform, title.strip(), description.strip(), len(listing["photo_order"]))
        warnings += voice.lint(f"{title}\n{description}", allow=[item["brand"], item["model"]])
        db.update_listing(
            conn, listing_id, title=title.strip(), description=description.strip(), specs=spec_list, keywords=kw,
            condition_grade=condition_grade if condition_grade in GRADES else listing["condition_grade"],
            price_cents=db.parse_money(price), warnings=warnings, edited=1,
            state="draft" if listing["state"] == "approved" else listing["state"],  # an edited approval needs a second look
        )
        pipeline.refresh_status(conn, listing["item_id"])
        return go(next or f"/items/{listing['item_id']}", "Saved your edits.")

    # --- export -----------------------------------------------------------------------

    def require_platform(platform_id: str):
        if platform_id not in PLATFORMS:
            raise HTTPException(404, "No such platform")
        return PLATFORMS[platform_id]

    @app.get("/export")
    def export_index(request: Request, conn=Depends(get_conn)):
        counts = {p: len(db.list_listings(conn, platform=p, state="approved")) for p in PLATFORMS}
        return render(request, "export_index.html", counts=counts)

    @app.get("/export/{platform_id}")
    def export_page(request: Request, platform_id: str, conn=Depends(get_conn)):
        platform = require_platform(platform_id)
        entries = export.build_entries(conn, platform_id)
        return render(request, "export.html", platform=platform, entries=entries, entry_text=export.listing_text)

    @app.get("/export/{platform_id}/listings.txt")
    def export_txt(platform_id: str, conn=Depends(get_conn)):
        platform = require_platform(platform_id)
        text = export.pack_text(export.build_entries(conn, platform_id), platform)
        return PlainTextResponse(text, headers={"Content-Disposition": f'inline; filename="{platform_id}-listings.txt"'})

    @app.get("/export/{platform_id}/pack.zip")
    def export_zip(platform_id: str, conn=Depends(get_conn)):
        require_platform(platform_id)
        data = export.build_zip(conn, settings, platform_id)
        return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{platform_id}-listing-pack.zip"'})

    # --- media ------------------------------------------------------------------------

    @app.get("/media/{sku}/{variant}/{filename}")
    def media(sku: str, variant: str, filename: str):
        path = images.media_path(settings, sku, variant, filename)
        if path is None:
            raise HTTPException(404, "No such photo")
        return FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})

    return app
