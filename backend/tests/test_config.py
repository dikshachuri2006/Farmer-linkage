import pytest
from app.core.config import Settings


def test_settings_default_values():
    settings = Settings()
    assert settings.PROJECT_NAME == "Farmer Market Linkage & Price Discovery API"
    assert settings.API_V1_STR == "/api"
    assert settings.ALGORITHM == "HS256"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0
    assert "postgresql+psycopg://" in settings.SQLALCHEMY_DATABASE_URI


def test_cors_origins_parsing():
    # Test JSON string parsing
    settings = Settings(ALLOWED_ORIGINS='["http://localhost:3000","http://example.com"]')
    assert "http://localhost:3000" in settings.ALLOWED_ORIGINS
    assert "http://example.com" in settings.ALLOWED_ORIGINS

    # Test comma-separated string parsing
    settings2 = Settings(ALLOWED_ORIGINS="http://localhost:3000,http://example.com")
    assert "http://localhost:3000" in settings2.ALLOWED_ORIGINS
    assert "http://example.com" in settings2.ALLOWED_ORIGINS


def test_database_url_override():
    custom_url = "postgresql+psycopg://custom_user:custom_pass@custom_host:5433/custom_db"
    settings = Settings(DATABASE_URL=custom_url)
    assert settings.SQLALCHEMY_DATABASE_URI == custom_url


@pytest.mark.parametrize(
    "kwargs",
    [
        {"ENVIRONMENT": "demo", "SECRET_KEY": "CHANGE_THIS_TO_A_SECURE_RANDOM_SECRET_KEY_AT_LEAST_32_CHARS", "DEBUG": False},
        {"ENVIRONMENT": "production", "SECRET_KEY": "a" * 32, "DEBUG": True},
        {"ENVIRONMENT": "production", "SECRET_KEY": "too-short", "DEBUG": False},
    ],
)
def test_non_development_requires_explicit_strong_secret_and_debug_off(kwargs):
    with pytest.raises(ValueError):
        Settings(**kwargs)


def test_development_does_not_use_the_published_placeholder_secret():
    configured = Settings(ENVIRONMENT="development")
    assert configured.SECRET_KEY != "CHANGE_THIS_TO_A_SECURE_RANDOM_SECRET_KEY_AT_LEAST_32_CHARS"
    assert len(configured.SECRET_KEY) >= 32
