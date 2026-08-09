<template>
  <section v-if="trace || content || message" class="decision-card" :class="toneClass" role="status" aria-live="polite">
    <div class="decision-card__icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M12 3.5 20 7.7v5.9c0 3.5-2.2 5.9-8 7.4-5.8-1.5-8-3.9-8-7.4V7.7L12 3.5Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
        <path d="M12 8v5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
        <circle cx="12" cy="16.5" r="1" fill="currentColor" />
      </svg>
    </div>

    <div class="decision-card__body">
      <div class="decision-card__topline">
        <span class="decision-card__eyebrow">规则校验结果</span>
        <span class="decision-card__state">{{ stateLabel }}</span>
      </div>
      <h3>{{ displayTitle }}</h3>
      <p class="decision-card__reason">{{ displayReason }}</p>

      <div v-if="resolutionLabels.length" class="decision-card__next">
        <span class="decision-card__next-label">建议下一步</span>
        <ol>
          <li v-for="(label, index) in resolutionLabels" :key="`${index}:${label}`">
            <span>{{ index + 1 }}</span>
            <strong>{{ label }}</strong>
          </li>
        </ol>
      </div>

      <div class="decision-card__foot">
        <span class="decision-card__dot" aria-hidden="true"></span>
        <span>结果来自学校业务规则实时校验，页面不会自行改写办理结论。</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  trace: { type: Object, default: null },
  content: { type: Object, default: null },
  message: { type: String, default: '' }
})

const displayTitle = computed(() => {
  if (props.content?.title) return props.content.title
  const domain = String(props.trace?.domain || '').toUpperCase()
  if (domain === 'GRADUATION') return '毕业资格还有待处理事项'
  if (domain === 'SELECTION') return '本次选课暂未通过校验'
  return '当前事项暂未通过校验'
})

const displayReason = computed(() =>
  props.content?.reason || props.message || '当前规则暂不允许办理，请按提示核对后再试。')

const resolutionLabels = computed(() => {
  if (props.content?.nextStep) return [props.content.nextStep]
  const rows = Array.isArray(props.trace?.availableResolutions) ? props.trace.availableResolutions : []
  return rows.map((item) => String(item?.label || '').trim()).filter(Boolean).slice(0, 3)
})

const stateLabel = computed(() => {
  const decision = String(props.trace?.decision || '').toUpperCase()
  return ['DENIED', 'BLOCKED', 'FAILED', 'ABNORMAL'].includes(decision) ? '需要处理' : '办理说明'
})

const toneClass = computed(() => {
  const decision = String(props.trace?.decision || '').toUpperCase()
  return ['DENIED', 'BLOCKED', 'FAILED', 'ABNORMAL'].includes(decision) ? 'is-warn' : 'is-info'
})
</script>

<style scoped>
.decision-card {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 14px;
  padding: 18px 20px;
  border: 1px solid var(--pri-100);
  border-radius: 16px;
  background: linear-gradient(135deg, #fff 0%, var(--pri-50) 100%);
  box-shadow: 0 10px 30px -24px rgba(47, 107, 255, .55);
}
.decision-card.is-warn {
  border-color: #fed7aa;
  background: linear-gradient(135deg, #fff 0%, #fff8ef 100%);
  box-shadow: 0 10px 30px -24px rgba(180, 83, 9, .45);
}
.decision-card__icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 13px;
  background: #fff;
  color: var(--pri);
  box-shadow: inset 0 0 0 1px var(--pri-100), 0 6px 18px rgba(47, 107, 255, .08);
}
.is-warn .decision-card__icon {
  color: var(--warn-fg);
  box-shadow: inset 0 0 0 1px #fed7aa, 0 6px 18px rgba(180, 83, 9, .08);
}
.decision-card__icon svg { width: 23px; height: 23px; }
.decision-card__body { min-width: 0; }
.decision-card__topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.decision-card__eyebrow {
  color: var(--t3);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
}
.decision-card__state {
  flex-shrink: 0;
  padding: 4px 9px;
  border-radius: 999px;
  background: rgba(47, 107, 255, .08);
  color: var(--pri);
  font-size: 11px;
  font-weight: 700;
}
.is-warn .decision-card__state { background: var(--warn-bg); color: var(--warn-fg); }
.decision-card h3 {
  margin: 7px 0 0;
  color: var(--t1);
  font-size: 16px;
  line-height: 1.45;
}
.decision-card__reason {
  margin: 7px 0 0;
  color: var(--t2);
  font-size: 13px;
  line-height: 1.7;
}
.decision-card__next {
  margin-top: 14px;
  padding: 13px 14px;
  border: 1px solid rgba(255, 255, 255, .8);
  border-radius: 12px;
  background: rgba(255, 255, 255, .72);
}
.decision-card__next-label {
  display: block;
  margin-bottom: 8px;
  color: var(--t3);
  font-size: 11px;
  font-weight: 600;
}
.decision-card__next ol { display: grid; gap: 7px; margin: 0; padding: 0; list-style: none; }
.decision-card__next li { display: grid; grid-template-columns: 22px minmax(0, 1fr); gap: 8px; align-items: start; }
.decision-card__next li > span {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 7px;
  background: var(--pri-50);
  color: var(--pri);
  font-size: 11px;
  font-weight: 700;
}
.is-warn .decision-card__next li > span { background: var(--warn-bg); color: var(--warn-fg); }
.decision-card__next strong { color: var(--t1); font-size: 12.5px; font-weight: 600; line-height: 1.65; }
.decision-card__foot {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 12px;
  color: var(--t4);
  font-size: 11px;
  line-height: 1.5;
}
.decision-card__dot { width: 6px; height: 6px; border-radius: 50%; background: var(--ok-fg); flex-shrink: 0; }
@media (max-width: 640px) {
  .decision-card { grid-template-columns: 36px minmax(0, 1fr); padding: 16px; }
  .decision-card__icon { width: 36px; height: 36px; border-radius: 11px; }
  .decision-card__icon svg { width: 20px; height: 20px; }
  .decision-card__topline { align-items: flex-start; }
}
</style>
