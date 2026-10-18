"""Per-platform listing drafts: title, description, specs, condition grade, keywords, photo order.

Drafts are built from a Facts bundle assembled in code (seller notes, what the vision step
read, which photos the seller waived). Live mode asks Claude to write in the house voice;
demo mode uses a plain template. Either way the same guards run afterwards:

- titles and descriptions are fitted to each platform's limits,
- an untested electronics item is always described as untested,
- shots marked "no box" etc. are stated in the listing,
- serial numbers never reach a public listing,
- the voice linter flags hype so the review card can show it.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from . import llm, voice
from .categories import GRADES, CATEGORIES, photo_order, waived_facts
from .config import Settings
from .models import Analysis, DraftsWire, DraftWire
from .platforms import Platform, check_draft, fit_description, fit_title, platforms_for

NOT_WORKING_RE = re.compile(
    r"\b(not working"
    r"|(?:does not|doesn'?t|will not|won'?t|can'?t|cannot|fails? to|failed to)\s+(?:work|boot|post|power(?: on| up)?|start|turn on)"
    r"|no post|no boot|dead|for parts|broken)\b",
    re.I,
)
_WORKING = re.compile(r"\b(tested|works|working|boots|posts|verified)\b", re.I)
_UNTESTED_SAID = re.compile(r"untested|not tested|haven'?t tested|have not tested|couldn'?t test|not been tested", re.I)
_NOT_WORKING_SAID = re.compile(r"not working|does not work|doesn'?t work|for parts|for repair", re.I)
_PRIVATE_SPEC_NAMES = re.compile(r"serial|imei|s/n", re.I)

_TITLE_ATTRS = {
    "board": ("Socket", "Chipset", "Form Factor"),
    "clothing": ("Size", "Color"),
    "sneakers": ("Size", "Colorway", "Color"),
}
_CATEGORY_WORD = {"board": "Motherboard", "clothing": "", "sneakers": "Sneakers", "other": "", "unknown": ""}


@dataclass
class Facts:
    sku: str
    category: str
    brand: str
    model: str
    product_name: str
    condition: str
    condition_rationale: str
    flaws: list[str]
    attributes: list[tuple[str, str]]
    model_numbers: list[str]  # public identifiers only; serials are left out
    seller_notes: str
    functional_status: str  # tested_working | not_working | untested | n/a
    testing_notes: list[str] = field(default_factory=list)  # the seller's own words about testing
    waived: list[tuple[str, str]] = field(default_factory=list)  # (sentence, keyword)
    unknowns: list[str] = field(default_factory=list)
    photo_count: int = 0

    def for_prompt(self) -> dict[str, Any]:
        d = asdict(self)
        d["waived"] = [fact for fact, _ in self.waived]
        d["attributes"] = [{"name": n, "value": v} for n, v in self.attributes]
        d["condition_label"] = GRADES[self.condition].label
        d["condition_definition"] = GRADES[self.condition].definition
        return d


def functional_status(category: str, notes: str) -> str:
    """What the seller has actually said about whether an electronic item works."""
    if category != "board":
        return "n/a"
    if NOT_WORKING_RE.search(notes):
        return "not_working"
    if _WORKING.search(notes):
        return "tested_working"
    return "untested"


def testing_notes(category: str, notes: str) -> list[str]:
    """Sentences from the seller's notes that describe testing, minus anything about price."""
    if category != "board":
        return []
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+|[;\n]+", notes):
        sentence = sentence.strip()
        if sentence and _WORKING.search(sentence) and not voice.lint(sentence) and "$" not in sentence:
            out.append(sentence.rstrip(".") + ".")
    return out


def build_facts(item: dict[str, Any], analysis: Analysis, photo_count: int) -> Facts:
    category = item["category"] if item["category"] in CATEGORIES else analysis.category
    grade = item["condition"] if item.get("condition") in GRADES else analysis.suggested_condition
    brand = item.get("brand") or analysis.brand
    model = item.get("model") or analysis.model
    attrs = [(a.name.strip(), a.value.strip()) for a in analysis.attributes if a.name.strip() and a.value.strip()]
    public_numbers = [n.value for n in analysis.model_numbers if n.kind != "serial" and n.value.strip() and n.value != model]
    return Facts(
        sku=item["sku"],
        category=category,
        brand=brand,
        model=model,
        product_name=analysis.product_name or CATEGORIES[category].label.lower(),
        condition=grade,
        condition_rationale=analysis.condition_rationale,
        flaws=[f.description for f in analysis.flaws],
        attributes=attrs,
        model_numbers=public_numbers,
        seller_notes=item.get("notes", ""),
        functional_status=functional_status(category, item.get("notes", "")),
        testing_notes=testing_notes(category, item.get("notes", "")),
        waived=waived_facts(category, item.get("waived_shots", [])),
        unknowns=list(analysis.unknowns),
        photo_count=photo_count,
    )


