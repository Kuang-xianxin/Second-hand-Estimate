<script setup lang="ts">
import { onMounted, reactive, computed } from 'vue'
import { getLoginState, openXianyuLogin, stopValuateTask } from '@/api'
import type { ValuationTask, ValuationStep, ValuationResult, LlmResult, SampleItem, BargainItem, AlgorithmResult, QualitySummary, SSEEventType, SSEQualitySummary } from '../types'

defineOptions({ name: 'HomeView' })

// 全局视图状态：管理当前选中任务、全局加载状态、全局错误信息等
// 用于在多任务并行时统一控制视图展示
// - currentTaskId: 当前选中任务的 ID（对应 ValuationTask.id）
// - tasks: 所有估价任务列表（按创建时间倒序）
// - isLoggedIn: 闲鱼登录态（由 checkLoginState 定时检测）
// - showLoginModal: 是否显示登录引导弹窗
const state = reactive({
  keyword: '',                         // 搜索框输入的关键词
  loading: false,                      // 是否有任务正在执行（控制按钮状态）
  error: '',                           // 当前错误信息（展示错误提示）
  result: null as ValuationResult | null,   // 当前选中任务的完整结果（含算法基准 + 多模型估价）
  steps: [] as ValuationStep[],            // 当前选中任务的步骤列表（用于流程展示）
  currentTaskId: '',                  // 当前选中任务的 ID（用于高亮 tab 和刷新视图）
  activeController: null as AbortController | null,  // 当前 fetch 请求的 AbortController（用于手动中断）
  tasks: [] as ValuationTask[],       // 所有估价任务列表（按创建时间倒序）
  isLoggedIn: false,                  // 闲鱼是否已登录
  checkingLogin: false,               // 是否正在检测登录态（防止重复检测）
  showLoginModal: false,             // 是否显示登录引导弹窗
  openingLogin: false,                // 是否正在打开登录页面（控制按钮 loading）
  ccdMarketOpen: false,               // 市场行情下拉是否展开
  selectedModels: ['deepseek'] as string[],  // 当前选中的大模型列表
})

// 可用模型选项
const AVAILABLE_MODELS = [
  { key: 'deepseek', label: 'DeepSeek' },
  { key: 'qwen', label: '通义千问' },
  { key: 'doubao', label: '豆包' },
]

// 计算属性：根据 currentTaskId 从 tasks 中取出对应任务对象
// 用法同 task，但支持响应式追踪 currentTaskId 变化
// 引用处: <section v-if="currentTask?.steps.length"> 等模板区域
const currentTask: any = computed(() => state.tasks.find(t => t.id === state.currentTaskId))

