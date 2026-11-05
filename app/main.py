from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.router import router as auth_router
from app.bets.router import router as bets_router
from app.competitions.router import router as competitions_router
from app.database import create_tables, get_db
from app.i18n import DEFAULT_LANG, SUPPORTED_LANGS
from app.models import Competition, User
from app.ranking.router import router as ranking_router
from app.scraper.scheduler import start_scheduler, stop_scheduler
from app.templating import current_lang, templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Typer - Ski Jumping Prediction Market", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.middleware("http")
async def language_middleware(request: Request, call_next):
    lang = request.cookies.get("lang", DEFAULT_LANG)
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    token = current_lang.set(lang)
    try:
        response = await call_next(request)
    finally:
        current_lang.reset(token)
    return response

app.include_router(auth_router)
app.include_router(competitions_router)
app.include_router(bets_router)
app.include_router(ranking_router)


@app.get("/set-lang")
def set_lang(request: Request, lang: str = Query(...)):
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    referer = request.headers.get("referer", "/")
    if not referer.startswith("/") and not referer.startswith(str(request.base_url)):
        referer = "/"
    response = RedirectResponse(url=referer, status_code=303)
    response.set_cookie("lang", lang, max_age=365 * 24 * 3600)
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    upcoming = (
        db.query(Competition)
        .filter(Competition.status == "upcoming", Competition.category == "WC", Competition.gender == "M")
        .order_by(Competition.date)
        .limit(5)
        .all()
    )

    from app.bets.scoring import score_bet
    from app.models import Bet, Result

    users = db.query(User).all()
    completed_comps = db.query(Competition).filter(Competition.status == "completed").all()

    podiums: dict[int, dict[int, str]] = {}
    for comp in completed_comps:
        results = db.query(Result).filter(Result.competition_id == comp.id, Result.rank <= 3).all()
        if len(results) >= 3:
            podiums[comp.id] = {r.rank: r.athlete_name for r in results}

    player_points = []
    for u in users:
        total = 0
        bets = db.query(Bet).filter(Bet.user_id == u.id).all()
        for bet in bets:
            podium = podiums.get(bet.competition_id)
            if podium:
                total += score_bet(bet, podium)
        player_points.append({"user": u, "points": total})

    player_points.sort(key=lambda p: p["points"], reverse=True)
    top_players = player_points[:3]

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "user": user, "upcoming": upcoming, "top_players": top_players},
    )
