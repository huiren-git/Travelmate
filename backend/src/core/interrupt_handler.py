from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from src.graph.state import TravelAgentState

class InterruptHandler(ABC):
    @abstractmethod
    def should_trigger(self, state: TravelAgentState) -> bool:
        """检查是否满足中断条件"""
        pass

    @abstractmethod
    def build_payload(self, state: TravelAgentState) -> Dict[str, Any]:
        """生成前端所需的中断数据"""
        pass

    @abstractmethod
    def handle_resume(self, state: TravelAgentState, action: str, payload: Optional[Dict]) -> Dict[str, Any]:
        """
        根据用户决策更新 State，返回需要更新的字段和可能的路由指示
        """
        pass