// 创建新的估价任务对象，初始化各字段并预设"正在爬取闲鱼数据..."步骤
// 返回 reactive 对象，支持直接在模板中响应式访问
// 引用处: doValuate() 中创建新任务
function buildTask(keywordText: string, models: string[]): ValuationTask {
  return reactive({
    id: `task-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,  // 生成唯一任务 ID
    keyword: keywordText,  // 搜索关键词（复制自入参）
    models,                 // 本次估价使用的模型列表（用于判断 pending 卡片数量）
    loading: true,          // 任务初始为加载中状态
    error: '',              // 初始无错误
    result: null,           // 完整结果待 SSE 完成后填充
    xd_confirmed: false,
        // 初始未确认 XD 卡信息
    steps: reactive([{
      id: Date.now() + Math.random(),  // 步骤唯一 ID
      text: '正在爬取闲鱼数据...',       // 初始步骤描述
      status: 'pending',               // pending=进行中，done=完成，error=失败，info=提示
      filteredOut: [],                 // 被筛除的商品列表
      expanded: false,                 // 是否展开详情
    }]),
    controller: null,
    partial: reactive({
      keyword: keywordText,  // 搜索关键词
      sample_count: 0,                            // 有效样本数量
      algorithm: null,                             // ValuationResult.algorithm，算法基准价结果
      quality_summary: null,                       // ValuationResult.quality_summary，质量汇总
      llm_results: reactive<LlmResult[]>([]),     // ValuationResult.llm_results，多个大模型估价结果
      samples: reactive<SampleItem[]>([]),         // ValuationResult.samples，参与估价的有效样本
      bargains: reactive<BargainItem[]>([]),      // ValuationResult.bargains，捡漏机会列表
    }),
  }) as ValuationTask
}

// 将指定任务的关键状态同步到全局 state，用于多任务切换时刷新视图
// 引用处: selectTask()、removeTask()、stopCurrentTask()、doValuate() 中
function syncViewByTask(task: ValuationTask) {
  if (!task) return
  state.loading = !!task.loading
  state.error = task.error || ''
  state.result = task.result
}

// 切换当前选中任务，高亮对应 tab 并刷新视图状态
// 引用处: doValuate() 中发起新任务后自动选中
function selectTask(taskId: string) {
  const task = state.tasks.find(t => t.id === taskId)  // 根据 ID 找到对应任务
  if (!task) return
  state.currentTaskId = taskId
  syncViewByTask(task)
}

// 删除指定任务；若任务正在进行则先调用 stopValuateTask 并 abort 请求
// 若删除的是当前选中任务，则自动切换到下一个任务或清空视图
// 引用处: 模板中 task-tab-remove 按钮点击事件
async function removeTask(taskId: string) {
  const idx = state.tasks.findIndex(t => t.id === taskId)  // 找到任务在列表中的索引，没找到返回-1


  if (idx < 0) return
  const target = state.tasks[idx]  // 待删除的任务对象
  state.activeController=target.controller

  if (target.loading) {
    try {
      await stopValuateTask(target.id)
    } catch {
      // ignore
    }
    if (state.currentTaskId === target.id && state.activeController) {
      state.activeController.abort()  // 中断正在进行中的请求
      state.activeController = null
    }
  }

  state.tasks.splice(idx, 1)  // 从任务列表中移除

  if (state.currentTaskId === taskId) {
    const nextTask = state.tasks[0]  // 切换到下一个任务（若有）
    if (nextTask) {
      state.currentTaskId = nextTask.id
      syncViewByTask(nextTask)
    } else {
      // 无剩余任务，清空视图状态
      state.currentTaskId = ''
      state.loading = false
      state.error = ''
      state.result = null
      state.steps = []
    }
  }
}

// 从 axios/fetch 错误对象中提取人类可读的错误信息
// 兼容 Pydantic 验证错误（resp.data.detail）、HTTP 错误和网络错误
// 引用处: openLoginPage()、doValuate() catch 块
function parseErrorText(e: unknown): string {
  const err = e as Record<string, unknown> | undefined   // 将错误对象转为字典
  const resp = err?.response as Record<string, unknown> | undefined  // axios 封装的响应对象
  const data = resp?.data as Record<string, unknown> | undefined     // 响应体中的 data 字段
  const detail = data?.detail                                // Pydantic 验证错误的 detail 字段
  if (typeof detail === 'string') return detail
  return ((e as Error)?.message) || '请求失败，请检查后端是否启动'
}

// 根据步骤文本判断展开详情的内容类型
// '成色分析完成' 开头 → 'condition'（展示成色分析记录）
// 其他 → 'filter'（展示被筛除商品）
// 引用处: 模板中 stepDetailKind(step) 的判断分支
function
  stepDetailKind(step: ValuationStep): 'condition' | 'filter' {
  const t = step?.text || ''  // 提取步骤文本内容
  return t.includes('成色分析完成') ? 'condition' : 'filter'
}

// 从 quality_flags 数组中提取 XD 卡状态文本
// 格式示例: "内存卡状态: 需自备"、"内存卡状态: 捆绑" 等
// 引用处: 模板中 getSdCardTag(s.quality_flags) 用于 SD 卡标签展示
function getSdCardTag(flags: string[] | undefined): string | null {
  if (!flags) return null
  const f = flags.find(f => f.startsWith('内存卡状态:'))  // 找到 XD 卡状态标记
  return f ? f.replace('内存卡状态:', '') : null
}

// 根据 XD 卡状态返回对应 CSS 类名，控制标签颜色
// '需自备' → sd-tag-self（红色）
// '捆绑'/'含卡' → sd-tag-bundle（绿色）
// '加购' → sd-tag-addon（橙色）
// 其他 → sd-tag-unknown（灰色）
// 引用处: 模板中 class="sd-card-tag" :class="getSdCardTagClass(...)"
function getSdCardTagClass(flags: string[] | undefined): string {
  const text = getSdCardTag(flags) || ''
  if (text.includes('需自备')) return 'sd-tag-self'
  if (text.includes('捆绑') || text.includes('含卡')) return 'sd-tag-bundle'
  if (text.includes('加购')) return 'sd-tag-addon'
  return 'sd-tag-unknown'
}

// 检测当前闲鱼登录态；若未登录则弹出引导窗口
// 在 onMounted 时自动调用一次；也可在用户操作后手动调用刷新
// 引用处: onMounted()、confirmLoginDone()
async function checkLoginState() {
  state.checkingLogin = true
  try {
    const resp = await getLoginState()
    state.isLoggedIn = !!resp?.logged_in
    if (!state.isLoggedIn) state.showLoginModal = true
  } catch {
    state.isLoggedIn = false
  } finally {
    state.checkingLogin = false
  }
}

// 调用后端接口打开闲鱼登录页面（通过 webbrowser 打开）
// 引用处: 登录弹窗中"打开闲鱼登录页"按钮点击事件
async function openLoginPage() {
  state.openingLogin = true
  try {
    await openXianyuLogin()
  } catch (e) {
    state.error = parseErrorText(e)
  } finally {
    state.openingLogin = false
  }
}

// 用户确认完成登录后，重新检测登录态并关闭弹窗
// 引用处: 登录弹窗中"我已登录，重新检测"按钮点击事件
async function confirmLoginDone() {
  await checkLoginState()
  if (state.isLoggedIn) state.showLoginModal = false
}

// 停止当前正在进行的估价任务
// 调用 stopValuateTask API + AbortController abort 双保险停止请求
// 引用处: 模板中"停止当前估价"按钮点击事件
async function stopCurrentTask() {
  if (!state.currentTaskId) return
  const task = state.tasks.find(t => t.id === state.currentTaskId)
  if (!task || !task.loading) return

  try {
    await stopValuateTask(task.id)
    
  } catch {
    // ignore
  }

  if (state.activeController) {
    state.activeController.abort()
    state.activeController = null
  }

  task.loading = false
  task.error = '已手动停止'
  task.steps.push({
    id: Date.now() + Math.random(),
    text: '已停止当前估价任务',
    status: 'error',
    filteredOut: [],
    expanded: false,
  })
  task.steps.forEach(step => {
    if(step.status === 'pending') {
    step.status = 'error'
    }
  });
  syncViewByTask(task)
}

// 发起一次完整的估价请求（SSE 流式接口）
// 流程: buildTask → POST /api/valuate/stream → 解析 SSE 事件 → 更新 task.steps/partial/result
// SSE 事件类型: start | step | xd_confirmed | base | llm | done | stopped | error
// 引用处: 搜索框回车、搜索按钮点击、"新增并行估价"按钮点击事件
async function doValuate() {
  if (!state.keyword.trim()) return
  if (state.checkingLogin) return
  if (!state.isLoggedIn) {
    state.showLoginModal = true
    return
  }

  const task = buildTask(state.keyword.trim(), [...state.selectedModels])  // 创建新任务对象
  state.tasks.unshift(task)                     // 新任务插入列表头部
  selectTask(task.id)                            // 自动选中新创建的任务
  state.keyword = ''                             // 清空搜索框

  task.controller = new AbortController()      // 用于手动中断 fetch 请求
  state.activeController = task.controller

  try {
    await new Promise<void>((resolve, reject) => {
      fetch(`/api/valuate/stream?task_id=${encodeURIComponent(task.id)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: task.keyword, models: state.selectedModels }),
        signal: state.tasks[0].controller?.signal,
      }).then(async (resp) => {
        if (!resp.ok) {
          const txt = await resp.text()
          reject(new Error(txt))
          return
        }
        const reader = resp.body!.getReader()  // SSE 响应流读取器
        const decoder = new TextDecoder()        // 将二进制数据解码为文本
        let buf = ''                             // 缓存不完整的 SSE 行
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          const parts = buf.split('\n\n')        // SSE 事件以双换行分隔
          buf = parts.pop() ?? ''
          for (const part of parts) {
            const eventMatch = part.match(/^event: (\w+)/m)   // 解析事件类型
            const dataMatch = part.match(/^data: (.+)/ms)     // 解析事件数据
            if (!eventMatch || !dataMatch) continue
            const evtType = eventMatch[1] as SSEEventType   // 事件类型字符串
            let payload: Record<string, unknown>
            try { payload = JSON.parse(dataMatch[1]) } catch { continue }

            switch (evtType) {
              case 'start': {
                task.id = (payload.task_id as string) || task.id
                break
              }
              case 'step': {
                if (payload.status === 'pending') {
                  task.steps.push({
                    id: Date.now() + Math.random(),
                    text: payload.text as string,
                    status: 'pending',
                    filteredOut: [],
                    expanded: false,
                  })
                } else {
                  const last = [...task.steps].reverse().find(s => s.status === 'pending')
                  if (last) {
                    last.status = 'done'
                    if (payload.text) last.text = payload.text as string
                    if ((payload.filtered_out as unknown[])?.length) {
                      last.filteredOut = payload.filtered_out as ValuationStep['filteredOut']
                    }
                  }
                }
                break
              }
              case 'xd_confirmed': {
                task.xd_confirmed = true
                task.steps.push({
                  id: Date.now() + Math.random(),
                  text: '【XD卡提示】' + (((payload.text as string) || '').split('\n')[0]),
                  status: 'info',
                  filteredOut: [],
                  expanded: false,
                  is_xd_hint: true,
                  xd_hint_full: payload.text as string | undefined,
                })
                break
              }
              case 'base': {
                const last = [...task.steps].reverse().find(s => s.status === 'pending')
                if (last) {
                  last.status = 'done'
                  last.text = `爬取完成，获得 ${payload.sample_count} 条有效样本`
                }
                task.partial.keyword = payload.keyword as string
                task.partial.sample_count = payload.sample_count as number
                task.partial.xd_card_model = payload.xd_card_model as boolean | undefined
                task.partial.xd_card_bundle_count = payload.xd_card_bundle_count as number | undefined
                task.partial.algorithm = payload.algorithm as AlgorithmResult | null
                task.partial.quality_summary = payload.quality_summary as SSEQualitySummary | null
                task.partial.samples = payload.samples as SampleItem[]
                task.partial.bargains = payload.bargains as BargainItem[]
                task.result = { ...task.partial }
                task.steps.push({
                  id: Date.now() + Math.random(),
                  text: '等待大模型分析结果...',
                  status: 'pending',
                  filteredOut: [],
                  expanded: false,
                })
                break
              }
              case 'llm': {
                const last = [...task.steps].reverse().find(s => s.status === 'pending')
                if (last) last.status = 'done'
                const modelShort = ((payload.model as string) || '').replace(/^ep-[^-]+-\d+-/, '').slice(0, 24)
                task.steps.push({
                  id: Date.now() + Math.random(),
                  text: payload.error
                    ? `${modelShort}：分析失败（${payload.error}）`
                    : `${modelShort} 估价完成：¥${payload.suggested_price}`,
                  status: (payload.error ? 'error' : 'done') as ValuationStep['status'],
                  filteredOut: [],
                  expanded: false,
                })
                const llmPayload = payload as unknown as LlmResult
                task.partial.llm_results = [...task.partial.llm_results, llmPayload]
                task.result = { ...task.partial }
                if (task.partial.llm_results.length < task.models.length) {
                  task.steps.push({
                    id: Date.now() + Math.random(),
                    text: '等待剩余模型结果...',
                    status: 'pending',
                    filteredOut: [],
                    expanded: false,
                  })
                }
                break
              }
              case 'done': {
                const last = [...task.steps].reverse().find(s => s.status === 'pending')
                if (last) {
                  last.status = 'done'
                  last.text = '全部分析完成'
                }
                task.loading = false
                resolve()
                break
              }
              case 'stopped': {
                task.loading = false
                task.error = (payload.detail as string) || '已停止'
                task.steps.push({
                  id: Date.now() + Math.random(),
                  text: '任务已停止',
                  status: 'error',
                  filteredOut: [],
                  expanded: false,
                })
                resolve()
                break
              }
              case 'error': {
                reject(new Error((payload.detail as string) || 'SSE 错误'))
                task.steps.forEach((step,index)=>{
                  if(step.status==='pending')
                  step.status='error'
                })
              }
            }

            if (task.id === state.currentTaskId) syncViewByTask(task)
          }
        }
        resolve()
      }).catch(reject)
    })
  } catch (e) {
    const err = e as Error  // 将异常对象转为标准 Error 类型以访问 message/name
    if (err.name === 'AbortError') {
      task.error = '已手动停止'
    } else {
      task.error = err?.message || '请求失败，请检查后端是否启动'
      task.steps.push({
        id: Date.now() + Math.random(),
        text: task.error,
        status: 'error',
        filteredOut: [],
        expanded: false,
      })
      // 若为登录态相关错误，自动弹出登录引导
      if (/401|登录态|请先登录/.test(task.error)) {
        state.showLoginModal = true
        state.isLoggedIn = false
      }
    }
  } finally {
    task.loading = false
    if (state.activeController === task.controller) state.activeController = null
    if (task.id === state.currentTaskId) syncViewByTask(task)
  }
}

