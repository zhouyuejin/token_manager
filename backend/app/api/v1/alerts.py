import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies import require_admin
from app.models.system_config import SystemConfig
from app.services.alert_service import DEFAULTS

router = APIRouter()
class AlertRuleConfig(BaseModel):
    channel_error_rate_percent: float = Field(ge=0, le=100)
    channel_error_min_requests: int = Field(ge=1)
    quota_remaining_percent: float = Field(ge=0, le=100)
    project_growth_multiplier: float = Field(gt=0)
    project_growth_min_cost_usd: float = Field(ge=0)

@router.get("/rules")
def get_alert_rules(db: Session = Depends(get_db), _: object = Depends(require_admin)):
    row = db.query(SystemConfig).filter_by(config_key="alert_rules").first()
    return {**DEFAULTS, **(json.loads(row.config_value) if row and row.config_value else {})}

@router.put("/rules")
def update_alert_rules(data: AlertRuleConfig, db: Session = Depends(get_db), _: object = Depends(require_admin)):
    row = db.query(SystemConfig).filter_by(config_key="alert_rules").first()
    if not row: row = SystemConfig(config_key="alert_rules", description="Task 3.4 告警规则阈值"); db.add(row)
    row.config_value = json.dumps(data.model_dump()); db.commit()
    return data.model_dump()