# --- demo / template drafting -------------------------------------------------------------


def _join(*parts: str) -> str:
    return " ".join(p.strip() for p in parts if p and p.strip())


def _attr(facts: Facts, *names: str) -> str:
    wanted = {n.lower() for n in names}
    for name, value in facts.attributes:
        if name.lower() in wanted:
            return value
    return ""


_GRADE_SENTENCE = {
    "new": "Brand new and unused.",
    "like_new": "Used lightly. I don't see any wear.",
    "good": "Used, with normal light wear.",
    "fair": "Used, with visible wear. Details below.",
    "for_parts": "Sold for parts or repair, as is.",
}


def template_draft(platform: Platform, facts: Facts) -> DraftWire:
    """A plain, honest draft built straight from the facts. No model involved."""
    word = _CATEGORY_WORD.get(facts.category, "")
    key_specs = [v for name in _TITLE_ATTRS.get(facts.category, ()) if (v := _attr(facts, name))]
    name = facts.model or facts.product_name
    title_parts = [facts.brand, name]
    if word and word.lower() not in name.lower():
        title_parts.append(word)
    title_parts += key_specs[:2]
    title = _join(*title_parts)
    if facts.category in ("clothing", "sneakers") and facts.condition == "new":
        title = _join(title, "NWT")

    opener_subject = _join(facts.brand, name, "motherboard" if facts.category == "board" and "motherboard" not in name.lower() else "")
    if facts.category in ("clothing", "sneakers"):
        size = _attr(facts, "Size")
        opener_subject = _join(facts.brand, name, facts.product_name if facts.product_name.lower() not in name.lower() else "")
        opener = f"{opener_subject}{', size ' + size if size else ''}."
    else:
        opener = f"{opener_subject}."
    lines = [opener, f"Condition: {GRADES[facts.condition].label}. {_GRADE_SENTENCE[facts.condition]}"]
    if facts.functional_status == "tested_working" and facts.testing_notes:
        lines.append(" ".join(facts.testing_notes))  # the seller's own words, verbatim

    if facts.flaws:
        lines += ["", "What to know:"] + [f"- {f.rstrip('.')}." for f in facts.flaws]
    elif facts.category == "board":
        lines += ["", "I haven't found cosmetic flaws, but the photos can't show everything. Please look closely at the socket photo."]
    else:
        lines += ["", "I didn't find any flaws. If something is unclear in the photos, ask and I'll send more."]

    specs = [(n, v) for n, v in facts.attributes if not _PRIVATE_SPEC_NAMES.search(n)]
    if facts.model_numbers:
        specs.append(("Other model numbers", ", ".join(facts.model_numbers)))
    if specs:
        lines += ["", "Details:"] + [f"- {n}: {v}" for n, v in specs]

    lines += ["", "Happy to send more photos or answer questions."]
    description = "\n".join(lines)

    keywords = [facts.brand, facts.model, facts.product_name, _CATEGORY_WORD.get(facts.category, ""), *[v for _, v in facts.attributes]]
    return DraftWire(
        platform=platform.id,
        title=title,
        description=description,
        specs=[{"name": n, "value": v} for n, v in specs],
        keywords=keywords,
    )


# --- live drafting ------------------------------------------------------------------------