// 组件挂载后自动检测一次闲鱼登录态（页面打开时提示未登录用户）
// 引用处: Vue 生命周期钩子
onMounted(() => {
  checkLoginState()
})
</script>

<template>
  <div class="home">
    <section class="search-section">
      <h1 class="page-title">二手商品智能估价</h1>
      <p class="page-sub">输入商品名称，获取市场价格区间与多模型分析</p>
      <div class="search-box">
        <input v-model="state.keyword" class="search-input" placeholder="例如：iPhone 15 Pro 256G"
          @keydown.enter="doValuate" />
        <button class="search-btn" @click="doValuate" :disabled="state.checkingLogin">
          <span v-if="!state.loading">开始估价</span>
          <span v-else class="loading-dots">分析中<span>.</span><span>.</span><span>.</span></span>
        </button>
      </div>
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
      <div class="task-actions">
        <button class="task-btn" @click="doValuate" :disabled="state.checkingLogin">新增并行估价</button>
        <button class="task-btn stop" @click="stopCurrentTask"
          :disabled="!state.loading || !state.currentTaskId">停止当前估价</button>
      </div>
      <div v-if="!state.isLoggedIn"  class="login-tip">
        <div class="login-tip-title">请先完成一次闲鱼登录授权</div>
      </div>
      <div v-if="state.showLoginModal" class="login-modal-mask">
        <div class="login-modal">
          <div class="login-modal-title">需要先登录闲鱼</div>
          <div class="login-modal-text">检测到当前无登录态。点击"打开闲鱼登录页"后，在浏览器完成登录，再点"我已登录，重新检测"。</div>
          <div class="login-modal-actions">
            <button class="modal-btn primary" @click="openLoginPage" :disabled="state.openingLogin">
              {{ state.openingLogin ? '打开中...' : '打开闲鱼登录页' }}
            </button>
            <button class="modal-btn ghost" @click="confirmLoginDone" :disabled="state.checkingLogin">我已登录，重新检测</button>
            <button class="modal-btn text" @click="state.showLoginModal = false">稍后再说</button>
          </div>
        </div>
      </div>
      <p v-if="state.error" class="error-msg">{{ state.error }}</p>
      <div v-if="state.tasks.length" class="task-tabs">
        <button v-for="t in state.tasks" :key="t.id" class="task-tab" :class="{ active: t.id === state.currentTaskId }"
          @click="selectTask(t.id)">
          <span class="task-tab-keyword">{{ t.keyword }}</span>
          <!--class动态绑定决定字体颜色-->
          <span class="task-tab-status" :class="t.loading ? 'running' : (t.error ? 'failed' : 'done')">   
            {{ t.loading ? '进行中' : (t.error ? '失败' : '完成') }}
          </span>
          <span class="task-tab-remove" title="删除该任务" @click.stop="removeTask(t.id)">×</span>
        </button>
      </div>
    </section>

    <!-- CCD市场行情快捷查看区域 -->
    <section class="ccd-market-section">
      <div class="ccd-market-header">
        <span class="ccd-market-icon">📷</span>
        <span class="ccd-market-title">配件情况</span>
        <span class="ccd-market-date">数据来源：闲鱼，1688，拼多多</span>
      </div>
      <div class="ccd-market-list">
        <div class="ccd-market-dropdown" :class="{ open: state.ccdMarketOpen }">
          <div class="dropdown-header" @click="state.ccdMarketOpen = !state.ccdMarketOpen">
            <span class="dropdown-arrow">{{ state.ccdMarketOpen ? '▼' : '▶' }}</span>
            <span class="dropdown-label">配件与内存卡行情（点击展开）</span>
          </div>
          <div class="dropdown-body">
            <div class="ccd-market-grid">
              <div class="ccd-market-card card">
                <div class="card-title">🔋 配件行情</div>
                <div class="card-items">
                  <div class="market-item card-type"><span class="item-name">读卡器</span></div>
                  <div class="market-item"><span class="item-name">　SD卡读卡器</span><span class="item-price">¥1.5</span></div>
                  <div class="market-item"><span class="item-name">　6合1读卡器</span><span class="item-price">¥6</span></div>
                  <div class="market-item"><span class="item-name">　万能充</span><span class="item-price">¥2.5</span></div>
                  <div class="market-item card-type"><span class="item-name">卡套</span></div>
                  <div class="market-item"><span class="item-name">　XD卡卡套</span><span class="item-price">¥15</span></div>
                  <div class="market-item"><span class="item-name">　索尼长棒卡套</span><span class="item-price">¥11</span></div>
                  <div class="market-item"><span class="item-name">　索尼短棒卡套</span><span class="item-price">¥10</span></div>
                  <div class="market-item card-type"><span class="item-name">电池</span></div>
                  <div class="market-item"><span class="item-name">　1.5V霸浮</span><span class="item-price">¥9.8/对</span></div>
                </div>
              </div>
              <div class="ccd-market-card card">
                <div class="card-title">💾 内存卡行情</div>
                <div class="card-items">
                  <div class="market-item card-type"><span class="item-name">XD卡(富士/奥林巴斯)</span><span class="item-note">值钱！</span></div>
                  <div class="market-item"><span class="item-name">　256MB</span><span class="item-price">¥90-150</span></div>
                  <div class="market-item"><span class="item-name">　512MB</span><span class="item-price">¥100-180</span></div>
                  <div class="market-item"><span class="item-name">　1GB</span><span class="item-price">¥120-200</span></div>
                  <div class="market-item card-type"><span class="item-name">MS卡长棒(索尼专用)</span><span class="item-note">值钱！</span></div>
                  <div class="market-item"><span class="item-name">　4MB</span><span class="item-price">¥16</span></div>
                  <div class="market-item"><span class="item-name">　8MB</span><span class="item-price">¥25</span></div>
                  <div class="market-item"><span class="item-name">　16MB</span><span class="item-price">¥30</span></div>
                  <div class="market-item"><span class="item-name">　32MB</span><span class="item-price">¥40</span></div>
                  <div class="market-item"><span class="item-name">　64MB</span><span class="item-price">¥60</span></div>
                  <div class="market-item"><span class="item-name">　128MB</span><span class="item-price">¥80</span></div>
                  <div class="market-item card-type"><span class="item-name">MS卡短棒</span><span class="item-note">同规格少¥5-20</span></div>
                  <div class="market-item card-type"><span class="item-name">SD卡(佳能/尼康)</span><span class="item-note warn">不值钱</span></div>
                  <div class="market-item"><span class="item-name">　2GB</span><span class="item-price">¥10-15</span></div>
                  <div class="market-item"><span class="item-name">　4GB</span><span class="item-price">¥10-20</span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="ccd-market-footer">
        <div class="market-insight">
          <span class="insight-icon">⚠️</span>
          <span class="insight-text">重要提示：超过6V的专用电池不能用万能充，会烧坏！闲鱼买内存卡需拍开箱视频。MS卡长棒比短棒贵，128MB最贵。</span>
        </div>
      </div>
    </section>

    <section v-if="currentTask?.steps.length" class="steps-section">
      <div class="steps-list">
        <template v-for="step in currentTask.steps" :key="step.id">
           <!--逻辑与当前面的值为零的时候直接短路，当有筛除数组有元素的时候才展开-->
          <div class="step-item"
            :class="['step-' + (step.status), step.filteredOut?.length ? 'step-expandable' : '']"
            @click="step.filteredOut?.length && (step.expanded = !step.expanded)"> 
            <span class="step-icon">
              <span v-if="step.status === 'done'">✓</span>
              <span v-else-if="step.status === 'error'">✗</span>
              <span v-else-if="step.status === 'info'">💡</span>
              <span v-else class="step-spinner"></span>
            </span>
            <span class="step-text">{{ step.text }}</span>
            <span v-if="step.filteredOut?.length" class="step-expand-hint">
              <template v-if="stepDetailKind(step) === 'condition'">
                {{ step.expanded ? '▲' : '▼' }} {{ step.filteredOut.length }} 条成色分析记录
              </template>
              <template v-else>
                {{ step.expanded ? '▲' : '▼' }} {{ step.filteredOut.length }} 条被筛除
              </template>
            </span>
          </div>
          <div v-if="step.expanded && step.filteredOut?.length" class="filtered-out-block">
            <div class="filtered-out-title">
              {{ stepDetailKind(step) === 'condition' ? '成色分析详情' : '被筛除详情' }}
            </div>
            <div v-for="(item, idx) in step.filteredOut" :key="idx" class="filtered-out-item">
              <span class="fo-reason">{{ item.reason }}</span>
              <span class="fo-title">{{ item.title }}</span>
              <span class="fo-price">¥{{ item.price }}</span>
            </div>
          </div>
        </template>
      </div>
    </section>

    <section v-if="currentTask?.result" class="result-section">
      <div class="final-valuation-section">
        <div class="section-title final-title">
          <span class="final-star">★</span> 最终估价建议 <span class="final-star">★</span>
        </div>
        <div class="llm-grid final-llm-grid">
          <div v-for="m in currentTask.result.llm_results" :key="m.model" class="llm-card final-llm-card"
            :class="{ 'has-error': !!m.error }">
            <div class="llm-model-name">{{ m.model }}</div>
            <div v-if="m.error" class="llm-error">{{ m.error }}</div>
            <template v-else>
              <div class="llm-price">¥{{ m.suggested_price }}</div>
              <div class="llm-range">¥{{ m.price_min }} — ¥{{ m.price_max }}</div>
              <div class="llm-confidence" :class="'conf-' + m.confidence">置信度：{{ m.confidence }}</div>
              <div class="llm-reasoning">{{ m.reasoning }}</div>
            </template>
          </div>
          <div
            v-for="n in Math.max(0, (currentTask.models?.length || 1) - (currentTask.result.llm_results?.length || 0))"
            :key="'pending-' + n" class="llm-card llm-card-pending">
            <div class="llm-model-name">分析中...</div>
            <div class="llm-pending-dots"><span>.</span><span>.</span><span>.</span></div>
          </div>
        </div>
      </div>

      <div class="algo-reference">
        <div class="algo-ref-header">
          <span class="algo-ref-icon">📊</span>
          <span class="algo-ref-label">算法基准参考</span>
          <span class="algo-ref-hint">仅供参考，不作为最终结果</span>
        </div>
        <div class="algo-ref-content" v-if="currentTask.result.algorithm">
          <div class="algo-ref-price">
            基准价 <span class="algo-price-val">¥{{ currentTask.result.algorithm.base_price }}</span>
          </div>
          <div class="algo-ref-range">
            合理区间：¥{{ currentTask.result.algorithm.price_min }} — ¥{{ currentTask.result.algorithm.price_max }}
          </div>
          <div class="algo-ref-sample">样本 {{ currentTask.result.sample_count }} 条</div>
        </div>
        <div v-else class="loading-placeholder">正在计算中...</div>
      </div>

      <div class="section-title">样本数据（参与估价）</div>
      <div v-if="currentTask.result.samples?.length" class="sample-list">
        <a v-for="s in currentTask.result.samples" :key="s.item_id" :href="s.url" target="_blank" class="sample-item">
          <img v-if="s.images && s.images.length" :src="s.images[0]" class="sample-thumb" loading="lazy" />
          <div v-else class="sample-thumb-placeholder">无图</div>
          <div class="sample-main">
            <div class="sample-title">{{ s.title }}</div>
            <div class="sample-meta">
              <span>成色：{{ s.condition || '未标注' }}</span>
              <span>质量分：{{ s.quality_score }}</span>
              <span>{{ s.sold ? '已售' : '在售' }}</span>
              <span v-if="currentTask.xd_confirmed && getSdCardTag(s.quality_flags)" class="sd-card-tag"
                :class="getSdCardTagClass(s.quality_flags)">{{ getSdCardTag(s.quality_flags) }}</span>
            </div>
            <div v-if="s.quality_flags && s.quality_flags.some((f: string) => f.startsWith('图片'))"
              class="sample-img-flags">
              <span v-for="f in s.quality_flags.filter((f: string) => f.startsWith('图片'))" :key="f"
                class="img-flag-tag">{{
                  f }}</span>
            </div>
          </div>
          <div class="sample-price">¥{{ s.price }}</div>
        </a>
      </div>
      <div v-else class="sample-empty">暂无样本数据</div>

      <div v-if="state.result?.bargains.length" class="section-title bargain-title">
        捡漏机会 <span class="bargain-count">{{ state.result.bargains.length }}</span>
      </div>
      <div v-if="state.result?.bargains.length" class="bargain-list">
        <a v-for="b in state.result.bargains" :key="b.item_id" :href="b.url" target="_blank" class="bargain-item"
          :class="{ 'bargain-item-xd': b.has_xd_bonus }">
          <div v-if="b.has_xd_bonus" class="xd-card-badge">
            含XD卡 {{ b.xd_card_size ? b.xd_card_size.toUpperCase() : '' }}
            <span class="xd-card-value">+约¥{{ b.xd_card_value }}卡值</span>
          </div>
          <div class="bargain-title-text">{{ b.title }}</div>
          <div class="bargain-prices">
            <span class="bargain-actual">¥{{ b.price }}</span>
            <span class="bargain-est">估价 ¥{{ b.estimated_price }}</span>
            <span class="bargain-profit" :class="{ 'profit-xd': b.has_xd_bonus }">
              +¥{{ b.profit_estimate }} 利润
            </span>
          </div>
        </a>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home {
  max-width: 900px;
  margin: 0 auto;
}

