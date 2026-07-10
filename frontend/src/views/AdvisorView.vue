<script setup lang="ts">
import { ref, computed } from 'vue'
import { startAdvisorRun, getAdvisorRun, submitAdvisorDecision } from '@/api'
import type { AdvisorStateData } from '@/types'

const query = ref('')
const loading = ref(false)
const runId = ref('')
const state = ref<AdvisorStateData | null>(null)
const error = ref('')
const nodeLog = ref<string[]>([])

// 节点中文名映射
const nodeLabels: Record<string, string> = {
  parse_requirement: '解析需求',
  normalize_model: '归一化型号',
  route_request: '路由请求',
  retrieve_market_data: '检索市场数据',
  retrieve_knowledge: '检索领域知识',
  inspect_images: '分析图片',
  grade_evidence: '证据评分',
  rewrite_query: '重写查询',
  calculate_valuation: '计算估价',
  assess_risk: '风险评估',
  generate_report: '生成报告',
  verify_report: '校验报告',
  human_review: '人工审核',
  persist_feedback: '保存结果',
}

const recommendationText: Record<string, string> = {
  buy: '建议入手',
  caution: '谨慎购买',
  skip: '不建议购买',
  insufficient_data: '数据不足',
}

const recommendationColor: Record<string, string> = {
  buy: '#4caf50',
  caution: '#ff9800',
  skip: '#f44336',
  insufficient_data: '#9e9e9e',
}

const severityColor: Record<string, string> = {
  low: '#4caf50',
  medium: '#ff9800',
  high: '#f44336',
  critical: '#d32f2f',
}

async function startAnalysis() {
  if (!query.value.trim()) return
  loading.value = true
  error.value = ''
  state.value = null
  nodeLog.value = ['正在启动 AI 决策引擎...']

  try {
    const resp = await startAdvisorRun({ query: query.value })
    runId.value = resp.run_id
    nodeLog.value.push(`任务已创建: ${resp.run_id.slice(0, 8)}...`)

    // Poll for result (max 30s)
    const seenNodes = new Set<string>()
    let attempts = 0
    while (attempts < 30) {
      await new Promise(r => setTimeout(r, 1000))
      attempts++
      try {
        const data = await getAdvisorRun(runId.value)
        state.value = data.state
        const node = data.state.current_node
        if (node && !seenNodes.has(node)) {
          seenNodes.add(node)
          const label = nodeLabels[node.split(':')[0]] || node
          nodeLog.value.push(`✓ ${label}`)
        }

        if (data.status === 'completed' || data.status === 'failed') {
          break
        }
      } catch {
        nodeLog.value.push('...等待中')
      }
    }
  } catch (e: any) {
    error.value = e?.message || '请求失败'
  } finally {
    loading.value = false
  }
}

const report = computed(() => state.value?.report)
const valuation = computed(() => state.value?.valuation)
const risks = computed(() => state.value?.risks || [])
const marketEvidence = computed(() => state.value?.market_evidence || [])
const knowledgeEvidence = computed(() => state.value?.knowledge_evidence || [])
</script>

