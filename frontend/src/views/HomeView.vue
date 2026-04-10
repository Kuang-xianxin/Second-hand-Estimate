<template>
  <div class="home">
    <!-- 搜索区 -->
    <section class="search-section">
      <h1 class="page-title">二手商品智能估价</h1>
      <p class="page-sub">输入商品名称，获取市场价格区间与多模型分析</p>
      <div class="search-box">
        <input
          v-model="state.keyword"
          class="search-input"
          placeholder="例如：iPhone 15 Pro 256G"
          @keydown.enter="doValuate"
          :disabled="false"
        />
        <button class="search-btn" @click="doValuate" :disabled="state.checkingLogin">
          <span v-if="!loading">开始估价</span>
          <span v-else class="loading-dots">分析中<span>.</span><span>.</span><span>.</span></span>
        </button>
      </div>
      <div class="task-actions">
        <button class="task-btn" @click="doValuate" :disabled="state.checkingLogin">新增并行估价</button>
        <button class="task-btn stop" @click="stopCurrentTask" :disabled="!state.loading || !state.currentTaskId">停止当前估价</button>
      </div>
      <div class="login-tip">
        <div class="login-tip-title">请先完成一次闲鱼登录授权</div>
        <div class="login-tip-text">
          在 `backend` 目录运行 `python save_xianyu_state.py`，登录成功后再回来估价。
        </div>
      </div>
      <div v-if="state.showLoginModal" class="login-modal-mask">
        <div class="login-modal">
          <div class="login-modal-title">需要先登录闲鱼</div>
          <div class="login-modal-text">
            检测到当前无登录态。点击“打开闲鱼登录页”后，在浏览器完成登录，再点“我已登录，重新检测”。
          </div>
          <div class="login-modal-actions">
            <button class="modal-btn primary" @click="openLoginPage" :disabled="state.openingLogin">
              {{ state.openingLogin ? '打开中...' : '打开闲鱼登录页' }}
            </button>
            <button class="modal-btn ghost" @click="confirmLoginDone" :disabled="state.checkingLogin">
              我已登录，重新检测
            </button>
            <button class="modal-btn text" @click="state.showLoginModal = false">
              稍后再说
            </button>
          </div>
        </div>
      </div>
      <p v-if="state.error" class="error-msg">{{ state.error }}</p>
      <div v-if="state.tasks.length" class="task-tabs">
        <button
          v-for="t in state.tasks"
          :key="t.id"
          class="task-tab"
          :class="{ active: t.id === state.currentTaskId }"
          @click="selectTask(t.id)"
        >
          <span class="task-tab-keyword">{{ t.keyword }}</span>
          <span class="task-tab-status" :class="t.loading ? 'running' : (t.error ? 'failed' : 'done')">
            {{ t.loading ? '进行中' : (t.error ? '失败' : '完成') }}
          </span>
          <span class="task-tab-remove" title="删除该任务" @click.stop="removeTask(t.id)">×</span>
        </button>
      </div>
    </section>

    <!-- 进度时间线 -->
    <section v-if="currentTask?.steps.length" class="steps-section">
      <div class="steps-list">
        <template v-for="step in currentTask?.steps" :key="step.id">
          <div
            class="step-item"
            :class="['step-' + (step.status === 'info' ? 'info' : step.status), step.filteredOut?.length ? 'step-expandable' : '']"
            @click="step.filteredOut?.length && (step.expanded = !step.expanded)"
          >
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

    <!-- 结果区 -->
    <section v-if="currentTask?.result" class="result-section">
      <!-- 多模型最终估价建议 -->
      <div class="final-valuation-section">
        <div class="section-title final-title">
          <span class="final-star">★</span> 最终估价建议 <span class="final-star">★</span>
        </div>
        <div class="llm-grid final-llm-grid">
          <div
            v-for="m in currentTask.result.llm_results"
            :key="m.model"
            class="llm-card final-llm-card"
            :class="{ 'has-error': m.error }"
          >
            <div class="llm-model-name">{{ m.model }}</div>
            <div v-if="m.error" class="llm-error">{{ m.error }}</div>
            <template v-else>
              <div class="llm-price">¥{{ m.suggested_price }}</div>
              <div class="llm-range">¥{{ m.price_min }} — ¥{{ m.price_max }}</div>
              <div class="llm-confidence" :class="'conf-'+m.confidence">置信度：{{ m.confidence }}</div>
              <div class="llm-reasoning">{{ m.reasoning }}</div>
            </template>
          </div>
          <!-- 等待中的模型占位 -->
          <div
            v-for="n in (3 - (currentTask.result.llm_results?.length || 0))"
            :key="'pending-'+n"
            class="llm-card llm-card-pending"
          >
            <div class="llm-model-name">分析中...</div>
            <div class="llm-pending-dots"><span>.</span><span>.</span><span>.</span></div>
          </div>
        </div>
      </div>

      <!-- 算法基准参考 -->
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

      <!-- 样本数据 -->
      <div class="section-title">样本数据（参与估价）</div>
      <div v-if="currentTask.result.samples?.length" class="sample-list">
        <a
          v-for="s in currentTask.result.samples"
          :key="s.item_id"
          :href="s.url"
          target="_blank"
          class="sample-item"
        >
          <img v-if="s.images && s.images.length" :src="s.images[0]" class="sample-thumb" loading="lazy" />
          <div v-else class="sample-thumb-placeholder">无图</div>
          <div class="sample-main">
            <div class="sample-title">{{ s.title }}</div>
            <div class="sample-meta">
              <span>成色：{{ s.condition || '未标注' }}</span>
              <span>质量分：{{ s.quality_score }}</span>
              <span>{{ s.sold ? '已售' : '在售' }}</span>
              <!-- 内存卡状态标签（仅XD卡机型确认后才显示） -->
              <span
                v-if="currentTask.xd_confirmed && getSdCardTag(s.quality_flags)"
                class="sd-card-tag"
                :class="getSdCardTagClass(s.quality_flags)"
              >{{ getSdCardTag(s.quality_flags) }}</span>
            </div>
            <div v-if="s.quality_flags && s.quality_flags.some(f => f.startsWith('图片'))" class="sample-img-flags">
              <span v-for="f in s.quality_flags.filter(f => f.startsWith('图片'))"
                    :key="f" class="img-flag-tag">{{ f }}</span>
            </div>
          </div>
          <div class="sample-price">¥{{ s.price }}</div>
        </a>
      </div>
      <div v-else class="sample-empty">暂无样本数据</div>

      <!-- 捡漏提醒 -->
      <div v-if="state.result.bargains.length" class="section-title bargain-title">
        捡漏机会 <span class="bargain-count">{{ state.result.bargains.length }}</span>
      </div>
      <div v-if="state.result.bargains.length" class="bargain-list">
        <a
          v-for="b in state.result.bargains"
          :key="b.item_id"
          :href="b.url"
          target="_blank"
          class="bargain-item"
          :class="{ 'bargain-item-xd': b.has_xd_bonus }"
        >
          <!-- XD卡醒目标签 -->
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

