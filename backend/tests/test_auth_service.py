import pytest
from src.auth.service import get_password_hash, verify_password, create_access_token, verify_token
from fastapi import HTTPException

def test_password_hashing():
    password = "testpassword123"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False

def test_jwt_token_creation_and_verification():
    data = {"sub": "test@example.com"}
    token = create_access_token(data)
    assert token is not None

    class MockException(Exception): pass
    email = verify_token(token, MockException)
    assert email == "test@example.com"
