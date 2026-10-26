import base64
import hashlib
import hmac
import os
from pathlib import Path

from fastapi import APIRouter, Cookie, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Next.js static export; the Docker image sets STATIC_DIR to its copy of the export.
STATIC_DIR = Path(
    os.environ.get("STATIC_DIR", Path(__file__).resolve().parents[2] / "frontend" / "out")
)

api = APIRouter(prefix="/api")
API_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
COOKIE_NAME = "pm_session"
USERNAME = "user"
PASSWORD = "password"
SESSION_SECRET = os.environ.get("SESSION_SECRET", "local-project-management-mvp")


class LoginRequest(BaseModel):
    username: str
    password: str


def create_session_token(username: str) -> str:
    signature = hmac.new(
        SESSION_SECRET.encode(), username.encode(), hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{username}.{encoded_signature}"


def session_username(session: str | None) -> str | None:
    if not session:
        return None

    username, separator, signature = session.partition(".")
    if not separator or username != USERNAME:
        return None

    expected = create_session_token(username)
    return username if hmac.compare_digest(session, expected) else None


@api.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@api.post("/login")
def login(credentials: LoginRequest, response: Response) -> dict[str, str]:
    valid_username = hmac.compare_digest(credentials.username, USERNAME)
    valid_password = hmac.compare_digest(credentials.password, PASSWORD)
    if not valid_username or not valid_password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_token(USERNAME),
        httponly=True,
        samesite="lax",
        max_age=86_400,
    )
    return {"username": USERNAME}


@api.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, httponly=True, samesite="lax")


@api.get("/me")
def me(pm_session: str | None = Cookie(default=None)) -> dict[str, str]:
    username = session_username(pm_session)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"username": username}


@api.api_route(
    "/{path:path}",
    methods=API_METHODS,
)
def api_not_found(path: str) -> None:
    raise HTTPException(status_code=404, detail="Not Found")


def api_root_not_found() -> None:
    raise HTTPException(status_code=404, detail="Not Found")


def create_app(static_dir: Path) -> FastAPI:
    app = FastAPI(title="Project Management MVP")
    app.include_router(api)
    app.add_api_route("/api", api_root_not_found, methods=API_METHODS)
    # Mounted last so registered /api routes take precedence over static files.
    # check_dir=False lets the API run before the frontend has been built.
    app.mount("/", StaticFiles(directory=static_dir, html=True, check_dir=False), name="static")
    return app


app = create_app(STATIC_DIR)
