<template>
  <section class="aa-textbook-object" aria-label="当前教材业务对象">
    <div class="aa-textbook-object__main">
      <strong>{{ title }}</strong>
      <span>{{ objectType }} · {{ objectId || '正式编号待生成' }}<template v-if="termName"> · {{ termName }}</template></span>
      <small>来源：{{ source }} · <b>{{ statusLabel }}</b></small>
    </div>
    <dl>
      <div><dt>当前责任</dt><dd>{{ currentOwner }}</dd></div>
      <div><dt>下一责任</dt><dd>{{ nextOwner }}</dd></div>
    </dl>
  </section>
</template>

<script>
export default {
  name: 'AaTextbookObjectBar',
  props: {
    title: { type: String, required: true },
    objectType: { type: String, required: true },
    objectId: { type: [String, Number], default: '' },
    termName: { type: String, default: '' },
    source: { type: String, required: true },
    statusLabel: { type: String, required: true },
    currentOwner: { type: String, required: true },
    nextOwner: { type: String, required: true }
  }
}
</script>

<style scoped>
.aa-textbook-object { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 13px 16px; border: 1px solid #d9e3f0; border-left: 3px solid #2f66bd; border-radius: 10px; background: #fff; }
.aa-textbook-object__main { display: grid; gap: 3px; min-width: 0; }
.aa-textbook-object__main strong { color: #18314f; font-size: 15px; }
.aa-textbook-object__main span, .aa-textbook-object__main small { color: #6c7c92; font-size: 12px; }
.aa-textbook-object__main b { color: #a56812; font-weight: 600; }
.aa-textbook-object dl { display: grid; grid-template-columns: repeat(2, minmax(112px, 1fr)); gap: 24px; margin: 0; }
.aa-textbook-object dl div { display: grid; gap: 3px; }
.aa-textbook-object dt { color: #8290a3; font-size: 11px; }
.aa-textbook-object dd { margin: 0; color: #20344f; font-size: 12px; font-weight: 650; }
@media (max-width: 820px) { .aa-textbook-object { align-items: flex-start; flex-direction: column; } .aa-textbook-object dl { width: 100%; } }
</style>
