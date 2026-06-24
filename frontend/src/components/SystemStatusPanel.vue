<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getSystemStats } from '@/api'
import type { RecentCrawlBatch, SystemStats } from '@/types'

const stats = ref<SystemStats | null>(null)
const loading = ref(true)
const error = ref('')
const selectedBatch = ref('')
let timer: ReturnType<typeof setInterval> | null = null

const brandLabels: Record<string, string> = {
  canon: '佳能',
  sony: '索尼',
  nikon: '尼康',
  fujifilm: '富士',
  olympus: '奥林巴斯',
  panasonic: '松下',
  casio: '卡西欧',
  samsung: '三星',
  kodak: '柯达',
  other: '其他',
}

const coveragePercent = computed(() => {
  if (!stats.value?.crawl_expected_models) return 0
  return Math.min(100, Math.round(stats.value.crawl_fresh_models_48h / stats.value.crawl_expected_models * 100))
})

async function load() {
  try {
    stats.value = await getSystemStats()
    error.value = ''
  } catch (e: any) {
    if (e?.response?.status === 401) {
      error.value = ''
    } else {
      error.value = '数据库概况加载失败'
    }
  } finally {
    loading.value = false
  }
}

function formatTime(value: string | null | undefined) {
  if (!value) return '-'
  const raw = value.endsWith('Z') ? value : `${value}Z`
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return '-'
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function duration(batch: RecentCrawlBatch) {
  if (!batch.started_at) return '-'
  const start = new Date(batch.started_at).getTime()
  const end = batch.finished_at ? new Date(batch.finished_at).getTime() : Date.now()
  if (Number.isNaN(start) || Number.isNaN(end)) return '-'
  const seconds = Math.max(0, Math.round((end - start) / 1000))
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
}

function brandName(key: string) {
  return brandLabels[key] || key || '其他'
}

function toggleBatch(id: string) {
  selectedBatch.value = selectedBatch.value === id ? '' : id
}

onMounted(() => {
  load()
  timer = setInterval(load, 30000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <section class="system-panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">数据库概况</div>
        <div class="panel-sub">每30s自动刷新</div>
      </div>
      <button class="refresh-btn" type="button" :disabled="loading" @click="load">
        {{ loading ? '...' : '刷新' }}
      </button>
    </div>

    <div v-if="loading && !stats" class="panel-state">加载中...</div>
    <div v-else-if="error && !stats" class="panel-state error">{{ error }}</div>
    <div v-else-if="stats" class="panel-body">
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-value">{{ stats.cached_models.toLocaleString() }}</div>
          <div class="stat-label">已缓存型号</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.total_items.toLocaleString() }}</div>
          <div class="stat-label">商品记录</div>
        </div>
        <div class="stat-card highlight">
          <div class="stat-value">{{ stats.total_bargains.toLocaleString() }}</div>
          <div class="stat-label">捡漏机会</div>
        </div>
        <div class="stat-card">
          <div class="stat-value small">{{ formatTime(stats.latest_crawl) }}</div>
          <div class="stat-label">最近更新</div>
        </div>
      </div>

      <div class="section-block">
        <div class="section-title">48小时更新覆盖</div>
        <div class="coverage-row">
          <div class="coverage-track">
            <div class="coverage-fill" :style="{ width: `${coveragePercent}%` }"></div>
          </div>
          <span class="coverage-num">{{ stats.crawl_fresh_models_48h }} / {{ stats.crawl_expected_models }}</span>
        </div>
        <div class="coverage-note" :class="{ warning: stats.crawl_stale_models_48h > 0 }">
          超过48小时或尚未覆盖：{{ stats.crawl_stale_models_48h }} 个型号
        </div>
      </div>

      <div class="section-block">
        <div class="section-title">型号覆盖</div>
        <div class="chip-list">
          <span v-for="(count, brand) in stats.brands" :key="brand" class="brand-chip">
            {{ brandName(String(brand)) }} {{ count }}
          </span>
        </div>
      </div>

      <div v-if="Object.keys(stats.bargains_by_brand || {}).length" class="section-block">
        <div class="section-title">捡漏分布</div>
        <div class="chip-list">
          <span v-for="(count, brand) in stats.bargains_by_brand" :key="brand" class="brand-chip bargain-chip">
            {{ brandName(String(brand)) }} {{ count }}个
          </span>
        </div>
      </div>

      <div v-if="stats.recent_batches?.length" class="section-block">
        <div class="section-title">最近爬取批次</div>
        <div class="batch-list">
          <button
            v-for="batch in stats.recent_batches.slice(0, 5)"
            :key="batch.batch_id"
            class="batch-item"
            type="button"
            @click="toggleBatch(batch.batch_id)"
          >
            <div class="batch-main">
              <span class="batch-id">{{ batch.batch_id.split('_').slice(0, 2).join('_') }}</span>
              <span class="batch-status" :class="`status-${batch.status}`">
                {{ batch.status === 'completed' ? '完成' : batch.status === 'failed' ? '失败' : '进行中' }}
              </span>
            </div>
            <div class="batch-meta">
              <span>{{ batch.success_count }}/{{ batch.total_keywords }} 型号成功</span>
              <span v-if="batch.total_items">{{ batch.total_items }}条</span>
              <span v-if="batch.bargains_found">{{ batch.bargains_found }}捡漏</span>
              <span>{{ duration(batch) }}</span>
            </div>
            <div v-if="selectedBatch === batch.batch_id" class="batch-detail">
              <div>开始：{{ formatTime(batch.started_at) }}</div>
              <div v-if="batch.finished_at">结束：{{ formatTime(batch.finished_at) }}</div>
              <div v-if="batch.error_message" class="batch-error">{{ batch.error_message }}</div>
            </div>
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.system-panel {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 18px;
  margin-bottom: 24px;
}

.panel-head,
.coverage-row,
.batch-main,
.batch-meta {
  display: flex;
  align-items: center;
}

.panel-head {
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.panel-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
}

.panel-sub {
  margin-top: 3px;
  font-size: 12px;
  color: var(--text2);
}

.refresh-btn,
.batch-item {
  background: var(--bg3);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 6px;
}

.refresh-btn {
  padding: 7px 12px;
}

.refresh-btn:disabled {
  opacity: 0.6;
}

.panel-state {
  color: var(--text2);
  padding: 24px 0;
  text-align: center;
}

.panel-state.error,
.batch-error {
  color: var(--red);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.stat-card {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
}

.stat-card.highlight {
  border-color: rgba(92, 184, 122, 0.45);
}

.stat-value {
  font-family: var(--font-mono);
  font-size: 24px;
  font-weight: 700;
  color: var(--accent);
}

.stat-value.small {
  font-size: 14px;
  line-height: 1.5;
}

.stat-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text2);
}

.section-block {
  margin-top: 18px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 10px;
}

.coverage-row {
  gap: 12px;
}

.coverage-track {
  flex: 1;
  height: 10px;
  border-radius: 999px;
  background: var(--bg3);
  overflow: hidden;
}

.coverage-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--green));
}