.search-section {
  margin-bottom: 48px;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 3px;
  margin-bottom: 8px;
}

.page-sub {
  color: var(--text2);
  font-size: 14px;
  margin-bottom: 24px;
}

.search-box {
  display: flex;
  gap: 12px;
  margin-bottom: 10px;
}

.model-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.model-selector-label {
  font-size: 12px;
  color: var(--text2);
  white-space: nowrap;
}

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

.model-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.model-btn.active {
  background: rgba(232, 197, 71, 0.12);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
}

.task-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}

.task-btn {
  background: var(--bg2);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
}

.task-btn.stop {
  border-color: rgba(224, 92, 92, 0.4);
  color: var(--red);
}

.task-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.search-input {
  flex: 1;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 20px;
  font-size: 16px;
  color: var(--text);
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: var(--accent);
}

.search-input:disabled {
  opacity: 0.5;
}

.search-btn {
  background: var(--accent);
  color: #0e0e10;
  font-weight: 700;
  font-size: 15px;
  padding: 0 32px;
  border-radius: var(--radius);
  transition: opacity 0.2s, transform 0.1s;
  white-space: nowrap;
  border: none;
  cursor: pointer;
}

.search-btn:hover:not(:disabled) {
  opacity: 0.85;
  transform: translateY(-1px);
}

