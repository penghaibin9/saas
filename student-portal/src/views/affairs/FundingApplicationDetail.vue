<template>
  <dialog ref="dialog" class="fund-detail" aria-labelledby="fund-detail-title" @cancel.prevent="$emit('close')" @click="backdrop">
    <header><div><h2 id="fund-detail-title">我的奖助申请</h2><p>申请编号 {{ applicationId }}</p></div><button class="sp-btn sp-btn--ghost" @click="$emit('close')">关闭</button></header>
    <div class="fund-detail__body">
      <StateBlock v-if="loading" type="loading" text="正在读取申请进度…" />
      <div v-else-if="error" role="alert"><p>{{ error }}</p><button class="sp-btn" @click="load">重新加载</button></div>
      <template v-else-if="detail">
        <section class="fund-detail__summary"><div><h3>{{ detail.projectName }}</h3><span>{{ detail.schoolYear || '学年未记录' }}</span></div><StatusTag :text="detail.statusLabel" tone="default" /><p role="status">{{ detail.progressHint }}</p><p v-if="detail.returnReason" class="fund-detail__opinion">处理意见：{{ detail.returnReason }}</p></section>
        <dl class="fund-detail__facts"><div><dt>申请标准金额</dt><dd>{{ money(detail.requestedAmount) }}</dd></div><div><dt>批准金额</dt><dd>{{ money(detail.approvedAmount) }}</dd></div><div><dt>提交时间</dt><dd>{{ time(detail.createdAt) }}</dd></div><div v-if="detail.publicityEnd"><dt>公示截止</dt><dd>{{ time(detail.publicityEnd) }}</dd></div><div v-if="detail.resultAt"><dt>结果时间</dt><dd>{{ time(detail.resultAt) }}</dd></div></dl>
        <div class="fund-detail__columns">
          <div class="fund-detail__sections">
            <section><h3>发放进度</h3><p class="fund-detail__muted">获资助与发放分开记录，到账情况请核对实际收款。</p><p v-if="!detail.disbursements.length">学校尚未登记这份申请的发放记录。</p><article v-for="item in detail.disbursements" :key="item.disbursementId" class="fund-detail__payment"><strong>{{ item.statusLabel }}</strong><b>{{ money(item.amount) }}</b><p v-if="item.issuedAt">登记发放时间 {{ time(item.issuedAt) }}</p><p v-if="item.failReason" class="fund-detail__opinion">{{ item.failReason }}</p></article></section>
            <section v-if="detail.appealResults.length"><h3>公示申诉与复核</h3><article v-for="item in detail.appealResults" :key="item.appealId"><strong>{{ item.resultLabel || item.statusLabel }}</strong><p>{{ item.reviewOpinion || '复核完成后在这里查看结论。' }}</p><time v-if="item.reviewedAt">{{ time(item.reviewedAt) }}</time></article></section>
            <section><h3>我提交的申请说明</h3><p class="fund-detail__statement">{{ detail.statement || '未填写' }}</p></section>
            <section><FundingEvidence :application-id="applicationId" /></section>
          </div>
          <section class="fund-detail__history"><h3>办理记录</h3><p v-if="!detail.history.length">暂无可核验的历史记录。</p><ol v-else><li v-for="item in detail.history" :key="item.id"><strong>{{ item.title }}</strong><time>{{ time(item.occurredAt) }}</time><p v-if="item.description">{{ item.description }}</p></li></ol></section>
        </div>
      </template>
    </div>
    <footer><button class="sp-btn sp-btn--ghost" :disabled="loading" @click="load">刷新进度</button><button v-if="detail?.allowedActions?.includes('EDIT_RETURNED')" class="sp-btn" @click="$emit('edit', detail)">按意见修改并重提</button></footer>
  </dialog>
</template>
<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import FundingEvidence from './FundingEvidence.vue'
import { portalApi } from '../../services/portalApi'

