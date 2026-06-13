import os
import shutil
from pathlib import Path
from src.database import SessionLocal
from src.auth.model import User
from src.athletes.model import Athlete, Analysis
from src.athletes.analysis_service import MEDIA_ROOT

def test_delete_analysis_success(client):
    # 1. Register and Login
    email = "test_delete@example.com"
    password = "securepassword"
    client.post("/auth/register", json={"email": email, "password": password})
    login_res = client.post("/auth/login", data={"username": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get DB session to insert athlete and analysis
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None

        # Create test Athlete
        athlete = Athlete(name="Test Athlete", user_id=user.id)
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        # Create test Analysis
        analysis = Analysis(athlete_id=athlete.id, user_id=user.id, status="reviewed")
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        analysis_id = analysis.id
        athlete_id = athlete.id

        # Create dummy directory/file on disk for analysis
        analysis_dir = MEDIA_ROOT / "athletes" / athlete_id / analysis_id
        analysis_dir.mkdir(parents=True, exist_ok=True)
        dummy_file = analysis_dir / "dummy.txt"
        dummy_file.write_text("dummy content")

        assert dummy_file.exists()

        # 2. Call DELETE endpoint
        response = client.delete(
            f"/athletes/{athlete_id}/analyses/{analysis_id}",
            headers=headers
        )
        assert response.status_code == 204

        # 3. Verify database record is deleted
        db.expire_all()
        deleted_analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        assert deleted_analysis is None

        # 4. Verify filesystem directory is deleted
        assert not analysis_dir.exists()

        # Clean up database test entries
        db.delete(athlete)
        db.delete(user)
        db.commit()
    finally:
        db.close()
