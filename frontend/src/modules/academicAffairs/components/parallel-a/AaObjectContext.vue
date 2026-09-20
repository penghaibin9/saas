<template>
  <section class="aa-a-object" aria-label="当前业务对象">
    <div class="aa-a-object__identity"><strong>{{ name }}</strong><p>{{ identity }}</p><small v-if="source">{{ source }}</small></div>
    <dl><div><dt>当前状态</dt><dd>{{ status || '状态待核对' }}</dd></div><div><dt>当前责任</dt><dd>{{ owner || '服务端未提供具体受理人' }}</dd></div></dl>
    <slot />
  </section>
</template>
<script setup>
defineProps({ name: { type: String, required: true }, identity: { type: String, default: '' }, source: { type: String, default: '' }, status: { type: String, default: '' }, owner: { type: String, default: '' } })
</script>
<style scoped>
.aa-a-object{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:16px;background:var(--bg-white,#fff);border:1px solid var(--border-200,#dbe3ed);border-left:3px solid var(--primary-600,#2d5cad);border-radius:10px;margin-bottom:14px;color:var(--text-900,#253951)}
.aa-a-object__identity{min-width:0}.aa-a-object strong{font-size:15px;overflow-wrap:anywhere}.aa-a-object p,.aa-a-object small{font-size:12px;line-height:1.7;color:var(--text-500,#68788c);margin:4px 0 0;overflow-wrap:anywhere}
dl{display:flex;gap:26px;margin:0;flex-wrap:wrap}dt{font-size:12px;color:var(--text-500,#68788c)}dd{margin:5px 0 0;font-size:13px;max-width:230px;overflow-wrap:anywhere}
@media(max-width:900px){.aa-a-object{align-items:flex-start;flex-direction:column}dl{gap:18px}}
</style>