.search-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.loading-dots span {
  animation: blink 1.2s infinite;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {

  0%,
  80%,
  100% {
    opacity: 0
  }

  40% {
    opacity: 1
  }
}

.login-tip {
  margin-bottom: 14px;
  padding: 12px 14px;
  background: rgba(232, 197, 71, 0.08);
  border: 1px solid rgba(232, 197, 71, 0.2);
  border-radius: var(--radius);
}

.login-tip-title {
  color: var(--accent);
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 4px;
}

.login-tip-text {
  color: var(--text2);
  font-size: 12px;
  line-height: 1.6;
  font-family: var(--font-mono);
}

.login-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(6, 8, 16, 0.72);
  display: grid;
  place-items: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.login-modal {
  width: min(560px, calc(100vw - 28px));
  background: linear-gradient(180deg, rgba(22, 22, 30, 0.98), rgba(16, 16, 24, 0.98));
  border: 1px solid rgba(232, 197, 71, 0.35);
  border-radius: 12px;
  box-shadow: 0 14px 40px rgba(0, 0, 0, 0.45);
  padding: 20px 20px 16px;
}

.login-modal-title {
  color: var(--accent);
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 8px;
}

.login-modal-text {
  color: var(--text2);
  font-size: 13px;
  line-height: 1.7;
}

.login-modal-actions {
  margin-top: 16px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.modal-btn {
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.modal-btn.primary {
  background: var(--accent);
  color: #18140a;
  border: none;
}

.modal-btn.ghost {
  background: rgba(232, 197, 71, 0.08);
  color: var(--accent);
  border: 1px solid rgba(232, 197, 71, 0.35);
}

.modal-btn.text {
  background: transparent;
  color: var(--text2);
  border: none;
}

.modal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-msg {
  color: var(--red);
  font-size: 13px;
  margin-top: 10px;
  padding: 10px 14px;
  background: rgba(224, 92, 92, 0.1);
  border-radius: var(--radius);
  border: 1px solid rgba(224, 92, 92, 0.2);
}

.task-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.task-tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--border);
  background: var(--bg2);
  color: var(--text2);
  border-radius: 999px;
  padding: 5px 8px 5px 12px;
  font-size: 12px;
  cursor: pointer;
}

.task-tab-remove {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--text2);
  background: var(--bg3);
  font-size: 14px;
  line-height: 1;
}

