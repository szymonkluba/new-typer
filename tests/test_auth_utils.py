from app.auth.utils import hash_password, verify_password


def test_hash_password_returns_bcrypt_string():
    h = hash_password("testpass")
    assert h.startswith("$2b$")


def test_hash_password_different_salts():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2


def test_verify_password_correct():
    h = hash_password("abc123")
    assert verify_password("abc123", h) is True


def test_verify_password_wrong():
    h = hash_password("abc123")
    assert verify_password("wrong", h) is False


def test_verify_password_empty_string():
    h = hash_password("something")
    assert verify_password("", h) is False


def test_hash_password_unicode():
    h = hash_password("zółć2024")
    assert verify_password("zółć2024", h) is True
    assert verify_password("wrong", h) is False


def test_hash_password_very_long():
    # bcrypt silently truncates at 72 bytes on some platforms,
    # raises ValueError on others — test whichever behavior applies
    try:
        h = hash_password("a" * 100)
        # truncation: 100-char and 72-char passwords produce the same hash
        assert verify_password("a" * 72, h) is True
    except ValueError:
        pass
    # 72-byte password always works
    h = hash_password("a" * 72)
    assert verify_password("a" * 72, h) is True
