""" 注册所有处理器，提供工厂方法 """
from typing import Dict, Type
from src.core.interrupt_handler import InterruptHandler
from src.handlers.budget_overrun_handler import BudgetOverrunHandler
# 未来新增：from src.handlers.conflict_handler import ConflictHandler

_handler_registry: Dict[str, Type[InterruptHandler]] = {
    "budget_overrun": BudgetOverrunHandler,
    # "conflict_resolution": ConflictHandler,
}

def get_handler(interrupt_type: str) -> InterruptHandler:
    """
    根据中断类型获取对应的处理器实例
    """
    handler_cls = _handler_registry.get(interrupt_type)
    if not handler_cls:
        raise ValueError(f"Unknown interrupt type: {interrupt_type}")
    return handler_cls()
