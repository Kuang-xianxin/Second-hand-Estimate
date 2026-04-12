<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getBargains, markBargainRead } from '@/api'
import type { BargainAlert } from '@/types'

// 捡漏提醒列表数据
const alerts = ref<BargainAlert[]>([])
// 是否正在加载数据
const loading = ref(true)
// 是否只看未读消息（过滤开关）
const unreadOnly = ref(false)

// 从后端加载捡漏提醒列表（支持按已读状态过滤）
async function load() {
  loading.value = true
  try {
    alerts.value = await getBargains(unreadOnly.value)
  } catch {
    // ignore
  }
  finally { loading.value = false }
}

// 组件挂载时自动加载一次数据
onMounted(load)

// 点击提醒卡片时标记为已读（点击外部链接前先更新状态）
async function handleClick(a: BargainAlert) {
  if (!a.is_read) {
    try {
      await markBargainRead(a.id)
      a.is_read = true
    } catch {
      // ignore
    }
  }
}

// 将 ISO 时间字符串格式化为 "YYYY-MM-DD HH:mm"
function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}
</script>

<template>
  <div class="bargain-view">
    <div class="bargain-header">
      <h2 class="page-title">捡漏提醒</h2>
      <label class="filter-toggle">
        <input type="checkbox" v-model="unreadOnly" @change="load" />
        只看未读
      </label>
    </div>

    <div v-if="loading" class="loading-text">加载中...</div>
    <div v-else-if="alerts.length === 0" class="empty-text">
      {{ unreadOnly ? '没有未读捡漏提醒' : '暂无捡漏记录，先去估价页搜索商品' }}
    </div>
    <div v-else class="alert-list">
      <a
        v-for="a in alerts"
        :key="a.id"
        :href="a.url"
        target="_blank"
        class="alert-card"
        :class="{ unread: !a.is_read }"
        @click="handleClick(a)"
      >
        <div class="alert-left">
          <div class="alert-dot" v-if="!a.is_read"></div>
          <div>
            <div class="alert-title">{{ a.title }}</div>
            <div class="alert-time">{{ formatTime(a.created_at) }}</div>
          </div>
        </div>
        <div class="alert-right">
          <div class="alert-price">¥{{ a.price }}</div>
          <div class="alert-est">估价 ¥{{ a.estimated_price }}</div>
          <div class="alert-profit">+¥{{ a.profit_estimate }}</div>
        </div>
      </a>
    </div>
  </div>
</template>

<style scoped>
.bargain-view { max-width: 800px; margin: 0 auto; }

.bargain-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--red);
  letter-spacing: 2px;
}

.filter-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text2);
  cursor: pointer;
}
.filter-toggle input { accent-color: var(--accent); }

.loading-text, .empty-text {
  color: var(--text2);
  font-size: 14px;
  text-align: center;
  padding: 60px 0;
}

.alert-list { display: flex; flex-direction: column; gap: 10px; }

.alert-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  transition: border-color 0.2s, background 0.2s;
  cursor: pointer;
  text-decoration: none;
}
.alert-card:hover { border-color: var(--red); background: rgba(224,92,92,0.05); }
.alert-card.unread { border-color: rgba(224,92,92,0.4); }

.alert-left {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.alert-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--red);
  margin-top: 5px;
  flex-shrink: 0;
}

.alert-title {
  font-size: 14px;
  color: var(--text);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  max-width: 420px;
}

.alert-time {
  font-size: 11px;
  color: var(--text2);
  font-family: var(--font-mono);
  margin-top: 4px;
}

.alert-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  font-family: var(--font-mono);
  white-space: nowrap;
}

.alert-price { font-size: 20px; font-weight: 700; color: var(--red); }
.alert-est { font-size: 11px; color: var(--text2); }
.alert-profit {
  font-size: 13px;
  font-weight: 600;
  color: var(--green);
  background: rgba(92,184,122,0.12);
  padding: 2px 8px;
  border-radius: 4px;
}
</style>