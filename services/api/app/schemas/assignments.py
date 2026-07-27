from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .common import ORMModel


class AssignmentPeriodMixin(BaseModel):
    valid_from: datetime
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be later than valid_from")
        return self


class LecturerAssignmentCreate(AssignmentPeriodMixin):
    lecturer_user_id: UUID
    module_offering_id: UUID
    responsibility_type: str = Field(default="lecturer", min_length=1, max_length=80)
    workload_percentage: Decimal | None = Field(default=None, ge=0, le=100)


class LecturerAssignmentResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    module_offering_id: UUID
    assigned_by_user_id: UUID
    responsibility_type: str
    workload_percentage: Decimal | None
    status: str
    valid_from: datetime
    valid_until: datetime | None
    ended_reason: str | None
    created_at: datetime


class CoordinatorAssignmentCreate(AssignmentPeriodMixin):
    user_id: UUID
    coordinator_type: str = Field(pattern="^(module|programme)$")
    target_type: str = Field(pattern="^(module|programme|module_offering)$")
    target_id: UUID


class CoordinatorAssignmentResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    coordinator_type: str
    target_type: str
    target_id: UUID
    assigned_by_user_id: UUID
    status: str
    valid_from: datetime
    valid_until: datetime | None
    created_at: datetime


class ModeratorAssignmentCreate(AssignmentPeriodMixin):
    user_id: UUID
    moderator_type: str = Field(pattern="^(internal|external)$")
    target_type: str = Field(pattern="^(module|programme|module_offering)$")
    target_id: UUID


class ModeratorAssignmentResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    moderator_type: str
    target_type: str
    target_id: UUID
    assigned_by_user_id: UUID
    status: str
    valid_from: datetime
    valid_until: datetime | None
    created_at: datetime


class AssignmentEndRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    effective_at: datetime | None = None


class DepartmentTeachingOverview(BaseModel):
    organisational_unit_id: UUID
    active_module_offerings: int
    active_lecturer_assignments: int
    unassigned_module_offerings: int
    active_coordinator_assignments: int
    active_moderator_assignments: int
    total_allocated_workload_percentage: Decimal
