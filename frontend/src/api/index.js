/**
 * api/index.js - API 接口模块
 * 
 * 本模块负责：
 * - 封装所有与后端通信的 HTTP 请求
 * - 统一处理请求配置（baseURL、超时时间等）
 * - 导出各种业务接口函数供组件调用
 * 
 * 使用技术：Axios（流行的 HTTP 客户端库）
 * 
 * 接口列表：
 * - getLoginState: 获取闲鱼登录状态
 * - openXianyuLogin: 打开闲鱼登录页面
 * - valuate: 执行商品估价
 * - stopValuateTask: 停止估价任务
 * - getHistory: 获取估价历史记录
 * - getHistoryDetail: 获取历史记录详情
 * - getBargains: 获取捡漏提醒
 * - markBargainRead: 标记捡漏为已读
 */

// 导入 axios 库，用于发送 HTTP 请求
import axios from 'axios'

/**
 * 创建 axios 实例
 * 
 * 为什么要创建实例而不是直接使用 axios？
 * - 可以统一配置公共参数（baseURL、timeout 等）
 * - 可以添加请求/响应拦截器
 * - 不同接口可以使用不同配置
 */
const http = axios.create({
  // baseURL: 所有请求的基础 URL 前缀
  // '/api' 会自动拼接在每个请求 URL 前面
  baseURL: '/api',
  
  // timeout: 请求超时时间（毫秒）
  // 30秒后如果服务器没有响应，则判定为超时
  timeout: 300000,
})

/**
 * getLoginState - 获取登录状态
 * 
 * 功能：检查用户是否已登录闲鱼
 * 
 * @returns {Object} { logged_in: boolean }
 * 
 * 使用示例：
 * ```javascript
 * const result = await getLoginState()
 * if (result.logged_in) {
 *   // 已登录，可以进行估价
 * }
 * ```
 */
export async function getLoginState() {
  const res = await http.get('/login-state')
  return res.data
}

/**
 * openXianyuLogin - 打开闲鱼登录页面
 * 
 * 功能：让后端打开浏览器并导航到闲鱼登录页面
 * 用户在浏览器中完成扫码登录后，数据会保存到后端
 * 
 * @returns {Object} 响应数据
 */
export async function openXianyuLogin() {
  const res = await http.post('/open-xianyu-login')
  return res.data
}

/**
 * valuate - 执行商品估价
 * 
 * 功能：根据关键词搜索闲鱼商品并进行智能估价
 * 
 * @param {string} keyword - 商品关键词，如 "iPhone 15 Pro"
 * @returns {Object} 估价结果
 * 
 * 注意：此函数在 HomeView.vue 中未直接使用
 * HomeView.vue 使用 SSE 流式接口获取实时进度
 */
export async function valuate(keyword) {
  const res = await http.post('/valuate', { keyword })
  return res.data
}

/**
 * stopValuateTask - 停止估价任务
 * 
 * 功能：取消正在进行的估价任务
 * 
 * @param {string} taskId - 任务ID
 */
export async function stopValuateTask(taskId) {
  // encodeURIComponent: 对 taskId 进行 URL 编码，防止特殊字符破坏 URL
  const res = await http.post(`/valuate/stop/${encodeURIComponent(taskId)}`)
  return res.data
}

/**
 * getHistory - 获取估价历史记录
 * 
 * 功能：获取用户之前的所有估价记录列表
 * 
 * @param {number} limit - 返回记录数量上限，默认 20
 * @returns {Array} 历史记录数组
 */
export async function getHistory(limit = 20) {
  // params: axios 自动将对象转换为 URL 查询参数
  const res = await http.get('/history', { params: { limit } })
  return res.data
}

/**
 * getHistoryDetail - 获取历史记录详情
 * 
 * 功能：获取单条历史记录的完整信息
 * 包括：大模型估价建议、价格分布、捡漏商品等
 * 
 * @param {number} id - 历史记录ID
 * @returns {Object} 记录详情
 */
export async function getHistoryDetail(id) {
  const res = await http.get(`/history/${id}`)
  return res.data
}

/**
 * getBargains - 获取捡漏提醒
 * 
 * 功能：获取系统发现的性价比高的商品
 * 这些商品的实际价格低于估价，存在捡漏机会
 * 
 * @param {boolean} unreadOnly - 是否只返回未读的提醒
 * @returns {Array} 捡漏商品列表
 */
export async function getBargains(unreadOnly = false) {
  // unreadOnly -> unread_only（转换为后端期望的命名风格）
  const res = await http.get('/bargains', { params: { unread_only: unreadOnly } })
  return res.data
}

/**
 * markBargainRead - 标记捡漏为已读
 * 
 * 功能：将某条捡漏提醒标记为已读状态
 * 前端会更新本地状态，后端也会记录
 * 
 * @param {number} id - 捡漏记录ID
 */
export async function markBargainRead(id) {
  // PATCH: 部分更新请求，与 PUT（完整更新）的区别
  const res = await http.patch(`/bargains/${id}/read`)
  return res.data
}
