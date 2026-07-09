<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getCacheStatus, getGlobalBargainCount, getGlobalBargains } from '@/api'
import CrawlProgressBar from '@/components/CrawlProgressBar.vue'
import SystemStatusPanel from '@/components/SystemStatusPanel.vue'
import type { CacheStatus, GlobalBargain } from '@/types'

const brandFilters = [
  { key: '', label: '全部' },
  { key: 'canon', label: '佳能' },
  { key: 'sony', label: '索尼' },
  { key: 'nikon', label: '尼康' },
  { key: 'fujifilm', label: '富士' },
  { key: 'olympus', label: '奥林巴斯' },
  { key: 'panasonic', label: '松下' },
  { key: 'casio', label: '卡西欧' },
]

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

const brandColors: Record<string, string> = {
  canon: '#c0392b',
  sony: '#2980b9',
  nikon: '#d68910',
  fujifilm: '#e67e22',
  olympus: '#8e44ad',
  panasonic: '#16a085',
  casio: '#c0392b',
}

const bargains = ref<GlobalBargain[]>([])
const loading = ref(true)
const selectedBrand = ref('')
const xdOnly = ref(false)
const total = ref(0)
const brandCounts = ref<Record<string, number>>({})
const cacheStatus = ref<CacheStatus | null>(null)
const latestText = ref('')

const filteredBargains = computed(() => bargains.value)

function brandName(key: string) {
  return brandLabels[key] || key || '其他'
}

function brandColor(key: string) {
  return brandColors[key || ''] || '#888'
}

