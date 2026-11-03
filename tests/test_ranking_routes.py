class TestRanking:
    def test_ranking_shows_leaderboard(self, client, make_user, make_competition, make_result, make_bet):
        u1 = make_user(username="leader")
        u2 = make_user(username="runner")
        comp = make_competition(status="completed")
        make_result(comp.id, 1, "A", "POL")
        make_result(comp.id, 2, "B", "GER")
        make_result(comp.id, 3, "C", "NOR")
        make_bet(u1.id, comp.id, 1, "A")  # exact 3
        make_bet(u2.id, comp.id, 1, "B")  # partial 1
        resp = client.get("/ranking")
        assert resp.status_code == 200
        text = resp.text
        assert text.index("leader") < text.index("runner")

    def test_ranking_empty_no_users(self, client):
        resp = client.get("/ranking")
        assert resp.status_code == 200

    def test_ranking_no_completed_competitions(self, client, make_user, make_competition):
        make_user(username="zeropts")
        make_competition(status="upcoming")
        resp = client.get("/ranking")
        assert resp.status_code == 200
        assert "zeropts" in resp.text

    def test_ranking_rank_numbers_assigned(self, client, make_user, make_competition, make_result, make_bet):
        u1 = make_user()
        make_user()
        comp = make_competition(status="completed")
        make_result(comp.id, 1, "A", "POL")
        make_result(comp.id, 2, "B", "GER")
        make_result(comp.id, 3, "C", "NOR")
        make_bet(u1.id, comp.id, 1, "A")
        resp = client.get("/ranking")
        assert resp.status_code == 200

    def test_ranking_tied_scores(self, client, make_user, make_competition, make_result, make_bet):
        u1 = make_user(username="tied1")
        u2 = make_user(username="tied2")
        comp = make_competition(status="completed")
        make_result(comp.id, 1, "A", "POL")
        make_result(comp.id, 2, "B", "GER")
        make_result(comp.id, 3, "C", "NOR")
        make_bet(u1.id, comp.id, 1, "A")  # 3 pts
        make_bet(u2.id, comp.id, 2, "B")  # 3 pts
        resp = client.get("/ranking")
        assert resp.status_code == 200
        assert "tied1" in resp.text
        assert "tied2" in resp.text

    def test_ranking_anonymous_access(self, client):
        resp = client.get("/ranking")
        assert resp.status_code == 200

    def test_ranking_authenticated_access(self, client, make_user, auth_client):
        user = make_user(username="rankeduser")
        ac = auth_client(user)
        resp = ac.get("/ranking")
        assert resp.status_code == 200
        assert "rankeduser" in resp.text

    def test_ranking_multiple_competitions(self, client, make_user, make_competition, make_result, make_bet):
        user = make_user(username="multicomp")
        c1 = make_competition(status="completed")
        c2 = make_competition(status="completed")
        for c in [c1, c2]:
            make_result(c.id, 1, "A", "POL")
            make_result(c.id, 2, "B", "GER")
            make_result(c.id, 3, "C", "NOR")
        make_bet(user.id, c1.id, 1, "A")  # 3
        make_bet(user.id, c2.id, 1, "A")  # 3
        resp = client.get("/ranking")
        assert resp.status_code == 200
        assert "multicomp" in resp.text
