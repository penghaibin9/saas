<template>
  <section class="leave-workspace">
    <header class="leave-heading"><div><h1>请假与返校</h1><p>申请、查进度、办返校，都在这里。</p></div><div class="leave-buttons"><button class="sp-btn sp-btn--ghost" @click="$emit('reload')">刷新</button><button class="sp-btn" :aria-expanded="applying" @click="applying = !applying">{{ applying ? '收起申请' : '申请请假' }}</button></div></header>
    <section v-show="applying" class="leave-apply"><slot name="apply" /></section>
    <div class="leave-grid">
      <aside class="leave-list sp-card" aria-label="我的请假记录">
        <div class="leave-filter"><label for="leave-status">我的记录 <span>{{ records.length }}</span></label><select id="leave-status" v-model="filter" class="sp-inp"><option value="all">全部记录</option><option value="active">办理中</option><option value="mine">需要我处理</option><option value="done">已结束</option></select></div>
        <StateBlock v-if="!filtered.length" type="empty" text="暂无符合条件的记录" />
        <button v-for="item in filtered" :key="item.id" class="leave-record" :class="{ selected: selectedId === item.id }" :aria-pressed="selectedId === item.id" @click="select(item.id)">
          <span class="leave-record-top"><strong>{{ item.leaveTypeLabel }}</strong><StatusTag :text="item.statusLabel" :tone="item.tone" /></span>
          <span>{{ item.startDate }} 至 {{ item.endDate }}</span><small>{{ item.days }} 天 · {{ item.reason || '查看申请详情' }}</small>
        </button>
      </aside>
      <section class="leave-detail sp-card" aria-label="请假办理详情" aria-live="polite">
        <StateBlock v-if="loading" type="loading" text="正在读取最新办理进度…" />
        <div v-else-if="error" role="alert"><StateBlock type="error" :text="error" /><button class="sp-btn sp-btn--ghost" @click="loadDetail">重新加载</button></div>
        <StateBlock v-else-if="!detail" type="empty" text="选择一条记录查看进度，或发起新的请假申请。" />
        <template v-else>
          <div class="leave-status"><div><StatusTag :text="detail.statusLabel" :tone="detail.tone" /><h2>{{ detail.leaveTypeLabel }} · {{ detail.days }} 天</h2><p>{{ detail.nextHint }}</p></div><div v-if="detail.handler" class="leave-handler"><small>当前处理人</small><strong>{{ detail.handler }}</strong></div></div>
          <dl class="leave-facts"><div><dt>开始时间</dt><dd>{{ date(detail.startTime, true) }}</dd></div><div><dt>结束时间</dt><dd>{{ date(detail.endTime, true) }}</dd></div><div class="wide"><dt>请假事由</dt><dd>{{ detail.reason || '未填写' }}</dd></div><div v-if="detail.returnReason" class="wide leave-opinion"><dt>处理意见</dt><dd>{{ detail.returnReason }}</dd></div></dl>
          <div class="leave-buttons leave-next"><button v-if="allows('EDIT_RETURNED') || allows('RESUBMIT')" class="sp-btn" :disabled="busy" @click="$emit('edit', detail)">修改后重新提交</button><button v-if="allows('SUBMIT_CANCEL')" class="sp-btn" :disabled="busy" @click="$emit('cancel', detail)">我已返校，申请销假</button><button v-if="allows('SUBMIT_EXTENSION')" class="sp-btn sp-btn--ghost" :disabled="busy" @click="$emit('extend', detail)">申请续假</button></div>
          <slot name="followup" :item="detail" />
          <section v-if="detail.extensions.length" class="leave-section"><h3>续假记录</h3><article v-for="item in detail.extensions" :key="item.id"><strong>{{ date(item.oldEndTime) }} → {{ date(item.newEndTime) }}</strong><StatusTag :text="item.statusLabel" /><p>{{ item.reason }}</p></article></section>
          <section v-if="detail.cancelRecords.length" class="leave-section"><h3>返校记录</h3><article v-for="item in detail.cancelRecords" :key="item.id"><strong>{{ item.statusLabel }}</strong><p>{{ item.proofNote || '已提交返校申请' }}</p><small v-if="item.actualReturnAt">实际返校：{{ date(item.actualReturnAt, true) }}</small><p v-if="item.confirmNote">{{ item.confirmNote }}</p></article></section>
          <section class="leave-section leave-materials"><div><h3>证明与补交材料</h3><p>老师要求补充的材料，可在材料中心查看并提交。</p></div><RouterLink class="sp-btn sp-btn--ghost" :to="{ path: '/materials', query: { bizType: 'LEAVE', bizId: detail.id } }">查看材料要求</RouterLink></section>
          <section class="leave-section"><h3>办理记录</h3><p v-if="!detail.timeline.length" class="sp-muted">暂无办理记录</p><ol class="leave-timeline"><li v-for="event in detail.timeline" :key="event.eventId"><span><strong>{{ event.actionLabel }}</strong><small>{{ event.operator || '系统' }}</small></span><time>{{ date(event.occurredAt, true) }}</time></li></ol></section>
        </template>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { affairsFourEndApi } from '../../services/affairsFourEndApi'
