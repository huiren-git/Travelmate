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
    image_url: str                  # 来自景点数据源的真实图片 URL
    status: Literal["completed", "ongoing", "upcoming"]  # 行程状态（增量修改的关键锁）
    tips: Optional[str]             # 购票/避坑提示
    # ---- 定价字段（由 cost_enrich 写入，前端展示可直接消费）----
    cost: Optional[float]           # 该项实际花费（已含 travelers 倍数）
    cost_category: Optional[Literal["transport", "hotel", "food", "tickets", "other"]]
    estimate_source: Optional[Literal["amap", "rule", "free", "pending"]]
    # 费用来源：高德 POI、规则估算、免费或待估算
    poi_ref: Optional[str]          # 命中的 POI 名称/ID，用于精确匹配与前端跳转
    location: Optional[str]         # "lng,lat"，供方法2 计算相邻 item 距离
    leg_transport_cost: Optional[float]  # 到达该 item 的交通腿费（方法2）


class DayPlan(TypedDict):
    """每日行程"""
    day: int                        # 第几天（从1开始）
    date: str                       # "2026-08-10"
    items: List[ItineraryItem]      # 该天行程项列表


class BudgetDetail(TypedDict):
    """预算明细"""
    level: Literal["economy", "mid", "luxury"]  # 预算等级
    total: float                    # 总预算
    detail: Dict[str, float]        # {"intercity_transport": 550, "local_transport": 100, "hotel": 800, "food": 500, "tickets": 300}
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

    travel_logistics: Optional[Dict[str, Any]]
    """行程级交通与全程住宿方案，供预算和前端展示共同使用"""

    budget_max_allowed: Optional[float]
    """用户预算金额上限（元）：文本由 supervisor 抽取写入，缺失时 budget_agent 按 budget_level 推导兜底；BudgetOverrunHandler 据此判定是否触发超支中断。"""

    budget_auto_retry: int
    """超支自动微调计数器（预留字段，当前无实际削减逻辑）。"""

    budget_dirty: bool
    """标记本轮 budget_max_allowed 是否发生变化（supervisor 抽取到与旧值不同的值时置 True）；
    validator 据其在 replan 模式下也重跑 budget_agent 重翻 total，budget_agent 重算后清回 False，避免死循环。"""

    auto_reduce_budget: bool
    """标记本轮因预算超支(5%-20%区间)进入自动微调闭环：validator 置 True 后路由回 itinerary_agent 自行削减行程，
    budget_agent 重算 total 后清回 False；计数器 budget_auto_retry 封顶 2 次保证不死循环。"""

    # ========== 5. 草稿产出（待 Validator 校验后才能生效） ==========
    draft_daily_itinerary: Optional[List[DayPlan]]
    """所有 PLAN/REPLAN 生成的行程草稿；仅通过全部校验后才能覆写 daily_itinerary。"""

    draft_budget: Optional[BudgetDetail]
    """基于行程草稿计算的预算草稿，通过 Validator 后才能覆写 budget。"""

    # ========== 6. 流程控制（元认知层） ==========
    intent: Literal["plan", "consult", "update_preferences", "replan"]
    """本轮用户意图，驱动只读咨询、偏好更新和局部行程调整的边界。"""

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

    terminal_status: Literal["running", "confirmed", "failed"]
    """本轮工作流状态。只有 confirmed 才代表可向用户展示的正式行程。"""

    failure_reason: Optional[str]
    """终止失败的机器可读/可展示原因；失败草稿保留用于诊断但不会作为正式结果返回。"""
    """流程是否已完成（Supervisor 根据此字段决定是否结束）"""

    user_decision: Optional[Dict[str, Any]]
    """用户在中断确认环节回灌的决策（含 action/hint/note 等），由 Validator 接住 interrupt() 返回值写入；REPLAN 模式下供 Itinerary Agent 读取以落实用户的修改意图"""

    replan_scope: Optional[Dict[str, Any]]
    """REPLAN 本轮授权范围，由 Itinerary Agent 解析写入、Validator 生成反馈语时复用。
    结构：{"kind":"item|day|all","target_dates":["YYYY-MM-DD"],"target_days":[1],
    "target_item_keys":["YYYY-MM-DD#HH:MM"],"instruction":"用户本轮原话"}。
    不声明会导致 LangGraph 对 update["replan_scope"] 抛 InvalidUpdateError。"""

    replan_changes: Optional[Dict[str, Any]]
    """REPLAN 本轮实际差异，由 Validator 计算写入：{"replaced":[],"removed":[],"added":[],"changed_dates":[],"empty":bool}"""

    summary_text: Optional[str]
    """本轮回复文案：PLAN 模式为行程总结语，REPLAN 模式为针对用户指令的执行反馈语；由 Validator 在 is_finished=True 时一次性生成，随 done 事件返回前端；不参与校验重试循环"""

    adaptation_log: Optional[List[Dict[str, Any]]]
    """参考行程规则适配产生的可展示修改记录。"""

    # ========== 7. 会话管理 ==========
    deleted_at: Optional[str]
    """逻辑删除时间（ISO 格式），为空表示会话仍可见"""

    # ========== 8. 路由控制（内部使用） ==========
    next_node: Optional[Literal["itinerary_agent", "budget_agent", "__end__"]]
    """Supervisor 路由决策结果，由 supervisor_router 读取"""
