<template>
  <ol class="aa-textbook-stage" aria-label="教材业务进度">
    <li v-for="(item, index) in stages" :key="item.label" :class="{ 'is-current': index === current, 'is-done': index < current }">
      <span>{{ index < current ? '✓' : index + 1 }}</span>
      <div><strong>{{ item.label }}</strong><small>{{ index === current ? '当前设计视角' : '按真实状态解锁' }}</small></div>
    </li>
  </ol>
</template>

<script>
export default {
  name: 'AaTextbookStageRail',
  props: { current: { type: Number, default: 0 } },
  data() {
    return { stages: [
      { label: '教学任务申报' }, { label: '审核征订' }, { label: '到货验收' },
      { label: '发放签收' }, { label: '费用库存' }
    ] }
  }
}
</script>

<style scoped>
.aa-textbook-stage { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; margin: 0; padding: 13px 16px; list-style: none; border: 1px solid #d9e3ef; border-radius: 10px; background: #fff; }
.aa-textbook-stage li { position: relative; display: flex; align-items: flex-start; gap: 9px; min-width: 0; color: #8a96a8; }
.aa-textbook-stage li:not(:last-child)::after { content: ''; position: absolute; top: 13px; right: 8px; width: calc(100% - 132px); height: 1px; background: #dbe3ed; }
.aa-textbook-stage li > span { display: grid; place-items: center; flex: 0 0 26px; width: 26px; height: 26px; border: 1px solid #dbe3ed; border-radius: 50%; background: #fff; font-size: 12px; font-weight: 700; }
.aa-textbook-stage li > div { display: grid; gap: 4px; min-width: 0; }
.aa-textbook-stage strong { color: #46566d; font-size: 12px; white-space: nowrap; }
.aa-textbook-stage small { font-size: 10px; white-space: nowrap; }
.aa-textbook-stage li.is-current > span { color: #fff; border-color: #2d66bd; background: #2d66bd; }
.aa-textbook-stage li.is-current strong { color: #2458a7; }
.aa-textbook-stage li.is-done > span { color: #278259; border-color: #b9dfcc; background: #edf9f2; }
@media (max-width: 980px) { .aa-textbook-stage { grid-template-columns: repeat(3, minmax(0, 1fr)); } .aa-textbook-stage li::after { display: none; } }
</style>
