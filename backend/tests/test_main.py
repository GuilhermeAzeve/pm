import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    (tmp_path / "index.html").write_text("<h1>Kanban Studio</h1>")
    (tmp_path / "404.html").write_text("<h1>Not found</h1>")
    (tmp_path / "_next").mkdir()
    (tmp_path / "_next" / "app.js").write_text("console.log('app');")
    with TestClient(create_app(tmp_path, tmp_path / "pm.db")) as client:
        yield client


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "ok"}


def test_login_sets_session_and_me_returns_user(client):
    response = client.post(
        "/api/login", json={"username": "user", "password": "password"}
    )
    assert response.status_code == 200
    assert response.json() == {"username": "user"}
    assert "HttpOnly" in response.headers["set-cookie"]

    me_response = client.get("/api/me")
    assert me_response.status_code == 200
    assert me_response.json() == {"username": "user"}


def test_login_rejects_wrong_credentials(client):
    response = client.post(
        "/api/login", json={"username": "user", "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}


def test_me_rejects_anonymous_request(client):
    response = client.get("/api/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_logout_clears_session(client):
    client.post("/api/login", json={"username": "user", "password": "password"})
    response = client.post("/api/logout")
    assert response.status_code == 204
    assert client.get("/api/me").status_code == 401


def test_root_serves_exported_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Kanban Studio" in response.text


def test_serves_exported_assets(client):
    response = client.get("/_next/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]


def test_unknown_path_returns_404_page(client):
    response = client.get("/missing")
    assert response.status_code == 404
    assert "Not found" in response.text


def test_unknown_api_route_is_not_found(client):
    response = client.get("/api/missing")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}


def test_unknown_api_post_is_not_found(client):
    response = client.post("/api/missing")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}


def test_api_root_is_json_not_found(client):
    response = client.get("/api")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}
