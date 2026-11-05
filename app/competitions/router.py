from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Competition, Result, User
from app.templating import _, templates

router = APIRouter(prefix="/competitions", tags=["competitions"])


@router.get("")
def competition_list(
    request: Request,
    status: str = Query("upcoming", pattern="^(upcoming|completed|all)$"),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Competition).filter(Competition.category == "WC", Competition.gender == "M")
    if status != "all":
        query = query.filter(Competition.status == status)
    competitions = query.order_by(Competition.date.desc()).all()
    return templates.TemplateResponse(
        "competitions/list.html",
        {"request": request, "user": user, "competitions": competitions, "status": status},
    )


@router.get("/{competition_id}")
def competition_detail(
    competition_id: int,
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    competition = db.query(Competition).filter(Competition.id == competition_id).first()
    if not competition:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "user": user, "message": _("err_competition_not_found")},
            status_code=404,
        )

    results = db.query(Result).filter(Result.competition_id == competition_id).order_by(Result.rank).all()

    user_bets = []
    if user:
        from app.models import Bet

        user_bets = (
            db.query(Bet)
            .filter(Bet.user_id == user.id, Bet.competition_id == competition_id)
            .order_by(Bet.position)
            .all()
        )

    return templates.TemplateResponse(
        "competitions/detail.html",
        {
            "request": request,
            "user": user,
            "competition": competition,
            "results": results,
            "user_bets": user_bets,
            "betting_open": competition.betting_open,
        },
    )