.coverage-num {
  min-width: 88px;
  text-align: right;
  font-family: var(--font-mono);
  color: var(--text2);
  font-size: 12px;
}

.coverage-note {
  margin-top: 6px;
  color: var(--text2);
  font-size: 12px;
}

.coverage-note.warning {
  color: var(--accent2);
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.brand-chip {
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 5px 9px;
  color: var(--text2);
  background: var(--bg3);
  font-size: 12px;
}

.bargain-chip {
  color: var(--green);
  border-color: rgba(92, 184, 122, 0.35);
}

.batch-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.batch-item {
  width: 100%;
  padding: 10px 12px;
  text-align: left;
}

.batch-main {
  justify-content: space-between;
  gap: 12px;
}

.batch-id,
.batch-meta {
  font-family: var(--font-mono);
}

.batch-id {
  color: var(--text);
  font-size: 12px;
}

.batch-status {
  font-size: 12px;
  color: var(--text2);
}

.status-completed {
  color: var(--green);
}

.status-failed {
  color: var(--red);
}

.batch-meta {
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 5px;
  color: var(--text2);
  font-size: 11px;
}

.batch-detail {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
  color: var(--text2);
  font-size: 12px;
  line-height: 1.7;
}

@media (max-width: 720px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 480px) {
  .system-panel {
    padding: 14px;
  }

  .stat-grid {
    grid-template-columns: 1fr;
  }
}
</style>
