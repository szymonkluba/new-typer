from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.bets.scoring import score_bet
from app.database import get_db
from app.models import Bet, Competition, Result, User

router = APIRouter(prefix="/ranking", tags=["ranking"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def leaderboard(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    users = db.query(User).all()

    completed_comps = db.query(Competition).filter(Competition.status == "completed").all()

    podiums: dict[int, dict[int, str]] = {}
    for comp in completed_comps:
        results = db.query(Result).filter(Result.competition_id == comp.id, Result.rank <= 3).all()
        if len(results) >= 3:
            podiums[comp.id] = {r.rank: r.athlete_name for r in results}

    rankings = []
    for u in users:
        total = 0
        bets = db.query(Bet).filter(Bet.user_id == u.id).all()
        for bet in bets:
            podium = podiums.get(bet.competition_id)
            if podium:
                total += score_bet(bet, podium)
        rankings.append({"user": u, "points": total})

    rankings.sort(key=lambda r: r["points"], reverse=True)

    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    return templates.TemplateResponse(
        "ranking/leaderboard.html",
        {"request": request, "user": user, "rankings": rankings},
    )
