<template>
  <section class="aa-schedule-object" aria-label="当前排课业务对象">
    <div class="aa-schedule-object__identity">
      <strong>{{ name || '当前对象待选择' }}</strong>
      <p>{{ identity || '请从当前页面选择正式业务对象' }}</p>
      <small>{{ source || '来源：正式课表与排课服务' }}</small>
    </div>
    <dl>
      <div><dt>当前状态</dt><dd>{{ status || '状态待核对' }}</dd></div>
      <div><dt>当前责任</dt><dd>{{ owner || '教务排课岗' }}</dd></div>
      <div><dt>下一责任</dt><dd>{{ nextOwner || '按正式状态流转' }}</dd></div>
    </dl>
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
.aa-schedule-object { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 13px 15px; border: 1px solid var(--border-200, #dbe3ed); border-left: 3px solid var(--primary-600, #2e63b8); border-radius: 11px; background: var(--bg-white, #fff); }
.aa-schedule-object__identity { min-width: 0; }
.aa-schedule-object__identity strong { display: block; color: var(--text-900, #193252); font-size: 15px; overflow-wrap: anywhere; }
.aa-schedule-object p, .aa-schedule-object small { display: block; margin: 4px 0 0; color: var(--text-500, #68788c); font-size: 12px; line-height: 1.55; overflow-wrap: anywhere; }
.aa-schedule-object dl { display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 24px; margin: 0; }
.aa-schedule-object dt { color: var(--text-400, #8794aa); font-size: 11px; }
.aa-schedule-object dd { margin: 4px 0 0; color: var(--text-800, #283d59); font-size: 12px; font-weight: 600; }
@media (max-width: 960px) { .aa-schedule-object { align-items: flex-start; flex-direction: column; } .aa-schedule-object dl { width: 100%; } }
@media (max-width: 640px) { .aa-schedule-object dl { grid-template-columns: 1fr; gap: 10px; } }
</style>
