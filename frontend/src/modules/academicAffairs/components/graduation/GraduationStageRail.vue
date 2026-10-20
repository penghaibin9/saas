<template>
  <ol class="grad-rail" aria-label="毕业资格办理阶段">
    <li
      v-for="(stage, index) in stages"
      :key="stage"
      :class="{ 'is-done': index < active, 'is-active': index === active }"
    >
      <span>{{ index < active ? '✓' : index + 1 }}</span>
      <b>{{ stage }}</b>
    </li>
  </ol>
</template>

<script>
export default {
  name: 'GraduationStageRail',
  props: {
    active: { type: Number, default: 0 }
  },
  data() {
    return { stages: ['审核批次', '毕业学生', '十一项证据', '学院审核', '教务终审', '证书归档'] }
  }
}
</script>

<style scoped>
.grad-rail { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); margin: 0; padding: 14px 18px; border: 1px solid #dce6f3; border-radius: 12px; background: #fff; list-style: none; }
.grad-rail li { position: relative; display: grid; justify-items: center; gap: 7px; min-width: 0; color: #8190a5; font-size: 12px; text-align: center; }
.grad-rail li::after { position: absolute; top: 12px; left: calc(50% + 16px); right: calc(-50% + 16px); height: 1px; background: #dce6f3; content: ''; }
.grad-rail li:last-child::after { display: none; }
.grad-rail span { position: relative; z-index: 1; display: grid; width: 24px; height: 24px; place-items: center; border: 1px solid #cbd8e8; border-radius: 50%; background: #f7f9fc; font-weight: 700; }
.grad-rail b { overflow: hidden; max-width: 100%; text-overflow: ellipsis; white-space: nowrap; }
.grad-rail .is-done { color: #3272cc; }
.grad-rail .is-done span { border-color: #b9d5fb; background: #eaf3ff; }
.grad-rail .is-done::after { background: #9ec4f6; }
.grad-rail .is-active { color: #1f5fbf; }
.grad-rail .is-active span { border-color: #1f66cc; background: #286bc7; color: #fff; box-shadow: 0 0 0 4px #e7f0ff; }
@media (max-width: 860px) { .grad-rail { overflow-x: auto; grid-template-columns: repeat(6, minmax(96px, 1fr)); } }
</style>
