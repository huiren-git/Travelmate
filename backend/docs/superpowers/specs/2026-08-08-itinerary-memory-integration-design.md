# Itinerary Agent Memory Integration Design

**Status:** Approved

## Goal

让 `itinerary_agent` 在生成或重规划行程前利用用户长期偏好，并从当前用户输入中沉淀稳定偏好和明确行程决策。

## Scope

本次修改 `src/agents/itinerary_agent.py`、`src/api/v1/chat.py` 及对应测试。不修改 `TravelAgentState`、LangGraph 拓扑或 ChromaDB 基础 CRUD。

## Data Flow

1. 从 `state["messages"]` 读取最新的人类消息作为用户需求描述。
2. 在 `_build_itinerary_messages` 前调用 `retrieve_memories`：
   - 使用 `state["user_id"]` 隔离用户；
   - 查询文本为最新用户需求；
   - 类型固定为 `preference`；
   - 返回最多 5 条相关记忆。
3. 将检索结果以 `relevant_preferences` 写入现有 Prompt payload。
4. 分析当前用户消息：
   - “喜欢、偏好、希望、不要太累、不喜欢、优先”等表达沉淀为 `preference`；
   - “换成、取消、别去、改成、调整、接受、拒绝”等表达沉淀为 `action`。
5. 以 `user_id`、`thread_id`、`plan_mode` 和消息指纹写入 metadata。
6. `/chat/resume` 校验通过后，将 `accept/modify/reject` 及其 hint/note 写入 `action` 记忆，因为该决策通过 LangGraph `Command(resume=...)` 传递，不会自动进入 `messages`。

## Error Handling

记忆检索或存储异常只记录日志并返回空结果，不阻断既有行程规划流程。没有用户 ID 或没有有效用户消息时跳过记忆操作。

## Testing

新增单元测试覆盖：

- Prompt 构建前按用户消息检索偏好，并把结果传给 LLM；
- 同一条包含偏好和修改决策的消息分别写入 `preference` 和 `action`；
- 原有 plan/replan 行为继续通过既有测试。
