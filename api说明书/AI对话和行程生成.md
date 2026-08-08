---
title: AI对话和行程生成
language_tabs:
  - shell: Shell
  - http: HTTP
  - javascript: JavaScript
  - ruby: Ruby
  - python: Python
  - php: PHP
  - java: Java
  - go: Go
toc_footers: []
includes: []
search: true
code_clipboard: true
highlight_theme: darkula
headingLevel: 2
generator: "@tarslib/widdershins v4.0.30"

---

# AI对话和行程生成

当主对话流程因 interrupt（如预算超支确认）暂停时，前端调用此接口传入用户决策，使 LangGraph 从断点处恢复执行

Base URLs:

# Authentication

# Default

## POST 发起/继续对话

POST /api/v1/chat/stream

支持两种模式：
1. 纯自然语言对话（不传 structured_input）
2. 结构化表单输入（传 structured_input，内部仅部分字段必填）

> Body 请求参数

```json
{
  "thread_id": "thread_20260810_001",
  "message": "帮我规划一个北京3日游，预算中等，大约2000块左右",
  "current_time": "2026-08-11 10:30:00",
  "structured_input": {
    "destination": "北京",
    "origin": "上海",
    "start_date": "2026-08-10",
    "duration": 3,
    "budget": {
      "level": "mid",
      "min_total": 1800,
      "max_total": 2200
    },
    "hotel_preference": "mid",
    "intercity_transport": [
      "high_speed_rail"
    ],
    "local_transport": [
      "metro",
      "taxi"
    ],
    "pace": "relaxed",
    "interests": [
      "history",
      "food"
    ],
    "travelers": 2,
    "travelers_type": "adult"
  }
}
```

### 请求参数

|名称|位置|类型|必选|说明|
|---|---|---|---|---|
|X-User-Id|header|string| 是 |none|
|body|body|object| 是 |none|
|» thread_id|body|string| 是 |会话ID，同一行程的会话ID一致|
|» message|body|string| 是 |用户输入的自然语言|
|» current_time|body|string| 否 |当前时间（REPLAN 模式下使用，用于时间锚定）|
|» structured_input|body|object| 否 |none|
|»» destination|body|string| 是 |目的地|
|»» origin|body|string| 否 |出发地（可选，由 GPS/IP 默认填充）|
|»» start_date|body|string| 否 |开始日期|
|»» duration|body|integer| 是 |旅行天数|
|»» budget|body|object| 是 |none|
|»»» level|body|string| 是 |预算等级|
|»»» min_total|body|number| 否 |预算下限（选填，仅用于硬校验）|
|»»» max_total|body|number| 否 |预算上限（选填，仅用于硬校验）|
|»» hotel_preference|body|string| 否 |酒店档次（选填，不填则跟随 budget.level）|
|»» intercity_transport|body|[string]| 否 |城际交通方式（多选）|
|»» local_transport|body|[string]| 否 |市内出行方式（多选）|
|»» pace|body|string| 否 |行程节奏（选填，默认 relaxed）|
|»» interests|body|[string]| 否 |兴趣偏好（多选）|
|»» travelers|body|integer| 否 |旅行人数|
|»» travelers_type|body|string| 否 |同行者类型（选填，默认 adult）|

#### 枚举值

|属性|值|
|---|---|
|»»» level|economy|
|»»» level|mid|
|»»» level|luxury|
|»» hotel_preference|economy|
|»» hotel_preference|mid|
|»» hotel_preference|luxury|
|»» intercity_transport|flight|
|»» intercity_transport|high_speed_rail|
|»» intercity_transport|train|
|»» intercity_transport|coach|
|»» intercity_transport|self_driving|
|»» local_transport|metro|
|»» local_transport|bus|
|»» local_transport|taxi|
|»» local_transport|self_driving|
|»» local_transport|bike|
|»» local_transport|walking|
|»» pace|intensive|
|»» pace|relaxed|
|»» interests|history|
|»» interests|culture|
|»» interests|food|
|»» interests|nature|
|»» interests|shopping|
|»» interests|art|
|»» interests|nightlife|
|»» travelers_type|adult|
|»» travelers_type|family|
|»» travelers_type|senior|

> 返回示例

> 200 Response

### 返回结果

