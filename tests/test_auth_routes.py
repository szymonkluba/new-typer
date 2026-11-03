from app.config import COOKIE_NAME
from app.models import User


class TestRegisterPage:
    def test_register_page_renders(self, client):
        resp = client.get("/auth/register")
        assert resp.status_code == 200
        assert "Register" in resp.text

    def test_register_page_redirects_if_logged_in(self, client, make_user, auth_client):
        user = make_user()
        ac = auth_client(user)
        resp = ac.get("/auth/register", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"


class TestRegisterSubmit:
    def test_register_success(self, client, db):
        resp = client.post(
            "/auth/register",
            data={"username": "newuser", "password": "pass123", "password_confirm": "pass123"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert COOKIE_NAME in resp.cookies
        assert db.query(User).filter(User.username == "newuser").first() is not None

    def test_register_short_username(self, client):
        resp = client.post(
            "/auth/register",
            data={"username": "ab", "password": "pass123", "password_confirm": "pass123"},
        )
        assert resp.status_code == 200
        assert "at least 3 characters" in resp.text

    def test_register_short_password(self, client):
        resp = client.post(
            "/auth/register",
            data={"username": "testuser", "password": "12345", "password_confirm": "12345"},
        )
        assert resp.status_code == 200
        assert "at least 6 characters" in resp.text

    def test_register_password_mismatch(self, client):
        resp = client.post(
            "/auth/register",
            data={"username": "testuser", "password": "pass123", "password_confirm": "pass456"},
        )
        assert resp.status_code == 200
        assert "do not match" in resp.text

    def test_register_duplicate_username(self, client, make_user):
        make_user(username="taken")
        resp = client.post(
            "/auth/register",
            data={"username": "taken", "password": "pass123", "password_confirm": "pass123"},
        )
        assert resp.status_code == 200
        assert "already taken" in resp.text

    def test_register_multiple_errors(self, client):
        resp = client.post(
            "/auth/register",
            data={"username": "a", "password": "1", "password_confirm": "2"},
        )
        assert resp.status_code == 200
        assert "at least 3 characters" in resp.text
        assert "at least 6 characters" in resp.text
        assert "do not match" in resp.text

    def test_register_preserves_username_on_error(self, client):
        resp = client.post(
            "/auth/register",
            data={"username": "myname", "password": "short", "password_confirm": "short"},
        )
        assert resp.status_code == 200
        assert "myname" in resp.text

    def test_register_exact_boundary_username(self, client, db):
        resp = client.post(
            "/auth/register",
            data={"username": "abc", "password": "pass123", "password_confirm": "pass123"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert db.query(User).filter(User.username == "abc").first() is not None

    def test_register_exact_boundary_password(self, client, db):
        resp = client.post(
            "/auth/register",
            data={"username": "bounduser", "password": "123456", "password_confirm": "123456"},
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_register_empty_username(self, client):
        resp = client.post(
            "/auth/register",
            data={"username": "", "password": "pass123", "password_confirm": "pass123"},
        )
        assert resp.status_code == 200
        assert "at least 3 characters" in resp.text

    def test_register_whitespace_username(self, client, db):
        resp = client.post(
            "/auth/register",
            data={"username": "   ", "password": "pass123", "password_confirm": "pass123"},
            follow_redirects=False,
        )
        # Whitespace-only passes len >= 3 check, creates user (no trim in code)
        assert resp.status_code == 303
        assert db.query(User).filter(User.username == "   ").first() is not None


class TestLoginPage:
    def test_login_page_renders(self, client):
        resp = client.get("/auth/login")
        assert resp.status_code == 200
        assert "Login" in resp.text

    def test_login_page_redirects_if_logged_in(self, client, make_user, auth_client):
        user = make_user()
        ac = auth_client(user)
        resp = ac.get("/auth/login", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"


class TestLoginSubmit:
    def test_login_success(self, client, make_user):
        make_user(username="testlogin", password="mypassword")
        resp = client.post(
            "/auth/login",
            data={"username": "testlogin", "password": "mypassword"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert COOKIE_NAME in resp.cookies

    def test_login_wrong_password(self, client, make_user):
        make_user(username="testlogin", password="mypassword")
        resp = client.post(
            "/auth/login",
            data={"username": "testlogin", "password": "wrongpass"},
        )
        assert resp.status_code == 200
        assert "Invalid username or password" in resp.text

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/auth/login",
            data={"username": "ghost", "password": "pass123"},
        )
        assert resp.status_code == 200
        assert "Invalid username or password" in resp.text

    def test_login_preserves_username_on_error(self, client):
        resp = client.post(
            "/auth/login",
            data={"username": "keepme", "password": "wrong"},
        )
        assert resp.status_code == 200
        assert "keepme" in resp.text

    def test_login_missing_form_fields(self, client):
        resp = client.post("/auth/login", data={})
        assert resp.status_code == 422


class TestLogout:
    def test_logout_redirects(self, client, make_user, auth_client):
        user = make_user()
        ac = auth_client(user)
        resp = ac.get("/auth/logout", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"

    def test_logout_without_being_logged_in(self, client):
        resp = client.get("/auth/logout", follow_redirects=False)
        assert resp.status_code == 303
