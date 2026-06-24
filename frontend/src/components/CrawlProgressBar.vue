<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getCrawlProgress } from '@/api'
import type { CrawlPhaseStep, CrawlProgress } from '@/types'

const props = withDefaults(defineProps<{
  autoHide?: boolean
}>(), {
  autoHide: true,
})

const progress = ref<CrawlProgress | null>(null)
const error = ref('')
let timer: ReturnType<typeof setInterval> | null = null

const percent = computed(() => {
  if (!progress.value) return 0
  if (typeof progress.value.progress_percent === 'number') {
    return Math.max(0, Math.min(100, Math.round(progress.value.progress_percent)))
  }
  if (progress.value.total > 0) {
    return Math.max(0, Math.min(100, Math.round(progress.value.done / progress.value.total * 100)))
  }
  return 0
})

const visible = computed(() => {
  if (!progress.value) return !props.autoHide && !!error.value
  const stage = progress.value.stage_key || progress.value.stage || ''
  if (props.autoHide && (stage.includes('idle') || stage.includes('空闲'))) return false
  return true
})

const phaseSteps = computed<CrawlPhaseStep[]>(() => {
  if (progress.value?.phase_steps?.length) return progress.value.phase_steps
  return [
    { key: 'crawling', label: '爬取商品', status: 'pending', start_percent: 0, end_percent: 70 },
    { key: 'pricing', label: '规则清洗/估价', status: 'pending', start_percent: 70, end_percent: 82 },
    { key: 'detecting_bargains', label: '检测捡漏', status: 'pending', start_percent: 82, end_percent: 92 },
    { key: 'saving', label: '写入缓存', status: 'pending', start_percent: 92, end_percent: 98 },
    { key: 'completed', label: '完成', status: 'pending', start_percent: 100, end_percent: 100 },
  ]
})

function stepClass(step: CrawlPhaseStep) {
  const stageKey = progress.value?.stage_key || ''
  return {
    done: step.status === 'done',
    current: step.key === stageKey && step.status !== 'done' && step.status !== 'error',
    error: step.status === 'error',
  }
}

function formatTime(value: string) {
  if (!value) return ''
  const raw = value.endsWith('Z') ? value : `${value}Z`
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

async function refresh() {
  try {
    progress.value = await getCrawlProgress()
    error.value = ''
  } catch {
    error.value = '无法获取后台爬取进度'
  }
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <section v-if="visible" class="crawl-progress-card">
    <div class="crawl-progress-head">
      <div class="crawl-stage">
        <span
          class="stage-mark"
          :class="{ done: progress?.stage_key === 'completed', error: progress?.stage_key === 'failed' }"
        >
          {{ progress?.stage_key === 'completed' ? '✓' : progress?.stage_key === 'failed' ? '!' : '•' }}
        </span>
        <span class="stage-title">{{ progress?.stage || '后台爬取' }}</span>
        <span v-if="progress?.keyword_total" class="stage-count">
          {{ progress.keyword_done ?? 0 }}/{{ progress.keyword_total }} 个型号
        </span>
      </div>
      <div class="crawl-meta">
        <span v-if="progress?.total_items">样本 {{ progress.total_items }}</span>
        <span v-if="progress?.bargains_found">捡漏 {{ progress.bargains_found }}</span>
        <span v-if="progress?.started_at">{{ formatTime(progress.started_at) }}</span>
      </div>
    </div>

    <div v-if="progress?.progress_text || progress?.current_keyword" class="progress-text">
      {{ progress.progress_text || progress.current_keyword }}
    </div>

    <div class="progress-track">
      <div class="progress-fill" :style="{ width: `${percent}%` }"></div>
      <span class="progress-percent">{{ percent }}%</span>
    </div>

    <div class="phase-list">
      <div
        v-for="step in phaseSteps"
        :key="step.key"
        class="phase-step"
        :class="stepClass(step)"
      >
        <span class="phase-dot"></span>
        <span>{{ step.label }}</span>
      </div>
    </div>

    <div v-if="progress?.fail_count" class="progress-error">
      失败 {{ progress.fail_count }} 个型号
    </div>
    <div v-else-if="error" class="progress-error">{{ error }}</div>
  </section>
</template>

<style scoped>
.crawl-progress-card {
  width: 100%;
  margin: 0 0 24px;
  padding: 14px 16px;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.crawl-progress-head,
.crawl-stage,
.crawl-meta,
.phase-list,
.phase-step {
  display: flex;
  align-items: center;
}

.crawl-progress-head {
  justify-content: space-between;
  gap: 14px;
}

.crawl-stage {
  gap: 8px;
  min-width: 0;
}

.stage-mark {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(232, 197, 71, 0.14);
  color: var(--accent);
  font-family: var(--font-mono);
  font-weight: 700;
}

.stage-mark.done {
  background: rgba(92, 184, 122, 0.14);
  color: var(--green);
}

.stage-mark.error {
  background: rgba(224, 92, 92, 0.14);
  color: var(--red);
}

.stage-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
}

.stage-count,
.crawl-meta,
.progress-text,
.phase-step {
  font-size: 12px;
  color: var(--text2);
}

.crawl-meta {
  gap: 12px;
  white-space: nowrap;
  font-family: var(--font-mono);
}

.progress-text {
  margin-top: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-track {
  position: relative;
  height: 10px;
  margin-top: 10px;
  background: var(--bg3);
  border-radius: 999px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  min-width: 4px;
  background: linear-gradient(90deg, var(--accent), var(--green));
  transition: width 0.35s ease;
}

.progress-percent {
  position: absolute;
  right: 8px;
  top: -2px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text);
}

.phase-list {
  margin-top: 10px;
  gap: 10px;
  flex-wrap: wrap;
}

.phase-step {
  gap: 5px;
}

.phase-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--border);
}

.phase-step.done .phase-dot {
  background: var(--green);
}

.phase-step.current .phase-dot {
  background: var(--accent);
}

.phase-step.error .phase-dot {
  background: var(--red);
}

.progress-error {
  margin-top: 8px;
  color: var(--red);
  font-size: 12px;
}

@media (max-width: 600px) {
  .crawl-progress-card {
    width: 100%;
  }

  .crawl-progress-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .crawl-meta {
    flex-wrap: wrap;
    gap: 8px;
  }
}
</style>
