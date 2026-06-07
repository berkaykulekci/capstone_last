from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from . import schemas, service
from .model import User


def register_user(user: schemas.UserCreate, db: Session):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    hashed_password = service.get_password_hash(user.password)
    new_user = User(email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully"}


def login_user(user: schemas.UserLogin, db: Session):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not service.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = service.create_access_token(data={"sub": db_user.email})
    return {"access_token": access_token, "token_type": "bearer"}


def process_forgot_password(email: str, db: Session):
    return {"message": "If the email is registered, a reset link has been sent."}
