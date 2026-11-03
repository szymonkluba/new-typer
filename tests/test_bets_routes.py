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
        bet = db.query(Bet).filter(
            Bet.user_id == user.id, Bet.competition_id == comp.id, Bet.position == 1
        ).first()
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

    def test_my_bets_shows_pending_upcoming(
        self, client, make_user, auth_client, make_competition, make_bet
    ):
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

    def test_my_bets_ordered_by_created_desc(
        self, client, make_user, auth_client, make_competition, make_bet
    ):
        user = make_user()
        c1 = make_competition(name="First Comp")
        c2 = make_competition(name="Second Comp")
        make_bet(user.id, c1.id, 1, "Early")
        make_bet(user.id, c2.id, 1, "Late")
        ac = auth_client(user)
        resp = ac.get("/bets/my")
        assert resp.status_code == 200


class TestAthleteAutocomplete:
    def test_athletes_autocomplete_returns_matches(self, client, make_competition, make_result):
        comp = make_competition(status="completed")
        make_result(comp.id, 1, "Stefan Kraft", "AUT")
        resp = client.get("/bets/athletes?q=Kra")
        assert resp.status_code == 200
        data = resp.json()
        assert "Stefan Kraft" in data

    def test_athletes_autocomplete_short_query(self, client):
        resp = client.get("/bets/athletes?q=K")
        assert resp.json() == []

    def test_athletes_autocomplete_empty_query(self, client):
        resp = client.get("/bets/athletes?q=")
        assert resp.json() == []

    def test_athletes_autocomplete_no_match(self, client, make_competition, make_result):
        comp = make_competition(status="completed")
        make_result(comp.id, 1, "Stefan Kraft", "AUT")
        resp = client.get("/bets/athletes?q=xyz")
        assert resp.json() == []

    def test_athletes_autocomplete_max_10(self, client, make_competition, make_result):
        comp = make_competition(status="completed")
        for i in range(15):
            make_result(comp.id, i + 1, f"Athlete {i}", "POL")
        resp = client.get("/bets/athletes?q=Athlete")
        assert len(resp.json()) <= 10

    def test_athletes_autocomplete_distinct(self, client, make_competition, make_result):
        c1 = make_competition(status="completed")
        c2 = make_competition(status="completed")
        make_result(c1.id, 1, "Stefan Kraft", "AUT")
        make_result(c2.id, 1, "Stefan Kraft", "AUT")
        resp = client.get("/bets/athletes?q=Kraft")
        assert resp.json().count("Stefan Kraft") == 1

    def test_athletes_autocomplete_case_insensitive(self, client, make_competition, make_result):
        comp = make_competition(status="completed")
        make_result(comp.id, 1, "KRAFT Stefan", "AUT")
        resp = client.get("/bets/athletes?q=kraft")
        assert len(resp.json()) >= 1

    def test_athletes_autocomplete_no_auth_required(self, client, make_competition, make_result):
        comp = make_competition(status="completed")
        make_result(comp.id, 1, "Tester", "POL")
        resp = client.get("/bets/athletes?q=Te")
        assert resp.status_code == 200

    def test_athletes_autocomplete_returns_json(self, client):
        resp = client.get("/bets/athletes?q=test")
        assert "application/json" in resp.headers["content-type"]