const props = defineProps({ applicationId: { type: String, required: true } })
const emit = defineEmits(['close', 'edit'])
const dialog=ref(null), detail=ref(null), loading=ref(true), error=ref('')
let seq=0
const time=value=>value ? new Date(value).toLocaleString('zh-CN',{hour12:false}) : '时间未记录'
const money=value=>value == null || value === '' ? '尚未确定' : `${value} 元`
function backdrop(event) { if(event.target===dialog.value) { const r=dialog.value.getBoundingClientRect(); if(event.clientX<r.left || event.clientX>r.right || event.clientY<r.top || event.clientY>r.bottom) emit('close') } }
async function load() {
  const request=++seq; loading.value=true; error.value=''; detail.value=null
  try { const data=await portalApi.affairsFundingDetail(props.applicationId); if(request!==seq)return; if(String(data?.applicationId)!==props.applicationId) throw new Error('申请信息不匹配，请重新打开'); detail.value=data }
  catch(e) { if(request===seq) error.value=e?.message || '详情暂时无法读取，请重试' }
  finally { if(request===seq) loading.value=false }
}
onMounted(()=>{dialog.value?.showModal(); load()})
onBeforeUnmount(()=>{seq++; dialog.value?.close()})
</script>
<style scoped>
.fund-detail { width:min(980px,94vw); max-height:90vh; overflow:hidden; padding:0; border:1px solid var(--line); border-radius:16px; color:var(--t1); background:var(--surface); box-shadow:0 24px 80px #0004; }
.fund-detail::backdrop { background:#10172466; }
.fund-detail header,.fund-detail footer { display:flex; align-items:center; justify-content:space-between; gap:16px; padding:16px 22px; background:var(--surface-2); }
.fund-detail header { border-bottom:1px solid var(--line); }.fund-detail footer { border-top:1px solid var(--line); justify-content:flex-end; }
.fund-detail h2 { margin:0; font-size:20px; }.fund-detail h3 { margin:0 0 10px; font-size:15px; }.fund-detail p { margin:8px 0; line-height:1.6; overflow-wrap:anywhere; }.fund-detail header p { margin:4px 0 0; font-size:12px; color:var(--t3); }
.fund-detail__body { padding:20px 22px; box-sizing:border-box; max-height:calc(90vh - 160px); overflow:auto; }.fund-detail__summary { display:flex; flex-wrap:wrap; justify-content:space-between; gap:8px; padding:16px; background:var(--pri-bg); border-radius:10px; }.fund-detail__summary p { flex-basis:100%; margin:0; }.fund-detail__summary span,.fund-detail__muted,.fund-detail time { color:var(--t3); font-size:12px; }
.fund-detail__facts { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; margin:20px 0; }.fund-detail dt { font-size:12px; color:var(--t3); margin-bottom:6px; }.fund-detail dd { margin:0; font-weight:600; font-variant-numeric:tabular-nums; }
.fund-detail__columns { display:grid; grid-template-columns:minmax(0,1.5fr) minmax(220px,1fr); gap:20px; }.fund-detail__sections { display:grid; gap:18px; }.fund-detail__sections>section { padding:16px; border:1px solid var(--line); border-radius:10px; }.fund-detail__statement,.fund-detail__opinion { white-space:pre-wrap; }.fund-detail__payment { display:flex; flex-wrap:wrap; justify-content:space-between; gap:8px; padding-top:12px; border-top:1px solid var(--line); }.fund-detail__payment p { flex-basis:100%; }
.fund-detail__history { padding:16px; background:var(--surface-2); border-radius:10px; }.fund-detail ol { padding-left:18px; margin:14px 0 0; border-left:1px solid var(--line); list-style:none; }.fund-detail li { position:relative; padding-bottom:20px; font-size:13px; }.fund-detail li::before { content:''; position:absolute; top:5px; left:-22px; width:7px; height:7px; border-radius:50%; background:var(--pri); }.fund-detail time { display:block; margin-top:5px; }
@media(max-width:760px){.fund-detail__columns{grid-template-columns:1fr}.fund-detail__facts{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
