from __future__ import annotations

import hashlib
from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from ..core.dependencies import AuthenticationDatabaseSession, CurrentContext, DatabaseSession
from ..core.mfa import TOTP
from ..core.settings import get_settings
from ..schemas.completion import (
    DatasetAcquisitionRequest,
    DatasetApprovalRequest,
    DatasetSourceCreate,
    DeletionApprovalRequest,
    DeletionRequestCreate,
    DeletionRequestResponse,
    EmailVerificationConfirm,
    EvaluationCampaignCreate,
    EvaluationResponseCreate,
    IntegrationConnectionCreate,
    IntegrationConnectionResponse,
    IntegrationSyncRequest,
    LegalHoldCreate,
    LegalHoldRelease,
    LegalHoldResponse,
    MFADisableRequest,
    MFAConfirmRequest,
    MFAEnrolRequest,
    MFAEnrolResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    SSOCallbackRequest,
    SSOCallbackResponse,
    SSOConnectionCreate,
    SSOConnectionResponse,
    SSOExchangeRequest,
    SSOStartRequest,
    SSOStartResponse,
    UserFeedbackCreate,
    UserFeedbackResponse,
)
from ..services.account_security import AccountSecurityService
from ..services.authorization import AuthorizationService
from ..services.data_preparation import DataPreparationService
from ..services.enterprise_integrations import EnterpriseIntegrationService
from ..services.evaluation_capture import EvaluationCaptureService
from ..services.privacy_completion import PrivacyCompletionService
from ..services.sso_authentication import SSOAuthenticationService
from ..schemas.auth import TokenResponse

router = APIRouter(tags=["completion and commercial readiness"])


def _source_ip_hash(request: Request) -> str | None:
    value = request.client.host if request.client else None
    return hashlib.sha256(value.encode()).hexdigest() if value else None


@router.post("/auth/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    session: AuthenticationDatabaseSession,
) -> dict:
    await AccountSecurityService(session).request_password_reset(
        payload, source_ip_hash=_source_ip_hash(request)
    )
    return {"message": "If the account exists and is eligible, password-reset instructions have been queued."}


