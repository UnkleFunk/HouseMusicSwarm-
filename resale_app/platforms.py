"""Marketplace specs and the fitting/validation rules for a draft.

Limits are written from memory of each marketplace's listing form and drift over time.
Check them against the live forms before relying on them, and edit them here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Platform:
    id: str
    label: str
    title_max: int
    desc_max: int
    max_photos: int
    categories: tuple[str, ...]  # item categories this platform is offered for
    condition_labels: dict[str, str]  # our grade -> the wording in that platform's dropdown
    guidance: str  # fed to the drafting step


_ALL = ("board", "clothing", "sneakers", "other", "unknown")

PLATFORMS: dict[str, Platform] = {
    p.id: p
    for p in (
        Platform(
            id="ebay",
            label="eBay",
            title_max=80,
            desc_max=4000,
            max_photos=24,
            categories=_ALL,
            condition_labels={
                "new": "New",
                "like_new": "Open box / Like new",
                "good": "Used",
                "fair": "Used",
                "for_parts": "For parts or not working",
            },
            guidance="Buyers search by keyword, so the title carries brand, model and the one or two specs buyers filter on. The description can be detailed. Item specifics come from the specs list.",
        ),
        Platform(
            id="mercari",
            label="Mercari",
            title_max=80,
            desc_max=1000,
            max_photos=12,
            categories=_ALL,
            condition_labels={
                "new": "New",
                "like_new": "Like new",
                "good": "Good",
                "fair": "Fair",
                "for_parts": "Poor",
            },
            guidance="Casual, friendly buyers. Short paragraphs. The description is limited to 1,000 characters, so lead with what it is and its condition.",
        ),
        Platform(
            id="facebook",
            label="Facebook Marketplace",
            title_max=100,
            desc_max=9000,
            max_photos=10,
            categories=_ALL,
            condition_labels={
                "new": "New",
                "like_new": "Used - Like new",
                "good": "Used - Good",
                "fair": "Used - Fair",
                "for_parts": "Used - Fair (say 'for parts' in the description)",
            },
            guidance="Neighbors browsing quickly. Say plainly what it is, its condition, and what is included. Do not invent a pickup area, shipping terms or a price.",
        ),
        Platform(
            id="poshmark",
            label="Poshmark",
            title_max=80,
            desc_max=500,
            max_photos=16,
            categories=("clothing", "sneakers"),
            condition_labels={
                "new": "New with tags (NWT)",
                "like_new": "Used (like new)",
                "good": "Used (good)",
                "fair": "Used (fair)",
                "for_parts": "Used (see flaws)",
            },
            guidance="Fashion buyers. Size, fit, fabric and flaws matter most. The description is limited to 500 characters, so keep it tight.",
        ),
    )
}
PLATFORM_IDS = tuple(PLATFORMS)


def platforms_for(category_id: str) -> list[Platform]:
    return [p for p in PLATFORMS.values() if category_id in p.categories]


_TRAILING_JUNK = re.compile(r"[\s\-–—,;:/|]+$")


def fit_title(title: str, limit: int) -> str:
    """Trim a title to `limit` characters on a word boundary, without a dangling separator."""
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) <= limit:
        return title
    cut = title[:limit]
    if title[limit] != " " and " " in cut:  # we cut mid-word
        cut = cut[: cut.rfind(" ")]
    return _TRAILING_JUNK.sub("", cut)


def fit_description(text: str, limit: int) -> str:
    """Shorten a description to `limit` characters, dropping detail bullets first."""
    text = text.strip()
    if len(text) <= limit:
        return text
    lines = text.split("\n")
    while len("\n".join(lines).rstrip()) > limit:
        bullets = [i for i, line in enumerate(lines) if line.startswith("- ")]
        if not bullets:
            break
        del lines[bullets[-1]]
    # A "Details:" header with no bullets left is just noise.
    out = "\n".join(lines)
    out = re.sub(r"\n*Details:\s*(?=\n|$)", "", out).rstrip()
    if len(out) <= limit:
        return re.sub(r"\n{3,}", "\n\n", out)
    cut = out[:limit]
    end = max(cut.rfind(". "), cut.rfind("\n"))
    if end > limit * 0.5:
        return cut[: end + 1].rstrip()
    return cut[: cut.rfind(" ")].rstrip() if " " in cut else cut


def check_draft(platform: Platform, title: str, description: str, photo_count: int) -> list[str]:
    warnings = []
    if not title.strip():
        warnings.append("Title is empty.")
    if len(title) > platform.title_max:
        warnings.append(f"Title is {len(title)} characters; {platform.label} allows {platform.title_max}.")
    if not description.strip():
        warnings.append("Description is empty.")
    if len(description) > platform.desc_max:
        warnings.append(f"Description is {len(description)} characters; {platform.label} allows {platform.desc_max}.")
    if photo_count > platform.max_photos:
        warnings.append(f"{photo_count} photos; {platform.label} takes {platform.max_photos}, so the list is cut to the first {platform.max_photos}.")
    return warnings
