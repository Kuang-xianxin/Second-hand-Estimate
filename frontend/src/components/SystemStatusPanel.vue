<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { getSystemStats } from '@/api'
import type { SystemStats } from '@/types'

const stats = ref<SystemStats | null>(null)
const loading = ref(true)
const error = ref('')
const activeBrand = ref<string | null>(null)
const expandedBatch = ref<string | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

async function load() {
  try {
    stats.value = await getSystemStats()
    error.value = ''
  } catch {
    error.value = '加载失败'
  } finally {
    loading.value = false
  }
}

function startPolling(intervalMs = 30000) {
  load()
  pollTimer = setInterval(load, intervalMs)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  try {
    // 后端存的是 CST(UTC+8) 但无时区标记，加 8 小时偏移
    const d = new Date(iso + (iso.endsWith('Z') || iso.includes('+') ? '' : '+08:00'))
    return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0') + ' ' + String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0')
  } catch { return iso }
}

function formatDuration(start: string | null | undefined, end: string | null | undefined): string {
  if (!start) return '-'
  try {
    const s = new Date(start).getTime()
    const e = end ? new Date(end).getTime() : Date.now()
    const diff = Math.round((e - s) / 1000)
    if (diff < 60) return `${diff}s`
    if (diff < 3600) return `${Math.round(diff / 60)}m`
    return `${Math.round(diff / 60 / 60)}h`
  } catch { return '-' }
}

const BRAND_COLORS: Record<string, string> = {
  canon: '#E74C3C',
  sony: '#3498DB',
  nikon: '#F39C12',
  fujifilm: '#E67E22',
  olympus: '#9B59B6',
  panasonic: '#1ABC9C',
  casio: '#C0392B',
  samsung: '#607D8B',
  pentax: '#795548',
  kodak: '#FF9800',
}

const BRAND_LABELS: Record<string, string> = {
  canon: '佳能', sony: '索尼', nikon: '尼康',
  fujifilm: '富士', olympus: '奥林巴斯', panasonic: '松下',
  casio: '卡西欧', samsung: '三星', pentax: '宾得', kodak: '柯达',
}

function brandLabel(key: string): string {
  return BRAND_LABELS[key] || key || '其他'
}

function brandColor(key: string): string {
  return BRAND_COLORS[key] || '#888'
}

const t0Percent = computed(() => Math.min(100, Math.round((stats.value?.cached_models || 0) / 200 * 100)))
const t1Percent = computed(() => Math.min(100, Math.round(((stats.value?.cached_models || 0) - 52) / 1012 * 100)))
const t2Percent = computed(() => 0)
const t0Count = computed(() => stats.value?.cached_models || 0)
const t1Count = computed(() => Math.max(0, (stats.value?.cached_models || 0) - 52))
const t2Count = computed(() => 0)

onMounted(() => startPolling(30000))
onUnmounted(stopPolling)

// 暴露刷新方法给父组件
defineExpose({ refresh: load })
</script>