<script setup>
/**
 * HomeView.vue - 估价主页的逻辑代码
 * 
 * 本部分负责：
 * - 状态管理（多个估价任务并行处理）
 * - SSE 流式数据处理
 * - 登录状态检测
 */

// 从 vue 导入响应式 API
import { onMounted, reactive, computed } from 'vue'

// 定义组件名称（用于调试和 keep-alive）
defineOptions({ name: 'HomeView' })

// 导入 API 函数
import { getLoginState, openXianyuLogin, stopValuateTask } from '@/api/index.js'

/**
 * state - 应用核心状态
 * 
 * 使用 reactive() 创建响应式对象，所有属性自动具备响应式
 * 无需 .value 访问，适合复杂状态结构
 */
const state = reactive({
  /** keyword - 用户输入的搜索关键词（商品名称） */
  keyword: '',
  /** loading - 是否正在执行估价任务 */
  loading: false,
  /** error - 错误信息文本（显示给用户的错误提示） */
  error: '',
  /** result - 当前估价结果（包含样本、大模型建议价、捡漏等） */
  result: null,
  /** steps - 估价进度步骤列表（实时展示爬取、分析过程） */
  steps: [],
  /** currentTaskId - 当前选中的任务ID（用于切换不同任务视图） */
  currentTaskId: '',
  /** activeController - 当前进行中的 AbortController（用于取消 SSE 请求） */
  activeController: null,
  /** tasks - 所有估价任务列表（支持并行多个任务） */
  tasks: [],
  /** isLoggedIn - 是否已登录闲鱼 */
  isLoggedIn: false,
  /** checkingLogin - 是否正在检查登录状态（防止重复请求） */
  checkingLogin: false,
  /** showLoginModal - 是否显示登录弹窗（未登录时引导用户登录） */
  showLoginModal: false,
  /** openingLogin - 是否正在打开登录页面（防止重复点击） */
  openingLogin: false,
})

