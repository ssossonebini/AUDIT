from fastapi import APIRouter, HTTPException
from typing import List

from app.schemas.audit import AuditCreate, AuditResponse

router = APIRouter()

# In-memory storage (replace with DB in production)
_audits: List[dict] = []
_next_id = 1


@router.get("/", response_model=List[AuditResponse])
async def list_audits():
    """List all audit records."""
    return _audits


@router.post("/", response_model=AuditResponse, status_code=201)
async def create_audit(audit: AuditCreate):
    """Create a new audit record."""
    global _next_id
    record = {"id": _next_id, **audit.model_dump()}
    _audits.append(record)
    _next_id += 1
    return record


@router.get("/{audit_id}", response_model=AuditResponse)
async def get_audit(audit_id: int):
    """Get a specific audit record by ID."""
    for audit in _audits:
        if audit["id"] == audit_id:
            return audit
    raise HTTPException(status_code=404, detail="Audit not found")


@router.delete("/{audit_id}", status_code=204)
async def delete_audit(audit_id: int):
    """Delete an audit record."""
    global _audits
    for i, audit in enumerate(_audits):
        if audit["id"] == audit_id:
            _audits.pop(i)
            return
    raise HTTPException(status_code=404, detail="Audit not found")
