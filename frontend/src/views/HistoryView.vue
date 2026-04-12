<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getHistory, getHistoryDetail } from '@/api'
import type { HistoryRecord, HistoryDetail } from '@/types'

// 估价历史记录列表（列表页展示）
const records = ref<HistoryRecord[]>([])
// 是否正在加载历史列表
const loading = ref(true)
// 当前选中的记录（用于展开详情）
const selected = ref<HistoryRecord | null>(null)
// 当前选中记录的详细数据（展开后加载）
const detail = ref<HistoryDetail | null>(null)
// 详情是否正在加载中
const detailLoading = ref(false)

// 组件挂载时获取最近50条估价历史记录
onMounted(async () => {
  try {
    records.value = await getHistory(50)
  } catch {
    // ignore
  }
  finally { loading.value = false }
})

// 切换记录的展开/收起状态
// 若再次点击同一记录则收起详情；若点击新记录则加载其详细数据
async function toggleDetail(r: HistoryRecord) {
  if (selected.value?.id === r.id) {
    selected.value = null
    detail.value = null
    return
  }
  selected.value = r
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await getHistoryDetail(r.id)
  } catch {
    // ignore
  }
  finally { detailLoading.value = false }
}

// 将 ISO 时间字符串格式化为 "YYYY-MM-DD HH:mm"
function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}
</script>

<template>
  <div class="history-view">
    <h2 class="page-title">估价历史</h2>
    <div v-if="loading" class="loading-text">加载中...</div>
    <div v-else-if="records.length === 0" class="empty-text">暂无估价记录</div>
    <div v-else class="record-list">
      <div
        v-for="r in records"
        :key="r.id"
        class="record-card"
        :class="{ active: selected?.id === r.id }"
        @click="toggleDetail(r)"
      >
        <div class="record-top">
          <span class="record-keyword">{{ r.keyword }}</span>
          <span class="record-time">{{ formatTime(r.created_at) }}</span>
        </div>
        <div class="record-prices">
          <span class="r-base">¥{{ r.base_price }}</span>
          <span class="r-range">¥{{ r.price_min }} — ¥{{ r.price_max }}</span>
          <span class="r-sample">{{ r.sample_count }} 条样本</span>
          <span class="r-chevron">{{ selected?.id === r.id ? '▲' : '▼' }}</span>
        </div>

        <!-- 详情面板 -->
        <div v-if="selected?.id === r.id" class="detail-panel" @click.stop>
          <div v-if="detailLoading" class="detail-loading">加载中...</div>
          <template v-else-if="detail">
            <!-- LLM建议价 -->
            <div v-if="detail.llm_results?.length" class="detail-section">
              <div class="detail-section-title">大模型建议价</div>
              <div class="llm-list">
                <div v-for="llm in detail.llm_results" :key="llm.model" class="llm-row">
                  <span class="llm-model">{{ llm.model }}</span>
                  <span class="llm-price">¥{{ llm.suggested_price ?? '—' }}</span>
                  <span class="llm-range" v-if="llm.price_min && llm.price_max">¥{{ llm.price_min }}—{{ llm.price_max }}</span>
                  <span class="llm-conf" v-if="llm.confidence">置信度 {{ llm.confidence }}</span>
                </div>
              </div>
            </div>

            <!-- 样本价格分布 -->
            <div v-if="detail.raw_prices?.length" class="detail-section">
              <div class="detail-section-title">样本价格分布（{{ detail.raw_prices.length }} 条）</div>
              <div class="price-tags">
                <span
                  v-for="(p, i) in detail.raw_prices.slice(0, 30)"
                  :key="i"
                  class="price-tag"
                  :class="{ outlier: p < detail.price_min || p > detail.price_max }"
                >¥{{ p }}</span>
                <span v-if="detail.raw_prices.length > 30" class="price-tag more">+{{ detail.raw_prices.length - 30 }} 更多</span>
              </div>
            </div>

            <!-- 捡漏 -->
            <div v-if="detail.bargains?.length" class="detail-section">
              <div class="detail-section-title">捡漏 {{ detail.bargains.length }} 件</div>
              <div class="bargain-mini-list">
                <a
                  v-for="b in detail.bargains"
                  :key="b.item_id"
                  :href="b.url"
                  target="_blank"
                  class="bargain-mini-item"
                >
                  <span class="bm-title">{{ b.title }}</span>
                  <span class="bm-price">¥{{ b.price }}</span>
                  <span class="bm-profit">+¥{{ b.profit_estimate }}</span>
                </a>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-view { max-width: 800px; margin: 0 auto; }

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 2px;
  margin-bottom: 28px;
}

.loading-text, .empty-text {
  color: var(--text2);
  font-size: 14px;
  text-align: center;
  padding: 60px 0;
}

.record-list { display: flex; flex-direction: column; gap: 12px; }

.record-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 22px;
  transition: border-color 0.2s;
  cursor: pointer;
  user-select: none;
}
.record-card:hover { border-color: var(--accent); }
.record-card.active { border-color: var(--accent); }

.record-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.record-keyword {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}

.record-time {
  font-size: 12px;
  color: var(--text2);
  font-family: var(--font-mono);
}

.record-prices {
  display: flex;
  align-items: center;
  gap: 16px;
  font-family: var(--font-mono);
}

.r-base { font-size: 22px; font-weight: 700; color: var(--accent); }
.r-range { font-size: 13px; color: var(--text2); }
.r-sample { font-size: 11px; color: var(--text2); margin-left: auto; }
.r-chevron { font-size: 11px; color: var(--text2); }

/* 详情面板 */
.detail-panel {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.detail-loading {
  color: var(--text2);
  font-size: 13px;
  padding: 12px 0;
}

.detail-section {
  margin-bottom: 16px;
}

.detail-section-title {
  font-size: 12px;
  color: var(--text2);
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 8px;
  font-family: var(--font-mono);
}

/* LLM结果 */
.llm-list { display: flex; flex-direction: column; gap: 6px; }
.llm-row {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg3);
  border-radius: 6px;
  padding: 8px 12px;
  font-family: var(--font-mono);
  font-size: 13px;
}
.llm-model { color: var(--text2); min-width: 100px; font-size: 11px; }
.llm-price { color: var(--accent); font-weight: 700; font-size: 16px; }
.llm-range { color: var(--text2); font-size: 12px; }
.llm-conf { color: var(--text2); font-size: 11px; margin-left: auto; }

/* 价格分布 */
.price-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.price-tag {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text);
}
.price-tag.outlier {
  color: var(--text2);
  text-decoration: line-through;
  opacity: 0.5;
}
.price-tag.more { color: var(--text2); border-style: dashed; }

/* 捡漏 */
.bargain-mini-list { display: flex; flex-direction: column; gap: 6px; }
.bargain-mini-item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--bg3);
  border: 1px solid rgba(224,92,92,0.2);
  border-radius: 6px;
  padding: 8px 12px;
  text-decoration: none;
  transition: border-color 0.2s;
}
.bargain-mini-item:hover { border-color: var(--red); }
.bm-title { flex: 1; font-size: 13px; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bm-price { font-family: var(--font-mono); font-size: 14px; font-weight: 700; color: var(--red); }
.bm-profit { font-family: var(--font-mono); font-size: 12px; color: var(--green); background: rgba(92,184,122,0.1); padding: 2px 6px; border-radius: 4px; }
</style>