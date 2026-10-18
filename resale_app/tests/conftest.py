"""Shared fixtures: an isolated data dir, demo mode, no worker thread, a fake Claude client."""

from __future__ import annotations

import dataclasses
import io
import random
import zlib
from types import SimpleNamespace

import pytest
from PIL import Image

from resale_app import db
from resale_app.config import Settings, get_settings


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setenv("RESALE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("RESALE_DROP_DIR", str(tmp_path / "drop"))
    monkeypatch.setenv("RESALE_MODE", "demo")
    monkeypatch.setenv("RESALE_WORKER", "0")
    monkeypatch.setenv("RESALE_SETTLE_SECONDS", "0")
    monkeypatch.delenv("RESALE_ACCESS_TOKEN", raising=False)
    return get_settings()


@pytest.fixture
def live_settings(settings) -> Settings:
    return dataclasses.replace(settings, mode="live")


@pytest.fixture
def conn(settings):
    c = db.connect(settings)
    yield c
    c.close()


def jpeg_bytes(color="red", size=(640, 480), seed=0) -> bytes:
    img = Image.new("RGB", size, color)
    # A grid of large random-coloured blocks: different seeds give visibly different images,
    # which survive JPEG compression as different bytes (a single pixel would not).
    rnd = random.Random(seed)
    bw, bh = size[0] // 4, size[1] // 4
    for gx in range(4):
        for gy in range(4):
            img.paste((rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)), (gx * bw, gy * bh, (gx + 1) * bw, (gy + 1) * bh))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def jpeg():
    return jpeg_bytes


def add_photos(conn, settings, item, names):
    from resale_app import images

    out = []
    for name in names:
        seed = zlib.crc32(f"{item['id']}/{name}".encode()) % 100000  # distinct bytes per item and name
        out.append(images.store_photo(conn, settings, item, name, jpeg_bytes(seed=seed)).photo)
    return out


@pytest.fixture
def add():
    return add_photos


class FakeMessages:
    """Stands in for client.messages. Each parse() call pops the next prepared output."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        if isinstance(out, tuple) and out[0] == "refusal":
            return SimpleNamespace(parsed_output=None, stop_reason="refusal", stop_details=SimpleNamespace(category=out[1]))
        if isinstance(out, str):  # a bare stop reason, e.g. "max_tokens"
            return SimpleNamespace(parsed_output=None, stop_reason=out, stop_details=None)
        return SimpleNamespace(parsed_output=out, stop_reason="end_turn", stop_details=None)


class FakeClient:
    def __init__(self, *outputs):
        self.messages = FakeMessages(outputs)


@pytest.fixture
def fake_client():
    return FakeClient