<template>
  <div class="sys-panel">
    <div class="panel-header">
      <span class="panel-icon">📊</span>
      <span class="panel-title">数据库概况</span>
      <span class="panel-auto">每30s自动刷新</span>
      <button class="refresh-btn" @click="load" :disabled="loading">
        {{ loading ? '...' : '↻' }}
      </button>
    </div>

    <div v-if="loading && !stats" class="panel-loading">
      <div class="loading-spinner-sm"></div>
    </div>

    <div v-else-if="error && !stats" class="panel-error">{{ error }}</div>

    <div v-else-if="stats" class="panel-body">
      <!-- 核心数字：2行 -->
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-value">{{ stats.cached_models.toLocaleString() }}</div>
          <div class="stat-label">已缓存型号</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.price_history_count.toLocaleString() }}</div>
          <div class="stat-label">商品记录</div>
        </div>
        <div class="stat-card highlight">
          <div class="stat-value">{{ stats.total_bargains.toLocaleString() }}</div>
          <div class="stat-label">捡漏机会</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ formatTime(stats.latest_crawl) }}</div>
          <div class="stat-label">最近更新</div>
        </div>
      </div>

      <!-- 分层覆盖进度 -->
      <div class="section">
        <div class="section-title">📊 数据覆盖</div>
        <div class="tier-bars">
          <div class="tier-row">
            <span class="tier-label t0">T0 热门</span>
            <div class="tier-bar-track"><div class="tier-bar-fill t0-fill" :style="{ width: t0Percent + '%' }"></div></div>
            <span class="tier-num">{{ t0Count }} / 200</span>
          </div>
          <div class="tier-row">
            <span class="tier-label t1">T1 普通</span>
            <div class="tier-bar-track"><div class="tier-bar-fill t1-fill" :style="{ width: t1Percent + '%' }"></div></div>
            <span class="tier-num">{{ t1Count }} / 1012</span>
          </div>
          <div class="tier-row">
            <span class="tier-label t2">T2 长尾</span>
            <div class="tier-bar-track"><div class="tier-bar-fill t2-fill" :style="{ width: t2Percent + '%' }"></div></div>
            <span class="tier-num">{{ t2Count }} / 779</span>
          </div>
        </div>
      </div>

      <!-- 品牌覆盖 -->
      <div class="section">
        <div class="section-title">🏷️ 型号覆盖 · 点击筛选</div>
        <div class="brand-chips">
          <span v-for="(count, brand) in stats.brands" :key="brand" class="brand-chip"
            :class="{ active: activeBrand === brand }"
            :style="{ background: activeBrand === brand ? brandColor(brand as string) + '22' : 'rgba(0,0,0,0.12)', borderColor: brandColor(brand as string), color: activeBrand === brand ? brandColor(brand as string) : '#888' }"
            @click="activeBrand = activeBrand === brand ? null : brand">
            {{ brandLabel(brand as string) }} {{ count }}
          </span>
        </div>
      </div>

      <!-- 捡漏分布 -->
      <div v-if="stats.bargains_by_brand && Object.keys(stats.bargains_by_brand).length" class="section">
        <div class="section-title">💰 捡漏分布</div>
        <div class="brand-chips">
          <span v-for="(count, brand) in stats.bargains_by_brand" :key="brand" class="brand-chip bargain-chip"
            :style="{ borderColor: brandColor(brand as string), color: brandColor(brand as string) }">
            {{ brandLabel(brand as string) }} {{ count }}个
          </span>
        </div>
      </div>

      <!-- 最近爬取批次 -->
      <div class="section">
        <div class="section-title">🕐 最近爬取批次</div>
        <div class="batch-list">
          <div v-for="b in stats.recent_batches.slice(0, 5)" :key="b.batch_id" class="batch-item"
            @click="expandedBatch = expandedBatch === b.batch_id ? null : b.batch_id">
            <div class="batch-meta">
              <span class="batch-id">{{ b.batch_id.split('_').slice(0,2).join('_') }}</span>
              <span class="batch-status" :class="'status-' + b.status">
                {{ b.status === 'completed' ? '✅' : b.status === 'failed' ? '❌' : '⏳' }}
              </span>
            </div>
            <div class="batch-stats">
              <span v-if="b.total_items">{{ b.total_items.toLocaleString() }}条</span>
              <span v-if="b.bargains_found">· {{ b.bargains_found }}捡漏</span>
              <span class="batch-time">{{ formatDuration(b.started_at, b.finished_at) }}</span>
            </div>
            <div v-if="expandedBatch === b.batch_id" class="batch-detail">
              <div>{{ b.status === 'failed' ? '❌' : '📋' }} {{ b.batch_id }}</div>
              <div>{{ b.success_count }}/{{ b.total_keywords }} 关键词成功</div>
              <div>开始: {{ formatTime(b.started_at) }}</div>
              <div v-if="b.finished_at">结束: {{ formatTime(b.finished_at) }}</div>
              <div v-if="b.error_message" class="batch-error">{{ b.error_message }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sys-panel {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  margin-bottom: 16px;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--bg3);
}

