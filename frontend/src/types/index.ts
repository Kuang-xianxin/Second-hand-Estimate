// ============================================================================
// SSE 事件类型（与后端 backend/app/api/valuate.py 保持一致）
// ============================================================================

/** SSE 事件类型枚举 */
export type SSEEventType =
  | 'start'         // 服务端返回任务真实 ID
  | 'step'          // 爬取/筛选过程中的进度步骤
  | 'xd_confirmed'   // 检测到 XD 卡相机
  | 'base'          // 爬取完成，推送基准价和样本数据
  | 'llm'           // 单个大模型估价结果
  | 'done'          // 所有流程完成
  | 'stopped'       // 任务被手动停止
  | 'error'         // 流程出错

// ============================================================================
// 以下为原有类型定义
// ============================================================================

/** SSE quality_summary 扁平结构（与后端直接对应） */
export interface SSEQualitySummary {
  avg_score: number
  high_quality_count: number
  mid_quality_count: number
  low_quality_count: number
}

// 闲鱼登录状态
// logged_in: 是否已登录闲鱼
// user_info: 登录用户信息（可选）
//   - nick: 用户昵称
//   - avatar: 用户头像（可选）
export interface LoginState {
  logged_in: boolean
  user_info?: {
    nick: string
    avatar?: string
  }
}

// 算法估价结果
// base_price: 计算得出的基准价格
// price_min / price_max: 合理价格区间
// outlier_low / outlier_high: 异常低价/高价商品的平均价格（用于过滤参考）
export interface AlgorithmResult {
  base_price: number
  price_min: number
  price_max: number
  outlier_low?: number
  outlier_high?: number
}

// 商品成色质量汇总
// score: 综合质量评分
// distribution: 质量分布（高/中/低成色商品数量）
// total: 参与统计的样本总数
export interface QualitySummary {
  score: number
  distribution: {
    high: number
    mid: number
    low: number
  }
  total: number
}

// 单条商品样本数据
// item_id: 闲鱼商品 ID（唯一标识）
// title: 商品标题
// price: 售价
// url: 商品链接
// condition: 成色（如"全新"、"99新"）
// quality_score: 质量评分
// quality_flags: 质量标记数组（如"图片模糊"、"内存卡状态: 捆绑"）
// images: 商品图片 URL 列表
// sold: 是否已售出
export interface SampleItem {
  item_id: string
  title: string
  price: number
  url: string
  condition?: string
  quality_score?: number
  quality_flags?: string[]
  images?: string[]
  sold?: boolean
}

// 大模型估价结果
// model: 模型名称（如"qwen-max"）
// suggested_price: 建议售价
// price_min / price_max: 价格区间
// confidence: 置信度（高/中/低）
// reasoning: 估价理由（文本分析）
// error: 若模型调用失败，记录错误信息
export interface LlmResult {
  model: string
  suggested_price: number
  price_min: number
  price_max: number
  confidence: '高' | '中' | '低'
  reasoning: string
  error?: string
}

// 捡漏商品项
// item_id / title / price / url: 商品基本信息
// estimated_price: 系统估算的合理价格
// profit_estimate: 预计利润（estimated_price - price）
// has_xd_bonus: 是否包含 XD 卡附加价值
// xd_card_size: XD 卡容量（如"512MB"）
// xd_card_value: XD 卡估算价值
export interface BargainItem {
  item_id: string
  title: string
  price: number
  url: string
  estimated_price: number
  profit_estimate: number
  has_xd_bonus?: boolean
  xd_card_size?: string
  xd_card_value?: number
}

// 完整估价结果（合并算法结果 + 样本 + 捡漏）
// keyword: 搜索关键词
// sample_count: 有效样本数量
// algorithm: 算法估价结果（可能为空）
// quality_summary: 质量汇总（可能为空）
// samples: 参与估价的有效样本列表
// llm_results: 多个大模型的估价结果
// bargains: 捡漏机会列表
// xd_card_model: 是否为 XD 卡相机型号
// xd_card_bundle_count: XD 卡捆绑销售数量
export interface ValuationResult {
  keyword: string 
  sample_count: number
  algorithm: AlgorithmResult | null
  quality_summary: SSEQualitySummary | null
  samples: SampleItem[]
  llm_results: LlmResult[]
  bargains: BargainItem[]
  xd_card_model?: boolean
  xd_card_bundle_count?: number
}

// 单条估价历史记录（列表展示用）
// id: 记录唯一 ID
// keyword: 搜索关键词
// created_at: 创建时间（ISO 格式）
// base_price: 基准价格
// price_min / price_max: 价格区间
// sample_count: 样本数量
export interface HistoryRecord {
  id: string
  keyword: string
  created_at: string
  base_price: number
  price_min: number
  price_max: number
  sample_count: number
}

// 估价历史详情（展开查看时使用），继承 HistoryRecord 并扩展
// llm_results: 大模型估价结果列表
// raw_prices: 所有样本的原始价格列表（用于展示分布）
// bargains: 捡漏机会列表
export interface HistoryDetail extends HistoryRecord {
  llm_results: LlmResult[]
  raw_prices: number[]
  bargains: BargainItem[]
}

// 捡漏提醒消息（推送/通知用）
// id: 提醒唯一 ID
// item_id / title / price / url: 商品基本信息
// estimated_price: 估算合理价格
// profit_estimate: 预计利润
// is_read: 是否已读
// created_at: 创建时间
// has_xd_bonus / xd_card_size / xd_card_value: XD 卡附加信息
export interface BargainAlert {
  id: string
  item_id: string
  title: string
  price: number
  url: string
  estimated_price: number
  profit_estimate: number
  is_read: boolean
  created_at: string
  has_xd_bonus?: boolean
  xd_card_size?: string
  xd_card_value?: number
}

// 步骤状态枚举
export type StepStatus = 'pending' | 'done' | 'error' | 'info'

// 估价流程中的单个步骤
// id: 步骤唯一 ID
// text: 步骤描述文本
// status: 状态（pending=进行中, done=已完成, error=失败, info=提示）
// filteredOut: 被筛除的商品列表（含原因）
// expanded: 是否展开详情
// is_xd_hint: 是否为 XD 卡专项提示
// xd_hint_full: XD 卡提示的完整内容
export interface ValuationStep {
  id: string | number
  text: string
  status: StepStatus
  filteredOut: Array<{
    reason: string
    title: string
    price: number
  }>
  expanded: boolean
  is_xd_hint?: boolean
  xd_hint_full?: string
}

// 估价任务（支持多任务并行）
// id: 任务唯一 ID
// keyword: 搜索关键词
// models: 本次估价使用的模型列表
// loading: 是否正在处理
// error: 错误信息（若有）
// result: 完整估价结果（完成后填充）
// xd_confirmed: 是否已确认 XD 卡检测结果
// steps: 步骤列表（流程展示）
// partial: 流式过程中逐步积累的中间结果（实时展示用）
export interface ValuationTask {
  id: string
  keyword: string
  models: string[]
  loading: boolean
  error: string
  result: ValuationResult | null
  xd_confirmed: boolean
  steps: ValuationStep[]
  controller: AbortController | null
  partial: {
    keyword: string
    sample_count: number
    algorithm: AlgorithmResult | null
    quality_summary: SSEQualitySummary | null
    llm_results: LlmResult[]
    samples: SampleItem[]
    bargains: BargainItem[]
    xd_card_model?: boolean
    xd_card_bundle_count?: number
  }
}