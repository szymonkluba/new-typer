from datetime import date, timedelta


class TestCompetitionList:
    def test_competitions_list_default_upcoming(self, client, make_competition):
        c = make_competition(name="Wisla WC", status="upcoming")
        make_competition(name="Oberstdorf WC", status="completed")
        resp = client.get("/competitions")
        assert resp.status_code == 200
        assert "Wisla WC" in resp.text
        assert "Oberstdorf WC" not in resp.text

    def test_competitions_list_completed(self, client, make_competition):
        make_competition(name="Wisla WC", status="upcoming")
        make_competition(name="Oberstdorf WC", status="completed")
        resp = client.get("/competitions?status=completed")
        assert resp.status_code == 200
        assert "Oberstdorf WC" in resp.text
        assert "Wisla WC" not in resp.text

    def test_competitions_list_all(self, client, make_competition):
        make_competition(name="Wisla WC", status="upcoming")
        make_competition(name="Oberstdorf WC", status="completed")
        resp = client.get("/competitions?status=all")
        assert resp.status_code == 200
        assert "Wisla WC" in resp.text
        assert "Oberstdorf WC" in resp.text

    def test_competitions_list_invalid_status(self, client):
        resp = client.get("/competitions?status=invalid")
        assert resp.status_code == 422

    def test_competitions_list_filters_non_wc(self, client, make_competition):
        make_competition(name="GP Event", category="GP")
        make_competition(name="WC Event", category="WC")
        resp = client.get("/competitions?status=all")
        assert "GP Event" not in resp.text
        assert "WC Event" in resp.text

    def test_competitions_list_filters_women(self, client, make_competition):
        make_competition(name="Women Event", gender="W")
        make_competition(name="Men Event", gender="M")
        resp = client.get("/competitions?status=all")
        assert "Women Event" not in resp.text
        assert "Men Event" in resp.text

    def test_competitions_list_empty(self, client):
        resp = client.get("/competitions")
        assert resp.status_code == 200

    def test_competitions_list_order_descending(self, client, make_competition):
        make_competition(name="Earlier", comp_date=date(2025, 1, 1))
        make_competition(name="Later", comp_date=date(2025, 6, 1))
        resp = client.get("/competitions?status=all")
        assert resp.status_code == 200
        text = resp.text
        assert text.index("Later") < text.index("Earlier")

    def test_competitions_list_anonymous(self, client, make_competition):
        make_competition()
        resp = client.get("/competitions")
        assert resp.status_code == 200

    def test_competitions_list_authenticated(self, client, make_user, auth_client, make_competition):
        user = make_user(username="compuser")
        make_competition()
        ac = auth_client(user)
        resp = ac.get("/competitions")
        assert resp.status_code == 200
        assert "compuser" in resp.text


class TestCompetitionDetail:
    def test_competition_detail_found(self, client, make_competition):
        comp = make_competition(name="Zakopane WC")
        resp = client.get(f"/competitions/{comp.id}")
        assert resp.status_code == 200
        assert "Zakopane WC" in resp.text

    def test_competition_detail_not_found(self, client):
        resp = client.get("/competitions/9999")
        assert resp.status_code == 404
        assert "Competition not found" in resp.text

    def test_competition_detail_shows_results(self, client, make_competition, make_result):
        comp = make_competition(status="completed")
        make_result(comp.id, 1, "Stefan Kraft", "AUT")
        resp = client.get(f"/competitions/{comp.id}")
        assert resp.status_code == 200
        assert "Stefan Kraft" in resp.text

    def test_competition_detail_results_ordered_by_rank(self, client, make_competition, make_result):
        comp = make_competition(status="completed")
        make_result(comp.id, 3, "Third", "NOR")
        make_result(comp.id, 1, "First", "POL")
        make_result(comp.id, 2, "Second", "GER")
        resp = client.get(f"/competitions/{comp.id}")
        text = resp.text
        assert text.index("First") < text.index("Second") < text.index("Third")

    def test_competition_detail_shows_user_bets(self, client, make_user, auth_client, make_competition, make_bet):
        user = make_user()
        comp = make_competition()
        make_bet(user.id, comp.id, 1, "My Pick")
        ac = auth_client(user)
        resp = ac.get(f"/competitions/{comp.id}")
        assert resp.status_code == 200
        assert "My Pick" in resp.text

    def test_competition_detail_no_bets_anonymous(self, client, make_competition):
        comp = make_competition()
        resp = client.get(f"/competitions/{comp.id}")
        assert resp.status_code == 200

    def test_competition_detail_no_bets_for_user(self, client, make_user, auth_client, make_competition):
        user = make_user()
        comp = make_competition()
        ac = auth_client(user)
        resp = ac.get(f"/competitions/{comp.id}")
        assert resp.status_code == 200

    def test_competition_detail_shows_bet_form_upcoming(self, client, make_user, auth_client, make_competition):
        user = make_user()
        comp = make_competition(status="upcoming")
        ac = auth_client(user)
        resp = ac.get(f"/competitions/{comp.id}")
        assert resp.status_code == 200
        assert f"/bets/place/{comp.id}" in resp.text

    def test_competition_detail_no_form_completed(self, client, make_user, auth_client, make_competition):
        user = make_user()
        comp = make_competition(status="completed")
        ac = auth_client(user)
        resp = ac.get(f"/competitions/{comp.id}")
        assert resp.status_code == 200
        assert "/bets/place/" not in resp.text
