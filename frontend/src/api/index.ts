import type {
  LoginState,
  ValuationResult,
  HistoryRecord,
  HistoryDetail,
  BargainAlert,
  CrawlProgress,
  SystemStats,
  CacheStatus,
  GlobalBargain,
  GlobalBargainCount,
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

// 获取后台数据库爬取进度
export async function getCrawlProgress(): Promise<CrawlProgress | null> {
  const res = await http.get<CrawlProgress | null>('/crawl/progress')
  return res.data
}

// 获取数据库概况和缓存覆盖统计
export function createCrawlProgressStream(): EventSource {
  return new EventSource(`${API_BASE}/crawl/progress/stream`)
}

export async function getSystemStats(): Promise<SystemStats> {
  const res = await http.get<SystemStats>('/stats/overview')
  return res.data
}

export async function getCacheStatus(): Promise<CacheStatus> {
  const res = await http.get<CacheStatus>('/cache/status')
  return res.data
}

export async function getGlobalBargains(params: {
  brand?: string
  xd_card?: boolean
  page?: number
  limit?: number
} = {}): Promise<GlobalBargain[]> {
  const res = await http.get<GlobalBargain[]>('/bargains/global', { params })
  return res.data
}

export async function getGlobalBargainCount(params: {
  brand?: string
  xd_card?: boolean
} = {}): Promise<GlobalBargainCount> {
  const res = await http.get<GlobalBargainCount>('/bargains/global/count', { params })
  return res.data
}
