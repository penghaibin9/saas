<template>
  <section v-if="receipt" class="aa-a-receipt" :class="{ 'is-pending': receipt.pending }" role="status" aria-live="polite">
    <strong>{{ receipt.title }}</strong><dl><div><dt>业务对象</dt><dd>{{ receipt.object }}</dd></div><div><dt>实际状态</dt><dd>{{ receipt.status }}</dd></div><div><dt>办理时间</dt><dd>{{ receipt.time || '服务端未提供办理时间' }}</dd></div></dl>
    <p>{{ receipt.next }}</p><slot />
  </section>
</template>
<script setup>
defineProps({ receipt: { type: Object, default: null } })
</script>
<style scoped>
.aa-a-receipt{padding:16px;border:1px solid var(--success-200,#b9dccc);border-radius:10px;background:var(--success-50,#f0faf5);margin:0 0 14px;color:var(--text-900,#253951)}.aa-a-receipt.is-pending{border-color:var(--warning-200,#ebd3a5);background:var(--warning-50,#fff8ec)}strong{font-size:14px}dl{display:flex;gap:24px;flex-wrap:wrap;margin:12px 0}dt{font-size:12px;color:var(--text-500,#68788c)}dd{margin:4px 0 0;font-size:13px}p{margin:8px 0 0;font-size:13px;line-height:1.6}
</style>