|状态码|状态码含义|说明|数据模型|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|SSE 流式响应|string|
|400|[Bad Request](https://tools.ietf.org/html/rfc7231#section-6.5.1)|参数校验失败|None|
|404|[Not Found](https://tools.ietf.org/html/rfc7231#section-6.5.4)|会话不存在|None|
|503|[Service Unavailable](https://tools.ietf.org/html/rfc7231#section-6.6.4)|AI 服务不可用|None|

## POST 停止生成

POST /api/v1/chat/stop/{thread_id}

用户主动点击“停止生成”按钮时调用，中断当前正在进行的 LLM 流式输出，释放服务端资源，终止 Agent 执行流程。

### 请求参数

|名称|位置|类型|必选|说明|
|---|---|---|---|---|
|thread_id|path|string| 是 |none|
|X-User-Id|header|string| 否 |用户id|

> 返回示例

> 200 Response

```json
{
  "code": 200,
  "message": "生成已终止",
  "data": {
    "thread_id": "thread_20260810_001",
    "stopped_at": "2026-08-10T09:00:15Z",
    "partial_tokens": 342,
    "has_partial_result": true,
    "tip": "已为您保留当前已生成的部分行程，可继续修改或重新生成"
  }
}
```

> 403 Response

```json
{
  "code": 40301,
  "message": "无权操作该会话",
  "details": "当前用户与会话创建者不匹配"
}
```

> 404 Response

```json
HTTP/1.1 404 Not Found
Content-Type: application/json

{
  "code": 40401,
  "message": "会话不存在",
  "details": {
    "thread_id": "thread_20260810_001",
    "error": "未找到该会话记录"
  }
}
```

### 返回结果

|状态码|状态码含义|说明|数据模型|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|none|Inline|
|403|[Forbidden](https://tools.ietf.org/html/rfc7231#section-6.5.3)|none|Inline|
|404|[Not Found](https://tools.ietf.org/html/rfc7231#section-6.5.4)|none|Inline|

### 返回数据结构

状态码 **200**

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|» code|integer|true|none||none|
|» message|string|true|none||none|
|» data|object|true|none||none|
|»» thread_id|string|true|none||none|
|»» stopped_at|string|true|none||none|
|»» partial_tokens|integer|true|none||none|
|»» has_partial_result|boolean|true|none||none|
|»» tip|string|true|none||none|

状态码 **403**

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|» code|integer|true|none||none|
|» message|string|true|none||none|
|» details|string|true|none||none|

状态码 **404**

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|» code|integer|true|none||none|
|» message|string|true|none||none|
|» details|object|true|none||none|
|»» thread_id|string|true|none||none|
|»» error|string|true|none||none|

# 对话中枢

<a id="opIdresumeChat"></a>

## POST 恢复中断流程

POST /api/v1/chat/resume

适用场景：
1. 预算超支确认：用户选择"接受超支"或"压缩预算"
2. 行程方案确认：用户选择"满意"或"调整"

恢复后继续沿用 SSE 流式返回后续内容。

> Body 请求参数

```json
{
  "thread_id": "thread_20260810_001",
  "user_decision": {
    "action": "accept",
    "hint": "帮我压缩到 2200 以内",
    "note": "可以接受超支，但尽量别超过太多"
  }
}
```

### 请求参数

|名称|位置|类型|必选|说明|
|---|---|---|---|---|
|X-User-Id|header|string| 是 |用户标识，用于权限校验|
|body|body|object| 是 |none|
|» thread_id|body|string| 是 |会话唯一标识，必须与中断时的一致|
|» user_decision|body|[UserDecision](#schemauserdecision)| 是 |用户对中断问题的决策|
|»» action|body|string| 是 |决策类型：|
|»» hint|body|string| 否 |修改指令（当 action = "modify" 时必填）。|
|»» note|body|string| 否 |补充说明，用于记录用户额外想法|

#### 详细说明

**»» action**: 决策类型：
- accept: 接受当前方案，继续执行
- modify: 拒绝当前方案，按 hint 修改后重试
- reject: 拒绝并终止当前流程

**»» hint**: 修改指令（当 action = "modify" 时必填）。
用自然语言描述修改诉求，如"把预算压缩到2000以内"或"删掉恭王府，换成什刹海划船"

#### 枚举值

|属性|值|
|---|---|
|»» action|accept|
|»» action|modify|
|»» action|reject|

> 返回示例

> 请求参数错误

```json
{
    "code": 40005,
    "message": "修改操作缺少具体指令",
    "details": {
        "field": "user_decision.hint",
        "error": "当 action 为 'modify' 时，hint 为必填字段，请提供具体的修改诉求"
    }
}
```

```json
{
    "code": 40006,
    "message": "决策类型无效",
    "details": {
        "field": "user_decision.action",
        "error": "值 'confirm' 不在允许的枚举范围内，允许值: accept, modify, reject"
    }
}
```

> 用户无权操作该会话

```json
{
    "code": 40301,
    "message": "无权操作该会话",
    "details": {
        "error": "当前用户与会话创建者不匹配"
    }
}
```

> 会话不存在

```json
{
    "code": 40401,
    "message": "会话不存在或已过期",
    "details": {
        "thread_id": "thread_20260810_001",
        "error": "未找到该会话记录"
    }
}
```

> 当前不在中断状态

```json
{
    "code": 40901,
    "message": "当前会话不在中断状态，无需恢复",
    "details": {
        "error": "Agent 流程已完成或尚未暂停，请检查当前状态后再调用恢复接口"
    }
}
```

> AI 服务不可用

```json
{
    "code": 50301,
    "message": "AI 服务暂时不可用，请稍后重试",
    "details": {
        "error": "OpenAI API 请求超时（>30s）"
    }
}
```

> 恢复成功，开始 SSE 流式响应

### 返回结果

|状态码|状态码含义|说明|数据模型|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|恢复成功，开始 SSE 流式响应|string|
|400|[Bad Request](https://tools.ietf.org/html/rfc7231#section-6.5.1)|请求参数错误|[ErrorResponse](#schemaerrorresponse)|
|403|[Forbidden](https://tools.ietf.org/html/rfc7231#section-6.5.3)|用户无权操作该会话|[ErrorResponse](#schemaerrorresponse)|
|404|[Not Found](https://tools.ietf.org/html/rfc7231#section-6.5.4)|会话不存在|[ErrorResponse](#schemaerrorresponse)|
|409|[Conflict](https://tools.ietf.org/html/rfc7231#section-6.5.8)|当前不在中断状态|[ErrorResponse](#schemaerrorresponse)|
|503|[Service Unavailable](https://tools.ietf.org/html/rfc7231#section-6.6.4)|AI 服务不可用|[ErrorResponse](#schemaerrorresponse)|

# 数据模型

<h2 id="tocS_UserDecision">UserDecision</h2>

<a id="schemauserdecision"></a>
<a id="schema_UserDecision"></a>
<a id="tocSuserdecision"></a>
<a id="tocsuserdecision"></a>

```json
{
  "action": "accept",
  "hint": "帮我压缩到 2200 以内",
  "note": "可以接受超支，但尽量别超过太多"
}

```

用户对中断问题的决策

### 属性

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|action|string|true|none||决策类型：<br />- accept: 接受当前方案，继续执行<br />- modify: 拒绝当前方案，按 hint 修改后重试<br />- reject: 拒绝并终止当前流程|
|hint|string|false|none||修改指令（当 action = "modify" 时必填）。<br />用自然语言描述修改诉求，如"把预算压缩到2000以内"或"删掉恭王府，换成什刹海划船"|
|note|string|false|none||补充说明，用于记录用户额外想法|

#### 枚举值

|属性|值|
|---|---|
|action|accept|
|action|modify|
|action|reject|

<h2 id="tocS_ErrorResponse">ErrorResponse</h2>

<a id="schemaerrorresponse"></a>
<a id="schema_ErrorResponse"></a>
<a id="tocSerrorresponse"></a>
<a id="tocserrorresponse"></a>

```json
{
  "code": 40401,
  "message": "会话不存在或已过期",
  "details": {
    "thread_id": "thread_20260810_001",
    "error": "未找到该会话记录"
  }
}

```

统一错误响应格式

### 属性

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|code|integer|true|none||业务错误码（4位或5位）|
|message|string|true|none||用户友好的错误信息|
|details|object|false|none||详细的错误信息，便于前端定位问题|

