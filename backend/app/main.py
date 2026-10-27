import base64
import hashlib
import hmac
import os
import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import httpx2
from fastapi import APIRouter, Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictInt, StringConstraints

from app import ai, board
from app.db import DATABASE_PATH, connect, init_db

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


Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class LoginRequest(BaseModel):
    username: str
    password: str


class RenameColumnRequest(BaseModel):
    title: Title


class CreateCardRequest(BaseModel):
    column_id: str = Field(alias="columnId")
    title: Title
    details: str


class UpdateCardRequest(BaseModel):
    title: Title
    details: str


class AITestRequest(BaseModel):
    prompt: Title


class MoveCardRequest(BaseModel):
    column_id: str = Field(alias="columnId")
    position: StrictInt


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


def require_username(pm_session: str | None = Cookie(default=None)) -> str:
    username = session_username(pm_session)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return username


@api.get("/me")
def me(username: str = Depends(require_username)) -> dict[str, str]:
    return {"username": username}


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    # One transaction per request: committed on success, rolled back on any error.
    conn = connect(request.app.state.database_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


Db = Annotated[sqlite3.Connection, Depends(get_db)]
Username = Annotated[str, Depends(require_username)]


@api.get("/board")
def read_board(username: Username, conn: Db) -> dict:
    return board.get_board(conn, board.get_or_create_board_id(conn, username))


@api.patch("/columns/{column_id}")
def rename_column(column_id: str, body: RenameColumnRequest, username: Username, conn: Db) -> dict:
    board_id = board.get_or_create_board_id(conn, username)
    board.rename_column(conn, board_id, column_id, body.title)
    return board.get_board(conn, board_id)


@api.post("/cards", status_code=201)
def create_card(body: CreateCardRequest, username: Username, conn: Db) -> dict:
    board_id = board.get_or_create_board_id(conn, username)
    board.create_card(conn, board_id, body.column_id, body.title, body.details)
    return board.get_board(conn, board_id)


@api.patch("/cards/{card_id}")
def update_card(card_id: str, body: UpdateCardRequest, username: Username, conn: Db) -> dict:
    board_id = board.get_or_create_board_id(conn, username)
    board.update_card(conn, board_id, card_id, body.title, body.details)
    return board.get_board(conn, board_id)


@api.post("/cards/{card_id}/move")
def move_card(card_id: str, body: MoveCardRequest, username: Username, conn: Db) -> dict:
    board_id = board.get_or_create_board_id(conn, username)
    board.move_card(conn, board_id, card_id, body.column_id, body.position)
    return board.get_board(conn, board_id)


@api.delete("/cards/{card_id}")
def delete_card(card_id: str, username: Username, conn: Db) -> dict:
    board_id = board.get_or_create_board_id(conn, username)
    board.delete_card(conn, board_id, card_id)
    return board.get_board(conn, board_id)


@api.post("/ai/test")
def ai_test(body: AITestRequest, request: Request, username: Username) -> dict[str, str]:
    try:
        reply = ai.chat(
            [{"role": "user", "content": body.prompt}],
            transport=request.app.state.ai_transport,
        )
    except ai.AINotConfiguredError:
        raise HTTPException(status_code=503, detail="AI is not configured") from None
    except ai.AIUpstreamError:
        raise HTTPException(status_code=502, detail="AI provider request failed") from None
    return {"reply": reply}


@api.api_route(
    "/{path:path}",
    methods=API_METHODS,
)
def api_not_found(path: str) -> None:
    raise HTTPException(status_code=404, detail="Not Found")


def api_root_not_found() -> None:
    raise HTTPException(status_code=404, detail="Not Found")


def create_app(
    static_dir: Path,
    database_path: Path = DATABASE_PATH,
    ai_transport: httpx2.BaseTransport | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(database_path, [USERNAME])
        yield

    app = FastAPI(title="Project Management MVP", lifespan=lifespan)
    app.state.database_path = database_path
    # None uses the real network; tests pass an httpx2.MockTransport.
    app.state.ai_transport = ai_transport

    @app.exception_handler(board.NotFoundError)
    async def not_found(request: Request, exc: board.NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(board.InvalidMoveError)
    async def invalid_move(request: Request, exc: board.InvalidMoveError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    app.include_router(api)
    app.add_api_route("/api", api_root_not_found, methods=API_METHODS)
    # Mounted last so registered /api routes take precedence over static files.
    # check_dir=False lets the API run before the frontend has been built.
    app.mount("/", StaticFiles(directory=static_dir, html=True, check_dir=False), name="static")
    return app


app = create_app(STATIC_DIR)
