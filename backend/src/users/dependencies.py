from fastapi import Depends
from ..database import get_db
from ..auth.dependencies import get_current_user


def get_user_db(db=Depends(get_db)):
    return db
