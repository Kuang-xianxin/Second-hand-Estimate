import axios from 'axios'
import type {
  LoginState,
  ValuationResult,
  HistoryRecord,
  HistoryDetail,
  BargainAlert,
} from '@/types'

// axios 实例，配置基础路径为 /api，超时 5 分钟（用于流式 SSE 请求）
const http = axios.create({
  baseURL: '/api',
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