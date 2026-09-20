<template>
  <ol class="aa-schedule-stage" :aria-label="ariaLabel">
    <li
      v-for="(step, index) in steps"
      :key="step"
      :class="{ 'is-done': index < activeIndex, 'is-current': index === activeIndex }"
      :aria-current="index === activeIndex ? 'step' : undefined"
    >
      <span>{{ index + 1 }}</span>
      <div><strong>{{ step }}</strong><small>{{ note(index) }}</small></div>
    </li>
  </ol>
</template>

<script>
const SCHEDULE_STEPS = ['创建批次', '安排课位', '冲突核验', '正式发布', '课表读取']
const SCHEDULING_STEPS = ['就绪任务', '约束条件', '试排编排', '冲突处理', '正式发布']

export default {
  name: 'AaScheduleStageRail',
  props: {
    mode: { type: String, default: 'schedule' },
    activeIndex: { type: Number, default: 0 }
  },
  computed: {
    steps() { return this.mode === 'scheduling' ? SCHEDULING_STEPS : SCHEDULE_STEPS },
    ariaLabel() { return this.mode === 'scheduling' ? '排课办理阶段' : '课表办理阶段' }
  },
  methods: {
    note(index) {
      if (index < this.activeIndex) return '上游事实可回查'
      if (index === this.activeIndex) return '当前办理环节'
      return '按真实状态解锁'
    }
  }
}
</script>

<style scoped>
.aa-schedule-stage { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 18px; margin: 0; padding: 14px 18px; list-style: none; border: 1px solid var(--border-200, #dbe3ed); border-radius: 12px; background: var(--bg-white, #fff); }
.aa-schedule-stage li { position: relative; display: flex; align-items: flex-start; gap: 9px; min-width: 0; color: var(--text-400, #8a94a6); }
.aa-schedule-stage li:not(:last-child)::after { content: ''; position: absolute; top: 13px; right: 0; width: calc(100% - 116px); height: 1px; background: var(--border-200, #dbe3ed); }
.aa-schedule-stage li > span { display: grid; place-items: center; flex: 0 0 26px; width: 26px; height: 26px; border: 1px solid var(--border-200, #dbe3ed); border-radius: 50%; background: #fff; font-size: 12px; font-weight: 700; }
.aa-schedule-stage li > div { display: grid; gap: 5px; min-width: 0; }
.aa-schedule-stage strong { color: var(--text-700, #3f4f67); font-size: 13px; white-space: nowrap; }
.aa-schedule-stage small { color: var(--text-400, #8794aa); font-size: 11px; white-space: nowrap; }
.aa-schedule-stage li.is-current > span { color: #fff; border-color: var(--primary-600, #2e63b8); background: var(--primary-600, #2e63b8); }
.aa-schedule-stage li.is-current strong { color: var(--primary-700, #1f4f98); }
.aa-schedule-stage li.is-done > span { color: #278259; border-color: #b9dfcc; background: #edf9f2; }
@media (max-width: 1000px) { .aa-schedule-stage { grid-template-columns: repeat(3, minmax(0, 1fr)); } .aa-schedule-stage li::after { display: none; } }
@media (max-width: 680px) { .aa-schedule-stage { grid-template-columns: 1fr 1fr; gap: 12px; } }
</style>
