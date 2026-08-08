import json

import pytest
from langchain_core.messages import AIMessage


class UnitValidatorLLM:
    """为不需要真实 LLM 的工作流测试提供高分软评估。"""

    # 初始化软评估调用记录。
    def __init__(self):
        self.calls = []

    # 返回稳定的高分软评估 JSON。
    async def ainvoke(self, messages):
        self.calls.append(messages)
        return AIMessage(
            content=json.dumps(
                {
                    "score": 95,
                    "passed": True,
                    "reason": "单元测试行程结构完整且可执行",
                    "issues": [],
                    "suggestions": [],
                },
                ensure_ascii=False,
            )
        )


# 仅为旧的 graph/supervisor 单元测试替换真实 Validator LLM。
@pytest.fixture(autouse=True)
def patch_validator_llm_for_workflow_tests(request, monkeypatch):
    test_file = str(request.node.fspath)
    if test_file.endswith("test_graph.py") or test_file.endswith("test_supervisor.py"):
        from src.graph import validator as validator_module

        monkeypatch.setattr(validator_module, "get_validator_llm", UnitValidatorLLM)
