<template>
  <section class="aa-task-object" aria-label="当前教学任务对象">
    <div class="aa-task-object__identity">
      <strong>{{ name || '当前教学任务' }}</strong>
      <p>{{ identity || '从正式教学任务读取对象身份' }}</p>
      <small>{{ source || '来源：已发布培养方案与当前学期教学任务批次。' }}</small>
    </div>
    <dl>
      <div><dt>当前责任</dt><dd>{{ owner || '当前业务责任岗' }}</dd></div>
      <div><dt>下一责任</dt><dd>{{ nextOwner || '按正式状态流转' }}</dd></div>
    </dl>
    <span class="aa-task-object__status">{{ status || '状态待核对' }}</span>
  </section>
</template>

<script setup>
defineProps({
  name: { type: String, default: '' },
  identity: { type: String, default: '' },
  source: { type: String, default: '' },
  status: { type: String, default: '' },
  owner: { type: String, default: '' },
  nextOwner: { type: String, default: '' }
})
</script>

<style scoped>
.aa-task-object {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) auto auto;
  align-items: center;
  gap: 24px;
  padding: 14px 16px;
  border: 1px solid var(--border-200, #dbe3ed);
  border-left: 3px solid var(--primary-600, #2d5cad);
  border-radius: 11px;
  background: var(--bg-white, #fff);
  color: var(--text-900, #253951);
}
.aa-task-object__identity { min-width: 0; }
.aa-task-object strong { display: block; font-size: 15px; overflow-wrap: anywhere; }
.aa-task-object p, .aa-task-object small { display: block; margin: 4px 0 0; color: var(--text-500, #68788c); font-size: 12px; line-height: 1.55; overflow-wrap: anywhere; }
.aa-task-object dl { display: flex; gap: 28px; margin: 0; }
.aa-task-object dt { color: var(--text-500, #68788c); font-size: 11px; }
.aa-task-object dd { max-width: 210px; margin: 4px 0 0; color: var(--text-800, #334761); font-size: 12px; font-weight: 600; }
.aa-task-object__status { padding: 5px 9px; border-radius: 5px; background: #fff5e6; color: #a86b12; font-size: 12px; white-space: nowrap; }
@media (max-width: 980px) { .aa-task-object { grid-template-columns: 1fr; gap: 12px; align-items: start; } }
</style>
