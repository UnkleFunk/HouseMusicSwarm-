"""Pydantic models for what the vision and drafting steps return.

The *Wire* classes are what Claude is asked to produce (structured outputs), so they
stay flat and use only strings, ints, lists and Literals.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ShotId = Literal[
    "front",
    "back",
    "side",
    "socket",
    "io",
    "serial_sticker",
    "ram_slots",
    "accessories",
    "brand_tag",
    "size_tag",
    "detail",
    "measurements",
    "pair_top",
    "heel",
    "toe_box",
    "tongue_label",
    "box_label",
    "soles",
    "insoles",
    "flaw_closeup",
    "other",
]
GradeId = Literal["new", "like_new", "good", "fair", "for_parts"]
CategoryId = Literal["board", "clothing", "sneakers", "other"]
QualityId = Literal["ok", "blurry", "dark", "cropped", "glare"]
NumberKind = Literal["model", "part_number", "serial", "style_code", "size", "upc", "other"]
Severity = Literal["minor", "moderate", "major"]
Confidence = Literal["low", "medium", "high"]


class PhotoRead(BaseModel):
    photo_number: int = Field(description="The photo's number as labelled in the message, starting at 1.")
    shot: ShotId = Field(description="What this photo mainly shows. Use 'other' if none fit.")
    quality: QualityId = Field(description="'ok' unless the photo is too blurry, dark, cropped or glary to read details from.")
    note: str = Field(description="One short sentence on anything notable in this photo, or an empty string.")


class ModelNumber(BaseModel):
    value: str = Field(description="Exactly as printed, character for character.")
    kind: NumberKind
    photo_number: int = Field(description="Photo it was read from; 0 if unknown.")


class Flaw(BaseModel):
    description: str = Field(description="Plain description of the flaw and where it is.")
    severity: Severity
    photo_number: int = Field(description="Photo that shows it; 0 if no photo shows it clearly.")


class Attribute(BaseModel):
    name: str
    value: str


class AnalysisWire(BaseModel):
    category: CategoryId
    brand: str = Field(description="Brand as printed or clearly shown; empty string if you cannot tell.")
    model: str = Field(description="Model name or number; empty string if you cannot tell.")
    product_name: str = Field(description="What the item is, in a few words, e.g. 'ATX motherboard', 'zip hoodie'.")
    identification_confidence: Confidence
    identification_evidence: str = Field(description="What you read or saw that supports the identification.")
    model_numbers: list[ModelNumber]
    label_text: list[str] = Field(description="Every legible line from labels, tags and stickers, as printed.")
    photos: list[PhotoRead]
    flaws: list[Flaw]
    attributes: list[Attribute] = Field(description="Specs and details that are readable or clearly visible (socket, chipset, size, colorway, fabric...).")
    suggested_condition: GradeId
    condition_rationale: str = Field(description="One or two plain sentences explaining the grade.")
    unknowns: list[str] = Field(description="Things a buyer would want to know that the photos do not show.")


class Analysis(AnalysisWire):
    photo_ids: list[int] = Field(default_factory=list, description="Database ids of the photos that were analysed, in order.")
    mode: str = "live"
    model_used: str = ""


class DraftWire(BaseModel):
    platform: str
    title: str
    description: str
    specs: list[Attribute]
    keywords: list[str]


class DraftsWire(BaseModel):
    drafts: list[DraftWire]
