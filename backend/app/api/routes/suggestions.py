from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.schemas.recommendation import SuggestionResponse
from app.services.shopping_service import shopping_service
from app.recommendations.co_purchase_engine import co_purchase_engine
from app.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/suggestions", tags=["Suggestions"])

@router.get("", response_model=SuggestionResponse)
def get_smart_suggestions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generates smart suggestions isolated strictly to the authenticated user's purchase history."""
    active_list = shopping_service.get_or_create_active_list(db, current_user.id)
    return co_purchase_engine.generate_recommendations(
        db=db,
        user_id=current_user.id,
        current_list_id=active_list.id
    )