<template>
  <div class="advisor-page">
    <!-- 输入区 -->
    <div class="input-section">
      <h2>AI 智能选购决策</h2>
      <p class="subtitle">输入预算、用途、型号 → AI 自动分析市场 + 知识 → 给出购买建议</p>
      <div class="input-row">
        <input
          v-model="query"
          @keyup.enter="startAnalysis"
          placeholder="例如：富士F30用XD卡，预算300-500值得买吗？"
          :disabled="loading"
          class="query-input"
        />
        <button @click="startAnalysis" :disabled="loading || !query.trim()" class="analyze-btn">
          {{ loading ? '分析中...' : '开始分析' }}
        </button>
      </div>
    </div>

    <!-- 错误 -->
    <div v-if="error" class="error-box">{{ error }}</div>

    <!-- 执行时间线 -->
    <div v-if="nodeLog.length > 1" class="timeline">
      <h3>执行时间线</h3>
      <div v-for="(log, i) in nodeLog" :key="i" class="timeline-item">
        <span class="timeline-dot" :class="{ active: i === nodeLog.length - 1 }"></span>
        <span class="timeline-text">{{ log }}</span>
      </div>
    </div>

    <!-- 决策报告 -->
    <div v-if="report" class="report-section">
      <h3>决策报告</h3>

      <!-- 建议 -->
      <div class="recommendation" :style="{ borderColor: recommendationColor[report.recommendation] || '#666' }">
        <span class="rec-badge" :style="{ background: recommendationColor[report.recommendation] || '#666' }">
          {{ recommendationText[report.recommendation] || report.recommendation }}
        </span>
        <p>{{ report.summary }}</p>
      </div>

      <!-- 估价 -->
      <div v-if="valuation" class="card">
        <h4>💰 估价结果</h4>
        <div class="price-row">
          <div class="price-item">
            <span class="price-label">基准价</span>
            <span class="price-value">¥{{ valuation.base_price?.toFixed(0) }}</span>
          </div>
          <div class="price-item">
            <span class="price-label">区间</span>
            <span class="price-value">¥{{ valuation.price_min?.toFixed(0) }} ~ ¥{{ valuation.price_max?.toFixed(0) }}</span>
          </div>
          <div class="price-item">
            <span class="price-label">样本</span>
            <span class="price-value">{{ valuation.sample_count }} 条</span>
          </div>
          <div class="price-item">
            <span class="price-label">置信度</span>
            <span class="price-value">{{ valuation.confidence === 'high' ? '高' : valuation.confidence === 'medium' ? '中' : '低' }}</span>
          </div>
        </div>
      </div>

      <!-- 风险 -->
      <div v-if="risks.length > 0" class="card">
        <h4>⚠️ 风险提示</h4>
        <div v-for="r in risks" :key="r.risk_id" class="risk-item">
          <span class="risk-severity" :style="{ background: severityColor[r.severity] || '#666' }">
            {{ r.severity === 'high' ? '高' : r.severity === 'medium' ? '中' : '低' }}
          </span>
          <span class="risk-category">{{ r.category }}</span>
          <p class="risk-desc">{{ r.description?.slice(0, 200) }}</p>
        </div>
      </div>

      <!-- 证据 -->
      <div v-if="marketEvidence.length > 0 || knowledgeEvidence.length > 0" class="card">
        <h4>📊 证据来源</h4>
        <div v-if="marketEvidence.length > 0">
          <p class="ev-label">市场证据 ({{ marketEvidence.length }} 条)</p>
          <div v-for="ev in marketEvidence" :key="ev.evidence_id" class="ev-item">
            [{{ ev.evidence_id }}] {{ ev.keyword }}: {{ ev.sample_count }} 样本, ¥{{ ev.base_price?.toFixed(0) }}
          </div>
        </div>
        <div v-if="knowledgeEvidence.length > 0" style="margin-top: 12px">
          <p class="ev-label">知识证据 ({{ knowledgeEvidence.length }} 条)</p>
          <div v-for="ev in knowledgeEvidence.slice(0, 5)" :key="ev.evidence_id" class="ev-item">
            [{{ ev.evidence_id }}] {{ ev.document_type }}: {{ ev.content_snippet?.slice(0, 80) }}...
          </div>
        </div>
      </div>

      <!-- 证据摘要 -->
      <div class="evidence-summary">
        {{ report.evidence_summary }} | 置信度: {{ ((state?.confidence || 0) * 100).toFixed(0) }}%
      </div>
    </div>
  </div>
</template>

<style scoped>
.advisor-page {
  max-width: 780px;
  margin: 0 auto;
}

.input-section {
  text-align: center;
  margin-bottom: 32px;
}

.input-section h2 {
  font-size: 24px;
  color: var(--accent);
  margin: 0 0 8px;
}

.subtitle {
  color: var(--text2);
  font-size: 14px;
  margin: 0 0 20px;
}

.input-row {
  display: flex;
  gap: 10px;
}

.query-input {
  flex: 1;
  padding: 14px 18px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg2);
  color: var(--text);
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s;
}

.query-input:focus {
  border-color: var(--accent);
}

.analyze-btn {
  padding: 14px 28px;
  background: var(--accent);
  color: #0e0e10;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: opacity 0.2s;
}

.analyze-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-box {
  background: rgba(244, 67, 54, 0.1);
  border: 1px solid rgba(244, 67, 54, 0.3);
  color: #f44336;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.timeline {
  margin-bottom: 24px;
}

.timeline h3 {
  font-size: 16px;
  color: var(--text);
  margin: 0 0 12px;
}

.timeline-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
  font-size: 13px;
  color: var(--text2);
}

.timeline-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--border);
  flex-shrink: 0;
}

.timeline-dot.active {
  background: var(--accent);
  box-shadow: 0 0 6px var(--accent);
}

.report-section h3 {
  font-size: 18px;
  margin: 0 0 16px;
  color: var(--text);
}

.recommendation {
  border: 2px solid;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}

.rec-badge {
  display: inline-block;
  color: #fff;
  padding: 4px 14px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
}

.recommendation p {
  margin: 0;
  font-size: 15px;
  color: var(--text);
  line-height: 1.6;
}

.card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 20px;
  margin-bottom: 12px;
}

.card h4 {
  margin: 0 0 12px;
  font-size: 15px;
  color: var(--text);
}

.price-row {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.price-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.price-label {
  font-size: 12px;
  color: var(--text2);
}

.price-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
}

.risk-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.risk-item:last-child {
  border-bottom: none;
}

.risk-severity {
  display: inline-block;
  color: #fff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  margin-right: 8px;
}

.risk-category {
  font-size: 13px;
  color: var(--text);
  font-weight: 600;
}

.risk-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text2);
  line-height: 1.5;
}

.ev-label {
  font-size: 12px;
  color: var(--text2);
  margin-bottom: 6px;
}

.ev-item {
  font-size: 12px;
  color: var(--text2);
  padding: 3px 0;
  font-family: monospace;
}

.evidence-summary {
  text-align: center;
  font-size: 12px;
  color: var(--text2);
  margin-top: 16px;
  padding: 10px;
  background: var(--bg2);
  border-radius: 8px;
}
</style>
