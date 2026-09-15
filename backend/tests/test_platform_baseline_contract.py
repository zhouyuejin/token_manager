from pathlib import Path


PLAN_DOC = Path(__file__).resolve().parents[2] / "docs" / "内部Token中转平台能力补齐计划.md"


def test_phase_0_baseline_is_recorded():
    text = PLAN_DOC.read_text(encoding="utf-8")

    assert "## Phase 0 执行记录" in text
    assert "API Key IP 白名单字段存在但代理链路未接入" in text
    assert "API Key 级 QPS/RPM/TPM 限流未实现" in text
    assert "渠道上游密钥当前按明文字段读取" in text
    assert "Phase 0 不改代理行为" in text


def test_frontend_workstream_is_recorded():
    text = PLAN_DOC.read_text(encoding="utf-8")

    assert "## 前端补齐总则" in text
    assert "Phase 1 前端补齐任务" in text
    assert "API Key 安全状态在列表、详情、创建/编辑/轮换/吊销流程中可见可操作" in text
    assert "Phase 2 前端补齐任务" in text
    assert "成本归因、预算、预扣、对账和导出必须有后台可操作入口" in text
