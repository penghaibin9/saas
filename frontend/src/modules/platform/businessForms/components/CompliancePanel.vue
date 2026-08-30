<template>
  <section class="compliance-panel" aria-label="合规检查">
    <header>
      <div>
        <h3>{{ title }}</h3>
        <p>来源：{{ providerCode || '未声明' }} · 策略版本：{{ policyVersion || '未评估' }}</p>
      </div>
      <span :class="['summary', summaryClass]">
        {{ summaryLabel }}
      </span>
    </header>
    <ul v-if="items.length">
      <li v-for="item in items" :key="item.code" :class="`state-${item.state}`">
        <div>
          <strong>{{ item.label }}</strong>
          <small>{{ item.code }} · {{ stateLabel(item.state) }}</small>
        </div>
        <p v-if="item.reason">{{ item.reason }}</p>
      </li>
    </ul>
    <p v-else class="empty">暂无来源评估结果；不会将“未评估”显示为通过。</p>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '合规检查' },
  assessment: { type: Object, default: () => ({}) },
})

const items = computed(() => props.assessment?.items || [])
const providerCode = computed(() => props.assessment?.providerCode || props.assessment?.provider_code || '')
const policyVersion = computed(() => props.assessment?.policyVersion || props.assessment?.policy_version || '')
const evaluated = computed(() => items.value.length > 0 && typeof props.assessment?.blocking === 'boolean')
const summaryClass = computed(() => !evaluated.value ? 'unknown' : props.assessment.blocking ? 'blocking' : 'passing')
const summaryLabel = computed(() => !evaluated.value ? '尚未评估' : props.assessment.blocking ? '存在阻断' : '当前检查通过')
const labels = {
  PASS: '通过', BLOCKER: '阻断', WARNING: '提醒', PENDING: '处理中',
  NOT_EVALUATED: '未评估', NOT_APPLICABLE: '不适用', EXEMPTED: '已豁免',
}
function stateLabel(state) { return labels[state] || '未评估' }
</script>

<style scoped>
.compliance-panel { border: 1px solid #dfe5ec; border-radius: 12px; padding: 16px; background: #fff; }
header, li { display: flex; justify-content: space-between; gap: 16px; }
header { align-items: flex-start; border-bottom: 1px solid #eef1f5; padding-bottom: 12px; }
h3, p { margin: 0; }
header p, small, .empty { color: #667085; }
.summary { border-radius: 999px; padding: 4px 10px; font-size: 13px; }
.blocking { color: #b42318; background: #fee4e2; }
.passing { color: #067647; background: #dcfae6; }
.unknown { color: #93370d; background: #fef0c7; }
ul { list-style: none; margin: 0; padding: 0; }
li { padding: 12px 0; border-bottom: 1px solid #f0f2f5; }
li:last-child { border-bottom: 0; }
li p { max-width: 55%; color: #475467; }
.state-NOT_EVALUATED, .state-PENDING { border-left: 3px solid #f79009; padding-left: 10px; }
.state-BLOCKER { border-left: 3px solid #d92d20; padding-left: 10px; }
</style>
