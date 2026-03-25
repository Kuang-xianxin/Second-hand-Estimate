import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

export async function valuate(keyword) {
  const res = await http.post('/valuate', { keyword })
  return res.data
}

export async function getHistory(limit = 20) {
  const res = await http.get('/history', { params: { limit } })
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
