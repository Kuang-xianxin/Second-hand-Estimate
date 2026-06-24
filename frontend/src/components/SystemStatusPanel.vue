<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getSystemStats } from '@/api'
import type { RecentCrawlBatch, SystemStats } from '@/types'

const props = defineProps<{ loggedIn: boolean }>()

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

watch(() => props.loggedIn, (val) => {
  if (val && !stats.value) load()
})
</script>
