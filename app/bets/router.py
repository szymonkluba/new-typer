from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.bets.scoring import score_bet
from app.database import get_db
from app.models import Bet, Competition, Result, User
from app.templating import templates

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
    if not competition or competition.status != "upcoming":
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
    db: Session = Depends(get_db),
):
    if len(q) < 2:
        return ""
    names = db.query(Result.athlete_name).filter(Result.athlete_name.ilike(f"%{q}%")).distinct().limit(10).all()
    html = "".join(
        f'<a href="#" onclick="event.preventDefault();'
        f"this.closest('.form-group').querySelector('input').value='{n[0].replace(chr(39), chr(92)+chr(39))}';"
        f"this.parentElement.innerHTML=''\">{n[0]}</a>"
        for n in names
    )
    return html
