<template>
  <section class="aeob" aria-label="当前考务业务对象">
    <div class="aeob-main">
      <span class="aeob-kicker">当前业务对象</span>
      <strong>{{ title || '等待选择考务对象' }}</strong>
      <span class="aeob-id">{{ objectId || '尚未载入对象编号' }}</span>
    </div>
    <div class="aeob-field"><span>对象来源</span><strong>{{ source || '考务管理' }}</strong></div>
    <div class="aeob-field"><span>当前状态</span><strong>{{ status || '待确认' }}</strong></div>
    <div class="aeob-field"><span>当前责任人</span><strong>{{ owner || '按正式权限判定' }}</strong></div>
    <div class="aeob-field"><span>当前阻断</span><strong :class="{ 'is-risk': blocked }">{{ blocker || '无已知阻断' }}</strong></div>
    <div class="aeob-field"><span>下一责任岗位</span><strong>{{ nextOwner || '按办理结果流转' }}</strong></div>
  </section>
</template>

<script>
export default {
  name: 'AaExamObjectBar',
  props: {
    title: { type: String, default: '' }, objectId: { type: String, default: '' },
    source: { type: String, default: '' }, status: { type: String, default: '' },
    owner: { type: String, default: '' }, blocker: { type: String, default: '' },
    nextOwner: { type: String, default: '' }, blocked: { type: Boolean, default: false }
  }
}
</script>

<style scoped>
.aeob { display: grid; grid-template-columns: minmax(240px, 1.45fr) repeat(5, minmax(120px, 1fr)); gap: 0; margin-bottom: 12px; overflow: hidden; border: 1px solid #dce5f2; border-radius: 12px; background: #fff; }
.aeob-main, .aeob-field { min-width: 0; padding: 12px 14px; border-right: 1px solid #edf1f7; }
.aeob-field:last-child { border-right: 0; }
.aeob-main { background: #f4f8ff; }
.aeob-kicker, .aeob-field span { display: block; margin-bottom: 4px; color: #71839f; font-size: 11px; }
.aeob-main strong, .aeob-field strong { display: block; color: #17365f; font-size: 13px; line-height: 1.45; overflow-wrap: anywhere; }
.aeob-main strong { font-size: 15px; }
.aeob-id { display: block; margin-top: 3px; color: #75859d; font: 11px/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.aeob-field strong.is-risk { color: #b45309; }
@media (max-width: 1180px) { .aeob { grid-template-columns: repeat(3, minmax(0, 1fr)); } .aeob-main { grid-column: span 3; } }
@media (max-width: 720px) { .aeob { grid-template-columns: 1fr; } .aeob-main { grid-column: auto; } .aeob-main, .aeob-field { border-right: 0; border-bottom: 1px solid #edf1f7; } }
</style>
