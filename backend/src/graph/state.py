from typing import Annotated, List, Dict, Optional, Literal, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


# ============================================================
# 子结构定义（供 State 引用）
# ============================================================

class ItineraryItem(TypedDict):
    """单条行程项"""
    time: str                       # "09:00"
    activity: str                   # "故宫博物院"
    duration: str                   # "3h"
    address: Optional[str]          # 详细地址
    status: Literal["completed", "ongoing", "upcoming"]  # 行程状态（增量修改的关键锁）
    tips: Optional[str]             # 购票/避坑提示


class DayPlan(TypedDict):
    """每日行程"""
    day: int                        # 第几天（从1开始）
    date: str                       # "2026-08-10"
    items: List[ItineraryItem]      # 该天行程项列表


class BudgetDetail(TypedDict):
    """预算明细"""
    level: Literal["economy", "mid", "luxury"]  # 预算等级
    total: float                    # 总预算
    detail: Dict[str, float]        # {"transport": 550, "hotel": 800, "food": 500, "tickets": 300}
    saving_tips: Optional[List[str]]  # 省钱建议


# ============================================================
# 核心 State 定义（LangGraph 状态机的心脏）
# ============================================================

class TravelAgentState(TypedDict):
    """
    LangGraph 全局状态
    
    所有节点（Supervisor / Itinerary Agent / Budget Agent / Validator）
    都通过这个 State 进行数据读写。
    """

    # ========== 1. 会话与上下文（基础） ==========
    messages: Annotated[List[BaseMessage], add_messages]
    """对话历史。使用 add_messages 规约器自动追加新消息，而非覆盖"""

    user_id: str
    """用户标识，用于查询长期记忆和权限校验"""

    thread_id: str
    """会话标识，用于 SQLite 状态持久化和中断恢复"""

    # ========== 2. 用户意图（输入层） ==========
    destination: Optional[str]
    """目的地城市"""

    origin: Optional[str]
    """出发城市（GPS/IP 默认填充，可手动修改）"""

    start_date: Optional[str]
    """出发日期（YYYY-MM-DD）"""

    duration: Optional[int]
    """旅行天数"""

    structured_preferences: Optional[Dict[str, Any]]
    """
    结构化偏好（来自快速表单）
    包含：budget_level, pace, interests, travelers, travelers_type, hotel_preference,
          intercity_transport, local_transport
    """

    # ========== 3. 外部数据（感知层，由 Pre-fetcher 填充） ==========
    weather_info: Optional[Dict[str, Any]]
    """天气信息 {"temp": 25, "desc": "晴", "city": "北京"}"""

    fetched_attractions: Optional[List[Dict[str, Any]]]
    """预取的景点列表 [{"name": "故宫", "address": "...", "rating": 4.8}]"""

    # ========== 4. 已生效产出（已通过 Validator 校验） ==========
    daily_itinerary: Optional[List[DayPlan]]
    """已生效的每日行程列表，前端正式展示和后续预算估算以此为准"""

    budget: Optional[BudgetDetail]
    """已生效的预算明细"""

    # ========== 5. 草稿产出（待 Validator 校验后才能生效） ==========
    draft_daily_itinerary: Optional[List[DayPlan]]
    """REPLAN 模式下生成的行程草稿，通过 Validator 后才能覆写 daily_itinerary"""

    draft_budget: Optional[BudgetDetail]
    """预算草稿预留字段，通过 Validator 后才能覆写 budget"""

    # ========== 6. 流程控制（元认知层） ==========
    plan_mode: Literal["plan", "replan"]
    """规划模式：plan=首次规划，replan=基于已生效数据修改"""

    current_mode: Literal["plan", "replan"]
    """兼容旧代码的模式字段，含义同 plan_mode"""

    current_time: Optional[str]
    """动态修改时的时间锚点（ISO 格式），用于锁定已完成行程"""

    validation_attempts: int
    """Harness Validator 重试计数器（最大3次，防止死循环）"""

    hard_validation_attempts: int
    """硬校验重试计数器，用于限制结构性错误反复修正"""

    soft_validation_attempts: int
    """LLM 软评估重试计数器，用于控制语义评分成本和质量摇摆"""

    validation_report: Optional[Dict[str, Any]]
    """校验报告 {"errors": [...], "warnings": [...], "score": 85}"""

    is_finished: bool
    """流程是否已完成（Supervisor 根据此字段决定是否结束）"""

    # ========== 7. 会话管理 ==========
    deleted_at: Optional[str]
    """逻辑删除时间（ISO 格式），为空表示会话仍可见"""

    # ========== 8. 路由控制（内部使用） ==========
    next_node: Optional[Literal["itinerary_agent", "budget_agent", "__end__"]]
    """Supervisor 路由决策结果，由 supervisor_router 读取"""
