import axios from 'axios'
import type {
  LoginState,
  ValuationResult,
  HistoryRecord,
  HistoryDetail,
  BargainAlert,
} from '@/types'

const http = axios.create({
  baseURL: '/api',
  timeout: 300000,
})

export async function getLoginState(): Promise<LoginState> {
  const res = await http.get<LoginState>('/login-state')
  return res.data
}

export async function openXianyuLogin(): Promise<void> {
  await http.post('/open-xianyu-login')
}

export async function valuate(keyword: string): Promise<ValuationResult> {
  const res = await http.post<ValuationResult>('/valuate', { keyword })
  return res.data
}

export async function stopValuateTask(taskId: string): Promise<void> {
  await http.post(`/valuate/stop/${encodeURIComponent(taskId)}`)
}

export async function getHistory(limit = 20): Promise<HistoryRecord[]> {
  const res = await http.get<HistoryRecord[]>('/history', { params: { limit } })
  return res.data
}

export async function getHistoryDetail(id: string): Promise<HistoryDetail> {
  const res = await http.get<HistoryDetail>(`/history/${id}`)
  return res.data
}

export async function getBargains(unreadOnly = false): Promise<BargainAlert[]> {
  const res = await http.get<BargainAlert[]>('/bargains', { params: { unread_only: unreadOnly } })
  return res.data
}

export async function markBargainRead(id: string): Promise<void> {
  await http.patch(`/bargains/${id}/read`)
}