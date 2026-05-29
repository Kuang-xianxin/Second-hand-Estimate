<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { getCrawlProgress } from '@/api'
import type { CrawlProgress } from '@/types'

const props = defineProps<{
  /** 是否自动隐藏（空闲时自动消失） */
  autoHide?: boolean
}>()

const progress = ref<CrawlProgress | null>(null)
const loading = ref(false)
const error = ref('')
let timer: ReturnType<typeof setInterval> | null = null

const percent = computed(() => {
  if (!progress.value || progress.value.total === 0) return 0
  return Math.min(100, Math.round((progress.value.done / progress.value.total) * 100))
})

const stageColor = computed(() => {
  const s = progress.value?.stage || ''
  if (s.includes('完成') || s.includes('空闲')) return 'green'
  if (s.includes('失败') || s.includes('错误')) return 'red'
  return 'yellow'
})

const stageIcon = computed(() => {
  const s = progress.value?.stage || ''
  if (s.includes('完成')) return '✓'
  if (s.includes('失败')) return '✗'
  return '⚡'
})

async function load() {
  try {
    progress.value = await getCrawlProgress()
    error.value = ''
  } catch {
    error.value = '无法获取进度'
  }
}

function startPolling() {
  load()
  timer = setInterval(load, 5000)
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

onMounted(startPolling)
onUnmounted(stopPolling)

// 暴露刷新方法给父组件
defineExpose({ refresh: load })
</script>

<template>
  <!-- 无进度时隐藏（autoHide=true）或显示空闲状态 -->
  <div v-if="progress" class="crawl-progress">
    <div class="progress-header">
      <div class="progress-stage">
        <span class="stage-icon" :class="'icon-' + stageColor">{{ stageIcon }}</span>
        <span v-if="progress.tier" class="tier-badge">{{ progress.tier.toUpperCase() }}</span>
        <span class="stage-text">{{ progress.stage || '进行中' }}</span>
        <span v-if="progress.total > 0" class="stage-count">
          {{ progress.done }}/{{ progress.total }} 个型号
        </span>
      </div>
      <div class="progress-meta">
        <span v-if="progress.current_keyword" class="current-kw">
          {{ progress.current_keyword.length > 30 ? progress.current_keyword.slice(0, 30) + '...' : progress.current_keyword }}
        </span>
        <span v-if="progress.total_items > 0" class="meta-item">
          📦 {{ progress.total_items }}
        </span>
        <span v-if="progress.bargains_found > 0" class="meta-item bargains">
          💎 {{ progress.bargains_found }}
        </span>
        <span v-if="progress.started_at" class="meta-item time">
          {{ new Date(progress.started_at + (progress.started_at.endsWith('Z') || progress.started_at.includes('+') ? '' : '+08:00')).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }}
        </span>
      </div>
    </div>

    <div class="progress-bar-wrap">
      <div class="progress-bar" :class="'bar-' + stageColor">
        <div class="progress-fill" :style="{ width: percent + '%' }"></div>
      </div>
      <span class="progress-pct">{{ percent }}%</span>
    </div>

    <div v-if="progress.fail_count > 0" class="progress-fail">
      失败 {{ progress.fail_count }} 个
    </div>
  </div>

  <!-- 空闲状态：autoHide=false 时显示 -->
  <div v-else-if="!autoHide" class="crawl-idle">
    <span class="idle-icon">💤</span>
    <span class="idle-text">后台暂无爬取任务</span>
  </div>
</template>

<style scoped>
.crawl-progress {
  background: linear-gradient(135deg, rgba(232, 197, 71, 0.06), rgba(232, 197, 71, 0.02));
  border: 1px solid rgba(232, 197, 71, 0.25);
  border-radius: var(--radius);
  padding: 10px 14px;
  margin-bottom: 14px;
}

.crawl-idle {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 14px;
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text2);
}

.idle-icon { font-size: 14px; }
.idle-text { font-family: var(--font-mono); }

.progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.progress-stage {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stage-icon {
  font-size: 14px;
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.tier-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(232,197,71,0.15);
  color: var(--accent);
  font-family: var(--font-mono);
  text-transform: uppercase;
}

.icon-yellow { color: var(--accent); }
.icon-green { color: var(--green); }
.icon-red { color: var(--red); }

.stage-text {
  font-size: 13px;
  font-weight: 700;
  color: var(--accent);
  font-family: var(--font-mono);
}

.stage-count {
  font-size: 11px;
  color: var(--text2);
  font-family: var(--font-mono);
  background: rgba(232, 197, 71, 0.1);
  padding: 1px 6px;
  border-radius: 8px;
}

.progress-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.current-kw {
  font-size: 11px;
  color: var(--text2);
  font-family: var(--font-mono);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-item {
  font-size: 11px;
  color: var(--text2);
  font-family: var(--font-mono);
}

.meta-item.bargains { color: var(--green); font-weight: 600; }

.time { opacity: 0.6; }

.progress-bar-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: var(--bg3);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.8s ease;
  background: var(--accent);
}

.bar-yellow .progress-fill { background: var(--accent); }
.bar-green .progress-fill { background: var(--green); }
.bar-red .progress-fill { background: var(--red); }

.progress-pct {
  font-size: 11px;
  font-weight: 700;
  color: var(--accent);
  font-family: var(--font-mono);
  min-width: 36px;
  text-align: right;
}

.progress-fail {
  margin-top: 4px;
  font-size: 11px;
  color: var(--red);
  font-family: var(--font-mono);
}
</style>