.task-tab-remove:hover {
  color: #fff;
  background: var(--red);
}

.task-tab.active {
  border-color: var(--accent);
  color: var(--text);
}

.task-tab-status.running {
  color: var(--accent);
}

.task-tab-status.done {
  color: var(--green);
}

.task-tab-status.failed {
  color: var(--red);
}

.section-title {
  font-size: 13px;
  letter-spacing: 3px;
  color: var(--text2);
  text-transform: uppercase;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

.final-valuation-section {
  margin-bottom: 24px;
}

.final-title {
  text-align: center;
  border-color: var(--accent);
  color: var(--accent);
  font-size: 16px;
  letter-spacing: 4px;
}

.final-star {
  color: var(--accent);
}

.final-llm-grid {
  margin-bottom: 0;
}

.final-llm-card {
  border: 2px solid var(--accent);
  background: linear-gradient(180deg, var(--bg3) 0%, var(--bg2) 100%);
}

.final-llm-card:hover {
  border-color: var(--accent);
  box-shadow: 0 0 20px rgba(232, 197, 71, 0.2);
}

.algo-reference {
  background: var(--bg2);
  border: 1px dashed var(--border);
  border-radius: var(--radius);
  padding: 16px 20px;
  margin-bottom: 20px;
  opacity: 0.7;
}

.algo-ref-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 12px;
}

