from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_auth_session, get_session
from .request_context import RequestContext, get_request_context

DatabaseSession = Annotated[AsyncSession, Depends(get_session)]
AuthenticationDatabaseSession = Annotated[AsyncSession, Depends(get_auth_session)]
CurrentContext = Annotated[RequestContext, Depends(get_request_context)]
