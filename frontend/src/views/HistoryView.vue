<template>
  <div class="history-view">
    <h2 class="page-title">估价历史</h2>
    <div v-if="loading" class="loading-text">加载中...</div>
    <div v-else-if="records.length === 0" class="empty-text">暂无估价记录</div>
    <div v-else class="record-list">
      <div v-for="r in records" :key="r.id" class="record-card">
        <div class="record-top">
          <span class="record-keyword">{{ r.keyword }}</span>
          <span class="record-time">{{ formatTime(r.created_at) }}</span>
        </div>
        <div class="record-prices">
          <span class="r-base">¥{{ r.base_price }}</span>
          <span class="r-range">¥{{ r.price_min }} — ¥{{ r.price_max }}</span>
          <span class="r-sample">{{ r.sample_count }} 条样本</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getHistory } from '@/api/index.js'

const records = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    records.value = await getHistory(50)
  } catch {}
  finally { loading.value = false }
})

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}
</script>

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
}
.record-card:hover { border-color: var(--accent); }

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
</style>
