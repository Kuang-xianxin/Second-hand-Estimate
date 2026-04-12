export interface LoginState {
  logged_in: boolean
  user_info?: {
    nick: string
    avatar?: string
  }
}

export interface AlgorithmResult {
  base_price: number
  price_min: number
  price_max: number
  outlier_low?: number
  outlier_high?: number
}

export interface QualitySummary {
  score: number
  distribution: {
    high: number
    mid: number
    low: number
  }
  total: number
}

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

export interface LlmResult {
  model: string
  suggested_price: number
  price_min: number
  price_max: number
  confidence: '高' | '中' | '低'
  reasoning: string
  error?: string
}

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

export interface ValuationResult {
  keyword: string
  sample_count: number
  algorithm: AlgorithmResult | null
  quality_summary: QualitySummary | null
  samples: SampleItem[]
  llm_results: LlmResult[]
  bargains: BargainItem[]
  xd_card_model?: boolean
  xd_card_bundle_count?: number
}

export interface HistoryRecord {
  id: string
  keyword: string
  created_at: string
  base_price: number
  price_min: number
  price_max: number
  sample_count: number
}

export interface HistoryDetail extends HistoryRecord {
  llm_results: LlmResult[]
  raw_prices: number[]
  bargains: BargainItem[]
}

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

export type StepStatus = 'pending' | 'done' | 'error' | 'info'

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

export interface ValuationTask {
  id: string
  keyword: string
  loading: boolean
  error: string
  result: ValuationResult | null
  xd_confirmed: boolean
  steps: ValuationStep[]
  partial: {
    keyword: string
    sample_count: number
    algorithm: AlgorithmResult | null
    quality_summary: QualitySummary | null
    llm_results: LlmResult[]
    samples: SampleItem[]
    bargains: BargainItem[]
    xd_card_model?: boolean
    xd_card_bundle_count?: number
  }
}