# This project was developed with assistance from AI tools.
"""Schemas for disclosure endpoints."""

from pydantic import BaseModel


class DisclosureItem(BaseModel):
    """A single disclosure with its acknowledgment status."""

    id: str
    label: str
    summary: str
    content: str
    acknowledged: bool


class DisclosureStatusResponse(BaseModel):
    """Response for GET /applications/{id}/disclosures."""

    application_id: int
    all_acknowledged: bool
    disclosures: list[DisclosureItem]
