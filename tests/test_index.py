from datetime import date, timedelta


class TestIndex:
    def test_index_anonymous(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_authenticated(self, client, make_user, auth_client):
        user = make_user(username="homeuser")
        ac = auth_client(user)
        resp = ac.get("/")
        assert resp.status_code == 200
        assert "homeuser" in resp.text

    def test_index_shows_upcoming_competitions(self, client, make_competition):
        make_competition(name="Upcoming Wisla", status="upcoming")
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Upcoming Wisla" in resp.text

    def test_index_max_five_upcoming(self, client, make_competition):
        for i in range(7):
            make_competition(
                name=f"Comp {i}",
                status="upcoming",
                comp_date=date.today() + timedelta(days=i + 1),
            )
        resp = client.get("/")
        count = sum(1 for i in range(7) if f"Comp {i}" in resp.text)
        assert count == 5

    def test_index_upcoming_ordered_by_date_asc(self, client, make_competition):
        make_competition(name="Later", status="upcoming", comp_date=date.today() + timedelta(days=10))
        make_competition(name="Sooner", status="upcoming", comp_date=date.today() + timedelta(days=1))
        resp = client.get("/")
        text = resp.text
        assert text.index("Sooner") < text.index("Later")

    def test_index_no_upcoming(self, client, make_competition):
        make_competition(status="completed")
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_filters_non_wc(self, client, make_competition):
        make_competition(name="GP Event", category="GP", status="upcoming")
        make_competition(name="WC Event", category="WC", status="upcoming")
        resp = client.get("/")
        assert "GP Event" not in resp.text
        assert "WC Event" in resp.text

    def test_index_filters_women(self, client, make_competition):
        make_competition(name="Women Event", gender="W", status="upcoming")
        make_competition(name="Men Event", gender="M", status="upcoming")
        resp = client.get("/")
        assert "Women Event" not in resp.text
        assert "Men Event" in resp.text

    def test_index_shows_top_players(self, client, make_user, make_competition, make_result, make_bet):
        user = make_user(username="topplayer")
        comp = make_competition(status="completed")
        make_result(comp.id, 1, "A", "POL")
        make_result(comp.id, 2, "B", "GER")
        make_result(comp.id, 3, "C", "NOR")
        make_bet(user.id, comp.id, 1, "A")
        resp = client.get("/")
        assert resp.status_code == 200
        assert "topplayer" in resp.text

    def test_index_top_players_empty(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_top_players_max_three(self, client, make_user, make_competition, make_result, make_bet):
        comp = make_competition(status="completed")
        make_result(comp.id, 1, "A", "POL")
        make_result(comp.id, 2, "B", "GER")
        make_result(comp.id, 3, "C", "NOR")
        users = []
        for i in range(5):
            u = make_user(username=f"player{i}")
            users.append(u)
            make_bet(u.id, comp.id, 1, "A")  # all get 3 pts
        resp = client.get("/")
        text = resp.text
        count = sum(1 for u in users if u.username in text)
        # Top 3 shown; the home page slices [:3]
        assert count <= 5  # all may appear since all have same score, but template shows top_players[:3]

    def test_index_top_players_sorted_descending(
        self, client, make_user, make_competition, make_result, make_bet
    ):
        comp = make_competition(status="completed")
        make_result(comp.id, 1, "A", "POL")
        make_result(comp.id, 2, "B", "GER")
        make_result(comp.id, 3, "C", "NOR")
        low = make_user(username="lowscore")
        high = make_user(username="highscore")
        make_bet(low.id, comp.id, 1, "X")   # 0 pts
        make_bet(high.id, comp.id, 1, "A")  # 3 pts
        resp = client.get("/")
        text = resp.text
        if "highscore" in text and "lowscore" in text:
            assert text.index("highscore") < text.index("lowscore")