_DRAFT_SYSTEM = (
    "You write marketplace listings for a small reseller from a bundle of facts. The facts are everything you know; "
    "do not add specs, history or claims that are not in them.\n\n"
    + voice.VOICE_GUIDE
    + "\nFor each platform requested, return one draft: title (within the platform's title limit), description "
    "(within its description limit, plain text, blank lines between paragraphs), specs (name/value pairs for item specifics; "
    "no serial numbers), and keywords (search terms, most useful first, at most 12). Do not include the condition grade in specs; "
    "it is handled separately. If functional_status is 'untested', say plainly that it is untested. If 'not_working', say it is sold for parts or repair. "
    "State every entry in 'waived' as a sentence in the description. List every flaw. "
    "'testing_notes' are the seller's own statements about testing; you may restate them, and nothing beyond them."
)


def _live_drafts(facts: Facts, platforms: list[Platform], settings: Settings, client: Any) -> list[DraftWire]:
    import json

    brief = {
        "facts": facts.for_prompt(),
        "platforms": [
            {
                "id": p.id,
                "label": p.label,
                "title_max_chars": p.title_max,
                "description_max_chars": p.desc_max,
                "guidance": p.guidance,
                "condition_wording": p.condition_labels[facts.condition],
            }
            for p in platforms
        ],
    }
    result = llm.parse_structured(
        client or llm.get_client(),
        model=settings.draft_model,
        system=_DRAFT_SYSTEM,
        content="Write the listing drafts.\n\n" + json.dumps(brief, indent=2),
        output_format=DraftsWire,
    )
    return result.drafts


# --- guards and assembly ------------------------------------------------------------------


def _clean_keywords(words: list[str], limit: int = 12) -> list[str]:
    seen, out = set(), []
    for w in words:
        w = re.sub(r"\s+", " ", w).strip(" ,;")
        if w and w.lower() not in seen:
            seen.add(w.lower())
            out.append(w)
    return out[:limit]


def _guard_extras(description: str, facts: Facts) -> str:
    """Sentences the listing must carry, added only if the draft does not already say them."""
    extras = []
    if facts.functional_status == "untested" and not _UNTESTED_SAID.search(description):
        extras.append("I haven't tested it, so it's sold as untested.")
    if facts.functional_status == "not_working" and not _NOT_WORKING_SAID.search(description):
        extras.append("It does not work and is sold for parts or repair.")
    for sentence, keyword in facts.waived:
        if keyword.lower() not in description.lower():
            extras.append(sentence)
    return "\n".join(extras)


def finalize(draft: DraftWire, platform: Platform, facts: Facts, ordered_photo_ids: list[int]) -> dict[str, Any]:
    """Apply limits and honesty guards; return the fields to store on the listing."""
    title = fit_title(draft.title, platform.title_max)
    extras = _guard_extras(draft.description, facts)
    budget = platform.desc_max - (len(extras) + 2 if extras else 0)
    description = fit_description(draft.description, budget)
    if extras:
        description = f"{description}\n\n{extras}"
    specs = [
        {"name": s.name.strip(), "value": s.value.strip()}
        for s in draft.specs
        if s.name.strip() and s.value.strip() and not _PRIVATE_SPEC_NAMES.search(s.name)
    ]
    shown = ordered_photo_ids[: platform.max_photos]
    warnings = check_draft(platform, title, description, len(ordered_photo_ids))
    own_words = [facts.brand, facts.model, *facts.model_numbers, *(v for _, v in facts.attributes)]
    warnings += voice.lint(f"{title}\n{description}", allow=own_words)
    return {
        "title": title,
        "description": description,
        "specs": specs,
        "condition_grade": facts.condition,
        "keywords": _clean_keywords(draft.keywords),
        "photo_order": shown,
        "warnings": warnings,
    }


def draft_listings(
    item: dict[str, Any],
    analysis: Analysis,
    photos: list[dict[str, Any]],
    settings: Settings,
    client: Any = None,
) -> dict[str, dict[str, Any]]:
    """platform id -> listing fields, ready for db.save_listing."""
    facts = build_facts(item, analysis, len(photos))
    targets = platforms_for(facts.category)
    if settings.mode == "demo":
        drafts = [template_draft(p, facts) for p in targets]
    else:
        drafts = _live_drafts(facts, targets, settings, client)
    by_platform = {d.platform: d for d in drafts}
    ordered = photo_order(facts.category, [(p["id"], p.get("shot")) for p in photos])
    out = {}
    for platform in targets:
        draft = by_platform.get(platform.id) or template_draft(platform, facts)  # never leave a platform blank
        out[platform.id] = finalize(draft, platform, facts, ordered)
    return out
