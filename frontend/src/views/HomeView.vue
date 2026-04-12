<script setup lang="ts">
import { onMounted, reactive, computed } from 'vue'
import { getLoginState, openXianyuLogin, stopValuateTask } from '../api'
import type { ValuationTask, ValuationStep, ValuationResult, LlmResult, SampleItem, BargainItem, AlgorithmResult, QualitySummary } from '../types'

defineOptions({ name: 'HomeView' })

const state = reactive({
  keyword: '',
  loading: false,
  error: '',
  result: null as ValuationResult | null,
  steps: [] as ValuationStep[],
  currentTaskId: '',
  activeController: null as AbortController | null,
  tasks: [] as ValuationTask[],
  isLoggedIn: false,
  checkingLogin: false,
  showLoginModal: false,
  openingLogin: false,
})

const currentTask: any = computed(() => state.tasks.find(t => t.id === state.currentTaskId))

function buildTask(keywordText: string): ValuationTask {
  return reactive({
    id: `task-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    keyword: keywordText,
    loading: true,
    error: '',
    result: null,
    xd_confirmed: false,
    steps: reactive([{
      id: Date.now() + Math.random(),
      text: '正在爬取闲鱼数据...',
      status: 'pending',
      filteredOut: [],
      expanded: false,
    }]),
    partial: reactive({
      keyword: keywordText,
      sample_count: 0,
      algorithm: null,
      quality_summary: null,
      llm_results: reactive<LlmResult[]>([]),
      samples: reactive<SampleItem[]>([]),
      bargains: reactive<BargainItem[]>([]),
    }),
  }) as ValuationTask
}

function syncViewByTask(task: ValuationTask) {
  if (!task) return
  state.loading = !!task.loading
  state.error = task.error || ''
  state.result = task.result
}

function selectTask(taskId: string) {
  const task = state.tasks.find(t => t.id === taskId)
  if (!task) return
  state.currentTaskId = taskId
  syncViewByTask(task)
}

async function removeTask(taskId: string) {
  const idx = state.tasks.findIndex(t => t.id === taskId)
  if (idx < 0) return
  const target = state.tasks[idx]

  if (target.loading) {
    try {
      await stopValuateTask(target.id)
    } catch {
      // ignore
    }
    if (state.currentTaskId === target.id && state.activeController) {
      state.activeController.abort()
      state.activeController = null
    }
  }

  state.tasks.splice(idx, 1)

  if (state.currentTaskId === taskId) {
    const nextTask = state.tasks[0]
    if (nextTask) {
      state.currentTaskId = nextTask.id
      syncViewByTask(nextTask)
    } else {
      state.currentTaskId = ''
      state.loading = false
      state.error = ''
      state.result = null
      state.steps = []
    }
  }
}

function parseErrorText(e: unknown): string {
  const err = e as Record<string, unknown> | undefined
  const resp = err?.response as Record<string, unknown> | undefined
  const data = resp?.data as Record<string, unknown> | undefined
  const detail = data?.detail
  if (typeof detail === 'string') return detail
  return ((e as Error)?.message) || '请求失败，请检查后端是否启动'
}

function stepDetailKind(step: ValuationStep): 'condition' | 'filter' {
  const t = step?.text || ''
  return t.includes('成色分析完成') ? 'condition' : 'filter'
}

function getSdCardTag(flags: string[] | undefined): string | null {
  if (!flags) return null
  const f = flags.find(f => f.startsWith('内存卡状态:'))
  return f ? f.replace('内存卡状态:', '') : null
}

function getSdCardTagClass(flags: string[] | undefined): string {
  const text = getSdCardTag(flags) || ''
  if (text.includes('需自备')) return 'sd-tag-self'
  if (text.includes('捆绑') || text.includes('含卡')) return 'sd-tag-bundle'
  if (text.includes('加购')) return 'sd-tag-addon'
  return 'sd-tag-unknown'
}

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

async function confirmLoginDone() {
  await checkLoginState()
  if (state.isLoggedIn) state.showLoginModal = false
}

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
  syncViewByTask(task)
}

async function doValuate() {
  if (!state.keyword.trim()) return
  if (state.checkingLogin) return
  if (!state.isLoggedIn) {
    state.showLoginModal = true
    return
  }

  const task = buildTask(state.keyword.trim())
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
        body: JSON.stringify({ keyword: task.keyword }),
        signal: controller.signal,
      }).then(async (resp) => {
        if (!resp.ok) {
          const txt = await resp.text()
          reject(new Error(txt))
          return
        }
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
            if (!eventMatch || !dataMatch) continue
            const evtType = eventMatch[1]
            let payload: Record<string, unknown>
            try { payload = JSON.parse(dataMatch[1]) } catch { continue }

            if (evtType === 'start') {
              task.id = (payload.task_id as string) || task.id
            } else if (evtType === 'step') {
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
                  if ((payload.filtered_out as Array<unknown>)?.length) {
                    last.filteredOut = payload.filtered_out as ValuationStep['filteredOut']
                  }
                }
              }
            } else if (evtType === 'xd_confirmed') {
              task.xd_confirmed = true
              task.steps.push({
                id: Date.now() + Math.random(),
                text: '【XD卡提示】' + ((payload.text as string) || '').split('\n')[0],
                status: 'info',
                filteredOut: [],
                expanded: false,
                is_xd_hint: true,
                xd_hint_full: payload.text as string | undefined,
              })
            } else if (evtType === 'base') {
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
              task.partial.quality_summary = payload.quality_summary as QualitySummary | null
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
            } else if (evtType === 'llm') {
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
              if (task.partial.llm_results.length < 3) {
                task.steps.push({
                  id: Date.now() + Math.random(),
                  text: '等待剩余模型结果...',
                  status: 'pending',
                  filteredOut: [],
                  expanded: false,
                })
              }
            } else if (evtType === 'done') {
              const last = [...task.steps].reverse().find(s => s.status === 'pending')
              if (last) {
                last.status = 'done'
                last.text = '全部分析完成'
              }
              task.loading = false
              resolve()
            } else if (evtType === 'stopped') {
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
            } else if (evtType === 'error') {
              reject(new Error((payload.detail as string) || 'SSE 错误'))
            }

            if (task.id === state.currentTaskId) syncViewByTask(task)
          }
        }
        resolve()
      }).catch(reject)
    })
  } catch (e) {
    const err = e as Error
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
      if (/401|登录态|请先登录/.test(task.error)) {
        state.showLoginModal = true
        state.isLoggedIn = false
      }
    }
  } finally {
    task.loading = false
    if (state.activeController === controller) state.activeController = null
    if (task.id === state.currentTaskId) syncViewByTask(task)
  }
}

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
      <div class="task-actions">
        <button class="task-btn" @click="doValuate" :disabled="state.checkingLogin">新增并行估价</button>
        <button class="task-btn stop" @click="stopCurrentTask"
          :disabled="!state.loading || !state.currentTaskId">停止当前估价</button>
      </div>
      <div class="login-tip">
        <div class="login-tip-title">请先完成一次闲鱼登录授权</div>
        <div class="login-tip-text">在 `backend` 目录运行 `python save_xianyu_state.py`，登录成功后再回来估价。</div>
      </div>
      <div v-if="state.showLoginModal" class="login-modal-mask">
        <div class="login-modal">
          <div class="login-modal-title">需要先登录闲鱼</div>
          <div class="login-modal-text">检测到当前无登录态。点击"打开闲鱼登录页"后，在浏览器完成登录，再点"我已登录，重新检测"。</div>
          <div class="login-modal-actions">
            <button class="modal-btn primary" @click="openLoginPage" :disabled="state.openingLogin">
              {{ state.openingLogin ? '打开中...' : '打开��鱼登录页' }}
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
          <span class="task-tab-status" :class="t.loading ? 'running' : (t.error ? 'failed' : 'done')">
            {{ t.loading ? '进行中' : (t.error ? '失败' : '完成') }}
          </span>
          <span class="task-tab-remove" title="删除该任务" @click.stop="removeTask(t.id)">×</span>
        </button>
      </div>
    </section>

    <section v-if="currentTask?.steps.length" class="steps-section">
      <div class="steps-list">
        <template v-for="step in currentTask.steps" :key="step.id">
          <div class="step-item"
            :class="['step-' + (step.status === 'info' ? 'info' : step.status), step.filteredOut?.length ? 'step-expandable' : '']"
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
          <div v-for="n in (3 - (currentTask.result.llm_results?.length || 0))" :key="'pending-' + n"
            class="llm-card llm-card-pending">
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
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
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
</style>