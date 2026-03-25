<template>
  <div class="home">
    <!-- 搜索区 -->
    <section class="search-section">
      <h1 class="page-title">二手商品智能估价</h1>
      <p class="page-sub">输入商品名称，获取市场价格区间与多模型分析</p>
      <div class="search-box">
        <input
          v-model="keyword"
          class="search-input"
          placeholder="例如：iPhone 15 Pro 256G"
          @keydown.enter="doValuate"
          :disabled="loading"
        />
        <button class="search-btn" @click="doValuate" :disabled="loading">
          <span v-if="!loading">开始估价</span>
          <span v-else class="loading-dots">分析中<span>.</span><span>.</span><span>.</span></span>
        </button>
      </div>
      <div class="login-tip">
        <div class="login-tip-title">请先完成一次闲鱼登录授权</div>
        <div class="login-tip-text">
          在 `backend` 目录运行 `python save_xianyu_state.py`，登录成功后再回来估价。
        </div>
      </div>
      <p v-if="error" class="error-msg">{{ error }}</p>
    </section>

    <!-- 结果区 -->
    <section v-if="result" class="result-section">
      <!-- 算法基准卡片 -->
      <div class="card algo-card">
        <div class="card-label">算法基准估价</div>
        <div class="base-price">¥{{ result.algorithm.base_price }}</div>
        <div class="price-range">
          合理区间：<span class="range-val">¥{{ result.algorithm.price_min }} — ¥{{ result.algorithm.price_max }}</span>
        </div>
        <div class="sample-info">参与计算样本：{{ result.sample_count }} 条</div>
        <div v-if="result.algorithm.low_outliers.length" class="outlier-info low">
          过低价格（已降权）：{{ result.algorithm.low_outliers.map(p => '¥'+p).join('、') }}
        </div>
        <div v-if="result.algorithm.high_outliers.length" class="outlier-info high">
          过高价格（已降权）：{{ result.algorithm.high_outliers.map(p => '¥'+p).join('、') }}
        </div>
      </div>

      <!-- 多模型对比 -->
      <div class="section-title">大模型分析对比</div>
      <div class="llm-grid">
        <div
          v-for="m in result.llm_results"
          :key="m.model"
          class="llm-card"
          :class="{ 'has-error': m.error }"
        >
          <div class="llm-model-name">{{ m.model }}</div>
          <div v-if="m.error" class="llm-error">{{ m.error }}</div>
          <template v-else>
            <div class="llm-price">¥{{ m.suggested_price }}</div>
            <div class="llm-range">¥{{ m.price_min }} — ¥{{ m.price_max }}</div>
            <div class="llm-confidence" :class="'conf-'+m.confidence">置信度：{{ m.confidence }}</div>
            <div class="llm-reasoning">{{ m.reasoning }}</div>
          </template>
        </div>
      </div>

      <!-- 捡漏提醒 -->
      <div v-if="result.bargains.length" class="section-title bargain-title">
        捡漏机会 <span class="bargain-count">{{ result.bargains.length }}</span>
      </div>
      <div v-if="result.bargains.length" class="bargain-list">
        <a
          v-for="b in result.bargains"
          :key="b.item_id"
          :href="b.url"
          target="_blank"
          class="bargain-item"
        >
          <div class="bargain-title-text">{{ b.title }}</div>
          <div class="bargain-prices">
            <span class="bargain-actual">¥{{ b.price }}</span>
            <span class="bargain-est">估价 ¥{{ b.estimated_price }}</span>
            <span class="bargain-profit">+¥{{ b.profit_estimate }} 利润</span>
          </div>
        </a>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { valuate } from '@/api/index.js'

const keyword = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)

async function doValuate() {
  if (!keyword.value.trim()) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await valuate(keyword.value.trim())
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || '请求失败，请检查后端是否启动'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.home { max-width: 900px; margin: 0 auto; }

.search-section { margin-bottom: 48px; }

.page-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 3px;
  margin-bottom: 8px;
}

.page-sub {
  color: var(--text2);
  font-size: 14px;
  margin-bottom: 24px;
}

.search-box {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}

.search-input {
  flex: 1;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 20px;
  font-size: 16px;
  color: var(--text);
  transition: border-color 0.2s;
}
.search-input:focus { border-color: var(--accent); }
.search-input:disabled { opacity: 0.5; }

