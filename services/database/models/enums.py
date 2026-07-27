from enum import StrEnum
class MembershipStatus(StrEnum): INVITED="invited"; ACTIVE="active"; SUSPENDED="suspended"; DEACTIVATED="deactivated"
class AssignmentStatus(StrEnum): DRAFT="draft"; ACTIVE="active"; ENDED="ended"; CANCELLED="cancelled"
class UploadBatchStatus(StrEnum): CREATED="created"; QUARANTINED="quarantined"; VALIDATING="validating"; AWAITING_CONFIRMATION="awaiting_confirmation"; PROCESSING="processing"; COMPLETED="completed"; PARTIALLY_COMPLETED="partially_completed"; FAILED="failed"; CANCELLED="cancelled"
class UploadItemStatus(StrEnum): RECEIVED="received"; QUARANTINED="quarantined"; VALIDATED="validated"; DUPLICATE="duplicate"; REQUIRES_REVIEW="requires_review"; STORED="stored"; INDEXED="indexed"; REJECTED="rejected"; FAILED="failed"
class DocumentVersionStatus(StrEnum): WORKING="working"; UNDER_REVIEW="under_review"; APPROVED="approved"; PUBLISHED="published"; SUPERSEDED="superseded"; ARCHIVED="archived"; REJECTED="rejected"
class DocumentVisibility(StrEnum): PRIVATE="private"; ASSIGNED_USERS="assigned_users"; MODULE="module"; PROGRAMME="programme"; DEPARTMENT="department"; INSTITUTION="institution"; PUBLIC="public"
class ExternalGrantStatus(StrEnum): PENDING="pending"; ACTIVE="active"; EXPIRED="expired"; REVOKED="revoked"
class ReviewTaskStatus(StrEnum): ASSIGNED="assigned"; ACCEPTED="accepted"; IN_PROGRESS="in_progress"; SUBMITTED="submitted"; RETURNED="returned"; COMPLETED="completed"; EXPIRED="expired"; REVOKED="revoked"
class VerificationStatus(StrEnum): PENDING="pending"; VERIFIED="verified"; PARTIALLY_VERIFIED="partially_verified"; FAILED="failed"; RETRACTED="retracted"
class WorkflowStatus(StrEnum): DRAFT="draft"; ACTIVE="active"; COMPLETED="completed"; REJECTED="rejected"; CANCELLED="cancelled"

class AuthSessionStatus(StrEnum): ACTIVE="active"; REVOKED="revoked"; EXPIRED="expired"
class InvitationStatus(StrEnum): PENDING="pending"; ACCEPTED="accepted"; EXPIRED="expired"; REVOKED="revoked"

class OutputWorkflowStatus(StrEnum):
    DRAFT="draft"
    UNDER_REVIEW="under_review"
    CHANGES_REQUESTED="changes_requested"
    APPROVED="approved"
    RELEASED="released"
    ARCHIVED="archived"
    REJECTED="rejected"

class AssessmentRiskLevel(StrEnum):
    NONE="none"
    LOW="low"
    MEDIUM="medium"
    HIGH="high"
    CRITICAL="critical"

class SafetyReviewStatus(StrEnum):
    PASSED="passed"
    PASSED_WITH_WARNINGS="passed_with_warnings"
    BLOCKED="blocked"
    REQUIRES_REVIEW="requires_review"

class ExportStatus(StrEnum):
    REQUESTED="requested"
    GENERATING="generating"
    COMPLETED="completed"
    FAILED="failed"

class ExportFormat(StrEnum):
    MARKDOWN="markdown"
    HTML="html"
    DOCX="docx"
    PDF="pdf"
    PPTX="pptx"
    XLSX="xlsx"

class ExportAudience(StrEnum):
    GENERIC="generic"
    LECTURER_PACK="lecturer_pack"
    STUDENT_COPY="student_copy"
    MODERATION_PACK="moderation_pack"



class ReviewCycleStatus(StrEnum):
    ASSIGNED="assigned"
    IN_REVIEW="in_review"
    DECISION_PENDING="decision_pending"
    CHANGES_REQUESTED="changes_requested"
    CONDITIONALLY_APPROVED="conditionally_approved"
    APPROVED="approved"
    REJECTED="rejected"
    COMPLETED="completed"
    EXPIRED="expired"
    REVOKED="revoked"

class ReviewFindingSeverity(StrEnum):
    INFO="info"
    LOW="low"
    MEDIUM="medium"
    HIGH="high"
    CRITICAL="critical"

class ReviewFindingStatus(StrEnum):
    OPEN="open"
    RESPONDED="responded"
    RESOLVED="resolved"
    ACCEPTED="accepted"
    DISPUTED="disputed"
    WITHDRAWN="withdrawn"

class ReviewRecommendation(StrEnum):
    APPROVE="approve"
    APPROVE_WITH_CONDITIONS="approve_with_conditions"
    CHANGES_REQUIRED="changes_required"
    REJECT="reject"

class ReviewDecisionCode(StrEnum):
    APPROVED="approved"
    APPROVED_WITH_CONDITIONS="approved_with_conditions"
    CHANGES_REQUIRED="changes_required"
    REJECTED="rejected"

class ReviewCorrectionStatus(StrEnum):
    REQUESTED="requested"
    IN_PROGRESS="in_progress"
    RESUBMITTED="resubmitted"
    ACCEPTED="accepted"
    CLOSED="closed"


class TeachingPlanStatus(StrEnum):
    DRAFT="draft"
    ACTIVE="active"
    PAUSED="paused"
    COMPLETED="completed"
    ARCHIVED="archived"

class TeachingSessionStatus(StrEnum):
    PLANNED="planned"
    DELIVERED="delivered"
    RESCHEDULED="rescheduled"
    CANCELLED="cancelled"
    MISSED="missed"

class ModuleReadinessStatus(StrEnum):
    NOT_STARTED="not_started"
    AT_RISK="at_risk"
    PARTIALLY_READY="partially_ready"
    READY="ready"
    BLOCKED="blocked"

class ReadinessItemStatus(StrEnum):
    MISSING="missing"
    IN_PROGRESS="in_progress"
    COMPLETE="complete"
    WAIVED="waived"
    NOT_APPLICABLE="not_applicable"

class WorkloadActivityStatus(StrEnum):
    ACTIVE="active"
    ENDED="ended"
    CANCELLED="cancelled"

class HandoverStatus(StrEnum):
    DRAFT="draft"
    SUBMITTED="submitted"
    CHANGES_REQUESTED="changes_requested"
    ACCEPTED="accepted"
    COMPLETED="completed"
    ARCHIVED="archived"

class AcademicCalendarEventStatus(StrEnum):
    SCHEDULED="scheduled"
    COMPLETED="completed"
    CANCELLED="cancelled"
