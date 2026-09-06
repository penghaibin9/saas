<template>
  <view class="fund-result">
    <view class="fund-result__head"><button @click="$emit('close')">返回申请</button><text>我的奖助申请</text><button :disabled="loading" @click="load">刷新</button></view>
    <scroll-view scroll-y class="fund-result__body">
      <view v-if="loading" class="fund-result__state">正在读取申请进度…</view>
      <view v-else-if="error" class="fund-result__state"><text>{{ error }}</text><button @click="load">重新加载</button></view>
      <view v-else-if="detail" class="fund-result__stack">
        <view class="fund-result__summary"><text class="fund-result__eyebrow">{{ detail.schoolYear || '学年未记录' }}</text><text class="fund-result__title">{{ detail.projectName }}</text><MobileStatusTag :status="detail.status" :label="detail.statusLabel" /><text class="fund-result__hint">{{ detail.progressHint }}</text><text v-if="detail.returnReason" class="fund-result__opinion">处理意见：{{ detail.returnReason }}</text></view>
        <view class="fund-result__card"><text class="fund-result__label">申请信息</text><view class="fund-result__money"><view><text>申请标准金额</text><text class="fund-result__money-value">{{ money(detail.requestedAmount) }}</text></view><view><text>批准金额</text><text class="fund-result__money-value">{{ money(detail.approvedAmount) }}</text></view></view><view class="fund-result__fact"><text>提交时间</text><text>{{ time(detail.createdAt) }}</text></view><view v-if="detail.publicityEnd" class="fund-result__fact"><text>公示截止</text><text>{{ time(detail.publicityEnd) }}</text></view><view v-if="detail.resultAt" class="fund-result__fact"><text>结果时间</text><text>{{ time(detail.resultAt) }}</text></view></view>
        <view class="fund-result__card"><text class="fund-result__label">发放进度</text><text class="fund-result__muted">获资助与发放分开记录，到账情况请核对实际收款。</text><text v-if="!detail.disbursements.length" class="fund-result__hint">学校尚未登记发放记录。</text><view v-for="item in detail.disbursements" :key="item.disbursementId" class="fund-result__payment"><view class="fund-result__fact"><text>{{ item.statusLabel }}</text><text class="fund-result__money-value">{{ money(item.amount) }}</text></view><text v-if="item.issuedAt" class="fund-result__muted">登记发放 {{ time(item.issuedAt) }}</text><text v-if="item.failReason" class="fund-result__opinion">{{ item.failReason }}</text></view></view>
        <view v-if="detail.appealResults.length" class="fund-result__card"><text class="fund-result__label">公示申诉与复核</text><view v-for="item in detail.appealResults" :key="item.appealId" class="fund-result__payment"><text>{{ item.resultLabel || item.statusLabel }}</text><text class="fund-result__hint">{{ item.reviewOpinion || '复核完成后在这里查看结论。' }}</text><text v-if="item.reviewedAt" class="fund-result__muted">{{ time(item.reviewedAt) }}</text></view></view>
        <view class="fund-result__card"><text class="fund-result__label">我提交的申请说明</text><text class="fund-result__statement">{{ detail.statement || '未填写' }}</text><MobileFundingEvidence :application-id="applicationId" /></view>
        <view class="fund-result__card"><text class="fund-result__label">办理记录</text><text v-if="!detail.history.length" class="fund-result__muted">暂无可核验的历史记录。</text><view v-for="item in detail.history" :key="item.id" class="fund-result__event"><text>{{ item.title }}</text><text class="fund-result__muted">{{ time(item.occurredAt) }}</text><text v-if="item.description" class="fund-result__hint">{{ item.description }}</text></view></view>
      </view>
    </scroll-view>
    <view v-if="detail?.allowedActions?.includes('EDIT_RETURNED')" class="fund-result__footer"><button @click="$emit('edit',detail)">按意见修改并重提</button></view>
  </view>
