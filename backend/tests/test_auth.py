def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_register_user(client):
    response = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "securepassword"}
    )
    assert response.status_code == 201
    assert response.json()["message"] == "User registered successfully"

def test_register_existing_user(client):
    # Ensure the user is registered first
    client.post(
        "/auth/register",
        json={"email": "duplicate@example.com", "password": "securepassword"}
    )
    response = client.post(
        "/auth/register",
        json={"email": "duplicate@example.com", "password": "securepassword"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"

def test_login_success(client):
    # Register first
    client.post(
        "/auth/register",
        json={"email": "login@example.com", "password": "securepassword"}
    )
    response = client.post(
        "/auth/login",
        data={"username": "login@example.com", "password": "securepassword"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_failure(client):
    response = client.post(
        "/auth/login",
        data={"username": "wrong@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"

def test_forgot_password(client):
    response = client.post(
        "/auth/forgot-password",
        json={"email": "test_forgot@example.com"}
    )
    assert response.status_code == 200
    assert "reset link" in response.json()["message"]
