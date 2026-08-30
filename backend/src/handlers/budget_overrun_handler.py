from typing import Any, Dict, Optional

from src.core.interrupt_handler import InterruptHandler
from src.graph.state import TravelAgentState

class BudgetOverrunHandler(InterruptHandler):
    def should_trigger(self, state: TravelAgentState) -> bool:
      """
      判断是否触发预算超支中断
      """
      budget = state.get("draft_budget") or state.get("budget")
      max_allowed = state.get("budget_max_allowed")
      if not budget or not max_allowed:
          return False
      
      overrun_ratio = budget["total"] / max_allowed
      
      # 1. 小于 5% 完全忽略
      if overrun_ratio < 1.05:
          return False
      
      # 2. 5%-20% 之间：检查是否已经自动微调过
      if overrun_ratio < 1.20:
          auto_retry_count = state.get("budget_auto_retry", 0)
          if auto_retry_count < 2:
              # 自动重试，不中断
              return False
          # 自动重试 2 次后仍超标，才中断
          return True
    
      # 3. 超过 20%：直接中断
      return True

    def overrun_ratio(self, state: TravelAgentState) -> Optional[float]:
        """返回当前预算/上限的比值；缺预算或上限时为 None。"""
        budget = state.get("draft_budget") or state.get("budget")
        max_allowed = state.get("budget_max_allowed")
        if not budget or not max_allowed:
            return None
        try:
            return float(budget["total"]) / float(max_allowed)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    def should_auto_retry(self, state: TravelAgentState) -> bool:
        """
        5%-20% 超支区间且自动微调次数未达上限时返回 True，
        表示应由系统自动削减行程并重算，而不是直接中断用户。
        """
        ratio = self.overrun_ratio(state)
        if ratio is None:
            return False
        if not (1.05 <= ratio < 1.20):
            return False
        auto_retry_count = state.get("budget_auto_retry", 0)
        return auto_retry_count < 2

    def build_payload(self, state: TravelAgentState) -> Dict:
        """
        构建预算超支中断的 payload，包含当前预算、超支百分比和处理选项
        """
        budget = state.get("draft_budget") or state["budget"]
        max_allowed = state.get("budget_max_allowed")
        overrun_percent = round((budget["total"] / max_allowed - 1) * 100, 1)
        return {
            "type": "budget_overrun",
            "title": "预算超支提醒",
            "description": f"当前预算为 {budget['total']} 元，超出上限 {overrun_percent}%。请选择如何处理。",
            "options": [
                {"id": "accept", "label": "接受超支，继续规划", "default": False},
            {"id": "modify", "label": "调整预算等级或削减行程", "default": True, "ui_hint": "select"},
            ],
            "extra": {
                "current_budget": budget,
                "max_allowed": max_allowed,
                "suggested_cuts": ["减少一个景点", "更换经济型酒店"]  # 可选辅助信息
            }
        }

    def handle_resume(self, state: TravelAgentState, action: str, payload: Optional[Dict]) -> Dict[str, Any]:
        """
        处理用户在预算超支中断后的选择，返回更新的状态字典
        """
        if action == "accept":
            # 直接继续，不做修改
            return {}  # 返回空更新，图继续执行
        elif action == "modify":
            # 用户可能提高了预算等级，或要求削减行程
            new_level = payload.get("level") if payload else None
            if new_level and new_level != state.get("budget_level"):
                # 更新预算等级，清空草稿，让 Itinerary 重新生成
                return {"budget_level": new_level, "auto_reduce_budget": True}
            else:
                # 可能用户选择了削减行程，但这里简化处理
                return {"auto_reduce_budget": True}
        return {}
