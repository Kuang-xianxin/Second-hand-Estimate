<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { getGlobalBargains, getGlobalBargainsCount, getCacheStatus, getSystemStats } from '@/api'
import type { GlobalBargainItem, CacheStatus, SystemStats } from '@/types'
import SystemStatusPanel from '@/components/SystemStatusPanel.vue'
import CrawlProgressBar from '@/components/CrawlProgressBar.vue'

// 品牌筛选选项
const BRAND_OPTIONS = [
  { key: '', label: '全部' },
  { key: 'canon', label: '佳能' },
  { key: 'sony', label: '索尼' },
  { key: 'nikon', label: '尼康' },
  { key: 'fujifilm', label: '富士' },
  { key: 'olympus', label: '奥林巴斯' },
  { key: 'panasonic', label: '松下' },
  { key: 'casio', label: '卡西欧' },
]

const BRAND_COLORS: Record<string, string> = {
  canon: '#E74C3C',
  sony: '#3498DB',
  nikon: '#F39C12',
  fujifilm: '#E67E22',
  olympus: '#9B59B6',
  panasonic: '#1ABC9C',
  casio: '#E91E63',
  samsung: '#607D8B',
  pentax: '#795548',
  kodak: '#FF9800',
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

const bargains = ref<GlobalBargainItem[]>([])
const loading = ref(true)
const selectedBrand = ref('')
const xdOnly = ref(false)
const total = ref(0)
const brandCounts = ref<Record<string, number>>({})
const cacheStatus = ref<CacheStatus | null>(null)
const lastUpdated = ref('')
const statsPanelRef = ref<InstanceType<typeof SystemStatusPanel> | null>(null)

const filteredBargains = computed(() => bargains.value)

async function load() {
  loading.value = true
  try {
    const [bargainsData, countData, statusData] = await Promise.all([
      getGlobalBargains({ brand: selectedBrand.value || undefined, xd_card: xdOnly.value || undefined, page: 1, limit: 50 }),
      getGlobalBargainsCount({ brand: selectedBrand.value || undefined, xd_card: xdOnly.value || undefined }),
      getCacheStatus().catch(() => null),
    ])
    bargains.value = bargainsData
    total.value = countData.total
    brandCounts.value = countData.brand_counts || {}
    cacheStatus.value = statusData
    if (statusData?.l2?.latest_crawl) {
      const d = new Date(statusData.l2.latest_crawl)
      lastUpdated.value = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
    }
    // 同步刷新系统状态面板
    statsPanelRef.value?.refresh()
  } catch (e) {
    bargains.value = []
  } finally {
    loading.value = false
  }
}

function getBrandLabel(brand: string): string {
  return BRAND_OPTIONS.find(b => b.key === brand)?.label || brand || '其他'
}

function getBrandColor(brand: string): string {
  return brandColors[brand || ''] || '#888'
}

onMounted(load)

function formatTime(iso: string | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

function handleBrandClick(brand: string) {
  selectedBrand.value = brand
  load()
}

function handleXdToggle() {
  xdOnly.value = !xdOnly.value
  load()
}
</script>

<template>
  <div class="bargain-plaza">
    <!-- 数据库概览面板 -->
    <SystemStatusPanel ref="statsPanelRef" />

    <!-- 爬取进度条（空闲时自动隐藏） -->
    <CrawlProgressBar :auto-hide="true" />

    <!-- 页面标题 -->
    <div class="plaza-header">
      <div class="header-top">
        <h2 class="page-title">捡漏广场</h2>
        <div class="total-badge">
          共 <strong>{{ total }}</strong> 件可捡漏
        </div>
      </div>
      <p class="page-sub">
        全站 CCD 相机捡漏机会，不限型号，按利润排序
      </p>
      <div class="update-info" v-if="lastUpdated">
        数据更新：{{ lastUpdated }}
        <span v-if="cacheStatus?.l2?.total_keywords" class="coverage-info">
          · 已覆盖 {{ cacheStatus.l2.total_keywords }} 个型号
        </span>
      </div>
    </div>

    <!-- 品牌筛选 -->
    <div class="filter-bar">
      <div class="brand-filters">
        <button
          v-for="opt in BRAND_OPTIONS"
          :key="opt.key"
          class="brand-btn"
          :class="{ active: selectedBrand === opt.key }"
          @click="handleBrandClick(opt.key)"
        >
          {{ opt.label }}
          <span v-if="opt.key && brandCounts[opt.key]" class="brand-count">{{ brandCounts[opt.key] }}</span>
        </button>
      </div>
      <button
        class="xd-filter-btn"
        :class="{ active: xdOnly }"
        @click="handleXdToggle"
      >
        {{ xdOnly ? '含XD卡 ✓' : '含XD卡' }}
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <div class="loading-spinner"></div>
      <p>正在加载捡漏数据...</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="bargains.length === 0" class="empty-state">
      <div class="empty-icon">🎉</div>
      <p>当前暂无符合条件的捡漏机会</p>
      <p class="empty-hint">后台每 1.5 小时自动更新，稍后再来看看吧</p>
    </div>

    <!-- 捡漏列表 -->
    <div v-else class="bargain-grid">
      <a
        v-for="item in filteredBargains"
        :key="item.item_id"
        :href="item.url || '#'"
        target="_blank"
        class="bargain-card"
        rel="noopener noreferrer"
      >
        <!-- 品牌标签 -->
        <div class="card-brand" :style="{ background: getBrandColor(item.brand || '') }">
          {{ getBrandLabel(item.brand || '') }}
        </div>

        <!-- 图片 -->
        <div v-if="item.image_url" class="card-image">
          <img :src="item.image_url" :alt="item.title" loading="lazy" @error="(e) => ((e.target as HTMLImageElement).style.display = 'none')" />
        </div>
        <div v-else class="card-image-placeholder">
          <span>{{ (item.title || '').slice(0, 10) }}</span>
        </div>

        <!-- 商品信息 -->
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

          <!-- XD卡标识 -->
          <div v-if="item.is_xd_card && item.xd_card_value > 0" class="xd-badge">
            含{{ item.xd_card_size?.toUpperCase() || '' }}XD卡 +约¥{{ item.xd_card_value }}卡值
          </div>

          <!-- 成色 -->
          <div class="card-meta">
            <span v-if="item.condition" class="condition-tag">{{ item.condition }}</span>
            <span v-if="item.quality_score" class="quality-score">质量分 {{ item.quality_score.toFixed(0) }}</span>
          </div>
        </div>

        <!-- 跳转按钮 -->
        <div class="card-action">
          查看闲鱼
        </div>
      </a>
    </div>
  </div>
</template>

<style scoped>
.bargain-plaza {
  max-width: 960px;
  margin: 0 auto;
  padding: 0 16px 40px;
}

/* 页面头部 */
.plaza-header {
  margin-bottom: 24px;
}

.header-top {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 8px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 3px;
  margin: 0;
}

.total-badge {
  background: rgba(232, 197, 71, 0.12);
  border: 1px solid rgba(232, 197, 71, 0.3);
  color: var(--accent);
  font-size: 13px;
  padding: 4px 12px;
  border-radius: 20px;
  font-family: var(--font-mono);
}

.total-badge strong {
  font-weight: 700;
}

.page-sub {
  color: var(--text2);
  font-size: 14px;
  margin: 0 0 6px;
}

.update-info {
  font-size: 12px;
  color: var(--text2);
  font-family: var(--font-mono);
  opacity: 0.7;
}

.coverage-info {
  color: var(--green);
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.brand-filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  flex: 1;
}

.brand-btn {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 5px 14px;
  font-size: 13px;
  color: var(--text2);
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 4px;
}

.brand-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.brand-btn.active {
  background: rgba(232, 197, 71, 0.12);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
}

.brand-count {
  background: rgba(232, 197, 71, 0.2);
  color: var(--accent);
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 10px;
  font-family: var(--font-mono);
}

.xd-filter-btn {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 5px 14px;
  font-size: 13px;
  color: var(--text2);
  cursor: pointer;
  transition: all 0.15s;
}

.xd-filter-btn:hover {
  border-color: #f39c12;
  color: #f39c12;
}

.xd-filter-btn.active {
  background: rgba(243, 156, 18, 0.12);
  border-color: #f39c12;
  color: #f39c12;
  font-weight: 600;
}

/* 加载状态 */
.loading-state {
  text-align: center;
  padding: 80px 0;
  color: var(--text2);
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 80px 0;
  color: var(--text2);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-hint {
  font-size: 13px;
  opacity: 0.7;
  margin-top: 8px;
}

/* 捡漏卡片网格 */
.bargain-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.bargain-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  transition: border-color 0.2s, transform 0.15s;
  display: flex;
  flex-direction: column;
  text-decoration: none;
  color: inherit;
  position: relative;
}

.bargain-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
}

/* 品牌标签 */
.card-brand {
  position: absolute;
  top: 8px;
  left: 8px;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  letter-spacing: 1px;
  z-index: 1;
}

/* 商品图片 */
.card-image {
  height: 160px;
  overflow: hidden;
  background: var(--bg);
}

.card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card-image-placeholder {
  height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  color: var(--text2);
  font-size: 12px;
  padding: 16px;
  text-align: center;
}

/* 卡片主体 */
.card-body {
  padding: 12px 14px;
  flex: 1;
}

.card-title {
  font-size: 13px;
  color: var(--text);
  line-height: 1.4;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-price-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 6px;
}

.current-price {
  font-size: 22px;
  font-weight: 700;
  color: var(--red);
  font-family: var(--font-mono);
}

.base-price {
  font-size: 12px;
  color: var(--text2);
  font-family: var(--font-mono);
}

.card-profit {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 6px;
}

.profit-amount {
  font-size: 14px;
  font-weight: 700;
  color: var(--green);
  font-family: var(--font-mono);
}

.profit-label {
  font-size: 11px;
  color: var(--green);
  opacity: 0.8;
}

.xd-badge {
  background: rgba(243, 156, 18, 0.1);
  border: 1px solid rgba(243, 156, 18, 0.3);
  color: #e67e22;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 6px;
  display: inline-block;
}

.card-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.condition-tag {
  background: var(--bg);
  color: var(--text2);
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
}

.quality-score {
  font-size: 11px;
  color: var(--text2);
  font-family: var(--font-mono);
}

/* 跳转按钮 */
.card-action {
  background: var(--red);
  color: #fff;
  text-align: center;
  padding: 8px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 1px;
  transition: background 0.15s;
}

.bargain-card:hover .card-action {
  background: #c0392b;
}

/* 响应式 */
@media (max-width: 600px) {
  .bargain-plaza {
    padding: 0 12px 32px;
  }

  .page-title {
    font-size: 22px;
  }

  .bargain-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }

  .card-image {
    height: 100px;
  }

  .card-image-placeholder {
    height: 100px;
    font-size: 10px;
  }

  .current-price {
    font-size: 18px;
  }

  .filter-bar {
    gap: 8px;
  }

  .brand-btn {
    padding: 4px 10px;
    font-size: 12px;
  }
}
</style>
