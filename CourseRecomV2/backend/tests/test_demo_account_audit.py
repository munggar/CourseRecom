from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

DEMO_ACCOUNTS = (
    ("2203001", "mahasiswa"),
    ("pa001", "dosen"),
    ("admin", "admin"),
)


def login_as(username: str, expected_role: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]

    identity = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert identity.status_code == 200, identity.text
    assert identity.json()["nim"] == username
    assert identity.json()["role"] == expected_role

    return {"Authorization": f"Bearer {token}"}


def test_all_three_documented_demo_accounts_authenticate_with_expected_roles():
    for username, role in DEMO_ACCOUNTS:
        login_as(username, role)


def test_demo_role_mismatch_is_rejected():
    response = client.post(
        "/api/auth/login",
        json={
            "username": "2203001",
            "password": "password123",
            "role": "admin",
        },
    )
    assert response.status_code == 403


def test_demo_accounts_obey_role_boundaries():
    student = login_as("2203001", "mahasiswa")
    advisor = login_as("pa001", "dosen")
    admin = login_as("admin", "admin")

    # Student can read the curriculum, but cannot enter advisor/admin areas.
    assert client.get("/api/mahasiswa/kurikulum", headers=student).status_code == 200
    assert client.get("/api/dosen/mahasiswa", headers=student).status_code == 403
    assert client.get("/api/admin/dashboard", headers=student).status_code == 403

    # Advisor can read the advisee list and review queue, but cannot enter admin/student areas.
    assert client.get("/api/dosen/mahasiswa", headers=advisor).status_code == 200
    assert client.get("/api/dosen/rencana-studi", headers=advisor).status_code == 200
    assert client.get("/api/admin/dashboard", headers=advisor).status_code == 403
    assert client.get("/api/mahasiswa/kurikulum", headers=advisor).status_code == 403

    # Admin can inspect administration data and the shared advisor roster, not student-only APIs.
    assert client.get("/api/admin/dashboard", headers=admin).status_code == 200
    assert client.get("/api/admin/courses", headers=admin).status_code == 200
    assert client.get("/api/dosen/mahasiswa", headers=admin).status_code == 200
    assert client.get("/api/mahasiswa/kurikulum", headers=admin).status_code == 403


def test_seeded_demo_student_starts_without_confirmed_khs():
    student = login_as("2203001", "mahasiswa")
    response = client.get("/api/mahasiswa/rekomendasi", headers=student)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "khs_required"
    assert response.json()["recommendations"] == []
