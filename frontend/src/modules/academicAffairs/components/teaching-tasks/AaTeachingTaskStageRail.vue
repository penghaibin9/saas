<template>
  <ol class="aa-task-rail" aria-label="教学任务办理阶段">
    <li
      v-for="(step, index) in normalizedSteps"
      :key="step.label"
      :class="{ 'is-current': index + 1 === current, 'is-done': index + 1 < current }"
    >
      <span class="aa-task-rail__number">{{ index + 1 < current ? '✓' : index + 1 }}</span>
      <span class="aa-task-rail__copy">
        <strong>{{ step.label }}</strong>
        <small>{{ index + 1 === current ? currentNote : index + 1 < current ? '上游事实可回查' : step.note }}</small>
      </span>
    </li>
  </ol>
</template>

<script setup>
const props = defineProps({
  current: { type: Number, default: 1 },
  currentNote: { type: String, default: '当前设计视角' },
  steps: { type: Array, default: () => [] }
})

const defaults = [
  { label: '方案生成', note: '按真实状态解锁' },
  { label: '分配教师', note: '按真实状态解锁' },
  { label: '教师确认', note: '按真实状态解锁' },
  { label: '学院教务核对', note: '按真实状态解锁' },
  { label: '正式就绪', note: '按真实状态解锁' }
]

const normalizedSteps = props.steps.length ? props.steps : defaults
</script>

<style scoped>
.aa-task-rail {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0;
  margin: 0;
  padding: 13px 16px;
  list-style: none;
  border: 1px solid var(--border-200, #dbe3ed);
  border-radius: 11px;
  background: var(--bg-white, #fff);
}
.aa-task-rail li { display: flex; align-items: flex-start; gap: 9px; min-width: 0; padding-right: 12px; }
.aa-task-rail__number {
  display: inline-grid;
  flex: 0 0 24px;
  width: 24px;
  height: 24px;
  place-items: center;
  border: 1px solid var(--border-200, #dbe3ed);
  border-radius: 50%;
  color: var(--text-500, #68788c);
  background: var(--bg-white, #fff);
  font-size: 12px;
}
.aa-task-rail__copy { display: grid; min-width: 0; gap: 3px; }
.aa-task-rail strong { color: var(--text-700, #40536b); font-size: 13px; font-weight: 600; }
.aa-task-rail small { color: var(--text-400, #8896a8); font-size: 11px; line-height: 1.4; }
.aa-task-rail li.is-current .aa-task-rail__number { border-color: var(--primary-600, #2d5cad); background: var(--primary-600, #2d5cad); color: #fff; }
.aa-task-rail li.is-current strong { color: var(--primary-700, #244f9a); }
.aa-task-rail li.is-done .aa-task-rail__number { border-color: #bce4ce; background: #edf8f2; color: #258657; }
@media (max-width: 1050px) { .aa-task-rail { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; } }
@media (max-width: 720px) { .aa-task-rail { grid-template-columns: 1fr; } }
</style>