.algo-ref-icon {
  font-size: 14px;
}

.algo-ref-label {
  color: var(--text2);
  font-weight: 600;
}

.algo-ref-hint {
  color: var(--text2);
  opacity: 0.6;
  font-size: 11px;
  margin-left: auto;
}

.algo-ref-content {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.algo-ref-price {
  font-size: 13px;
  color: var(--text2);
}

.algo-price-val {
  font-weight: 700;
  color: var(--text);
  font-family: var(--font-mono);
  margin-left: 4px;
}

.algo-ref-range {
  font-size: 12px;
  color: var(--text2);
  font-family: var(--font-mono);
}

.algo-ref-sample {
  font-size: 11px;
  color: var(--text2);
  opacity: 0.7;
}

.llm-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

@media (max-width: 700px) {
  .llm-grid {
    grid-template-columns: 1fr;
  }
}

.llm-card {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  transition: border-color 0.2s;
}

.llm-card:hover {
  border-color: var(--accent);
}

.llm-card.has-error {
  border-color: rgba(224, 92, 92, 0.3);
}

.llm-model-name {
  font-size: 11px;
  letter-spacing: 2px;
  color: var(--text2);
  margin-bottom: 12px;
  font-family: var(--font-mono);
}

.llm-price {
  font-size: 30px;
  font-weight: 700;
  color: var(--text);
  font-family: var(--font-mono);
  margin-bottom: 4px;
}

.llm-range {
  font-size: 12px;
  color: var(--text2);
  font-family: var(--font-mono);
  margin-bottom: 8px;
}

.llm-confidence {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 10px;
  font-family: var(--font-mono);
}

.conf-高 {
  background: rgba(92, 184, 122, 0.15);
  color: var(--green);
}

.conf-中 {
  background: rgba(232, 197, 71, 0.15);
  color: var(--accent);
}

.conf-低 {
  background: rgba(224, 92, 92, 0.15);
  color: var(--red);
}

.llm-reasoning {
  font-size: 12px;
  color: var(--text2);
  line-height: 1.6;
}

.llm-error {
  font-size: 12px;
  color: var(--red);
  line-height: 1.6;
}

.sample-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 28px;
}

.sample-item {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  transition: border-color 0.2s, background 0.2s;
  text-decoration: none;
}

.sample-item:hover {
  border-color: var(--accent);
  background: rgba(232, 197, 71, 0.05);
}

.sample-thumb {
  width: 64px;
  height: 64px;
  object-fit: cover;
  border-radius: 6px;
  flex-shrink: 0;
  border: 1px solid var(--border);
  background: var(--bg2);
}

.sample-thumb-placeholder {
  width: 64px;
  height: 64px;
  border-radius: 6px;
  flex-shrink: 0;
  background: var(--bg2);
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: var(--text2);
}

.sample-img-flags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.img-flag-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(255, 180, 0, 0.12);
  color: #c8960a;
  border: 1px solid rgba(255, 180, 0, 0.25);
}

.sd-card-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
}

.sd-tag-self {
  background: rgba(224, 92, 92, 0.15);
  color: #e05c5c;
  border: 1px solid rgba(224, 92, 92, 0.35);
}

.sd-tag-bundle {
  background: rgba(92, 184, 122, 0.15);
  color: #5cc87a;
  border: 1px solid rgba(92, 184, 122, 0.35);
}

.sd-tag-addon {
  background: rgba(255, 136, 0, 0.15);
  color: #ff8800;
  border: 1px solid rgba(255, 136, 0, 0.35);
}

.sd-tag-unknown {
  background: rgba(120, 130, 160, 0.15);
  color: #7882a0;
  border: 1px solid rgba(120, 130, 160, 0.3);
}

.sample-main {
  min-width: 0;
  flex: 1;
}

.sample-title {
  color: var(--text);
  font-size: 14px;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sample-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--text2);
  font-size: 12px;
  font-family: var(--font-mono);
}

.sample-price {
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 20px;
  font-weight: 700;
  white-space: nowrap;
}

.sample-empty {
  color: var(--text2);
  font-size: 12px;
  margin-top: -8px;
  margin-bottom: 20px;
}

.llm-card-pending {
  opacity: 0.6;
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {

  0%,
  100% {
    opacity: 0.6;
  }

  50% {
    opacity: 0.3;
  }
}

.llm-pending-dots {
  font-size: 24px;
  color: var(--accent);
  letter-spacing: 4px;
  margin-top: 12px;
}

.llm-pending-dots span {
  animation: blink 1.2s step-start infinite;
}

.llm-pending-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.llm-pending-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

.loading-placeholder {
  color: var(--text2);
  font-size: 14px;
  padding: 12px 0;
  animation: pulse 1.4s ease-in-out infinite;
}

.steps-section {
  margin-bottom: 32px;
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 20px 24px;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.step-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  font-family: var(--font-mono);
  transition: opacity 0.3s;
}

.step-expandable {
  cursor: pointer;
  border-radius: 4px;
  padding: 2px 4px;
  margin: 0 -4px;
}

.step-expandable:hover {
  background: var(--bg3);
}

.step-expand-hint {
  margin-left: auto;
  font-size: 11px;
  color: var(--text2);
  white-space: nowrap;
}

.filtered-out-block {
  margin: 2px 0 8px 24px;
  border-left: 2px solid var(--border);
  padding-left: 12px;
}

.filtered-out-title {
  font-size: 11px;
  color: var(--text2);
  letter-spacing: 1px;
  margin-bottom: 6px;
  text-transform: uppercase;
}

.filtered-out-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background: var(--bg3);
  border-radius: 4px;
  margin-bottom: 4px;
  font-size: 12px;
}

