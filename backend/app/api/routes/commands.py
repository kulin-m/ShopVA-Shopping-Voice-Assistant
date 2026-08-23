from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from app.database.connection import get_db
from app.database.models import User
from app.schemas.command import CommandRequest, CommandResponse
from app.ai.llm_service import llm_service
from app.services.shopping_service import shopping_service
from app.api.dependencies.auth import get_current_user

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/commands", tags=["Commands"])

@router.post("", response_model=CommandResponse)
def process_voice_command(
    request: CommandRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Processes voice command for the currently authenticated user."""
    if not request.transcript or not request.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty")

    logger.info(f"🎤 [VOICE COMMAND RECEIVED] User={current_user.email} (ID={current_user.id}): '{request.transcript}'")

    parsed = llm_service.parse_command(request.transcript)
    logger.info(f"🧠 [PARSED COMMAND]: Intent={parsed.intent}, Item='{parsed.item}', Qty={parsed.quantity}, Size='{parsed.size}'")

    # Authoritative execution under current_user.id
    response = shopping_service.process_command(db=db, user_id=current_user.id, parsed=parsed)

    reason = response.data.get("size_reason") if response.data else "N/A"
    logger.info(f"✅ [ACTION RESULT]: {response.message} (Reason: {reason})")

    return response
