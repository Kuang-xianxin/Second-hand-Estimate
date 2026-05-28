import type {
  LoginState,
  ValuationResult,
  HistoryRecord,
  HistoryDetail,
  BargainAlert,
  CachedValuation,
  CacheStatus,
  GlobalBargainItem,
  GlobalBargainCount,
  ConditionalBargainItem,
  CrawlProgress,
  SystemStats,
  AuthResponse,
  XianyuAuthState,
} from '@/types'
import axios from 'axios'

// API 基础地址：
//   开发环境 (npm run dev): Vite dev server 代理到 /api → http://localhost:8000
//   生产环境: 使用环境变量 VITE_API_BASE_URL（由部署平台注入）
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

// axios 实例，配置基础路径，超时 5 分钟（用于流式 SSE 请求）
const http = axios.create({
  baseURL: API_BASE,
  timeout: 300000,
})

const AUTH_TOKEN_KEY = 'guessr_auth_token'

export function getAuthToken(): string {
  return localStorage.getItem(AUTH_TOKEN_KEY) || ''
}

export function setAuthToken(token: string) {
  if (token) localStorage.setItem(AUTH_TOKEN_KEY, token)
  else localStorage.removeItem(AUTH_TOKEN_KEY)
}

export function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

http.interceptors.request.use((config) => {
  const token = getAuthToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export async function registerAccount(username: string, password: string): Promise<AuthResponse> {
  const res = await http.post<AuthResponse>('/auth/register', { username, password })
  setAuthToken(res.data.token)
  return res.data
}

export async function loginAccount(username: string, password: string): Promise<AuthResponse> {
  const res = await http.post<AuthResponse>('/auth/login', { username, password })
  setAuthToken(res.data.token)
  return res.data
}

export async function logoutAccount(): Promise<void> {
  try {
    await http.post('/auth/logout')
  } finally {
    setAuthToken('')
  }
}

export async function getCurrentAccount(): Promise<AuthResponse | null> {
  const token = getAuthToken()
  if (!token) return null
  const res = await http.get<{ user: AuthResponse['user']; xianyu: XianyuAuthState }>('/auth/me')
  return { token, user: res.data.user, xianyu: res.data.xianyu }
}

export async function startXianyuAuth(): Promise<XianyuAuthState> {
  const res = await http.post<XianyuAuthState>('/xianyu/auth/start', {})
  return res.data
}

export async function verifyXianyuAuth(): Promise<XianyuAuthState> {
  const res = await http.post<XianyuAuthState>('/xianyu/verify')
  return res.data
}

export async function bindCurrentXianyuState(): Promise<XianyuAuthState> {
  const res = await http.post<XianyuAuthState>('/xianyu/bind-current-state', {})
  return res.data
}

// 获取闲鱼登录状态
export async function getLoginState(): Promise<LoginState> {
  const res = await http.get<LoginState>('/login-state')
  return res.data
}

// 打开闲鱼登录页面（在浏览器中自动打开）
export async function openXianyuLogin(): Promise<void> {
  await http.post('/open-xianyu-login')
}

// 发起一次完整的估价请求（普通 POST 接口，非 SSE）
export async function valuate(keyword: string): Promise<ValuationResult> {
  const res = await http.post<ValuationResult>('/valuate', { keyword })
  return res.data
}

// 停止指定 ID 的估价任务
export async function stopValuateTask(taskId: string): Promise<void> {
  await http.post(`/valuate/stop/${encodeURIComponent(taskId)}`)
}

// 获取估价历史记录列表（按时间倒序）
// limit: 最大返回条数，默认 20
export async function getHistory(limit = 20): Promise<HistoryRecord[]> {
  const res = await http.get<HistoryRecord[]>('/history', { params: { limit } })
  return res.data
}

// 获取单条历史记录的完整详情（含大模型结果、样本价格分布、捡漏列表）
export async function getHistoryDetail(id: string): Promise<HistoryDetail> {
  const res = await http.get<HistoryDetail>(`/history/${id}`)
  return res.data
}

// 获取捡漏提醒列表
// unreadOnly: true=只看未读，false=全部
export async function getBargains(unreadOnly = false): Promise<BargainAlert[]> {
  const res = await http.get<BargainAlert[]>('/bargains', { params: { unread_only: unreadOnly } })
  return res.data
}

// 标记指定捡漏提醒为已读
export async function markBargainRead(id: string): Promise<void> {
  await http.patch(`/bargains/${id}/read`)
}

// ============================================================================
// 以下为新版缓存优先 + 捡漏广场 API
// ============================================================================

/** 缓存优先估价（L1 Redis < 1ms 或 L2 PostgreSQL < 20ms），命中直接返回。 */
export async function valuateCached(keyword: string): Promise<CachedValuation> {
  const res = await http.get<CachedValuation>('/valuate/cached', { params: { keyword } })
  return res.data
}

/** 获取缓存系统状态 */
export async function getCacheStatus(): Promise<CacheStatus> {
  const res = await http.get<CacheStatus>('/cache/status')
  return res.data
}

/** 获取全局捡漏列表（捡漏广场用） */
export async function getGlobalBargains(params?: {
  brand?: string
  xd_card?: boolean
  page?: number
  limit?: number
}): Promise<GlobalBargainItem[]> {
  const res = await http.get<GlobalBargainItem[]>('/bargains/global', { params })
  return res.data
}

/** 获取全局捡漏总数 */
export async function getGlobalBargainsCount(params?: {
  brand?: string
  xd_card?: boolean
}): Promise<GlobalBargainCount> {
  const res = await http.get<GlobalBargainCount>('/bargains/global/count', { params })
  return res.data
}

/** 按型号查询条件捡漏（有捡漏才返回，无则空） */
export async function getBargainsByKeyword(keyword: string): Promise<ConditionalBargainItem[]> {
  const res = await http.get<ConditionalBargainItem[]>('/bargains/by-keyword', { params: { keyword } })
  return res.data
}

/** 获取爬取实时进度（无进度时返回 null） */
export async function getCrawlProgress(): Promise<CrawlProgress | null> {
  const res = await http.get<CrawlProgress | null>('/crawl/progress')
  return res.data
}

/** 获取系统统计概览 */
export async function getSystemStats(): Promise<SystemStats> {
  const res = await http.get<SystemStats>('/stats/overview')
  return res.data
}
