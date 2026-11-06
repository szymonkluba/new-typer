from types import SimpleNamespace

from app.bets.scoring import (
    EXACT_MATCH_POINTS,
    PARTIAL_MATCH_POINTS,
    get_user_total_points,
    normalize_name,
    score_bet,
    score_competition_bets,
)


def _fake_bet(position, athlete_name):
    return SimpleNamespace(position=position, athlete_name=athlete_name)


# --- normalize_name ---


def test_normalize_name_basic():
    assert normalize_name("John Doe") == "JOHN DOE"


def test_normalize_name_extra_whitespace():
    assert normalize_name("  john   doe  ") == "JOHN DOE"


def test_normalize_name_already_upper():
    assert normalize_name("JOHN DOE") == "JOHN DOE"


def test_normalize_name_single_word():
    assert normalize_name("krafty") == "KRAFTY"


def test_normalize_name_empty_string():
    assert normalize_name("") == ""


def test_normalize_name_tabs_and_newlines():
    assert normalize_name("john\tdoe\n") == "JOHN DOE"


# --- score_bet ---


def test_score_bet_exact_match():
    bet = _fake_bet(1, "Stefan Kraft")
    podium = {1: "Stefan Kraft", 2: "Dawid Kubacki", 3: "Halvor Granerud"}
    assert score_bet(bet, podium) == EXACT_MATCH_POINTS


def test_score_bet_partial_match():
    bet = _fake_bet(1, "Dawid Kubacki")
    podium = {1: "Stefan Kraft", 2: "Dawid Kubacki", 3: "Halvor Granerud"}
    assert score_bet(bet, podium) == PARTIAL_MATCH_POINTS


def test_score_bet_no_match():
    bet = _fake_bet(1, "Nobody Here")
    podium = {1: "Stefan Kraft", 2: "Dawid Kubacki", 3: "Halvor Granerud"}
    assert score_bet(bet, podium) == 0


def test_score_bet_case_insensitive():
    bet = _fake_bet(1, "stefan kraft")
    podium = {1: "STEFAN KRAFT", 2: "Dawid Kubacki", 3: "Halvor Granerud"}
    assert score_bet(bet, podium) == EXACT_MATCH_POINTS


def test_score_bet_whitespace_insensitive():
    bet = _fake_bet(1, "  Stefan  Kraft ")
    podium = {1: "Stefan Kraft", 2: "Dawid Kubacki", 3: "Halvor Granerud"}
    assert score_bet(bet, podium) == EXACT_MATCH_POINTS


def test_score_bet_all_three_exact():
    podium = {1: "A", 2: "B", 3: "C"}
    total = sum(score_bet(_fake_bet(pos, name), podium) for pos, name in [(1, "A"), (2, "B"), (3, "C")])
    assert total == 9


def test_score_bet_all_three_partial():
    podium = {1: "A", 2: "B", 3: "C"}
    total = sum(score_bet(_fake_bet(pos, name), podium) for pos, name in [(1, "B"), (2, "C"), (3, "A")])
    assert total == 3


def test_score_bet_mixed():
    podium = {1: "A", 2: "B", 3: "C"}
    exact = score_bet(_fake_bet(1, "A"), podium)
    partial = score_bet(_fake_bet(2, "C"), podium)
    miss = score_bet(_fake_bet(3, "X"), podium)
    assert exact + partial + miss == 4


# --- score_competition_bets (needs DB) ---


def test_score_competition_bets_happy_path(db, make_user, make_competition, make_result, make_bet):
    user = make_user()
    comp = make_competition(status="completed")
    make_result(comp.id, 1, "A", "POL")
    make_result(comp.id, 2, "B", "GER")
    make_result(comp.id, 3, "C", "NOR")
    make_bet(user.id, comp.id, 1, "A")
    make_bet(user.id, comp.id, 2, "B")
    make_bet(user.id, comp.id, 3, "X")
    scores = score_competition_bets(db, comp.id)
    assert scores[user.id] == 6  # 3 + 3 + 0


def test_score_competition_bets_less_than_3_results(db, make_competition, make_result):
    comp = make_competition(status="completed")
    make_result(comp.id, 1, "A", "POL")
    make_result(comp.id, 2, "B", "GER")
    assert score_competition_bets(db, comp.id) == {}


def test_score_competition_bets_no_bets(db, make_competition, make_result):
    comp = make_competition(status="completed")
    make_result(comp.id, 1, "A", "POL")
    make_result(comp.id, 2, "B", "GER")
    make_result(comp.id, 3, "C", "NOR")
    assert score_competition_bets(db, comp.id) == {}


