from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if not (REPO_ROOT / "docs").exists():
    REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_DOC = REPO_ROOT / "docs" / "内部Token中转平台能力补齐计划.md"


def test_phase_0_baseline_is_recorded():
    text = PLAN_DOC.read_text(encoding="utf-8")

    assert "## Phase 0 执行记录" in text
    assert "### 真实能力清单" in text
    assert "### 后续执行规则" in text
    assert "## Phase 1: 访问控制与 API Key 安全" in text
    assert "## Phase 2: 额度、预算与账务闭环" in text


def test_frontend_workstream_is_recorded():
    text = PLAN_DOC.read_text(encoding="utf-8")

    assert "## 前端补齐总则" in text
    assert "### Phase 1 前端补齐任务" in text
    assert "### Phase 2 前端补齐任务" in text
    assert "### Phase 3 前端补齐任务" in text


def test_phase_0_frontend_baseline_is_recorded():
    text = PLAN_DOC.read_text(encoding="utf-8")

    assert "### 前端真实能力清单" in text
    assert "### 验证命令基线" in text
    assert "Phase 1 前端补齐执行记录" in text
    assert "Phase 2 前端补齐任务" in text
