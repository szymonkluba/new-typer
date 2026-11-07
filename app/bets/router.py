from html import escape

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.bets.scoring import score_bet
from app.database import get_db
from app.models import Athlete, Bet, Competition, Result, User
from app.templating import _, templates

router = APIRouter(prefix="/bets", tags=["bets"])


@router.post("/place/{competition_id}")
def place_bet(
    competition_id: int,
    request: Request,
    first: str = Form(...),
    second: str = Form(...),
    third: str = Form(...),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    competition = db.query(Competition).filter(Competition.id == competition_id).first()
    if not competition or not competition.betting_open:
        return RedirectResponse(url="/competitions", status_code=303)

    existing = db.query(Bet).filter(Bet.user_id == user.id, Bet.competition_id == competition_id).all()
    for bet in existing:
        db.delete(bet)
    if existing:
        db.flush()

    for position, name in [(1, first), (2, second), (3, third)]:
        name = name.strip()
        if name:
            db.add(
                Bet(
                    user_id=user.id,
                    competition_id=competition_id,
                    position=position,
                    athlete_name=name,
                )
            )
    db.commit()

    return RedirectResponse(url=f"/competitions/{competition_id}", status_code=303)


@router.get("/my")
def my_bets(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    bets = db.query(Bet).filter(Bet.user_id == user.id).order_by(Bet.created_at.desc()).all()

    bet_details = []
    for bet in bets:
        comp = bet.competition
        points = None
        if comp.status == "completed":
            results = db.query(Result).filter(Result.competition_id == comp.id, Result.rank <= 3).all()
            if len(results) >= 3:
                podium = {r.rank: r.athlete_name for r in results}
                points = score_bet(bet, podium)
        bet_details.append({"bet": bet, "competition": comp, "points": points})

    return templates.TemplateResponse(
        "bets/my_bets.html",
        {"request": request, "user": user, "bet_details": bet_details},
    )


@router.get("/athletes", response_class=HTMLResponse)
def athlete_autocomplete(
    q: str = "",
    first: str = "",
    second: str = "",
    third: str = "",
    db: Session = Depends(get_db),
):
    q = q or first or second or third
    if len(q) < 2:
        return ""
    athletes = (
        db.query(Athlete.name, Athlete.nation)
        .filter(Athlete.name.ilike(f"%{q}%"))
        .order_by(Athlete.name)
        .limit(10)
        .all()
    )
    if not athletes:
        return f'<div class="suggestion-empty">{escape(_("no_athletes_found"))}</div>'
    html = "".join(
        f'<a href="#" class="suggestion-item"'
        f' onclick="event.preventDefault();'
        f"this.closest('.form-group').querySelector('input').value="
        f"'{escape(name).replace(chr(39), chr(92) + chr(39))}';"
        f"this.closest('.suggestions').innerHTML=''\">"
        f'<span class="suggestion-name">{escape(name)}</span>'
        f'<span class="suggestion-nation">{escape(nation)}</span>'
        f"</a>"
        for name, nation in athletes
    )
    return html