.fo-reason {
  color: var(--red);
  font-size: 11px;
  background: rgba(224, 92, 92, 0.12);
  padding: 1px 5px;
  border-radius: 3px;
  white-space: nowrap;
}

.fo-title {
  flex: 1;
  color: var(--text2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fo-price {
  color: var(--text2);
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: nowrap;
}

.step-icon {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  flex-shrink: 0;
}

.step-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--text2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1.2s linear infinite;
}
@keyframes spin {
  0% {
    transform: rotate(0deg) scale(1);
  }
  50% {
    transform: rotate(180deg) scale(1.15);
  }
  100% {
    transform: rotate(360deg) scale(1);
  }
}

.step-text {
  flex: 1;
}

.bargain-title {
  color: var(--red);
  border-color: rgba(224, 92, 92, 0.3);
}

.bargain-count {
  background: var(--red);
  color: #fff;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 10px;
  font-family: var(--font-mono);
}

.bargain-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bargain-item {
  background: var(--bg2);
  border: 1px solid rgba(224, 92, 92, 0.25);
  border-radius: var(--radius);
  padding: 14px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  transition: border-color 0.2s, background 0.2s;
  text-decoration: none;
}

.bargain-item:hover {
  border-color: var(--red);
  background: rgba(224, 92, 92, 0.06);
}

.bargain-title-text {
  font-size: 14px;
  color: var(--text);
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.bargain-prices {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
  font-family: var(--font-mono);
  font-size: 13px;
}

.bargain-actual {
  color: var(--red);
  font-weight: 700;
  font-size: 16px;
}

.bargain-est {
  color: var(--text2);
}

.bargain-profit {
  background: rgba(92, 184, 122, 0.15);
  color: var(--green);
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.bargain-profit.profit-xd {
  background: rgba(255, 136, 0, 0.18);
  color: #ff8800;
}

.bargain-item.bargain-item-xd {
  border-color: rgba(255, 136, 0, 0.45);
  background: rgba(255, 136, 0, 0.04);
}

.bargain-item.bargain-item-xd:hover {
  border-color: #ff8800;
  background: rgba(255, 136, 0, 0.10);
}

.xd-card-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: linear-gradient(135deg, #ff8800, #ff5500);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 4px;
  margin-bottom: 6px;
  box-shadow: 0 1px 4px rgba(255, 100, 0, 0.3);
}

.xd-card-value {
  background: rgba(255, 255, 255, 0.25);
  border-radius: 3px;
  padding: 0 5px;
  font-weight: 600;
}

.step-item.info {
  background: rgba(255, 136, 0, 0.05);
  border-color: rgba(255, 136, 0, 0.25);
}

.step-item.info .step-icon {
  background: rgba(255, 136, 0, 0.15);
  color: #ff8800;
  border-color: rgba(255, 136, 0, 0.3);
}

.step-item.info .step-dot {
  background: #ff8800;
}

.step-item.info .step-text {
  color: #cc6600;
}

.step-item.info .step-dot {
  background: #ff8800;
  box-shadow: 0 0 0 3px rgba(255, 136, 0, 0.2);
}

/* CCD市场行情展示区域 */
.ccd-market-section {
  margin-top: 32px;
  padding: 20px 24px;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.ccd-market-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.ccd-market-icon {
  font-size: 20px;
}

.ccd-market-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--accent);
}

.ccd-market-date {
  font-size: 11px;
  color: var(--text2);
  margin-left: auto;
}

.ccd-market-tip {
  margin-bottom: 16px;
  padding: 8px 12px;
  background: rgba(232, 197, 71, 0.08);
  border-radius: 6px;
  font-size: 13px;
}

.trend-info {
  color: var(--accent);
}

.trend-down {
  color: #ff8800;
}

.ccd-market-list {
  margin-bottom: 12px;
}

.ccd-market-dropdown {
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.dropdown-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--bg3);
  cursor: pointer;
  font-size: 13px;
  user-select: none;
  transition: background 0.15s;
}

.dropdown-header:hover {
  background: rgba(232, 197, 71, 0.08);
}

.dropdown-arrow {
  color: var(--accent);
  font-size: 10px;
}

.dropdown-label {
  color: var(--text2);
}

.dropdown-body {
  display: none;
  padding: 14px;
  background: var(--bg2);
}

.ccd-market-dropdown.open .dropdown-body {
  display: block;
}

.ccd-market-dropdown.open .dropdown-header {
  border-bottom: 1px solid var(--border);
}

.ccd-market-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.ccd-market-card {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
}

.ccd-market-card.hot {
  border-color: rgba(224, 92, 92, 0.3);
}

.ccd-market-card.mid {
  border-color: rgba(232, 197, 71, 0.25);
}

.ccd-market-card.low {
  border-color: rgba(120, 130, 160, 0.25);
}

.ccd-market-card.card {
  border-color: rgba(92, 184, 122, 0.25);
}

.card-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}

.card-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.market-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.item-name {
  color: var(--text2);
}

.item-price {
  color: var(--accent);
  font-weight: 600;
  font-family: var(--font-mono);
}

.market-item.card-type {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--border);
}

.item-note {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(92, 184, 122, 0.15);
  color: var(--green);
  font-weight: 600;
}

.item-note.warn {
  background: rgba(224, 92, 92, 0.12);
  color: var(--red);
}

.ccd-market-footer {
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.market-insight {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  color: var(--text2);
  line-height: 1.5;
}

.insight-icon {
  flex-shrink: 0;
}

.insight-text {
  color: #a08800;
}

.light .insight-text {
  color: #8a6d00;
}
</style>