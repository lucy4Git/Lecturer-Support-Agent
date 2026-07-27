from __future__ import annotations
from datetime import date
from uuid import UUID
from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base,TenantOwnedMixin,TimestampMixin,UUIDPrimaryKeyMixin
class Institution(Base,UUIDPrimaryKeyMixin,TimestampMixin):
    __tablename__="institutions"; __table_args__=(UniqueConstraint("slug"),{"schema":"tenant"})
    slug:Mapped[str]=mapped_column(String(80),nullable=False); legal_name:Mapped[str]=mapped_column(String(255),nullable=False); display_name:Mapped[str]=mapped_column(String(180),nullable=False); institution_type:Mapped[str]=mapped_column(String(80),nullable=False); country_code:Mapped[str|None]=mapped_column(String(2)); default_timezone:Mapped[str]=mapped_column(String(80),default="UTC",nullable=False); default_locale:Mapped[str]=mapped_column(String(20),default="en",nullable=False); is_active:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False); configuration:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
class OrganisationalUnitType(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="organisational_unit_types"; __table_args__=(UniqueConstraint("tenant_id","code"),{"schema":"tenant"})
    code:Mapped[str]=mapped_column(String(60),nullable=False); display_name:Mapped[str]=mapped_column(String(100),nullable=False); plural_name:Mapped[str]=mapped_column(String(120),nullable=False); level_order:Mapped[int]=mapped_column(Integer,nullable=False); allows_children:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False); metadata_schema:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
class OrganisationalUnit(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="organisational_units"; __table_args__=(UniqueConstraint("tenant_id","code"),Index("ix_org_units_parent","tenant_id","parent_id"),Index("ix_org_units_path","tenant_id","materialized_path"),{"schema":"tenant"})
    unit_type_id:Mapped[UUID]=mapped_column(ForeignKey("tenant.organisational_unit_types.id",ondelete="RESTRICT"),nullable=False); parent_id:Mapped[UUID|None]=mapped_column(ForeignKey("tenant.organisational_units.id",ondelete="RESTRICT")); code:Mapped[str]=mapped_column(String(80),nullable=False); name:Mapped[str]=mapped_column(String(255),nullable=False); short_name:Mapped[str|None]=mapped_column(String(100)); materialized_path:Mapped[str]=mapped_column(Text,nullable=False); depth:Mapped[int]=mapped_column(Integer,default=0,nullable=False); is_active:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False); valid_from:Mapped[date|None]=mapped_column(Date); valid_to:Mapped[date|None]=mapped_column(Date); attributes:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
class OrganisationalUnitClosure(Base,TenantOwnedMixin):
    __tablename__="organisational_unit_closure"; __table_args__=(UniqueConstraint("tenant_id","ancestor_id","descendant_id"),{"schema":"tenant"})
    ancestor_id:Mapped[UUID]=mapped_column(ForeignKey("tenant.organisational_units.id",ondelete="CASCADE"),primary_key=True); descendant_id:Mapped[UUID]=mapped_column(ForeignKey("tenant.organisational_units.id",ondelete="CASCADE"),primary_key=True); depth:Mapped[int]=mapped_column(Integer,nullable=False)
class TenantTerminology(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="terminology"; __table_args__=(UniqueConstraint("tenant_id","term_key"),{"schema":"tenant"})
    term_key:Mapped[str]=mapped_column(String(100),nullable=False); singular_value:Mapped[str]=mapped_column(String(150),nullable=False); plural_value:Mapped[str]=mapped_column(String(160),nullable=False); locale:Mapped[str]=mapped_column(String(20),default="en",nullable=False)
class TenantSetting(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="settings"; __table_args__=(UniqueConstraint("tenant_id","setting_key"),{"schema":"tenant"})
    setting_key:Mapped[str]=mapped_column(String(150),nullable=False); setting_value:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False); is_secret_reference:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
class AcademicPeriod(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="academic_periods"; __table_args__=(UniqueConstraint("tenant_id","code"),Index("ix_academic_period_dates","tenant_id","starts_on","ends_on"),{"schema":"tenant"})
    code:Mapped[str]=mapped_column(String(60),nullable=False); name:Mapped[str]=mapped_column(String(150),nullable=False); period_type:Mapped[str]=mapped_column(String(50),nullable=False); starts_on:Mapped[date]=mapped_column(Date,nullable=False); ends_on:Mapped[date]=mapped_column(Date,nullable=False); is_current:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