def test_score_competition_bets_multiple_users(db, make_user, make_competition, make_result, make_bet):
    u1 = make_user()
    u2 = make_user()
    comp = make_competition(status="completed")
    make_result(comp.id, 1, "A", "POL")
    make_result(comp.id, 2, "B", "GER")
    make_result(comp.id, 3, "C", "NOR")
    make_bet(u1.id, comp.id, 1, "A")  # exact 3
    make_bet(u2.id, comp.id, 1, "B")  # partial 1
    scores = score_competition_bets(db, comp.id)
    assert scores[u1.id] == 3
    assert scores[u2.id] == 1


def test_score_competition_bets_ignores_non_podium(db, make_user, make_competition, make_result, make_bet):
    user = make_user()
    comp = make_competition(status="completed")
    make_result(comp.id, 1, "A", "POL")
    make_result(comp.id, 2, "B", "GER")
    make_result(comp.id, 3, "C", "NOR")
    make_result(comp.id, 4, "D", "AUT")
    make_bet(user.id, comp.id, 1, "D")  # D is rank 4, not podium
    scores = score_competition_bets(db, comp.id)
    assert scores[user.id] == 0


# --- get_user_total_points (needs DB) ---


def test_get_user_total_points_single_competition(db, make_user, make_competition, make_result, make_bet):
    user = make_user()
    comp = make_competition(status="completed")
    make_result(comp.id, 1, "A", "POL")
    make_result(comp.id, 2, "B", "GER")
    make_result(comp.id, 3, "C", "NOR")
    make_bet(user.id, comp.id, 1, "A")  # exact 3
    assert get_user_total_points(db, user.id) == 3


def test_get_user_total_points_multiple_competitions(db, make_user, make_competition, make_result, make_bet):
    user = make_user()
    c1 = make_competition(status="completed")
    c2 = make_competition(status="completed")
    for c in [c1, c2]:
        make_result(c.id, 1, "A", "POL")
        make_result(c.id, 2, "B", "GER")
        make_result(c.id, 3, "C", "NOR")
    make_bet(user.id, c1.id, 1, "A")  # 3
    make_bet(user.id, c2.id, 1, "A")  # 3
    assert get_user_total_points(db, user.id) == 6


def test_get_user_total_points_no_completed(db, make_user, make_competition):
    user = make_user()
    make_competition(status="upcoming")
    assert get_user_total_points(db, user.id) == 0


def test_get_user_total_points_no_bets(db, make_user, make_competition, make_result):
    user = make_user()
    comp = make_competition(status="completed")
    make_result(comp.id, 1, "A", "POL")
    make_result(comp.id, 2, "B", "GER")
    make_result(comp.id, 3, "C", "NOR")
    assert get_user_total_points(db, user.id) == 0


def test_get_user_total_points_ignores_upcoming(db, make_user, make_competition, make_result, make_bet):
    user = make_user()
    comp = make_competition(status="upcoming")
    make_result(comp.id, 1, "A", "POL")
    make_result(comp.id, 2, "B", "GER")
    make_result(comp.id, 3, "C", "NOR")
    make_bet(user.id, comp.id, 1, "A")
    assert get_user_total_points(db, user.id) == 0


def test_get_user_total_points_incomplete_podium(db, make_user, make_competition, make_result, make_bet):
    user = make_user()
    comp = make_competition(status="completed")
    make_result(comp.id, 1, "A", "POL")
    make_result(comp.id, 2, "B", "GER")
    make_bet(user.id, comp.id, 1, "A")
    assert get_user_total_points(db, user.id) == 0


# --- end-to-end canonical name scoring ---


def test_scoring_with_canonical_athlete_names(db, make_user, make_competition, make_result, make_bet):
    """Verify scoring works when all names come from the same Athlete record."""
    user = make_user()
    comp = make_competition(status="completed")
    make_result(comp.id, 1, "KRAFT Stefan", "AUT", fis_code=6996)
    make_result(comp.id, 2, "KUBACKI Dawid", "POL", fis_code=6997)
    make_result(comp.id, 3, "GRANERUD Halvor Egner", "NOR", fis_code=6998)
    make_bet(user.id, comp.id, 1, "KRAFT Stefan")
    make_bet(user.id, comp.id, 2, "KUBACKI Dawid")
    make_bet(user.id, comp.id, 3, "GRANERUD Halvor Egner")
    scores = score_competition_bets(db, comp.id)
    assert scores[user.id] == 9


def test_normalize_name_unicode_nfkc():
    name_with_nbsp = "KRAFT Stefan"
    assert normalize_name(name_with_nbsp) == "KRAFT STEFAN"
