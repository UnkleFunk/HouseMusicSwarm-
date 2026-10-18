"""Categories, condition grades, the shot checklist per category, and missing-photo logic.

The checklist is the single source of truth for three things: the prompts shown when a
photo is missing, the order photos should go in a listing, and the guidance the vision
step receives. Missing photos are computed here from the shot labels on each photo, not
asserted by the model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Grade:
    id: str
    label: str
    definition: str


GRADES: dict[str, Grade] = {
    g.id: g
    for g in (
        Grade("new", "New", "Unused. Sealed, or with original tags."),
        Grade("like_new", "Like new", "Used lightly. No visible wear."),
        Grade("good", "Good", "Used, with normal light wear. Flaws, if any, are minor and described."),
        Grade("fair", "Fair", "Used, with visible wear or flaws. All described in the listing."),
        Grade("for_parts", "For parts or repair", "Not working, or needs work. Sold as is."),
    )
}
GRADE_IDS = tuple(GRADES)


@dataclass(frozen=True)
class ShotSpec:
    id: str
    label: str
    prompt: str
    required: bool = False
    when_flaws: bool = False  # required only when the photos show flaws
    waived_fact: str = ""  # sentence the listing states if the seller marks this shot "not applicable"
    waived_keyword: str = ""  # if this word is already in the description, skip the waived_fact


@dataclass(frozen=True)
class Category:
    id: str
    label: str
    shots: tuple[ShotSpec, ...]  # in the order they should appear in a listing
    read_guide: str  # what the vision step should look for in this category


_BOARD = Category(
    id="board",
    label="Motherboard / PC board",
    shots=(
        ShotSpec("front", "Whole board, top-down", "Lay the board flat on a plain surface and photograph the whole top side, square-on, in good light.", required=True),
        ShotSpec("socket", "CPU socket close-up", "Close-up of the CPU socket, lit from the side so every pin or contact is visible. Buyers check for bent pins first.", required=True),
        ShotSpec("io", "Rear I/O panel", "The rear I/O ports from the side, so the port count and any bent or damaged ports show.", required=True),
        ShotSpec("back", "Back of the board", "The underside of the board, flat and in focus, including any stickers, backplate or solder damage.", required=True),
        ShotSpec("serial_sticker", "Serial / model sticker", "The serial and model sticker, close enough that every character is readable.", required=True),
        ShotSpec("ram_slots", "RAM and PCIe slots", "The RAM and PCIe slots, so buyers can see the clips and latches are intact."),
        ShotSpec(
            "accessories",
            "What's included",
            "Everything that comes with it (I/O shield, SATA cables, box, manual) in one shot.",
            waived_fact="Board only. No box, I/O shield or cables.",
            waived_keyword="board only",
        ),
        ShotSpec("flaw_closeup", "Flaw close-ups", "A close-up of each flaw (scratch, bent pin, burn mark, stuck clip), with something for scale.", when_flaws=True),
    ),
    read_guide=(
        "A computer motherboard or similar board. Read the brand and model name (usually silk-screened on the PCB "
        "near the PCIe slots, or on a heatsink), the revision (REV x.xx), socket, chipset, form factor, RAM type and "
        "slot count, and the rear I/O ports. Look closely at the CPU socket for bent, missing or pushed-in pins or "
        "contacts, and say plainly if the photo is not sharp enough to tell. Note scratches, burn marks, corrosion, "
        "missing or cracked parts, stuck RAM clips and bent ports. Photos cannot show whether a board works, so never "
        "suggest it does."
    ),
)

_CLOTHING = Category(
    id="clothing",
    label="Clothing",
    shots=(
        ShotSpec("front", "Front", "The whole garment from the front, laid flat or on a hanger, in even light.", required=True),
        ShotSpec("back", "Back", "The whole garment from the back.", required=True),
        ShotSpec("brand_tag", "Brand tag", "The brand tag or neck label, flat and readable.", required=True),
        ShotSpec("size_tag", "Size and care tag", "The size and fabric/care tag, close enough to read the size, fabric percentages and origin.", required=True),
        ShotSpec("flaw_closeup", "Flaw close-ups", "A close-up of every flaw (pilling, stains, holes, fading, cracking prints, stuck zips), in daylight.", when_flaws=True),
        ShotSpec("detail", "Fabric or print detail", "A close-up of the fabric, print or hardware (zip, buttons)."),
        ShotSpec("measurements", "Measurements", "The garment flat with a tape measure for chest (pit to pit) and length."),
    ),
    read_guide=(
        "A garment. Read the brand, garment type, size from the tag, fabric content percentages, country of origin, "
        "and any style or RN/CA numbers. Note the colour. Note pilling, stains, holes, fading, cracked prints, stretched "
        "collars or cuffs, stuck zips, missing buttons. Smell and fit cannot be judged from photos."
    ),
)

_SNEAKERS = Category(
    id="sneakers",
    label="Sneakers",
    shots=(
        ShotSpec("side", "Side profile", "One shoe from the outer side, on a plain floor, in daylight.", required=True),
        ShotSpec("pair_top", "Top-down pair", "Both shoes from above, side by side."),
        ShotSpec("heel", "Heel and back", "The back of both shoes, showing heel wear and the heel tab."),
        ShotSpec("toe_box", "Toe box", "The toe box from the front, showing creasing."),
        ShotSpec("tongue_label", "Size label inside the tongue", "The label inside the tongue or under it: size, style code, production date."),
        ShotSpec(
            "box_label",
            "Box label",
            "The label on the end of the box (style code, size, colorway). No box? Mark this as not applicable and the listing will say so.",
            required=True,
            waived_fact="No original box.",
            waived_keyword="box",
        ),
        ShotSpec("soles", "Soles", "The outsoles of both shoes, flat on to the camera, showing tread wear.", required=True),
        ShotSpec("insoles", "Insoles", "The insoles with the tongue pulled forward, showing the heel and footbed wear. Pull them out if they come out.", required=True),
        ShotSpec("flaw_closeup", "Flaw close-ups", "A close-up of every flaw (scuffs, yellowing, glue gaps, midsole cracks, heel drag).", when_flaws=True),
    ),
    read_guide=(
        "Sneakers or shoes. Read the brand, model name, colorway name, style code (on the box label or the inside "
        "tongue/wall label, for example 'DM7866-001'), size (US/UK/EU) and production date. Note sole wear, creasing, "
        "yellowing, scuffs, heel drag, insole wear, glue separation and cracked midsole foam."
    ),
)

_OTHER = Category(
    id="other",
    label="Other",
    shots=(
        ShotSpec("front", "Front / overall", "The whole item in even light.", required=True),
        ShotSpec("back", "Back", "The back of the item."),
        ShotSpec("serial_sticker", "Label or serial sticker", "Any label, tag or sticker with the brand and model, close enough to read."),
        ShotSpec("flaw_closeup", "Flaw close-ups", "A close-up of every flaw.", when_flaws=True),
    ),
    read_guide="Anything else. Identify only what you can read or clearly see. Do not guess a model.",
)

CATEGORIES: dict[str, Category] = {c.id: c for c in (_BOARD, _CLOTHING, _SNEAKERS, _OTHER)}
CATEGORY_IDS = tuple(CATEGORIES)
# 'unknown' is a valid item category before the photos have been read.
ITEM_CATEGORY_CHOICES = (("unknown", "Not sure. Let the photos decide"),) + tuple((c.id, c.label) for c in CATEGORIES.values())


@dataclass(frozen=True)
class MissingShot:
    id: str
    label: str
    prompt: str
    required: bool
    issue: str  # "" when simply absent, else the photo quality problem ("blurry", "dark", ...)


def get_category(category_id: str) -> Category | None:
    return CATEGORIES.get(category_id)


def shot_label(category_id: str, shot_id: str | None) -> str:
    cat = CATEGORIES.get(category_id)
    if cat and shot_id:
        for spec in cat.shots:
            if spec.id == shot_id:
                return spec.label
    return "Photo" if not shot_id or shot_id == "other" else shot_id.replace("_", " ").capitalize()


def missing_shots(
    category_id: str,
    present: set[str],
    bad: dict[str, str] | None = None,
    has_flaws: bool = False,
    waived: Iterable[str] = (),
) -> list[MissingShot]:
    """What the seller still needs to photograph.

    `present` is the set of shot ids covered by a usable photo; `bad` maps shot ids that
    only have an unusable photo (blurry, dark, ...) to the problem; `waived` are shots
    the seller marked not applicable.
    """
    cat = CATEGORIES.get(category_id)
    if cat is None:
        return []
    bad = bad or {}
    waived_set = set(waived)
    out: list[MissingShot] = []
    for spec in cat.shots:
        if spec.id in present or spec.id in waived_set:
            continue
        needed = spec.required or (spec.when_flaws and has_flaws)
        issue = bad.get(spec.id, "")
        if not needed and not issue:
            # Recommended shots are still offered, flagged as optional.
            out.append(MissingShot(spec.id, spec.label, spec.prompt, False, ""))
            continue
        prompt = spec.prompt
        if issue:
            prompt = f"The {spec.label.lower()} photo is {issue}. Please retake it. " + spec.prompt
        out.append(MissingShot(spec.id, spec.label, prompt, needed, issue))
    return out


def required_missing(shots: Iterable[MissingShot]) -> list[MissingShot]:
    return [s for s in shots if s.required]


def photo_order(category_id: str, photos: Iterable[tuple[int, str | None]]) -> list[int]:
    """Photo ids in the order they should be uploaded: the category's shot order, then the rest."""
    cat = CATEGORIES.get(category_id)
    rank = {spec.id: i for i, spec in enumerate(cat.shots)} if cat else {}
    indexed = list(enumerate(photos))
    indexed.sort(key=lambda t: (rank.get(t[1][1] or "", len(rank)), t[0]))
    return [pid for _, (pid, _shot) in indexed]


def waived_facts(category_id: str, waived: Iterable[str]) -> list[tuple[str, str]]:
    """(fact, keyword) pairs the listing should state for shots the seller marked not applicable."""
    cat = CATEGORIES.get(category_id)
    if cat is None:
        return []
    waived_set = set(waived)
    return [(s.waived_fact, s.waived_keyword) for s in cat.shots if s.id in waived_set and s.waived_fact]