import { leaveDate as date, leaveError, presentLeave } from '../../services/leavePresentation'
const props = defineProps({ items: { type: Array, default: () => [] }, busy: Boolean })
defineEmits(['reload', 'edit', 'cancel', 'extend'])
const route = useRoute(), router = useRouter()
const applying = ref(false), filter = ref('all'), selectedId = ref(''), detail = ref(null), loading = ref(false), error = ref('')
const records = computed(() => props.items.map(presentLeave))
const done = ['CLOSED', 'ARCHIVED', 'REJECTED', 'CANCELLED']
const filtered = computed(() => records.value.filter(item => filter.value === 'all' || (filter.value === 'done' ? done.includes(item.status) : filter.value === 'mine' ? item.allowedActions?.some(a => ['EDIT_RETURNED', 'RESUBMIT', 'SUBMIT_CANCEL', 'SUBMIT_EXTENSION'].includes(a)) : !done.includes(item.status))))
const allows = (action) => Array.isArray(detail.value?.allowedActions) && detail.value.allowedActions.includes(action)
let epoch = 0
async function loadDetail() {
  const ticket = ++epoch
  if (!selectedId.value) { detail.value = null; return }
  loading.value = true; error.value = ''; detail.value = null
  try { const data = await affairsFourEndApi.getLeaveDetail(selectedId.value); if (ticket === epoch) detail.value = data }
  catch (e) { if (ticket === epoch) error.value = leaveError(e, '暂时无法读取这条申请，请重试。') }
  finally { if (ticket === epoch) loading.value = false }
}
function select(id) { router.replace({ path: route.path, query: { ...route.query, recordId: id } }) }
watch(() => [route.query.recordId, props.items], () => {
  selectedId.value = String(route.query.recordId || records.value[0]?.id || '')
  loadDetail()
}, { immediate: true })
onBeforeUnmount(() => { epoch++ })
</script>

<style scoped>
.leave-workspace{color:var(--t1)}.leave-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:16px}.leave-heading h1{font-size:21px;margin:0}.leave-heading p{margin:6px 0 0;font-size:13px;color:var(--t3)}.leave-buttons{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.leave-grid{display:grid;grid-template-columns:minmax(230px,290px) minmax(0,1fr);gap:16px;align-items:start}.leave-list{padding:0;overflow:hidden}.leave-filter{padding:16px;border-bottom:1px solid var(--line)}.leave-filter label{display:flex;justify-content:space-between;margin-bottom:10px;font-weight:600}.leave-filter span{color:var(--t3)}.leave-record{display:flex;flex-direction:column;gap:10px;box-sizing:border-box;width:100%;padding:18px 16px;border:0;border-bottom:1px solid var(--line);border-left:3px solid transparent;background:var(--surface);text-align:left;color:var(--t2);cursor:pointer;font-size:12px}.leave-record.selected{background:var(--pri-50);border-left-color:var(--pri)}.leave-record-top{display:flex;align-items:center;justify-content:space-between;gap:8px}.leave-record strong{font-size:14px;color:var(--t1)}.leave-record small{color:var(--t3);display:block;max-width:100%;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.leave-detail{padding:24px;min-height:360px}.leave-status{display:flex;align-items:start;justify-content:space-between;gap:16px}.leave-status h2{font-size:22px;margin:12px 0 8px}.leave-status p{font-size:13px;color:var(--t3);line-height:1.7;margin:0}.leave-handler{background:var(--bg);padding:12px 16px;border-radius:8px;flex-shrink:0}.leave-handler small,.leave-handler strong{display:block}.leave-handler small{color:var(--t3);font-size:11px;margin-bottom:5px}.leave-facts{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:24px 0}.leave-facts .wide{grid-column:1/-1}.leave-facts dt{font-size:12px;color:var(--t3);margin-bottom:7px}.leave-facts dd{margin:0;font-size:14px;line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere}.leave-opinion{padding:12px;background:var(--pri-50);border-left:3px solid var(--pri);border-radius:4px}.leave-section{border-top:1px solid var(--line);padding-top:18px;margin-top:22px}.leave-section h3{margin:0 0 12px;font-size:14px}.leave-section article{padding:12px 0;font-size:13px}.leave-section article>strong{margin-right:12px}.leave-section p{color:var(--t3);font-size:13px;line-height:1.6}.leave-materials{display:flex;align-items:center;justify-content:space-between;gap:12px}.leave-materials p{margin:0}.leave-timeline{padding:0;margin:0;list-style:none}.leave-timeline li{display:flex;justify-content:space-between;gap:12px;padding:12px 0;border-bottom:1px solid var(--line);font-size:12px}.leave-timeline strong{font-weight:500}.leave-timeline small{margin-left:12px;color:var(--t3)}.leave-timeline time{color:var(--t3);font-variant-numeric:tabular-nums}.leave-apply{margin-bottom:16px}.leave-record:focus-visible{outline:2px solid var(--pri);outline-offset:-3px}@media(max-width:920px){.leave-grid{grid-template-columns:1fr}.leave-list{max-height:300px;overflow:auto}.leave-detail{padding:18px}.leave-heading{align-items:start}.leave-handler{display:none}}
</style>
