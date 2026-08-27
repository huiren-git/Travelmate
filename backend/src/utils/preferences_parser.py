"""将前端中文标签的结构化偏好解析为后端内部英文枚举格式。

前端 StructuredPreferences 使用中文展示标签（如 "舒适出行" / "轻松" / "美食"），
而后端 blackboard.structured_preferences 及其下游 state_utils 中的 get_* 辅助函数
使用英文枚举（如 "mid" / "relaxed" / "food"）。本模块负责二者之间的映射。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

# 中文标签 -> 后端英文枚举
_BUDGET_LEVEL_MAP = {
    "经济实惠": "economy",
    "舒适出行": "mid",
    "奢华体验": "luxury",
}

_PACE_MAP = {
    "轻松": "relaxed",
    "适中": "relaxed",  # 后端仅 intensive/relaxed，适中按宽松处理
    "紧凑": "intensive",
}

_TRAVELERS_TYPE_MAP = {
    "独自出行": "adult",
    "情侣": "adult",
    "朋友": "adult",
    "亲子": "family",
    "家庭": "family",
    "长辈同行": "senior",
}

_HOTEL_PREFERENCE_MAP = {
    "经济型酒店": "economy",
    "舒适型酒店": "mid",
    "高端酒店": "luxury",
    "特色民宿": "mid",  # 无对应枚举，按舒适型处理
}

# 城际/市内交通在前端为单选字符串，后端为列表
_INTERCITY_MAP = {
    "火车": ["train"],
    "飞机": ["flight"],
    "自驾": ["self_driving"],
    "无偏好": [],
}

_LOCAL_MAP = {
    "步行": ["walking"],
    "公共交通": ["metro", "bus"],
    "打车": ["taxi"],
    "租车": ["self_driving"],
    "无偏好": [],
}

# 兴趣在前端为中文标签，后端为英文枚举；未知标签原样保留
_INTEREST_MAP = {
    "美食": "food",
    "历史": "history",
    "文化": "culture",
    "自然": "nature",
    "购物": "shopping",
    "艺术": "art",
    "夜生活": "nightlife",
}


def parse_structured_preferences(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """将前端中文结构化偏好解析为后端内部英文枚举格式。

    未提供或无法识别的字段会被忽略，保证下游 get_* 辅助函数能安全回退到默认值。
    返回的字典键与 blackboard.structured_preferences 及 state_utils 中的 get_*
    读取逻辑保持一致（budget_level / pace / travelers / travelers_type /
    hotel_preference / intercity_transport / local_transport / interests）。
    """
    if not raw:
        return {}

    result: Dict[str, Any] = {}

    budget_level = _BUDGET_LEVEL_MAP.get(str(raw.get("budget_level") or "").strip())
    if budget_level:
        result["budget_level"] = budget_level

    pace = _PACE_MAP.get(str(raw.get("pace") or "").strip())
    if pace:
        result["pace"] = pace

    travelers = raw.get("travelers")
    if isinstance(travelers, int) and travelers > 0:
        result["travelers"] = travelers

    travelers_type = _TRAVELERS_TYPE_MAP.get(
        str(raw.get("travelers_type") or "").strip()
    )
    if travelers_type:
        result["travelers_type"] = travelers_type

    hotel = _HOTEL_PREFERENCE_MAP.get(str(raw.get("hotel_preference") or "").strip())
    if hotel:
        result["hotel_preference"] = hotel

    intercity = _INTERCITY_MAP.get(str(raw.get("intercity_transport") or "").strip())
    if intercity is not None:  # 空列表也是合法值
        result["intercity_transport"] = intercity

    local = _LOCAL_MAP.get(str(raw.get("local_transport") or "").strip())
    if local is not None:
        result["local_transport"] = local

    raw_interests = raw.get("interests")
    if isinstance(raw_interests, list):
        mapped: List[str] = []
        for item in raw_interests:
            if not isinstance(item, str):
                continue
            label = item.strip()
            if not label:
                continue
            mapped.append(_INTEREST_MAP.get(label, label))
        if mapped:
            result["interests"] = mapped

    start_date = str(raw.get("start_date") or "").strip()
    if start_date:
        try:
            date.fromisoformat(start_date)
            result["start_date"] = start_date
        except ValueError:
            pass

    return result
