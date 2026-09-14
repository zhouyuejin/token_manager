from app.models.model import Model, PriceType, ModelStatus
from app.core.database import Base
from app.services.model_pricing_service import sync_model_prices
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_sync_model_prices_updates_known_models_and_skips_unknown():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[Model.__table__])
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    known = Model(
        id=1,
        model_id="openai-gpt-4o-mini",
        display_name="GPT-4o Mini",
        price_type=PriceType.token,
        price_per_1k_input=0,
        price_per_1k_output=0,
        price_per_request=0,
        status=ModelStatus.active,
    )
    provider_scoped = Model(
        id=3,
        model_id="anthropic-claude-3-5-sonnet-latest",
        display_name="Claude 3.5 Sonnet",
        price_type=PriceType.token,
        price_per_1k_input=0,
        price_per_1k_output=0,
        price_per_request=0,
        status=ModelStatus.active,
    )
    tiered = Model(
        id=4,
        model_id="volcengine-doubao-seed-2-0-pro-260215",
        display_name="Doubao Pro",
        price_type=PriceType.token,
        price_per_1k_input=0,
        price_per_1k_output=0,
        price_per_request=0,
        status=ModelStatus.active,
    )
    unknown = Model(
        id=2,
        model_id="custom-private-model",
        display_name="Private Model",
        price_type=PriceType.token,
        price_per_1k_input=9,
        price_per_1k_output=9,
        price_per_request=0,
        status=ModelStatus.active,
    )
    db.add_all([known, provider_scoped, tiered, unknown])
    db.commit()

    result = sync_model_prices(db, price_map={
        "gpt-4o-mini": {
            "input_cost_per_token": 0.00000015,
            "output_cost_per_token": 0.0000006,
        },
        "anthropic/claude-3-5-sonnet-latest": {
            "input_cost_per_token": 0.000003,
            "output_cost_per_token": 0.000015,
        },
        "volcengine/doubao-seed-2-0-pro-260215": {
            "tiered_pricing": [{
                "input_cost_per_token": 0.00000046,
                "output_cost_per_token": 0.0000023,
            }],
        }
    })

    db.refresh(known)
    db.refresh(provider_scoped)
    db.refresh(tiered)
    db.refresh(unknown)

    assert result == {"total": 4, "updated": 3, "skipped": 1}
    assert float(known.price_per_1k_input) == 0.00015
    assert float(known.price_per_1k_output) == 0.0006
    assert float(provider_scoped.price_per_1k_input) == 0.003
    assert float(provider_scoped.price_per_1k_output) == 0.015
    assert float(tiered.price_per_1k_input) == 0.00046
    assert float(tiered.price_per_1k_output) == 0.0023
    assert float(known.price_per_request) == 0
    assert float(unknown.price_per_1k_input) == 9
    db.close()
