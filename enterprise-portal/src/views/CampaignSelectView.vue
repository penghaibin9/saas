<script setup>
import { computed,onMounted,ref } from 'vue'
import { useRouter } from 'vue-router'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import { setSelectedCampaignId } from '../services/request'
const router=useRouter(),loading=ref(true),error=ref(''),items=ref([])
const activeItems=computed(()=>items.value.filter(item=>!['CLOSED','ARCHIVED'].includes(String(item.status||''))))
async function load(){loading.value=true;error.value='';try{const data=await enterpriseInternshipApi.campaigns();items.value=Array.isArray(data)?data:(data?.items||[])}catch(e){error.value=e.message||'招聘季列表加载失败'}finally{loading.value=false}}
async function enter(item){const id=item.id||item.campaignId;if(!id)return;setSelectedCampaignId(id);await router.push('/home')}
onMounted(load)
</script>
<template><main class="select-page"><section class="panel"><div class="brand">跃科 · 企业协同中心</div><h1>选择招聘季</h1><p>企业范围由登录成员身份确定；这里只选择要进入的招聘季，不允许选择 companyId。</p><div v-if="error" class="ep-error">{{ error }}。A01 企业招聘季列表接口未开放时，本页保持 fail-closed。</div><div v-if="loading" class="ep-card ep-empty">正在读取当前企业可参与招聘季…</div><div v-else-if="!activeItems.length" class="ep-card ep-empty">当前没有可进入的招聘季</div><div v-else class="campaigns"><button v-for="item in activeItems" :key="item.id||item.campaignId" class="campaign ep-card" type="button" @click="enter(item)"><div><strong>{{ item.campaignName||item.name }}</strong><span>{{ item.status }}</span></div><p>{{ item.phaseLabel||'阶段由服务端状态与时间窗口派生' }}</p><small>进入招聘工作台 →</small></button></div><button class="back" type="button" @click="router.push('/login')">返回登录</button></section></main></template>
<style scoped>.select-page{min-height:100vh;background:var(--page);padding:56px 20px}.panel{width:min(900px,100%);margin:0 auto}.brand{color:var(--pri);font-weight:800}.panel h1{margin:12px 0 6px;font-size:28px}.panel>p{margin:0 0 22px;color:var(--t3)}.campaigns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.campaign{text-align:left;padding:18px;border-color:var(--line)}.campaign:hover{border-color:var(--pri-100);box-shadow:0 8px 24px rgba(47,107,255,.08)}.campaign>div{display:flex;justify-content:space-between;gap:12px}.campaign strong{font-size:16px}.campaign span{font-size:11px;color:var(--pri);background:var(--pri-50);padding:3px 7px;border-radius:4px}.campaign p{color:var(--t3);font-size:13px}.campaign small{color:var(--pri);font-weight:600}.back{margin-top:18px;border:0;background:transparent;color:var(--t3)}@media(max-width:700px){.campaigns{grid-template-columns:1fr}}</style>
