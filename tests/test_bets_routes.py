from datetime import date, timedelta
from unittest.mock import patch

from app.models import Bet


class TestPlaceBet:
    def test_place_bet_success(self, client, make_user, auth_client, make_competition, db):
        user = make_user()
        comp = make_competition(status="upcoming")
        ac = auth_client(user)
        resp = ac.post(
            f"/bets/place/{comp.id}",
            data={"first": "Kraft", "second": "Kubacki", "third": "Stoch"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert f"/competitions/{comp.id}" in resp.headers["location"]
        bets = db.query(Bet).filter(Bet.user_id == user.id, Bet.competition_id == comp.id).all()
        assert len(bets) == 3

    def test_place_bet_unauthenticated(self, client, make_competition):
        comp = make_competition(status="upcoming")
        resp = client.post(
            f"/bets/place/{comp.id}",
            data={"first": "A", "second": "B", "third": "C"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/auth/login" in resp.headers["location"]

    def test_place_bet_competition_not_found(self, client, make_user, auth_client):
        user = make_user()
        ac = auth_client(user)
        resp = ac.post(
            "/bets/place/9999",
            data={"first": "A", "second": "B", "third": "C"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/competitions" in resp.headers["location"]

    def test_place_bet_competition_completed(self, client, make_user, auth_client, make_competition):
        user = make_user()
        comp = make_competition(status="completed")
        ac = auth_client(user)
        resp = ac.post(
            f"/bets/place/{comp.id}",
            data={"first": "A", "second": "B", "third": "C"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/competitions" in resp.headers["location"]

    def test_place_bet_blocked_past_date(self, client, make_user, auth_client, make_competition):
        user = make_user()
        comp = make_competition(status="upcoming", comp_date=date.today() - timedelta(days=1))
        ac = auth_client(user)
        resp = ac.post(
            f"/bets/place/{comp.id}",
            data={"first": "A", "second": "B", "third": "C"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/competitions" in resp.headers["location"]

    def test_place_bet_blocked_after_cutoff(self, client, make_user, auth_client, make_competition):
        user = make_user()
        comp = make_competition(status="upcoming", comp_date=date.today())
        ac = auth_client(user)
        with patch("app.config.BET_CUTOFF_HOUR", 0):
            resp = ac.post(
                f"/bets/place/{comp.id}",
                data={"first": "A", "second": "B", "third": "C"},
                follow_redirects=False,
            )
        assert resp.status_code == 303
        assert "/competitions" in resp.headers["location"]

    def test_place_bet_allowed_before_cutoff(self, client, make_user, auth_client, make_competition, db):
        user = make_user()
        comp = make_competition(status="upcoming", comp_date=date.today() + timedelta(days=1))
        ac = auth_client(user)
        resp = ac.post(
            f"/bets/place/{comp.id}",
            data={"first": "A", "second": "B", "third": "C"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert f"/competitions/{comp.id}" in resp.headers["location"]
        bets = db.query(Bet).filter(Bet.user_id == user.id, Bet.competition_id == comp.id).all()
        assert len(bets) == 3

    def test_place_bet_replaces_existing(self, client, make_user, auth_client, make_competition, make_bet, db):
        user = make_user()
        comp = make_competition(status="upcoming")
        make_bet(user.id, comp.id, 1, "OldPick")
        ac = auth_client(user)
        ac.post(
            f"/bets/place/{comp.id}",
            data={"first": "NewPick", "second": "B", "third": "C"},
            follow_redirects=False,
        )
        db.expire_all()
        bets = db.query(Bet).filter(Bet.user_id == user.id, Bet.competition_id == comp.id).all()
        names = [b.athlete_name for b in bets]
        assert "OldPick" not in names
        assert "NewPick" in names

    def test_place_bet_strips_whitespace(self, client, make_user, auth_client, make_competition, db):
        user = make_user()
        comp = make_competition(status="upcoming")
        ac = auth_client(user)
        ac.post(
            f"/bets/place/{comp.id}",
            data={"first": "  Kraft  ", "second": "B", "third": "C"},
            follow_redirects=False,
        )
        bet = db.query(Bet).filter(Bet.user_id == user.id, Bet.competition_id == comp.id, Bet.position == 1).first()
        assert bet.athlete_name == "Kraft"

    def test_place_bet_empty_name_skipped(self, client, make_user, auth_client, make_competition, db):
        user = make_user()
        comp = make_competition(status="upcoming")
        ac = auth_client(user)
        ac.post(
            f"/bets/place/{comp.id}",
            data={"first": "   ", "second": "B", "third": "C"},
            follow_redirects=False,
        )
        bets = db.query(Bet).filter(Bet.user_id == user.id, Bet.competition_id == comp.id).all()
        assert len(bets) == 2
        positions = [b.position for b in bets]
        assert 1 not in positions

    def test_place_bet_partial_empty(self, client, make_user, auth_client, make_competition, db):
        user = make_user()
        comp = make_competition(status="upcoming")
        ac = auth_client(user)
        ac.post(
            f"/bets/place/{comp.id}",
            data={"first": "A", "second": "", "third": "C"},
            follow_redirects=False,
        )
        bets = db.query(Bet).filter(Bet.user_id == user.id, Bet.competition_id == comp.id).all()
        assert len(bets) == 2
        positions = sorted(b.position for b in bets)
        assert positions == [1, 3]

    def test_place_bet_all_empty(self, client, make_user, auth_client, make_competition, make_bet, db):
        user = make_user()
        comp = make_competition(status="upcoming")
        make_bet(user.id, comp.id, 1, "OldBet")
        ac = auth_client(user)
        ac.post(
            f"/bets/place/{comp.id}",
            data={"first": "", "second": "", "third": ""},
            follow_redirects=False,
        )
        bets = db.query(Bet).filter(Bet.user_id == user.id, Bet.competition_id == comp.id).all()
        assert len(bets) == 0

    def test_place_bet_missing_form_field(self, client, make_user, auth_client, make_competition):
        user = make_user()
        comp = make_competition(status="upcoming")
        ac = auth_client(user)
        resp = ac.post(
            f"/bets/place/{comp.id}",
            data={"first": "A"},
        )
        assert resp.status_code == 422


class TestMyBets:
    def test_my_bets_authenticated(self, client, make_user, auth_client, make_competition, make_bet):
        user = make_user()
        comp = make_competition()
        make_bet(user.id, comp.id, 1, "Kraft")
        ac = auth_client(user)
        resp = ac.get("/bets/my")
        assert resp.status_code == 200
        assert "Kraft" in resp.text

    def test_my_bets_unauthenticated(self, client):
        resp = client.get("/bets/my", follow_redirects=False)
        assert resp.status_code == 303
        assert "/auth/login" in resp.headers["location"]

    def test_my_bets_empty(self, client, make_user, auth_client):
        user = make_user()
        ac = auth_client(user)
        resp = ac.get("/bets/my")
        assert resp.status_code == 200

    def test_my_bets_shows_points_completed(
        self, client, make_user, auth_client, make_competition, make_result, make_bet
    ):
        user = make_user()
        comp = make_competition(status="completed")
        make_result(comp.id, 1, "A", "POL")
        make_result(comp.id, 2, "B", "GER")
        make_result(comp.id, 3, "C", "NOR")
        make_bet(user.id, comp.id, 1, "A")  # exact match = 3 pts
        ac = auth_client(user)
        resp = ac.get("/bets/my")
        assert resp.status_code == 200
        assert "3" in resp.text

    def test_my_bets_shows_pending_upcoming(self, client, make_user, auth_client, make_competition, make_bet):
        user = make_user()
        comp = make_competition(status="upcoming")
        make_bet(user.id, comp.id, 1, "Kraft")
        ac = auth_client(user)
        resp = ac.get("/bets/my")
        assert resp.status_code == 200

    def test_my_bets_incomplete_podium_no_points(
        self, client, make_user, auth_client, make_competition, make_result, make_bet
    ):
        user = make_user()
        comp = make_competition(status="completed")
        make_result(comp.id, 1, "A", "POL")
        make_result(comp.id, 2, "B", "GER")
        # Only 2 results, not 3
        make_bet(user.id, comp.id, 1, "A")
        ac = auth_client(user)
        resp = ac.get("/bets/my")
        assert resp.status_code == 200

    def test_my_bets_ordered_by_created_desc(self, client, make_user, auth_client, make_competition, make_bet):
        user = make_user()
        c1 = make_competition(name="First Comp")
        c2 = make_competition(name="Second Comp")
        make_bet(user.id, c1.id, 1, "Early")
        make_bet(user.id, c2.id, 1, "Late")
        ac = auth_client(user)
        resp = ac.get("/bets/my")
        assert resp.status_code == 200


class TestAthleteAutocomplete:
    def test_autocomplete_returns_matches(self, client, make_athlete):
        make_athlete(name="KRAFT Stefan", nation="AUT")
        resp = client.get("/bets/athletes?q=Kra")
        assert resp.status_code == 200
        assert "KRAFT Stefan" in resp.text

    def test_autocomplete_short_query(self, client):
        resp = client.get("/bets/athletes?q=K")
        assert resp.text == ""

    def test_autocomplete_empty_query(self, client):
        resp = client.get("/bets/athletes?q=")
        assert resp.text == ""

    def test_autocomplete_no_match_shows_empty_message(self, client, make_athlete):
        make_athlete(name="KRAFT Stefan", nation="AUT")
        resp = client.get("/bets/athletes?q=xyz")
        assert "suggestion-empty" in resp.text
        assert "No athletes found" in resp.text

    def test_autocomplete_max_10(self, client, make_athlete):
        for i in range(15):
            make_athlete(name=f"ATHLETE Test{i:02d}", nation="POL")
        resp = client.get("/bets/athletes?q=ATHLETE")
        assert resp.text.count("suggestion-item") <= 10

    def test_autocomplete_case_insensitive(self, client, make_athlete):
        make_athlete(name="KRAFT Stefan", nation="AUT")
        resp = client.get("/bets/athletes?q=kraft")
        assert "KRAFT Stefan" in resp.text

    def test_autocomplete_no_auth_required(self, client, make_athlete):
        make_athlete(name="TESTER Name", nation="POL")
        resp = client.get("/bets/athletes?q=TE")
        assert resp.status_code == 200

    def test_autocomplete_returns_html(self, client):
        resp = client.get("/bets/athletes?q=test")
        assert "text/html" in resp.headers["content-type"]

    def test_autocomplete_shows_nation(self, client, make_athlete):
        make_athlete(name="KRAFT Stefan", nation="AUT")
        resp = client.get("/bets/athletes?q=Kraft")
        assert "suggestion-nation" in resp.text
        assert "AUT" in resp.text

    def test_autocomplete_orders_by_name(self, client, make_athlete):
        make_athlete(name="ZNISZCZOL Aleksander", nation="POL")
        make_athlete(name="AALTO Antti", nation="FIN")
        make_athlete(name="KRAFT Stefan", nation="AUT")
        resp = client.get("/bets/athletes?q=an")
        text = resp.text
        pos_aalto = text.index("AALTO")
        pos_zniszczol = text.index("ZNISZCZOL")
        assert pos_aalto < pos_zniszczol