.panel-icon { font-size: 16px; }

.panel-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  flex: 1;
}

.panel-auto {
  font-size: 10px;
  color: var(--text2);
  opacity: 0.5;
  font-family: var(--font-mono);
}

.refresh-btn {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text2);
  cursor: pointer;
  font-size: 12px;
  padding: 2px 8px;
  transition: all 0.15s;
}
.refresh-btn:hover { border-color: var(--accent); color: var(--accent); }
.refresh-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.panel-loading {
  padding: 24px;
  text-align: center;
  color: var(--text2);
}

.panel-error {
  padding: 16px;
  color: var(--red);
  font-size: 13px;
}

.panel-body { padding: 16px; }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.stat-card {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 8px;
  text-align: center;
}

.stat-card.highlight {
  border-color: rgba(92, 184, 122, 0.35);
  background: rgba(92, 184, 122, 0.06);
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
  font-family: var(--font-mono);
  margin-bottom: 2px;
}

.stat-card.highlight .stat-value { color: var(--green); }

.stat-label {
  font-size: 11px;
  color: var(--text2);
}

.section { margin-bottom: 14px; }

.section-title {
  font-size: 11px;
  color: var(--text2);
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border);
}

.brand-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.brand-chip {
  background: rgba(0, 0, 0, 0.12);
  border: 1px solid color-mix(in srgb, #888888 40%, transparent);
  color: #888888;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 12px;
  font-family: var(--font-mono);
}

.batch-list { display: flex; flex-direction: column; gap: 6px; }

.batch-item {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
  transition: border-color 0.15s;
}
.batch-item:hover { border-color: var(--accent); }

.batch-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.batch-id {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text);
}

.batch-status {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}

.status-completed { background: rgba(92, 184, 122, 0.15); color: var(--green); }
.status-failed { background: rgba(224, 92, 92, 0.15); color: var(--red); }
.status-running { background: rgba(232, 197, 71, 0.15); color: var(--accent); }

.batch-stats {
  font-size: 11px;
  color: var(--text2);
  font-family: var(--font-mono);
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.bargain-hint { color: var(--green); font-weight: 600; }

.batch-time { margin-left: auto; color: var(--text2); opacity: 0.6; }

.empty-hint { font-size: 12px; color: var(--text2); opacity: 0.5; font-style: italic; }

/* 分层进度条 */
.tier-bars { display: flex; flex-direction: column; gap: 6px; }
.tier-row { display: flex; align-items: center; gap: 8px; }
.tier-label { font-size: 11px; width: 60px; font-weight: 600; }
.tier-label.t0 { color: #E74C3C; }
.tier-label.t1 { color: #F39C12; }
.tier-label.t2 { color: #888; }
.tier-bar-track { flex: 1; height: 8px; background: var(--bg3); border-radius: 4px; overflow: hidden; }
.tier-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
.t0-fill { background: linear-gradient(90deg, #E74C3C, #F39C12); }
.t1-fill { background: linear-gradient(90deg, #3498DB, #1ABC9C); }
.t2-fill { background: #888; }
.tier-num { font-size: 10px; color: var(--text2); font-family: var(--font-mono); width: 70px; text-align: right; }

/* 捡漏标签 */
.bargain-chip { background: rgba(92,184,122,0.08) !important; }

.batch-detail {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--border);
  font-size: 11px;
  color: var(--text2);
  font-family: var(--font-mono);
}
.batch-error { color: var(--red); }

.brand-chip.active {
  font-weight: 700;
  transform: scale(1.05);
}
.brand-chip {
  cursor: pointer;
  transition: all 0.15s;
}

.loading-spinner-sm {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto;
}

@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 600px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .stat-value { font-size: 18px; }
}
</style>
