from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import Boolean,DateTime,ForeignKey,Index,Integer,String,Text,Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped,mapped_column
from .base import Base,TenantOwnedMixin,TimestampMixin,UUIDPrimaryKeyMixin
from .enums import WorkflowStatus
class AuditEvent(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin):
    __tablename__="audit_events"; __table_args__=(Index("ix_audit_event_time","tenant_id","occurred_at"),{"schema":"audit"})
    occurred_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False); actor_user_id:Mapped[UUID|None]=mapped_column(ForeignKey("iam.users.id")); actor_role_code:Mapped[str|None]=mapped_column(String(80)); action:Mapped[str]=mapped_column(String(150),nullable=False); resource_type:Mapped[str]=mapped_column(String(100),nullable=False); resource_id:Mapped[UUID|None]=mapped_column(Uuid(as_uuid=True)); correlation_id:Mapped[str]=mapped_column(String(100),nullable=False); request_id:Mapped[str|None]=mapped_column(String(100)); source_ip_hash:Mapped[str|None]=mapped_column(String(64)); before_state:Mapped[dict|None]=mapped_column(JSONB); after_state:Mapped[dict|None]=mapped_column(JSONB); metadata_payload:Mapped[dict]=mapped_column("metadata",JSONB,default=dict,nullable=False)
class ApprovalWorkflow(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="approval_workflows"; __table_args__=(Index("ix_workflow_target","tenant_id","target_type","target_id"),{"schema":"review"})
    workflow_type:Mapped[str]=mapped_column(String(100),nullable=False); target_type:Mapped[str]=mapped_column(String(60),nullable=False); target_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),nullable=False); initiated_by_user_id:Mapped[UUID]=mapped_column(ForeignKey("iam.users.id"),nullable=False); status:Mapped[str]=mapped_column(String(30),default=WorkflowStatus.DRAFT.value,nullable=False); current_step:Mapped[int]=mapped_column(Integer,default=0,nullable=False); workflow_definition:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False); completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class WorkflowAction(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="workflow_actions"; __table_args__=(Index("ix_workflow_action","tenant_id","workflow_id","sequence_number"),{"schema":"review"})
    workflow_id:Mapped[UUID]=mapped_column(ForeignKey("review.approval_workflows.id"),nullable=False); sequence_number:Mapped[int]=mapped_column(Integer,nullable=False); actor_user_id:Mapped[UUID]=mapped_column(ForeignKey("iam.users.id"),nullable=False); action:Mapped[str]=mapped_column(String(80),nullable=False); comment:Mapped[str|None]=mapped_column(Text); decision_data:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
class RetentionRule(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="retention_rules"; __table_args__=(Index("ix_retention_rule","tenant_id","resource_type"),{"schema":"privacy"})
    resource_type:Mapped[str]=mapped_column(String(100),nullable=False); classification:Mapped[str]=mapped_column(String(80),nullable=False); retention_days:Mapped[int]=mapped_column(Integer,nullable=False); disposition_action:Mapped[str]=mapped_column(String(80),nullable=False); legal_basis:Mapped[str|None]=mapped_column(Text); is_active:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
class SecurityEvent(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin):
    __tablename__="security_events"; __table_args__=(Index("ix_security_event","tenant_id","severity","occurred_at"),{"schema":"audit"})
    occurred_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False); severity:Mapped[str]=mapped_column(String(20),nullable=False); event_type:Mapped[str]=mapped_column(String(120),nullable=False); actor_user_id:Mapped[UUID|None]=mapped_column(ForeignKey("iam.users.id")); correlation_id:Mapped[str|None]=mapped_column(String(100)); description:Mapped[str]=mapped_column(Text,nullable=False); details:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False); resolved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class OutboxEvent(Base,UUIDPrimaryKeyMixin,TenantOwnedMixin,TimestampMixin):
    __tablename__="outbox_events"; __table_args__=(Index("ix_outbox_unpublished","tenant_id","published_at","created_at"),{"schema":"audit"})
    aggregate_type:Mapped[str]=mapped_column(String(100),nullable=False); aggregate_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),nullable=False); event_type:Mapped[str]=mapped_column(String(150),nullable=False); payload:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False); correlation_id:Mapped[str]=mapped_column(String(100),nullable=False); publish_attempts:Mapped[int]=mapped_column(Integer,default=0,nullable=False); published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); last_error:Mapped[str|None]=mapped_column(Text)
