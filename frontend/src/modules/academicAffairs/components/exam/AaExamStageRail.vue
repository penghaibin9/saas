<template>
  <ol class="aaer" :aria-label="ariaLabel">
    <li
      v-for="(step, index) in steps"
      :key="step"
      :class="['aaer-step', { 'is-done': index < activeIndex, 'is-active': index === activeIndex }]"
    >
      <span class="aaer-index">{{ index < activeIndex ? '✓' : index + 1 }}</span>
      <span class="aaer-label">{{ step }}</span>
    </li>
  </ol>
</template>

<script>
export default {
  name: 'AaExamStageRail',
  props: {
    steps: { type: Array, required: true },
    activeIndex: { type: Number, default: 0 },
    ariaLabel: { type: String, default: '考务办理阶段' }
  }
}
</script>

<style scoped>
.aaer { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0; margin: 0 0 16px; padding: 14px 18px; list-style: none; border: 1px solid #dce5f2; border-radius: 12px; background: #fff; }
.aaer-step { position: relative; display: flex; align-items: center; gap: 8px; min-width: 0; color: #7b8ca6; font-size: 13px; }
.aaer-step:not(:last-child)::after { content: ''; position: absolute; left: 34px; right: 10px; top: 13px; height: 1px; background: #dce5f2; }
.aaer-index { position: relative; z-index: 1; display: grid; place-items: center; flex: 0 0 26px; width: 26px; height: 26px; border: 1px solid #cbd7e8; border-radius: 50%; background: #fff; font-weight: 700; }
.aaer-label { position: relative; z-index: 1; padding-right: 8px; background: #fff; line-height: 1.35; }
.aaer-step.is-done, .aaer-step.is-active { color: #1f5cc2; }
.aaer-step.is-done .aaer-index { border-color: #b9d0f5; background: #eaf2ff; }
.aaer-step.is-active .aaer-index { border-color: #2f66c5; background: #2f66c5; color: #fff; box-shadow: 0 0 0 4px #eaf2ff; }
.aaer-step.is-active .aaer-label { color: #153e7b; font-weight: 650; }
@media (max-width: 900px) {
  .aaer { grid-template-columns: 1fr; gap: 8px; }
  .aaer-step:not(:last-child)::after { display: none; }
}
</style>