@router.post("/auth/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    payload: PasswordResetConfirm,
    session: AuthenticationDatabaseSession,
) -> Response:
    await AccountSecurityService(session).confirm_password_reset(
        payload.reset_token.get_secret_value(), payload.new_password.get_secret_value()
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/email-verification/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_email_verification(
    payload: EmailVerificationConfirm,
    session: AuthenticationDatabaseSession,
) -> Response:
    await AccountSecurityService(session).confirm_email_verification(
        payload.verification_token.get_secret_value()
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/sso/start", response_model=SSOStartResponse)
async def start_sso(
    payload: SSOStartRequest,
    session: AuthenticationDatabaseSession,
) -> SSOStartResponse:
    return await SSOAuthenticationService(session).start(payload)


@router.post("/auth/sso/callback", response_model=SSOCallbackResponse)
async def complete_sso_callback(
    payload: SSOCallbackRequest,
    session: AuthenticationDatabaseSession,
) -> SSOCallbackResponse:
    return await SSOAuthenticationService(session).callback(
        state_value=payload.state.get_secret_value(), code=payload.code.get_secret_value()
    )


@router.post("/auth/sso/exchange", response_model=TokenResponse)
async def exchange_sso_handoff(
    payload: SSOExchangeRequest,
    request: Request,
    session: AuthenticationDatabaseSession,
) -> TokenResponse:
    user_agent = request.headers.get("user-agent")
    source_ip = request.client.host if request.client else None
    return await SSOAuthenticationService(session).exchange(
        payload,
        user_agent_hash=hashlib.sha256(user_agent.encode()).hexdigest() if user_agent else None,
        source_ip_hash=hashlib.sha256(source_ip.encode()).hexdigest() if source_ip else None,
    )


@router.post("/account/email-verification/request", status_code=status.HTTP_202_ACCEPTED)
async def request_email_verification(
    session: DatabaseSession,
    context: CurrentContext,
) -> dict:
    await AccountSecurityService(session, context).request_email_verification()
    return {"status": "queued"}


@router.post("/account/mfa/enrol", response_model=MFAEnrolResponse, status_code=status.HTTP_201_CREATED)
async def enrol_mfa(
    payload: MFAEnrolRequest,
    session: DatabaseSession,
    context: CurrentContext,
) -> MFAEnrolResponse:
    device, secret, codes = await AccountSecurityService(session, context).enrol_mfa(payload.label)
    uri = TOTP(get_settings()).provisioning_uri(secret=secret, account_name=str(context.user_id))
    return MFAEnrolResponse(device_id=device.id, secret=secret, provisioning_uri=uri, recovery_codes=codes)


@router.post("/account/mfa/{device_id}/confirm")
async def confirm_mfa(
    device_id: UUID,
    payload: MFAConfirmRequest,
    session: DatabaseSession,
    context: CurrentContext,
) -> dict:
    device = await AccountSecurityService(session, context).confirm_mfa(device_id, payload.code)
    return {"device_id": str(device.id), "status": device.status}


@router.post("/account/mfa/{device_id}/disable")
async def disable_mfa(
    device_id: UUID,
    payload: MFADisableRequest,
    session: DatabaseSession,
    context: CurrentContext,
) -> dict:
    device = await AccountSecurityService(session, context).disable_mfa(
        device_id, payload.code, payload.reason
    )
    return {"device_id": str(device.id), "status": device.status}


@router.get("/integrations", response_model=list[IntegrationConnectionResponse])
async def list_integrations(session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="integrations.read"
    )
    return await EnterpriseIntegrationService(session, context).list_connections()


@router.post("/integrations", response_model=IntegrationConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(payload: IntegrationConnectionCreate, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="integrations.manage"
    )
    return await EnterpriseIntegrationService(session, context).create_connection(payload)


@router.post("/integrations/{connection_id}/test", response_model=IntegrationConnectionResponse)
async def test_integration(connection_id: UUID, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="integrations.manage"
    )
    return await EnterpriseIntegrationService(session, context).test_connection(connection_id)


@router.post("/integrations/{connection_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_integration(connection_id: UUID, payload: IntegrationSyncRequest, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="integrations.manage"
    )
    run = await EnterpriseIntegrationService(session, context).request_sync(connection_id, payload)
    return {"sync_run_id": str(run.id), "status": run.status}


@router.get("/sso-connections", response_model=list[SSOConnectionResponse])
async def list_sso_connections(session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="sso.manage"
    )
    return await EnterpriseIntegrationService(session, context).list_sso_connections()


@router.post("/sso-connections", response_model=SSOConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_sso_connection(payload: SSOConnectionCreate, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="sso.manage"
    )
    return await EnterpriseIntegrationService(session, context).create_sso_connection(payload)


@router.post("/privacy/legal-holds", response_model=LegalHoldResponse, status_code=status.HTTP_201_CREATED)
async def create_legal_hold(payload: LegalHoldCreate, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="privacy.legal_holds.manage"
    )
    return await PrivacyCompletionService(session, context).create_legal_hold(payload)


@router.post("/privacy/legal-holds/{hold_id}/release", response_model=LegalHoldResponse)
async def release_legal_hold(hold_id: UUID, payload: LegalHoldRelease, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="privacy.legal_holds.manage"
    )
    return await PrivacyCompletionService(session, context).release_legal_hold(hold_id, payload.reason)


@router.post("/privacy/deletion-requests", response_model=DeletionRequestResponse, status_code=status.HTTP_201_CREATED)
async def request_deletion(payload: DeletionRequestCreate, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="privacy.deletion.manage"
    )
    return await PrivacyCompletionService(session, context).request_deletion(payload)


@router.post("/privacy/deletion-requests/{request_id}/decision", response_model=DeletionRequestResponse)
async def decide_deletion(request_id: UUID, payload: DeletionApprovalRequest, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="privacy.deletion.approve"
    )
    return await PrivacyCompletionService(session, context).approve_deletion(
        request_id, approve=payload.approve, reason=payload.reason
    )


@router.post("/feedback", response_model=UserFeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(payload: UserFeedbackCreate, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="feedback.submit"
    )
    return await EvaluationCaptureService(session, context).create_feedback(payload)


@router.post("/evaluation/campaigns", status_code=status.HTTP_201_CREATED)
async def create_evaluation_campaign(payload: EvaluationCampaignCreate, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="evaluation.manage"
    )
    item = await EvaluationCaptureService(session, context).create_campaign(payload)
    return {"campaign_id": str(item.id), "status": item.status}


@router.post("/evaluation/campaigns/{campaign_id}/responses", status_code=status.HTTP_201_CREATED)
async def submit_evaluation_response(campaign_id: UUID, payload: EvaluationResponseCreate, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="evaluation.participate"
    )
    item = await EvaluationCaptureService(session, context).submit_response(campaign_id, payload)
    return {"response_id": str(item.id), "computed_scores": item.computed_scores}


@router.post("/data-sources", status_code=status.HTTP_201_CREATED)
async def create_dataset_source(payload: DatasetSourceCreate, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="datasets.manage"
    )
    item = await DataPreparationService(session, context).create_source(payload)
    return {"source_id": str(item.id), "approval_status": item.approval_status}


@router.post("/data-sources/{source_id}/decision")
async def decide_dataset_source(source_id: UUID, payload: DatasetApprovalRequest, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="datasets.approve"
    )
    item = await DataPreparationService(session, context).approve_source(
        source_id, approve=payload.approve, note=payload.review_note
    )
    return {"source_id": str(item.id), "approval_status": item.approval_status}


@router.post("/data-sources/{source_id}/acquisitions", status_code=status.HTTP_202_ACCEPTED)
async def acquire_dataset_source(source_id: UUID, payload: DatasetAcquisitionRequest, session: DatabaseSession, context: CurrentContext):
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="datasets.acquire"
    )
    item = await DataPreparationService(session, context).request_acquisition(
        source_id, limit=payload.limit, query=payload.query
    )
    return {"acquisition_run_id": str(item.id), "status": item.status}
