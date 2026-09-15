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


def test_phase_0_frontend_baseline_is_recorded():
    text = PLAN_DOC.read_text(encoding="utf-8")

    assert "### 前端真实能力清单" in text
    assert "用户侧路由已覆盖统计、通知、API Key、聊天和设置" in text
    assert "管理员侧路由已覆盖 dashboard、用户、渠道、模型、模型分组和日志" in text
    assert "Phase 1/2 所需的安全、预算、项目和账务页面仍未接入" in text
    assert "Phase 0 前端不做 UI 调整" in text
