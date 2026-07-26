from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ApiError(BaseModel):
    code: str
    message: str
    user_message: str
    details: Any = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ApiError
    request_id: str
    path: str
    timestamp: datetime = Field(
        default_factory=datetime.utcnow
    )