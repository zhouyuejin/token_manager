from decimal import Decimal
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from app.models.model import Model, PriceType


PRICE_MAP_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"

FALLBACK_PRICE_MAP: Dict[str, Dict[str, float]] = {
    "gpt-4o-mini": {"input_cost_per_token": 0.00000015, "output_cost_per_token": 0.0000006},
    "gpt-4o": {"input_cost_per_token": 0.0000025, "output_cost_per_token": 0.00001},
    "deepseek-chat": {"input_cost_per_token": 0.00000027, "output_cost_per_token": 0.0000011},
    "deepseek-coder": {"input_cost_per_token": 0.00000027, "output_cost_per_token": 0.0000011},
    "claude-3-5-haiku-latest": {"input_cost_per_token": 0.0000008, "output_cost_per_token": 0.000004},
    "claude-3-5-sonnet-latest": {"input_cost_per_token": 0.000003, "output_cost_per_token": 0.000015},
}

KNOWN_PREFIXES = (
    "openai-",
    "anthropic-",
    "azure-",
    "deepseek-",
    "minimax-",
    "volcengine-",
    "google-",
)


def fetch_price_map() -> Dict[str, Any]:
    try:
        response = httpx.get(PRICE_MAP_URL, timeout=10)
        response.raise_for_status()
        return {**FALLBACK_PRICE_MAP, **response.json()}
    except Exception:
        return FALLBACK_PRICE_MAP


def sync_model_prices(db: Session, price_map: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
    prices = price_map or fetch_price_map()
    updated = 0
    skipped = 0

    for model in db.query(Model).all():
        price = _find_price(prices, model.model_id)
        token_price = _token_price(price)
        if not token_price:
            skipped += 1
            continue

        model.price_type = PriceType.token
        model.price_per_1k_input = _per_1k(token_price["input_cost_per_token"])
        model.price_per_1k_output = _per_1k(token_price["output_cost_per_token"])
        model.price_per_request = Decimal("0")
        updated += 1

    db.commit()
    return {"total": updated + skipped, "updated": updated, "skipped": skipped}


def _find_price(prices: Dict[str, Any], model_id: str) -> Optional[Dict[str, Any]]:
    candidates = _price_key_candidates(model_id)
    for candidate in candidates:
        price = prices.get(candidate)
        if isinstance(price, dict):
            return price
    return None


def _price_key_candidates(model_id: str) -> list[str]:
    candidates = [model_id]
    for prefix in KNOWN_PREFIXES:
        if model_id.startswith(prefix):
            provider = prefix[:-1]
            upstream_model = model_id[len(prefix):]
            candidates.extend([upstream_model, f"{provider}/{upstream_model}", f"{provider}.{upstream_model}"])
            break
    return list(dict.fromkeys(candidates))


def _per_1k(value: Any) -> Decimal:
    return Decimal(str(value or 0)) * Decimal("1000")


def _token_price(price: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not price:
        return None
    if "input_cost_per_token" in price and "output_cost_per_token" in price:
        return price
    tiers = price.get("tiered_pricing")
    if isinstance(tiers, list) and tiers:
        first_tier = tiers[0]
        if isinstance(first_tier, dict) and "input_cost_per_token" in first_tier and "output_cost_per_token" in first_tier:
            return first_tier
    return None
