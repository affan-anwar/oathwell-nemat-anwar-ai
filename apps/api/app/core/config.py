import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    token_minutes: int
    llm_provider: str
    anthropic_api_key: str
    llm_model: str
    allow_private_urls: bool
    max_actions_per_day: int
    approval_hours: int
    cors_origins: list
    login_max_failures: int
    login_window_minutes: int
    ai_monthly_limit: int
    max_body_bytes: int
    price_in: float | None
    price_out: float | None
    price_currency: str
    prices: dict


def _prices() -> dict:
    """AI_PRICES = {"openai:model-id": {"in": 2.5, "out": 10}}  (price per million tokens, from the provider's price list)"""
    import json
    try:
        v = json.loads(os.getenv("AI_PRICES", "") or "{}")
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def get_settings() -> Settings:
    e = os.getenv
    return Settings(
        database_url=e("DATABASE_URL", "sqlite:///./dev.db"),
        secret_key=e("APP_SECRET_KEY", ""),
        token_minutes=int(e("TOKEN_MINUTES", "60")),
        llm_provider=e("LLM_PROVIDER", ""),
        anthropic_api_key=e("ANTHROPIC_API_KEY", ""),
        llm_model=e("LLM_MODEL", "claude-sonnet-5-5"),
        allow_private_urls=e("ALLOW_PRIVATE_URLS", "false") == "true",
        max_actions_per_day=int(e("MAX_ACTIONS_PER_DAY", "20")),
        approval_hours=int(e("APPROVAL_HOURS", "48")),
        cors_origins=[o for o in e("CORS_ORIGINS", "").split(",") if o],
        login_max_failures=int(e("LOGIN_MAX_FAILURES", "5")),
        login_window_minutes=int(e("LOGIN_WINDOW_MINUTES", "15")),
        ai_monthly_limit=int(e("AI_MONTHLY_LIMIT", "200")),
        max_body_bytes=int(e("MAX_BODY_BYTES", "1000000")),
        price_in=float(e("LLM_PRICE_INPUT_PER_MTOK")) if e("LLM_PRICE_INPUT_PER_MTOK") else None,
        price_out=float(e("LLM_PRICE_OUTPUT_PER_MTOK")) if e("LLM_PRICE_OUTPUT_PER_MTOK") else None,
        price_currency=e("LLM_PRICE_CURRENCY", "USD"),
        prices=_prices(),
    )
