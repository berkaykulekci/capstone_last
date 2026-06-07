from fastapi import APIRouter, Depends
from .schema import UserResponse
from ..auth.dependencies import get_current_user
from ..auth.model import User

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
