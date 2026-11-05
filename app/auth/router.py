from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import create_session_token, get_current_user
from app.auth.utils import hash_password, verify_password
from app.config import COOKIE_MAX_AGE, COOKIE_NAME
from app.database import get_db
from app.models import User
from app.templating import _, templates

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/register")
def register_page(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    errors = []
    if len(username) < 3:
        errors.append(_("err_username_short"))
    if len(password) < 6:
        errors.append(_("err_password_short"))
    if password != password_confirm:
        errors.append(_("err_password_mismatch"))
    if db.query(User).filter(User.username == username).first():
        errors.append(_("err_username_taken"))

    if errors:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "errors": errors, "username": username},
        )

    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()

    response = RedirectResponse(url="/", status_code=303)
    token = create_session_token(user.id)
    response.set_cookie(COOKIE_NAME, token, max_age=COOKIE_MAX_AGE, httponly=True)
    return response


@router.get("/login")
def login_page(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "errors": [_("err_invalid_credentials")], "username": username},
        )

    response = RedirectResponse(url="/", status_code=303)
    token = create_session_token(user.id)
    response.set_cookie(COOKIE_NAME, token, max_age=COOKIE_MAX_AGE, httponly=True)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
