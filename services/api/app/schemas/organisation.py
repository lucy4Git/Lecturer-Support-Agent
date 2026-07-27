from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .common import ORMModel


class OrganisationalUnitTypeCreate(BaseModel):
    code: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9_-]+$")
    display_name: str = Field(min_length=2, max_length=100)
    plural_name: str = Field(min_length=2, max_length=120)
    level_order: int = Field(ge=0, le=100)
    allows_children: bool = True
    metadata_schema: dict = Field(default_factory=dict)


class OrganisationalUnitTypeResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    code: str
    display_name: str
    plural_name: str
    level_order: int
    allows_children: bool
    metadata_schema: dict
    created_at: datetime


class OrganisationalUnitCreate(BaseModel):
    unit_type_id: UUID
    parent_id: UUID | None = None
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=255)
    short_name: str | None = Field(default=None, max_length=100)
    valid_from: date | None = None
    valid_to: date | None = None
    attributes: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_period(self) -> "OrganisationalUnitCreate":
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be on or after valid_from")
        return self


class OrganisationalUnitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    short_name: str | None = Field(default=None, max_length=100)
    attributes: dict | None = None
    is_active: bool | None = None
    valid_to: date | None = None


class OrganisationalUnitMove(BaseModel):
    new_parent_id: UUID | None = None
    reason: str = Field(min_length=3, max_length=1000)


class OrganisationalUnitResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    unit_type_id: UUID
    parent_id: UUID | None
    code: str
    name: str
    short_name: str | None
    materialized_path: str
    depth: int
    is_active: bool
    valid_from: date | None
    valid_to: date | None
    attributes: dict
    created_at: datetime


class TerminologyUpsert(BaseModel):
    term_key: str = Field(min_length=2, max_length=100)
    singular_value: str = Field(min_length=1, max_length=150)
    plural_value: str = Field(min_length=1, max_length=160)
    locale: str = Field(default="en", min_length=2, max_length=20)


class InstitutionSettingUpsert(BaseModel):
    setting_key: str = Field(min_length=2, max_length=150)
    setting_value: dict
    is_secret_reference: bool = False
