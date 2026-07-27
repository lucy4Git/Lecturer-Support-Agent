from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import Boolean,DateTime,ForeignKey,Index,Integer,String,Text,UniqueConstraint,Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped,mapped_column
from .base import Base,TenantOwnedMixin,TimestampMixin,UUIDPrimaryKeyMixin
from .enums import VerificationStatus
class Source(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="sources"; __table_args__=(UniqueConstraint("tenant_id","canonical_identifier"),Index("ix_source_url","tenant_id","canonical_url"),{"schema":"source"})
    source_type:Mapped[str]=mapped_column(String(80),nullable=False); title:Mapped[str]=mapped_column(String(1000),nullable=False); authors:Mapped[list]=mapped_column(JSONB,default=list,nullable=False); publisher_or_organisation:Mapped[str|None]=mapped_column(String(500)); publication_date:Mapped[str|None]=mapped_column(String(50)); canonical_url:Mapped[str|None]=mapped_column(Text); canonical_identifier:Mapped[str]=mapped_column(String(500),nullable=False); doi:Mapped[str|None]=mapped_column(String(255)); licence:Mapped[str|None]=mapped_column(String(255)); reliability_tier:Mapped[str]=mapped_column(String(40),default="unrated",nullable=False); is_institutional:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False); is_restricted:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False); retraction_status:Mapped[str]=mapped_column(String(40),default="not_checked",nullable=False); metadata_payload:Mapped[dict]=mapped_column("metadata",JSONB,default=dict,nullable=False)
class SourceRetrieval(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="source_retrievals"; __table_args__=(Index("ix_source_retrieval_request","tenant_id","ai_request_id"),{"schema":"source"})
    ai_request_id:Mapped[UUID]=mapped_column(ForeignKey("ai.ai_requests.id"),nullable=False); source_id:Mapped[UUID]=mapped_column(ForeignKey("source.sources.id"),nullable=False); retrieved_by:Mapped[str]=mapped_column(String(80),nullable=False); retrieval_query:Mapped[str]=mapped_column(Text,nullable=False); retrieved_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False); rank:Mapped[int|None]=mapped_column(Integer); relevance_score:Mapped[str|None]=mapped_column(String(50)); access_snapshot:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
class Citation(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="citations"; __table_args__=(Index("ix_citation_output","tenant_id","output_version_id","citation_number"),{"schema":"source"})
    output_version_id:Mapped[UUID]=mapped_column(ForeignKey("conversation.output_versions.id"),nullable=False); source_retrieval_id:Mapped[UUID]=mapped_column(ForeignKey("source.source_retrievals.id"),nullable=False); citation_number:Mapped[int]=mapped_column(Integer,nullable=False); locator:Mapped[str|None]=mapped_column(String(255)); supporting_excerpt_hash:Mapped[str|None]=mapped_column(String(64)); display_label:Mapped[str]=mapped_column(String(500),nullable=False); verified:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
class ClaimCitation(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="claim_citations"; __table_args__=(UniqueConstraint("tenant_id","citation_id","claim_key"),{"schema":"source"})
    citation_id:Mapped[UUID]=mapped_column(ForeignKey("source.citations.id"),nullable=False); claim_key:Mapped[str]=mapped_column(String(180),nullable=False); claim_text:Mapped[str]=mapped_column(Text,nullable=False); entailment_score:Mapped[str|None]=mapped_column(String(50)); verifier_notes:Mapped[str|None]=mapped_column(Text)
class VerificationResult(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="verification_results"; __table_args__=(Index("ix_verification_target","tenant_id","target_type","target_id"),{"schema":"source"})
    target_type:Mapped[str]=mapped_column(String(60),nullable=False); target_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),nullable=False); verification_type:Mapped[str]=mapped_column(String(80),nullable=False); status:Mapped[str]=mapped_column(String(40),default=VerificationStatus.PENDING.value,nullable=False); verifier:Mapped[str]=mapped_column(String(120),nullable=False); findings:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False); verified_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
