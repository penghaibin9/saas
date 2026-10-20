<template>
  <view class="lifecycle-card">
    <view class="head"><view><text class="kicker">跨域里程碑</text><text class="title">{{ title }}</text></view><button size="mini" :loading="loading" @click="load">刷新</button></view>
    <view v-if="error" class="error">{{ error }}</view>
    <view v-for="item in items" :key="item.id" class="fact">
      <text class="time">{{ date(item.eventTime) }}</text>
      <view><text class="fact-title">{{ item.title }}</text><text class="fact-type">{{ item.summary || item.factType }}</text></view>
    </view>
    <view v-if="!loading && !items.length" class="empty">当前授权范围内暂无里程碑</view>
    <view v-if="compareSummary" class="compare">
      <text>比较摘要</text><text>新增 {{ compareSummary.added || 0 }}</text><text>删除 {{ compareSummary.removed || 0 }}</text><text>修改 {{ compareSummary.modified || 0 }}</text>
    </view>
    <text v-if="mode === 'teacher'" class="notice">移动端仅展示摘要；复杂比较请前往管理端。</text>
  </view>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '@/services/documentLifecycleApi'
import { normalizeError } from '@/services/request'
const props=defineProps({studentId:{type:[String,Number],required:true},mode:{type:String,default:'student'},title:{type:String,default:'学生成长时间线'},compareSummary:{type:Object,default:null}})
const items=ref([]),loading=ref(false),error=ref('')
async function load(){loading.value=true;error.value='';try{const data=await api.milestones(props.studentId);items.value=data?.items||[]}catch(e){error.value=normalizeError(e)?.message||'加载失败'}finally{loading.value=false}}
const date=value=>value?new Date(value).toLocaleDateString():'—'
onMounted(load)
</script>

<style scoped lang="scss">
.lifecycle-card{padding:28rpx;border-radius:20rpx;background:#fff}.head{display:flex;justify-content:space-between;align-items:center}.kicker,.title{display:block}.kicker{font-size:22rpx;color:#2563eb}.title{margin-top:6rpx;font-size:32rpx;font-weight:700}.fact{display:flex;gap:20rpx;padding:22rpx 0;border-bottom:1rpx solid #eef2f7}.time{width:150rpx;color:#64748b;font-size:22rpx}.fact-title,.fact-type{display:block}.fact-title{font-weight:600}.fact-type,.empty,.notice{margin-top:6rpx;color:#64748b;font-size:22rpx}.error{padding:20rpx 0;color:#b91c1c}.compare{display:flex;gap:14rpx;flex-wrap:wrap;padding-top:20rpx;color:#334155}
</style>
