# SSE 下拉表单相关代码导航

## 一、模型选择（HomeView.vue）

### 1.1 模型选项定义

[HomeView.vue 第 27-35 行](file:///d:/cursor项目文件/估二手/frontend/src/views/HomeView.vue#L27)

```javascript
const AVAILABLE_MODELS = [
  { key: 'deepseek', label: 'DeepSeek' },
  { key: 'qwen', label: '通义千问' },
  { key: 'doubao', label: '豆包' },
]
```

### 1.2 模型选择 UI 按钮

[HomeView.vue 第 462-473 行](file:///d:/cursor项目文件/估二手/frontend/src/views/HomeView.vue#L462)

```vue
<div class="model-selector">
  <span class="model-selector-label">模型选择：</span>
  <button v-for="m in AVAILABLE_MODELS" :key="m.key" class="model-btn"
    :class="{ active: state.selectedModels.includes(m.key) }" @click="() => {
      const idx = state.selectedModels.indexOf(m.key)
      if (idx >= 0) {
        if (state.selectedModels.length > 1) state.selectedModels.splice(idx, 1)
      } else {
        state.selectedModels.push(m.key)
      }
    }">{{ m.label }}</button>
</div>
```

### 1.3 模型按钮样式

[HomeView.vue 第 682-703 行](file:///d:/cursor项目文件/估二手/frontend/src/views/HomeView.vue#L682)

```css
.model-btn {
  background: var(--bg2);
  color: var(--text2);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.model-btn.active {
  background: rgba(232, 197, 71, 0.12);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
}
```

---

## 二、SSE 请求发起（HomeView.vue）

### 2.1 doValuate() 函数定义

[HomeView.vue 第 245-268 行](file:///d:/cursor项目文件/估二手/frontend/src/views/HomeView.vue#L245)

```javascript
async function doValuate() {
  if (!state.keyword.trim()) return
  if (state.checkingLogin) return
  if (!state.isLoggedIn) {
    state.showLoginModal = true
    return
  }

  const task = buildTask(state.keyword.trim(), [...state.selectedModels])
  state.tasks.unshift(task)
  selectTask(task.id)
  state.keyword = ''

  const controller = new AbortController()
  state.activeController = controller

  try {
    await new Promise<void>((resolve, reject) => {
      fetch(`/api/valuate/stream?task_id=${encodeURIComponent(task.id)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: task.keyword, models: state.selectedModels }),
        signal: controller.signal,
      })
```

### 2.2 SSE 流读取解析

[HomeView.vue 第 274-290 行](file:///d:/cursor项目文件/估二手/frontend/src/views/HomeView.vue#L274)

```javascript
const reader = resp.body!.getReader()
const decoder = new TextDecoder()
let buf = ''
while (true) {
  const { done, value } = await reader.read()
  if (done) break
  buf += decoder.decode(value, { stream: true })
  const parts = buf.split('\n\n')
  buf = parts.pop() ?? ''
  for (const part of parts) {
    const eventMatch = part.match(/^event: (\w+)/m)
    const dataMatch = part.match(/^data: (.+)/ms)
```

### 2.3 SSE 事件类型处理

[HomeView.vue 第 291-390 行](file:///d:/cursor项目文件/估二手/frontend/src/views/HomeView.vue#L291)

```javascript
switch (evtType) {
  case 'start': {
    task.id = (payload.task_id as string) || task.id
    break
  }
  case 'step': {
    // 处理步骤更新
    break
  }
  case 'xd_confirmed': {
    task.xd_confirmed = true
    // 处理 XD 卡提示
    break
  }
  case 'base': {
    // 处理基准价和样本数据
    task.partial.algorithm = payload.algorithm as AlgorithmResult | null
    task.partial.quality_summary = payload.quality_summary as SSEQualitySummary | null
    task.result = { ...task.partial }
    break
  }
  case 'llm': {
    // 处理大模型估价结果
    const llmPayload = payload as unknown as LlmResult
    task.partial.llm_results = [...task.partial.llm_results, llmPayload]
    task.result = { ...task.partial }
    break
  }
  case 'done': {
    task.loading = false
    resolve()
    break
  }
}
```

---

## 三、后端 SSE 接口（valuate.py）

### 3.1 SSE 流式接口定义

[valuate.py 第 656-671 行](file:///d:/cursor项目文件/估二手/backend/app/api/valuate.py#L656)

```python
@router.post("/valuate/stream")
async def valuate_stream(req: ValuateRequest, db: AsyncSession = Depends(get_db), task_id: Optional[str] = Query(None)):
    """SSE 流式估价：爬取完立即推送基础数据，大模型结果谁先完成先推送谁。"""
    task_id = (task_id or str(uuid.uuid4())).strip()
    _register_stream_task(task_id)
    original_keyword = req.keyword.strip()
    keyword = _canonicalize_keyword(original_keyword)

    async def event_stream():
        yield f"event: start\ndata: {json.dumps({'task_id': task_id}, ensure_ascii=False)}\n\n"
        if _is_stream_task_stopped(task_id):
            yield f"event: stopped\ndata: {json.dumps({'task_id': task_id, 'detail': '任务已停止'}, ensure_ascii=False)}\n\n"
            return
```

### 3.2 LLM 结果转换

[valuate.py 第 127-138 行](file:///d:/cursor项目文件/估二手/backend/app/api/valuate.py#L127)

```python
def _to_valuation_for_stream(data: dict, model_name: str) -> dict:
    """把 LLM 返回的 dict 转成可 JSON 序列化的 dict（供 SSE 推送）"""
    v = _to_valuation_raw(data, model_name)
    return {
        "model": v.model_name,
        "suggested_price": v.suggested_price,
        "price_min": v.price_min,
        "price_max": v.price_max,
        "reasoning": v.reasoning,
        "confidence": v.confidence,
        "error": v.error,
    }
```

---

## 四、数据类型定义（types/index.ts）

### 4.1 SSE 事件类型定义

[types/index.ts 第 1-27 行](file:///d:/cursor项目文件/估二手/frontend/src/types/index.ts#L1)

```typescript
export type SSEEventType =
  | 'start'         // 服务端返回任务真实 ID
  | 'step'          // 爬取/筛选过程中的进度步骤
  | 'xd_confirmed'  // 检测到 XD 卡相机
  | 'base'          // 爬取完成，推送基准价和样本数据
  | 'llm'           // 单个大模型估价结果
  | 'done'          // 所有流程完成
  | 'stopped'       // 任务被手动停止
  | 'error'         // 流程出错
```

---

## 快速跳转清单

| 功能 | 文件 | 行号 |
|------|------|------|
| 模型选项定义 | HomeView.vue | [27-35](file:///d:/cursor项目文件/估二手/frontend/src/views/HomeView.vue#L27) |
| 模型选择 UI | HomeView.vue | [462-473](file:///d:/cursor项目文件/估二手/frontend/src/views/HomeView.vue#L462) |
| 模型按钮样式 | HomeView.vue | [682-703](file:///d:/cursor项目文件/估二手/frontend/src/views/HomeView.vue#L682) |
| doValuate 请求 | HomeView.vue | [245-268](file:///d:/cursor项目文件/估二手/frontend/src/views/HomeView.vue#L245) |
| SSE 流读取 | HomeView.vue | [274-290](file:///d:/cursor项目文件/估二手/frontend/src/views/HomeView.vue#L274) |
| SSE 事件处理 | HomeView.vue | [291-390](file:///d:/cursor项目文件/估二手/frontend/src/views/HomeView.vue#L291) |
| SSE 接口定义 | valuate.py | [656-671](file:///d:/cursor项目文件/估二手/backend/app/api/valuate.py#L656) |
| LLM 结果转换 | valuate.py | [127-138](file:///d:/cursor项目文件/估二手/backend/app/api/valuate.py#L127) |
| SSE 类型定义 | types/index.ts | [1-27](file:///d:/cursor项目文件/估二手/frontend/src/types/index.ts#L1) |

---

> 点击上方的链接即可跳转到对应文件的指定行号
