from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AuditCreate(BaseModel):
    title: str
    description: Optional[str] = None
    target: str
    status: str = "pending"


class AuditResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    target: str
    status: str
