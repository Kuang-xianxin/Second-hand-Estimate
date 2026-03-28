import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 300000,
})

export async function getLoginState() {
  const res = await http.get('/login-state')
  return res.data
}

export async function openXianyuLogin() {
  const res = await http.post('/open-xianyu-login')
  return res.data
}

export async function valuate(keyword) {
  const res = await http.post('/valuate', { keyword })
  return res.data
}

export async function getHistory(limit = 20) {
  const res = await http.get('/history', { params: { limit } })
  return res.data
}

export async function getHistoryDetail(id) {
  const res = await http.get(`/history/${id}`)
  return res.data
}

export async function getBargains(unreadOnly = false) {
  const res = await http.get('/bargains', { params: { unread_only: unreadOnly } })
  return res.data
}

export async function markBargainRead(id) {
  const res = await http.patch(`/bargains/${id}/read`)
  return res.data
}
