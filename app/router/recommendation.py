from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from crud.user import get_current_user, require_admin
from services import PersonalizedRecService
from core.pkgs.database import get_db
import asyncpg
from typing import List

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.post("/train", summary="Train Recommendation Model (Admin Only)")
async def train_model_endpoint(background_tasks: BackgroundTasks, admin: dict = Depends(require_admin)):
    """
    Triggers a background task to train the personalized recommendation model.
    This is a long-running process and should be triggered periodically.
    """
    background_tasks.add_task(PersonalizedRecService.train_and_cache_model)
    return {"message": "Recommendation model training has been started in the background."}

@router.get("/", summary="Get Personalized Recommendations")
async def get_recommendations_for_user(db: asyncpg.Connection = Depends(get_db), current_user: dict = Depends(get_current_user)) -> List[dict]:
    """
    Returns a list of personalized product recommendations for the current user.
    The model must be trained first via the /train endpoint.
    """
    user_id = current_user.get('id') # I need to get the user ID from the token payload
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token.")

    recommendations = await PersonalizedRecService.get_personalized_recommendations(db, user_id)
    return recommendations
