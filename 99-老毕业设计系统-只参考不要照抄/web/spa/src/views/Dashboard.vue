<script setup>
import { onMounted, ref } from 'vue';
import api from '../api/client';

const radar = ref([]);
const ai = ref(null);
const err = ref('');

onMounted(async () => {
  try {
    // 复用后端新接口：风险雷达 + AI 状态
    radar.value = (await api.get('/bigscreen/risk-radar')).dimensions || [];
  } catch (e) { err.value = e.message; }
  try { ai.value = await api.get('/ai/status'); } catch (_) {}
});
</script>

<template>
  <div>
    <h3>工作台</h3>
    <p v-if="err" class="err">{{ err }}</p>
    <div class="grid">
      <div v-for="d in radar" :key="d.key" class="card" :class="{ hot: d.value > 0 }">
        <div class="v">{{ d.value }}</div>
        <div class="l">{{ d.label }}</div>
      </div>
    </div>
    <p v-if="ai" class="ai">AI 服务：{{ ai.mode === 'live' ? '已接入(' + ai.model + ')' : '演示模式' }}</p>
  </div>
</template>

<style scoped>
h3 { margin: 0 0 14px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
.card { background: #fff; border-radius: 12px; padding: 18px; border: 1px solid #e8edf3; }
.card.hot { border-left: 4px solid #f59e0b; }
.v { font-size: 26px; font-weight: 700; color: #0f2456; }
.l { color: #5b6b82; font-size: 13px; margin-top: 4px; }
.ai { margin-top: 16px; color: #5b6b82; }
.err { color: #dc2626; }
</style>