.search-btn {
  background: var(--accent);
  color: #0e0e10;
  font-weight: 700;
  font-size: 15px;
  padding: 0 32px;
  border-radius: var(--radius);
  transition: opacity 0.2s, transform 0.1s;
  white-space: nowrap;
}
.search-btn:hover:not(:disabled) { opacity: 0.85; transform: translateY(-1px); }
.search-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.loading-dots span {
  animation: blink 1.2s infinite;
}
.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%,80%,100% { opacity:0 } 40% { opacity:1 } }

.login-tip {
  margin-bottom: 14px;
  padding: 12px 14px;
  background: rgba(232, 197, 71, 0.08);
  border: 1px solid rgba(232, 197, 71, 0.2);
  border-radius: var(--radius);
}

.login-tip-title {
  color: var(--accent);
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 4px;
}

.login-tip-text {
  color: var(--text2);
  font-size: 12px;
  line-height: 1.6;
  font-family: var(--font-mono);
}

.error-msg {
  color: var(--red);
  font-size: 13px;
  margin-top: 10px;
  padding: 10px 14px;
  background: rgba(224,92,92,0.1);
  border-radius: var(--radius);
  border: 1px solid rgba(224,92,92,0.2);
}

/* 结果区 */
.card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px 28px;
  margin-bottom: 28px;
}

.card-label {
  font-size: 12px;
  color: var(--text2);
  letter-spacing: 2px;
  text-transform: uppercase;
  margin-bottom: 10px;
}

.base-price {
  font-size: 48px;
  font-weight: 700;
  color: var(--accent);
  font-family: var(--font-mono);
  line-height: 1;
  margin-bottom: 10px;
}

.price-range {
  font-size: 14px;
  color: var(--text2);
  margin-bottom: 6px;
}

.range-val { color: var(--text); font-family: var(--font-mono); }

.sample-info {
  font-size: 12px;
  color: var(--text2);
  font-family: var(--font-mono);
}

.outlier-info {
  font-size: 12px;
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  font-family: var(--font-mono);
}
.outlier-info.low { background: rgba(92,184,122,0.08); color: var(--green); }
.outlier-info.high { background: rgba(224,92,92,0.08); color: var(--red); }

.section-title {
  font-size: 13px;
  letter-spacing: 3px;
  color: var(--text2);
  text-transform: uppercase;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

.llm-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

@media (max-width: 700px) {
  .llm-grid { grid-template-columns: 1fr; }
}

.llm-card {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  transition: border-color 0.2s;
}
.llm-card:hover { border-color: var(--accent); }
.llm-card.has-error { border-color: rgba(224,92,92,0.3); }

.llm-model-name {
  font-size: 11px;
  letter-spacing: 2px;
  color: var(--text2);
  margin-bottom: 12px;
  font-family: var(--font-mono);
}

.llm-price {
  font-size: 30px;
  font-weight: 700;
  color: var(--text);
  font-family: var(--font-mono);
  margin-bottom: 4px;
}

.llm-range {
  font-size: 12px;
  color: var(--text2);
  font-family: var(--font-mono);
  margin-bottom: 8px;
}

.llm-confidence {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 10px;
  font-family: var(--font-mono);
}
.conf-高 { background: rgba(92,184,122,0.15); color: var(--green); }
.conf-中 { background: rgba(232,197,71,0.15); color: var(--accent); }
.conf-低 { background: rgba(224,92,92,0.15); color: var(--red); }

.llm-reasoning {
  font-size: 12px;
  color: var(--text2);
  line-height: 1.6;
}

.llm-error {
  font-size: 12px;
  color: var(--red);
  line-height: 1.6;
}

.bargain-title {
  color: var(--red);
  border-color: rgba(224,92,92,0.3);
}

.bargain-count {
  background: var(--red);
  color: #fff;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 10px;
  font-family: var(--font-mono);
}

.bargain-list { display: flex; flex-direction: column; gap: 10px; }

.bargain-item {
  background: var(--bg2);
  border: 1px solid rgba(224,92,92,0.25);
  border-radius: var(--radius);
  padding: 14px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  transition: border-color 0.2s, background 0.2s;
}
.bargain-item:hover {
  border-color: var(--red);
  background: rgba(224,92,92,0.06);
}

.bargain-title-text {
  font-size: 14px;
  color: var(--text);
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.bargain-prices {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
  font-family: var(--font-mono);
  font-size: 13px;
}

.bargain-actual { color: var(--red); font-weight: 700; font-size: 16px; }
.bargain-est { color: var(--text2); }
.bargain-profit {
  background: rgba(92,184,122,0.15);
  color: var(--green);
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}
</style>