</template>
<script setup>
import { onUnmounted, ref, watch } from 'vue'
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
const props=defineProps({applicationId:{type:String,required:true}})
const emit=defineEmits(['close','edit'])
const detail=ref(null), loading=ref(true), error=ref('')
let seq=0
const money=value=>value == null || value === '' ? '尚未确定' : `${value} 元`
const time=value=>value ? new Date(value).toLocaleString('zh-CN',{hour12:false}) : '时间未记录'
async function load() {
  const request=++seq; loading.value=true; error.value=''; detail.value=null
  try { const data=await studentApi.getFundingDetail(props.applicationId); if(request!==seq)return; if(String(data?.applicationId)!==props.applicationId) throw new Error('申请信息不匹配，请重新打开'); detail.value=data }
  catch(e) { if(request===seq) error.value=normalizeError(e).text || '详情暂时无法读取，请重试' }
  finally { if(request===seq) loading.value=false }
}
watch(()=>props.applicationId,load,{immediate:true})
onUnmounted(()=>{seq++})
</script>
<style scoped>
.fund-result { position:fixed; inset:0; z-index:200; display:flex; flex-direction:column; color:var(--text-primary,#243c31); background:var(--bg-page,#f4f6f8); }
.fund-result__head { display:flex; justify-content:space-between; align-items:center; padding:calc(8px + env(safe-area-inset-top)) 12px 8px; background:var(--bg-card,#fff); border-bottom:1px solid var(--border-light,#e3e8e6); flex-shrink:0; font-weight:600; }.fund-result__head button { margin:0; padding:0 8px; line-height:36px; min-height:36px; background:transparent; color:var(--brand-primary,#278578); font-size:13px; }.fund-result button::after { border:0; }
.fund-result__body { flex:1; height:0; min-height:0; }.fund-result__stack { display:flex; flex-direction:column; gap:12px; padding:16px 14px calc(24px + env(safe-area-inset-bottom)); }.fund-result__summary { display:flex; flex-direction:column; align-items:flex-start; gap:10px; padding:18px; border-radius:14px; background:var(--primary-50,#eaf4ef); }.fund-result__title { font-size:20px; font-weight:650; }.fund-result__eyebrow { color:var(--text-secondary,#607568); font-size:12px; }
.fund-result__card { padding:16px; border:1px solid var(--border-light,#e3e8e6); border-radius:12px; background:var(--bg-card,#fff); }.fund-result__label { display:block; margin-bottom:12px; font-weight:600; font-size:15px; }.fund-result__money { display:flex; gap:16px; margin-bottom:14px; }.fund-result__money>view { flex:1; min-width:0; }.fund-result__money text:not(.fund-result__money-value) { display:block; margin-bottom:6px; color:var(--text-secondary,#65776c); font-size:12px; }.fund-result__money-value { font-size:17px; font-weight:650; font-variant-numeric:tabular-nums; }
.fund-result__fact { display:flex; justify-content:space-between; align-items:baseline; gap:12px; margin:9px 0; font-size:13px; }.fund-result__fact>text:first-child { flex-shrink:0; }.fund-result__fact>text:last-child { text-align:right; }.fund-result__hint,.fund-result__statement,.fund-result__opinion { display:block; font-size:14px; line-height:1.7; white-space:pre-wrap; overflow-wrap:anywhere; }.fund-result__muted { display:block; margin:6px 0; font-size:12px; line-height:1.6; color:var(--text-secondary,#65776c); }.fund-result__payment { padding-top:12px; margin-top:10px; border-top:1px solid var(--border-light,#e3e8e6); }
.fund-result__event { display:flex; flex-direction:column; margin-left:4px; padding:0 0 18px 16px; border-left:2px solid var(--border-light,#dbe5df); font-size:14px; }.fund-result__secondary { margin:12px 0 0; background:var(--primary-50,#eaf4ef); color:var(--brand-primary,#278578); font-size:13px; }.fund-result__footer { padding:10px 16px calc(10px + env(safe-area-inset-bottom)); background:var(--bg-card,#fff); border-top:1px solid var(--border-light,#e3e8e6); }.fund-result__footer button { background:var(--brand-primary,#278578); color:#fff; font-size:15px; }.fund-result__state { padding:32px 20px; text-align:center; }
</style>
