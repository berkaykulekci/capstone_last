from fastapi import APIRouter, Depends, status
from . import schemas, controller
from ..database import get_db

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db=Depends(get_db)):
    return controller.register_user(user, db)

from fastapi.security import OAuth2PasswordRequestForm

@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    # Swagger Auth button sends `username` and `password` as form data.
    # We map `username` to our `email` field.
    user_login = schemas.UserLogin(email=form_data.username, password=form_data.password)
    return controller.login_user(user_login, db)

@router.post("/forgot-password")
def forgot_password(request: schemas.PasswordReset, db=Depends(get_db)):
    return controller.process_forgot_password(request.email, db)