/**
 * currentTask - 当前选中任务的计算属性
 * 
 * computed() 创建计算属性，当 tasks 或 currentTaskId 变化时自动更新
 * 响应式依赖：state.tasks、state.currentTaskId
 */
const currentTask = computed(() => state.tasks.find(t => t.id === state.currentTaskId))

/**
 * buildTask - 创建新任务对象
 * 
 * 功能：
 * - 生成唯一任务ID（使用时间戳+随机数）
 * - 初始化任务状态和步骤列表
 * - 创建 partial 数据结构用于接收实时数据
 * 
 * @param {string} keywordText - 商品关键词
 * @returns {Object} 任务对象
 */
function buildTask(keywordText) {
  return reactive({
    /** id - 任务唯一标识符 */
    id: `task-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    /** keyword - 该任务的搜索关键词 */
    keyword: keywordText,
    /** loading - 任务是否仍在运行中 */
    loading: true,
    /** error - 任务错误信息（如有） */
    error: '',
    /** result - 任务最终结果（完整数据） */
    result: null,
    /** xd_confirmed - 是否已确认XD卡机型（索尼相机特有功能） */
    xd_confirmed: false,
    /** steps - 进度步骤列表（实时更新，展示爬取→筛选→分析流程） */
    steps: reactive([{ 
      text: '正在爬取闲鱼数据...', 
      status: 'pending', 
      id: Date.now() + Math.random(), 
      filteredOut: [], 
      expanded: false 
    }]),
    /** partial - 中间数据容器（边接收边组装，避免数据丢失） */
    partial: reactive({
      /** keyword - 商品关键词 */
      keyword: keywordText,
      /** sample_count - 样本数量 */
      sample_count: 0,
      /** algorithm - 算法计算结果 */
      algorithm: null,
      /** quality_summary - 质量评分汇总 */
      quality_summary: null,
      /** llm_results - 大模型分析结果列表 */
      llm_results: reactive([]),
      /** samples - 样本商品列表 */
      samples: reactive([]),
      /** bargains - 捡漏商品列表 */
      bargains: reactive([]),
    }),
  })
}

/**
 * syncViewByTask - 同步视图与任务状态
 * 
 * 当用户切换到不同任务时，更新视图显示对应任务的数据
 * 包括：加载状态、错误信息、结果数据
 * 
 * @param {Object} task - 任务对象
 */
function syncViewByTask(task) {
  if (!task) return
  /** loading - 是否显示加载状态 */
  state.loading = !!task.loading
  /** error - 显示任务的错误信息 */
  state.error = task.error || ''
  /** result - 显示任务的估价结果 */
  state.result = task.result
}

/**
 * selectTask - 切换当前选中的任务
 * 
 * 功能：
 * - 将指定任务设为当前活动任务
 * - 同步更新视图显示该任务的数据
 * 
 * @param {string} taskId - 要选中的任务ID
 */
function selectTask(taskId) {
  const task = state.tasks.find(t => t.id === taskId)
  if (!task) return
  /** currentTaskId - 更新当前任务ID */
  state.currentTaskId = taskId
  /** 同步视图显示该任务数据 */
  syncViewByTask(task)
}

/**
 * removeTask - 删除指定任务
 * 
 * 工作流程：
 * 1. 如果任务正在运行，先通知后端停止
 * 2. 中断前端的 SSE 网络请求（使用 AbortController）
 * 3. 从任务列表中移除该任务
 * 4. 如果删除的是当前任务，自动切换到下一个或清空视图
 * 
 * @param {string} taskId - 要删除的任务ID
 */
async function removeTask(taskId) {
  /** idx - 在任务列表中的索引位置 */
  const idx = state.tasks.findIndex(t => t.id === taskId)
  if (idx < 0) return
  const target = state.tasks[idx]

  /** 如果任务仍在运行，需要先停止它 */
  if (target.loading) {
    try {
      /** 通知后端停止任务 */
      await stopValuateTask(target.id)
    } catch {}
    /** 如果是当前活动任务，中断 SSE 请求 */
    if (state.currentTaskId === target.id && state.activeController) {
      state.activeController.abort()
      state.activeController = null
    }
  }

  /** 从任务列表中移除该任务 */
  state.tasks.splice(idx, 1)

  /** 如果删除的是当前任务，需要切换视图 */
  if (state.currentTaskId === taskId) {
    const nextTask = state.tasks[0]
    if (nextTask) {
      /** 切换到下一个任务 */
      state.currentTaskId = nextTask.id
      syncViewByTask(nextTask)
    } else {
      /** 没有更多任务，重置视图状态 */
      state.currentTaskId = ''
      state.loading = false
      state.error = ''
      state.result = null
      state.steps = []
    }
  }
}

/**
 * parseErrorText - 解析错误信息
 * 
 * 从各种格式的错误对象中提取友好的错误文本
 * 支持从 axios 响应错误、超链接错误对象中提取
 * 
 * @param {Object} e - 错误对象（可能是 Error/AxiosError）
 * @returns {string} 解析后的错误文本
 */
function parseErrorText(e) {
  /** detail - 尝试从 axios 响应中提取 detail 字段 */
  const detail = e?.response?.data?.detail
  /** 如果 detail 是字符串，直接返回 */
  if (typeof detail === 'string') return detail
  /** 如果 detail 是对象，尝试取 nested detail */
  if (detail?.detail) return detail.detail
  /** 否则返回默认错误信息 */
  return e?.message || '请求失败，请检查后端是否启动'
}

/**
 * stepDetailKind - 判断步骤详情类型
 * 
 * 用于区分"成色分析记录"和"普通筛除记录"
 * 成色分析是质量评估筛除，标注为不同样式
 * 
 * @param {Object} step - 步骤对象
 * @returns {string} 'condition' 或 'filter'
 */
function stepDetailKind(step) {
  const t = step?.text || ''
  /** 如果步骤文本包含'成色分析完成'，则为条件类型 */
  if (t.includes('成色分析完成')) return 'condition'
  /** 否则为普通筛除类型 */
  return 'filter'
}

/**
 * getSdCardTag - 从质量标志中提取内存卡状态标签
 * 
 * 索尼相机商品会有内存卡状态标注，如"需自备"、"含卡"等
 * 这个函数从 quality_flags 数组中提取相关标签
 * 
 * @param {Array} flags - 商品质量标志数组
 * @returns {string|null} 内存卡状态标签，或 null
 */
function getSdCardTag(flags) {
  if (!flags) return null
  /** 查找以'内存卡状态:'开头的标志 */
  const f = flags.find(f => f.startsWith('内存卡状态:'))
  /** 去掉前缀后返回 */
  return f ? f.replace('内存卡状态:', '') : null
}

/**
 * getSdCardTagClass - 获取内存卡标签的CSS类名
 * 
 * 根据内存卡状态返回不同的样式类，用于区分：
 * - 需自备：红色警示风格（用户需额外购买）
 * - 捆绑含卡：绿色信任风格（包含卡，划算）
 * - 有加购项：橙色提示风格
 * - 未知状态：灰色中性风格
 * 
 * @param {Array} flags - 商品质量标志数组
 * @returns {string} CSS 类名
 */
function getSdCardTagClass(flags) {
  const text = getSdCardTag(flags) || ''
  /** 需自备 → 红色警示风格 */
  if (text.includes('需自备')) return 'sd-tag-self'
  /** 捆绑含卡 → 绿色信任风格 */
  if (text.includes('捆绑') || text.includes('含卡')) return 'sd-tag-bundle'
  /** 有加购项 → 橙色提示风格 */
  if (text.includes('加购')) return 'sd-tag-addon'
  /** 未知状态 → 灰色中性风格 */
  return 'sd-tag-unknown'
}

/**
 * checkLoginState - 检查闲鱼登录状态
 * 
 * 功能：
 * - 调用后端 API 获取当前登录状态
 * - 如果未登录则显示登录引导弹窗
 * 
 * 工作流程：
 * 1. 设置 checkingLogin=true，防止重复请求
 * 2. 调用 getLoginState API
 * 3. 根据响应更新 isLoggedIn 状态
 * 4. 如果未登录，显示登录弹窗引导用户
 * 5. 请求完成后重置 checkingLogin=false
 */
async function checkLoginState() {
  state.checkingLogin = true
  try {
    const resp = await getLoginState()
    /** isLoggedIn - 是否已登录闲鱼 */
    state.isLoggedIn = !!resp?.logged_in
    /** 如果未登录，显示登录引导弹窗 */
    if (!state.isLoggedIn) state.showLoginModal = true
  } catch {
    state.isLoggedIn = false
  } finally {
    state.checkingLogin = false
  }
}

/**
 * openLoginPage - 打开闲鱼登录页面
 * 
 * 功能：
 * - 调用后端 API 打开系统默认浏览器
 * - 导航到闲鱼登录页面进行扫码登录
 * 
 * 工作流程：
 * 1. 设置 openingLogin=true，显示'打开中...'状态
 * 2. 调用 openXianyuLogin API
 * 3. 如果发生错误，更新 error 状态显示给用户
 * 4. 请求完成后重置 openingLogin=false
 */
async function openLoginPage() {
  state.openingLogin = true
  try {
    /** 打开浏览器并导航到闲鱼登录页 */
    await openXianyuLogin()
  } catch (e) {
    /** 解析并显示错误信息 */
    state.error = parseErrorText(e)
  } finally {
    state.openingLogin = false
  }
}

/**
 * confirmLoginDone - 确认登录完成
 * 
 * 用户在外部（浏览器）完成闲鱼登录后调用
 * 重新检测登录状态，如果已登录则关闭登录弹窗
 */
async function confirmLoginDone() {
  /** 重新检查登录状态 */
  await checkLoginState()
  /** 如果已登录，关闭登录弹窗 */
  if (state.isLoggedIn) state.showLoginModal = false
}

/**
 * stopCurrentTask - 停止当前正在运行的估价任务
 * 
 * 功能：
 * - 通知后端停止当前任务
 * - 中断前端的 SSE 网络请求
 * - 更新任务状态为'已停止'
 * 
 * 工作流程：
 * 1. 获取当前任务
 * 2. 通知后端停止任务
 * 3. 中断 SSE 请求
 * 4. 更新任务状态和添加停止步骤
 */
async function stopCurrentTask() {
  /** 没有当前任务，直接返回 */
  if (!state.currentTaskId) return
  const task = state.tasks.find(t => t.id === state.currentTaskId)
  if (!task || !task.loading) return

  try {
    /** 通知后端停止指定任务 */
    await stopValuateTask(task.id)
  } catch {}

  /** 如果有活跃的 SSE 请求，中断它 */
  if (state.activeController) {
    state.activeController.abort()
    state.activeController = null
  }

  /** 更新任务状态为已停止 */
  task.loading = false
  task.error = '已手动停止'
  task.steps.push({ 
    text: '已停止当前估价任务', 
    status: 'error', 
    id: Date.now() + Math.random(), 
    filteredOut: [], 
    expanded: false 
  })
  /** 同步视图 */
  syncViewByTask(task)
}

/**
 * doValuate - 执行商品估价（核心函数）
 * 
 * 这是最重要的函数，使用 SSE（Server-Sent Events）实现：
 * - 实时获取估价进度
 * - 分步展示爬取、筛选、分析过程
 * - 支持多模型并行分析
 * 
 * SSE 通信流程：
 * 1. 发送 POST 请求到 /api/valuate/stream
 * 2. 后端通过 SSE 推送各种事件
 * 3. 前端解析事件并实时更新 UI
 */
async function doValuate() {
  if (!state.keyword.trim()) return
  if (state.checkingLogin) return
  if (!state.isLoggedIn) {
    state.showLoginModal = true
    return
  }

  // 创建新任务
  const task = buildTask(state.keyword.trim())
  // 将新任务添加到列表头部
  state.tasks.unshift(task)
  // 选中新任务
  selectTask(task.id)
  // 点击“开始估价”后清空输入框，方便连续输入下一次
  state.keyword = ''

  // 创建 AbortController 用于取消请求
  const controller = new AbortController()
  // 保存当前活跃的控制器
  state.activeController = controller

  try {
    await new Promise((resolve, reject) => {
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
        const reader = resp.body.getReader()
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
            let payload
            try { payload = JSON.parse(dataMatch[1]) } catch { continue }

            // ========== 处理不同类型的 SSE 事件 ==========

            // start: 任务开始，获取正式任务ID
            if (evtType === 'start') {
              task.id = payload.task_id || task.id
            // step: 进度步骤更新
            } else if (evtType === 'step') {
              if (payload.status === 'pending') {
                task.steps.push({ text: payload.text, status: 'pending', id: Date.now() + Math.random(), filteredOut: [], expanded: false })
              } else {
                const last = [...task.steps].reverse().find(s => s.status === 'pending')
                if (last) {
                  last.status = 'done'
                  if (payload.text) last.text = payload.text
                  if (payload.filtered_out?.length) last.filteredOut = payload.filtered_out
                }
              }
            // xd_confirmed: 检测到XD卡机型（索尼相机特有）
            } else if (evtType === 'xd_confirmed') {
              task.xd_confirmed = true
              task.steps.push({
                text: '【XD卡提示】' + (payload.text || '').split('\n')[0],
                status: 'info',
                id: Date.now() + Math.random(),
                filteredOut: [],
                expanded: false,
                is_xd_hint: true,
                xd_hint_full: payload.text || '',
              })
            // base: 基础数据返回（爬取完成）
            } else if (evtType === 'base') {
              const last = [...task.steps].reverse().find(s => s.status === 'pending')
              if (last) {
                last.status = 'done'
                last.text = `爬取完成，获得 ${payload.sample_count} 条有效样本`
              }
              task.partial.keyword = payload.keyword
              task.partial.sample_count = payload.sample_count
              task.partial.xd_card_model = payload.xd_card_model || false
              task.partial.xd_card_bundle_count = payload.xd_card_bundle_count || 0
              task.partial.algorithm = payload.algorithm
              task.partial.quality_summary = payload.quality_summary
              task.partial.samples = payload.samples
              task.partial.bargains = payload.bargains
              task.result = { ...task.partial }
              task.steps.push({ text: '等待大模型分析结果...', status: 'pending', id: Date.now() + Math.random(), filteredOut: [], expanded: false })
            // llm: 大模型分析结果
            } else if (evtType === 'llm') {
              const last = [...task.steps].reverse().find(s => s.status === 'pending')
              if (last) last.status = 'done'
              const modelShort = payload.model.replace(/^ep-[^-]+-\d+-/, '').slice(0, 24)
              task.steps.push({
                text: payload.error ? `${modelShort}：分析失败（${payload.error}）` : `${modelShort} 估价完成：¥${payload.suggested_price}`,
                status: payload.error ? 'error' : 'done',
                id: Date.now() + Math.random(),
                filteredOut: [],
                expanded: false,
              })
              task.partial.llm_results = [...task.partial.llm_results, payload]
              task.result = { ...task.partial }
              if (task.partial.llm_results.length < 3) {
                task.steps.push({ text: '等待剩余模型结果...', status: 'pending', id: Date.now() + Math.random(), filteredOut: [], expanded: false })
              }
            // done: 全部完成
            } else if (evtType === 'done') {
              const last = [...task.steps].reverse().find(s => s.status === 'pending')
              if (last) {
                last.status = 'done'
                last.text = '全部分析完成'
              }
              task.loading = false
              resolve()
            // stopped: 任务被停止
            } else if (evtType === 'stopped') {
              task.loading = false
              task.error = payload.detail || '已停止'
              task.steps.push({ text: '任务已停止', status: 'error', id: Date.now() + Math.random(), filteredOut: [], expanded: false })
              resolve()
            // error: 发生错误
            } else if (evtType === 'error') {
              reject(new Error(payload.detail || 'SSE 错误'))
            }

            if (task.id === state.currentTaskId) syncViewByTask(task)
          }
        }
        resolve()
      }).catch(reject)
    })
  } catch (e) {
    if (e?.name === 'AbortError') {
      task.error = '已手动停止'
    } else {
      task.error = e?.message || '请求失败，请检查后端是否启动'
      task.steps.push({ text: task.error, status: 'error', id: Date.now() + Math.random(), filteredOut: [], expanded: false })
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

/**
 * onMounted - 组件挂载后自动执行
 * 
 * 组件首次渲染到 DOM 后调用
 * 这里用于检查登录状态
 */
onMounted(() => {
  checkLoginState()
})
</script>

<style scoped>
.home { max-width: 900px; margin: 0 auto; }

.search-section { margin-bottom: 48px; }

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
}

.task-btn.stop {
  border-color: rgba(224,92,92,0.4);
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
.search-input:focus { border-color: var(--accent); }
.search-input:disabled { opacity: 0.5; }

.search-btn {
  background: var(--accent);
  color: #0e0e10;
  font-weight: 700;
  font-size: 15px;
  padding: 0 32px;
  border-radius: var(--radius);
  transition: opacity 0.2s, transform 0.1s;
  white-space: nowrap;
}
.search-btn:hover:not(:disabled) { opacity: 0.85; transform: translateY(-1px); }
.search-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.loading-dots span {
  animation: blink 1.2s infinite;
}
.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%,80%,100% { opacity:0 } 40% { opacity:1 } }

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
}

.modal-btn.primary {
  background: var(--accent);
  color: #18140a;
}

.modal-btn.ghost {
  background: rgba(232, 197, 71, 0.08);
  color: var(--accent);
  border: 1px solid rgba(232, 197, 71, 0.35);
}

.modal-btn.text {
  background: transparent;
  color: var(--text2);
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
  background: rgba(224,92,92,0.1);
  border-radius: var(--radius);
  border: 1px solid rgba(224,92,92,0.2);
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

.task-tab-status.running { color: var(--accent); }
.task-tab-status.done { color: var(--green); }
.task-tab-status.failed { color: var(--red); }

/* 结果区 */
.card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px 28px;
  margin-bottom: 28px;
}

.card-label {
  font-size: 12px;
  color: var(--text2);
  letter-spacing: 2px;
  text-transform: uppercase;
  margin-bottom: 10px;
}

.base-price {
  font-size: 48px;
  font-weight: 700;
  color: var(--accent);
  font-family: var(--font-mono);
  line-height: 1;
  margin-bottom: 10px;
}

.price-range {
  font-size: 14px;
  color: var(--text2);
  margin-bottom: 6px;
}

.range-val { color: var(--text); font-family: var(--font-mono); }

.sample-info {
  font-size: 12px;
  color: var(--text2);
  font-family: var(--font-mono);
}

.outlier-info {
  font-size: 12px;
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  font-family: var(--font-mono);
}
.outlier-info.low { background: rgba(92,184,122,0.08); color: var(--green); }
.outlier-info.high { background: rgba(224,92,92,0.08); color: var(--red); }

.quality-card {
  margin-top: -10px;
}

.quality-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
}

.quality-score {
  font-size: 30px;
  font-weight: 700;
  color: var(--green);
  font-family: var(--font-mono);
}

.quality-meta {
  font-size: 12px;
  color: var(--text2);
}

.quality-stacked-bar {
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--bg3);
  border: 1px solid var(--border);
  display: flex;
}

.seg {
  height: 100%;
  display: inline-block;
}

.seg.high { background: linear-gradient(90deg, #2da66f, #51c087); }
.seg.mid { background: linear-gradient(90deg, #caa83d, #e0c35e); }
.seg.low { background: linear-gradient(90deg, #b74a4a, #d66767); }

.quality-legend {
  margin-top: 10px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
  font-family: var(--font-mono);
}

.lg {
  padding: 2px 8px;
  border-radius: 999px;
}

.lg.high { background: rgba(92,184,122,0.15); color: var(--green); }
.lg.mid { background: rgba(232,197,71,0.15); color: var(--accent); }
.lg.low { background: rgba(224,92,92,0.15); color: var(--red); }

.section-title {
  font-size: 13px;
  letter-spacing: 3px;
  color: var(--text2);
  text-transform: uppercase;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

/* 最终估价建议区域 */
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

/* 算法基准参考（精简） */
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

.algo-ref-icon { font-size: 14px; }

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

/* 质量分精简卡片 */
.quality-mini-card {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 8px 16px;
  font-size: 12px;
  margin-bottom: 24px;
}

.quality-mini-label {
  color: var(--text2);
}

.quality-mini-score {
  font-weight: 700;
  color: var(--green);
  font-family: var(--font-mono);
  font-size: 14px;
}

.quality-mini-bar {
  color: var(--text2);
  font-family: var(--font-mono);
  font-size: 11px;
}

.llm-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

@media (max-width: 700px) {
  .llm-grid { grid-template-columns: 1fr; }
}

.llm-card {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  transition: border-color 0.2s;
}
.llm-card:hover { border-color: var(--accent); }
.llm-card.has-error { border-color: rgba(224,92,92,0.3); }

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
.conf-高 { background: rgba(92,184,122,0.15); color: var(--green); }
.conf-中 { background: rgba(232,197,71,0.15); color: var(--accent); }
.conf-低 { background: rgba(224,92,92,0.15); color: var(--red); }

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
}
.sample-item:hover {
  border-color: var(--accent);
  background: rgba(232,197,71,0.05);
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
  background: rgba(255,180,0,0.12);
  color: #c8960a;
  border: 1px solid rgba(255,180,0,0.25);
}

/* 内存卡状态标签 */
.sd-card-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
}
/* 需自备 → 红色警示风格 */
.sd-tag-self {
  background: rgba(224,92,92,0.15);
  color: #e05c5c;
  border: 1px solid rgba(224,92,92,0.35);
}
/* 捆绑含卡 → 绿色信任风格 */
.sd-tag-bundle {
  background: rgba(92,184,122,0.15);
  color: #5cc87a;
  border: 1px solid rgba(92,184,122,0.35);
}
/* 有加购项 → 橙色提示风格 */
.sd-tag-addon {
  background: rgba(255,136,0,0.15);
  color: #ff8800;
  border: 1px solid rgba(255,136,0,0.35);
}
/* 未知 → 灰色中性风格 */
.sd-tag-unknown {
  background: rgba(120,130,160,0.15);
  color: #7882a0;
  border: 1px solid rgba(120,130,160,0.3);
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
  0%, 100% { opacity: 0.6; }
  50% { opacity: 0.3; }
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
.llm-pending-dots span:nth-child(2) { animation-delay: 0.2s; }
.llm-pending-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes blink {
  0%, 80%, 100% { opacity: 0; }
  40% { opacity: 1; }
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
.step-expandable:hover { background: var(--bg3); }

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
  background: rgba(224,92,92,0.12);
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

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.step-done { color: var(--green); }
.step-pending { color: var(--text2); }
.step-error { color: var(--red); }

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
  to { transform: rotate(360deg); }
}

.step-text { flex: 1; }

.bargain-title {
  color: var(--red);
  border-color: rgba(224,92,92,0.3);
}

.bargain-count {
  background: var(--red);
  color: #fff;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 10px;
  font-family: var(--font-mono);
}

.bargain-list { display: flex; flex-direction: column; gap: 10px; }

.bargain-item {
  background: var(--bg2);
  border: 1px solid rgba(224,92,92,0.25);
  border-radius: var(--radius);
  padding: 14px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  transition: border-color 0.2s, background 0.2s;
}
.bargain-item:hover {
  border-color: var(--red);
  background: rgba(224,92,92,0.06);
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

.bargain-actual { color: var(--red); font-weight: 700; font-size: 16px; }
.bargain-est { color: var(--text2); }
.bargain-profit {
  background: rgba(92,184,122,0.15);
  color: var(--green);
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}
.bargain-profit.profit-xd {
  background: rgba(255,136,0,0.18);
  color: #ff8800;
}
.bargain-item.bargain-item-xd {
  border-color: rgba(255,136,0,0.45);
  background: rgba(255,136,0,0.04);
}
.bargain-item.bargain-item-xd:hover {
  border-color: #ff8800;
  background: rgba(255,136,0,0.10);
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
  box-shadow: 0 1px 4px rgba(255,100,0,0.3);
}
.xd-card-value {
  background: rgba(255,255,255,0.25);
  border-radius: 3px;
  padding: 0 5px;
  font-weight: 600;
}

.step-item.info {
  background: rgba(255,136,0,0.05);
  border-color: rgba(255,136,0,0.25);
}
.step-item.info .step-icon {
  background: rgba(255,136,0,0.15);
  color: #ff8800;
  border-color: rgba(255,136,0,0.3);
}
.step-item.info .step-dot {
  background: #ff8800;
}
.step-item.info .step-text {
  color: #cc6600;
}

.step-item.info .step-dot {
  background: #ff8800;
  box-shadow: 0 0 0 3px rgba(255,136,0,0.2);
}
</style>
