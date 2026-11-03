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
    import pytest

    # bcrypt 4.x rejects passwords > 72 bytes
    with pytest.raises(ValueError, match="72 bytes"):
        hash_password("a" * 100)
    # 72-byte password works fine
    h = hash_password("a" * 72)
    assert verify_password("a" * 72, h) is True
