from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import current_org, current_user, get_session
from app.models.membership import Role
from app.workers.auto_approval import run_once

router = APIRouter(prefix="/auto-approval", tags=["auto-approval"])


@router.post("/run")
def run_auto_approval(user=Depends(current_user), org=Depends(current_org), db: Session = Depends(get_session)):
    # Only OWNER/ADMIN may trigger a manual run
    if org.membership.role not in (Role.OWNER, Role.ADMIN):
        raise HTTPException(status_code=403, detail="insufficient role to run auto-approval")
    counts = run_once()
    return {"ok": True, "processed": counts.get("processed", 0)}
