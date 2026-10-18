"""The listing voice, and a linter that catches the hype it forbids."""

from __future__ import annotations

import re
from typing import Iterable

VOICE_GUIDE = """\
Write as the seller, in first person, the way a careful person talks to a neighbour about something they are selling.
- Warm, plain and honest. Short sentences. No hype, no sales pitch.
- Never use words like stunning, amazing, rare, grail, must-have, steal, perfect, flawless, pristine, mint, fire. No exclamation marks, no emoji, no ALL CAPS words (model codes and acronyms such as CPU, USB, DDR4 are fine).
- Say what is wrong with the item early and plainly. Flaws come before the sign-off, never buried.
- Only state what the photos show or the seller's notes say. If something is not known, say it is not known. Never guess a spec.
- Never claim an item works, is tested, or is authentic unless the seller's notes say so. For electronics with no testing noted, say it is untested.
- Never include serial numbers, what the seller paid, the seller's address or contact details, or shipping, return or pickup terms that were not given.
- Structure: one opening line (what it is and its condition), then the flaws, then what is included, then a short Details list ("- Name: value"), then a one-line close such as "Happy to send more photos or answer questions."
- Titles are plain keywords: brand, model, the one or two specs buyers filter on, size or colorway. No decorative symbols, no hype words.
"""

_HYPE_WORDS = [
    "stunning", "amazing", "incredible", "awesome", "gorgeous", "insane", "unbelievable",
    "grail", "must-have", "must have", "steal", "bargain", "wow", "fire", "killer",
    "perfect", "flawless", "pristine", "immaculate", "mint", "rare", "hard to find",
    "one of a kind", "one-of-a-kind", "collector's dream", "don't miss", "dont miss",
    "won't last", "wont last", "hurry", "best deal", "great deal", "crazy",
]
_HYPE_RE = re.compile(r"(?<![\w-])(" + "|".join(re.escape(w) for w in _HYPE_WORDS) + r")(?![\w-])", re.I)
_PAID_RE = re.compile(r"\b(i paid|paid \$|bought (it )?for|cost me|retail(ed)? (at|for))\b", re.I)
_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⬆✅❌]")
_CAPS_RE = re.compile(r"\b[A-Z]{4,}\b")
_CAPS_OK = {"DDR", "DDR4", "DDR5", "NVME", "SATA", "M.2", "AM4", "AM5", "LGA", "ATX", "MATX", "EATX", "ITX", "WIFI", "HDMI", "DISPLAYPORT", "BIOS", "UEFI", "RGB", "PCIE", "NWT", "NWOT", "USB", "ASUS", "MSI", "EVGA", "NIKE", "ADIDAS", "SIZE", "TUF", "ROG", "AORUS", "GIGABYTE", "ASROCK", "SUPERMICRO"}


def lint(text: str, allow: Iterable[str] = ()) -> list[str]:
    """Reasons a piece of listing text breaks the voice. Empty list means it reads clean.

    `allow` holds words that may be written in capitals because they are part of the item's
    own name (brand, model, spec values), e.g. "TUF GAMING" on a board.
    """
    allowed = {w.upper() for phrase in allow for w in re.split(r"[^A-Za-z0-9.]+", phrase) if w}
    problems: list[str] = []
    hype = sorted({m.group(1).lower() for m in _HYPE_RE.finditer(text)})
    if hype:
        problems.append("Hype wording: " + ", ".join(hype) + ".")
    if "!" in text:
        problems.append("Exclamation mark.")
    if _EMOJI_RE.search(text):
        problems.append("Emoji.")
    shouting = sorted({w for w in _CAPS_RE.findall(text) if w not in _CAPS_OK and w not in allowed and not re.search(r"\d", w)})
    # One stray caps word is often a brand; two or more reads as shouting.
    if len(shouting) >= 2:
        problems.append("ALL CAPS words: " + ", ".join(shouting[:5]) + ".")
    if _PAID_RE.search(text):
        problems.append("Mentions what was paid.")
    return problems
