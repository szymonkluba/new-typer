from sqlalchemy.orm import Session

from app.models import Bet, Result

EXACT_MATCH_POINTS = 3
PARTIAL_MATCH_POINTS = 1


def score_bet(bet: Bet, podium: dict[int, str]) -> int:
    """Score a single bet against the podium.

    podium: {1: "ATHLETE NAME", 2: "ATHLETE NAME", 3: "ATHLETE NAME"}
    """
    name = normalize_name(bet.athlete_name)
    podium_names = {pos: normalize_name(n) for pos, n in podium.items()}

    if podium_names.get(bet.position) == name:
        return EXACT_MATCH_POINTS
    if name in podium_names.values():
        return PARTIAL_MATCH_POINTS
    return 0


def score_competition_bets(db: Session, competition_id: int) -> dict[int, int]:
    """Score all bets for a competition. Returns {user_id: total_points}."""
    results = db.query(Result).filter(Result.competition_id == competition_id, Result.rank <= 3).all()
    if len(results) < 3:
        return {}

    podium = {r.rank: r.athlete_name for r in results}

    bets = db.query(Bet).filter(Bet.competition_id == competition_id).all()
    scores: dict[int, int] = {}
    for bet in bets:
        pts = score_bet(bet, podium)
        scores[bet.user_id] = scores.get(bet.user_id, 0) + pts

    return scores


def get_user_total_points(db: Session, user_id: int) -> int:
    """Calculate total points for a user across all completed competitions."""
    from app.models import Competition

    completed = db.query(Competition).filter(Competition.status == "completed").all()

    total = 0
    for comp in completed:
        results = db.query(Result).filter(Result.competition_id == comp.id, Result.rank <= 3).all()
        if len(results) < 3:
            continue
        podium = {r.rank: r.athlete_name for r in results}

        bets = db.query(Bet).filter(Bet.user_id == user_id, Bet.competition_id == comp.id).all()
        for bet in bets:
            total += score_bet(bet, podium)

    return total


def normalize_name(name: str) -> str:
    return " ".join(name.upper().split())