function formatTime(value: string | null | undefined) {
  if (!value) return ''
  const raw = value.endsWith('Z') ? value : `${value}Z`
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function load() {
  loading.value = true
  try {
    const [items, count, cache] = await Promise.all([
      getGlobalBargains({
        brand: selectedBrand.value || undefined,
        xd_card: xdOnly.value || undefined,
        page: 1,
        limit: 50,
      }),
      getGlobalBargainCount({
        brand: selectedBrand.value || undefined,
        xd_card: xdOnly.value || undefined,
      }),
      getCacheStatus().catch(() => null),
    ])
    bargains.value = items
    total.value = count.total
    brandCounts.value = count.brand_counts || {}
    cacheStatus.value = cache
    latestText.value = formatTime(cache?.l2?.latest_crawl)
  } catch {
    bargains.value = []
    total.value = 0
    brandCounts.value = {}
  } finally {
    loading.value = false
  }
}

function selectBrand(key: string) {
  selectedBrand.value = key
  load()
}

function toggleXdOnly() {
  xdOnly.value = !xdOnly.value
  load()
}

onMounted(load)
</script>

<template>
  <div class="bargain-plaza">
    <SystemStatusPanel />
    <CrawlProgressBar :auto-hide="true" />

    <header class="plaza-header">
      <div class="header-top">
        <h2 class="page-title">捡漏广场</h2>
        <div class="total-badge">
          共 <strong>{{ total }}</strong> 件可捡漏
        </div>
      </div>
      <p class="page-sub">全站 CCD 相机捡漏机会，不限型号，按利润排序</p>
      <div v-if="latestText" class="update-info">
        数据更新：{{ latestText }}
        <span v-if="cacheStatus?.l2?.total_keywords">
          · 已覆盖 {{ cacheStatus.l2.total_keywords }} 个型号
        </span>
      </div>
    </header>

    <div class="filter-bar">
      <div class="brand-filters">
        <button
          v-for="brand in brandFilters"
          :key="brand.key"
          type="button"
          class="brand-btn"
          :class="{ active: selectedBrand === brand.key }"
          @click="selectBrand(brand.key)"
        >
          {{ brand.label }}
          <span v-if="brand.key && brandCounts[brand.key]" class="brand-count">
            {{ brandCounts[brand.key] }}
          </span>
        </button>
      </div>
      <button
        type="button"
        class="xd-filter-btn"
        :class="{ active: xdOnly }"
        @click="toggleXdOnly"
      >
        {{ xdOnly ? '含XD卡 ✓' : '含XD卡' }}
      </button>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="loading-spinner"></div>
      <p>正在加载捡漏数据...</p>
    </div>

    <div v-else-if="filteredBargains.length === 0" class="empty-state">
      <div class="empty-icon">暂无</div>
      <p>当前暂无符合条件的捡漏机会</p>
      <p class="empty-hint">后台自动更新后会在这里显示</p>
    </div>

    <div v-else class="bargain-grid">
      <a
        v-for="item in filteredBargains"
        :key="item.item_id"
        :href="item.url || '#'"
        target="_blank"
        rel="noopener noreferrer"
        class="bargain-card"
      >
        <div class="card-brand" :style="{ background: brandColor(item.brand || '') }">
          {{ brandName(item.brand || '') }}
        </div>
        <div v-if="item.image_url" class="card-image">
          <img :src="item.image_url" :alt="item.title" loading="lazy" />
        </div>
        <div v-else class="card-image-placeholder">
          <span>{{ (item.title || '').slice(0, 10) }}</span>
        </div>
        <div class="card-body">
          <div class="card-title">{{ item.title }}</div>
          <div class="card-price-row">
            <span class="current-price">¥{{ item.current_price }}</span>
            <span class="base-price">估价 ¥{{ item.base_price }}</span>
          </div>
          <div class="card-profit">
            <span class="profit-amount">+¥{{ item.profit_estimate.toFixed(0) }}</span>
            <span class="profit-label">利润</span>
          </div>
          <div v-if="item.is_xd_card && item.xd_card_value" class="xd-badge">
            含{{ item.xd_card_size?.toUpperCase() || '' }}XD卡 +约¥{{ item.xd_card_value }}卡值
          </div>
          <div v-if="item.card_status_uncertain_needs_confirm" class="card-status-badge">
            卡状态待确认
          </div>
          <div class="card-meta">
            <span v-if="item.condition" class="condition-tag">{{ item.condition }}</span>
            <span v-if="item.quality_score" class="quality-score">
              质量分 {{ item.quality_score.toFixed(0) }}
            </span>
          </div>
        </div>
        <div class="card-action">查看闲鱼</div>
      </a>
    </div>
  </div>
</template>

<style scoped>
.bargain-plaza {
  max-width: 1100px;
  margin: 0 auto;
}

.plaza-header {
  margin: 8px 0 20px;
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.page-title {
  font-size: 26px;
  color: var(--accent);
  letter-spacing: 2px;
}

.total-badge {
  color: var(--text2);
  font-size: 14px;
}

.total-badge strong {
  color: var(--green);
  font-family: var(--font-mono);
  font-size: 22px;
}

.page-sub,
.update-info {
  margin-top: 8px;
  color: var(--text2);
  font-size: 13px;
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.brand-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.brand-btn,
.xd-filter-btn {
  background: var(--bg2);
  border: 1px solid var(--border);
  color: var(--text2);
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 13px;
}

.brand-btn.active,
.xd-filter-btn.active {
  color: var(--accent);
  border-color: var(--accent);
  background: rgba(232, 197, 71, 0.1);
}

.brand-count {
  margin-left: 4px;
  font-family: var(--font-mono);
}

.loading-state,
.empty-state {
  text-align: center;
  color: var(--text2);
  padding: 56px 0;
}

.loading-spinner {
  width: 26px;
  height: 26px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  margin: 0 auto 12px;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-icon {
  font-size: 22px;
  color: var(--accent);
  margin-bottom: 8px;
}

.empty-hint {
  font-size: 12px;
  margin-top: 4px;
}

.bargain-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}

.bargain-card {
  position: relative;
  overflow: hidden;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 8px;
  transition: border-color 0.2s, transform 0.2s;
}

.bargain-card:hover {
  border-color: var(--green);
  transform: translateY(-2px);
}

.card-brand {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 1;
  color: white;
  padding: 3px 7px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
}

.card-image,
.card-image-placeholder {
  height: 150px;
  background: var(--bg3);
}

.card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card-image-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text2);
  padding: 16px;
  text-align: center;
}

.card-body {
  padding: 12px;
}

.card-title {
  height: 40px;
  overflow: hidden;
  color: var(--text);
  font-size: 14px;
  line-height: 1.45;
}

.card-price-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  margin-top: 10px;
}

.current-price {
  color: var(--red);
  font-family: var(--font-mono);
  font-size: 22px;
  font-weight: 700;
}

.base-price {
  color: var(--text2);
  font-size: 12px;
}

.card-profit {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}

.profit-amount {
  color: var(--green);
  font-family: var(--font-mono);
  font-size: 20px;
  font-weight: 700;
}

.profit-label {
  color: var(--text2);
  font-size: 12px;
}

.xd-badge {
  margin-top: 8px;
  padding: 5px 8px;
  border-radius: 4px;
  background: rgba(232, 197, 71, 0.12);
  color: var(--accent);
  font-size: 12px;
}

.card-status-badge {
  margin-top: 8px;
  padding: 5px 8px;
  border-radius: 4px;
  background: rgba(245, 158, 11, 0.14);
  color: #b45309;
  border: 1px solid rgba(245, 158, 11, 0.35);
  font-size: 12px;
  font-weight: 600;
}

.card-meta {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  color: var(--text2);
  font-size: 12px;
}

.card-action {
  border-top: 1px solid var(--border);
  padding: 9px 12px;
  color: var(--accent);
  font-size: 13px;
  text-align: center;
}

@media (max-width: 640px) {
  .header-top,
  .filter-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .bargain-grid {
    grid-template-columns: 1fr;
  }
}
</style>
