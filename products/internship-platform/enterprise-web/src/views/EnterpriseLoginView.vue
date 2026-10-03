<script setup>
import { reactive,ref,watch } from 'vue'
import { useRouter } from 'vue-router'
import { enterpriseAuthApi } from '../services/authApi'
import { getSelectedCampaignId } from '../services/request'

const router=useRouter(),loading=ref(false),error=ref(''),contexts=ref([]),selectedMemberId=ref('')
const form=reactive({tenantCode:'',loginName:'',password:''})
watch(()=>[form.tenantCode,form.loginName],()=>{contexts.value=[];selectedMemberId.value='';error.value=''})
// Authority contract: 前端不会直接提交 companyId 作为 Authority；只回传 A01 提供的 memberId 供服务端重新校验。
async function submit(){
  if(contexts.value.length&&!selectedMemberId.value){error.value='请选择要进入的企业';return}
  loading.value=true;error.value=''
  try{
    await enterpriseAuthApi.login({...form,...(selectedMemberId.value?{memberId:selectedMemberId.value}:{})})
    await router.push(getSelectedCampaignId()?'/home':'/campaign-select')
  }catch(e){
    const options=Array.isArray(e?.details?.contexts)?e.details.contexts:[]
    if(e?.bizCode==='ENTERPRISE_CONTEXT_REQUIRED'&&options.length){
      contexts.value=options.map(item=>({memberId:String(item.memberId||''),companyName:item.companyName||'未命名企业',memberRole:item.memberRole||'成员'})).filter(item=>item.memberId)
      selectedMemberId.value=''
      error.value='当前账号关联多个企业，请选择本次要进入的企业。'
    }else error.value=e.message||'企业登录失败'
  }finally{loading.value=false}
}
</script>
<template><main class="auth"><section class="ep-card card"><div class="logo">跃科</div><h1>企业协同中心</h1><p>企业账号必须由学校建立合作关系后开通，不提供开放式企业自注册。</p><form @submit.prevent="submit"><label>学校编码<input v-model.trim="form.tenantCode" class="ep-input" autocomplete="organization" required></label><label>手机号或登录账号<input v-model.trim="form.loginName" class="ep-input" autocomplete="username" required></label><label>密码<input v-model="form.password" type="password" class="ep-input" autocomplete="current-password" required></label><fieldset v-if="contexts.length" class="context-picker"><legend>选择要进入的企业</legend><button v-for="item in contexts" :key="item.memberId" type="button" class="context-option" :class="{selected:selectedMemberId===item.memberId}" @click="selectedMemberId=item.memberId"><span><strong>{{ item.companyName }}</strong><small>{{ item.memberRole }}</small></span><b>{{ selectedMemberId===item.memberId?'已选择':'选择' }}</b></button><p>进入后系统会重新校验你的企业成员关系和学校授权范围，浏览器不能自行指定企业权限。</p></fieldset><div v-if="error" class="ep-error">{{ error }}</div><button class="ep-btn ep-btn-primary submit" :disabled="loading||(contexts.length&&!selectedMemberId)">{{ loading?'登录中…':'登录' }}</button></form><p class="invite">首次激活请使用学校发送的企业邀请链接。</p></section></main></template>
<style scoped>.auth{min-height:100vh;display:grid;place-items:center;padding:24px}.card{width:min(480px,100%);padding:34px}.logo{color:var(--pri);font-size:22px;font-weight:800}.card h1{margin:12px 0 8px}.card>p{color:var(--t3);line-height:1.7}form{margin-top:22px}label{display:flex;flex-direction:column;gap:7px;margin-bottom:14px;font-size:13px;color:var(--t2)}.ep-input,.submit{width:100%}.context-picker{border:1px solid var(--line);border-radius:10px;padding:12px;margin:4px 0 14px}.context-picker legend{padding:0 6px;color:var(--t2);font-size:13px;font-weight:700}.context-option{width:100%;display:flex;align-items:center;justify-content:space-between;gap:12px;text-align:left;border:1px solid var(--line);background:#fff;border-radius:8px;padding:11px 12px;margin:7px 0}.context-option.selected{border-color:var(--pri);background:var(--pri-50)}.context-option span{display:flex;flex-direction:column;gap:3px}.context-option small,.context-picker p{font-size:11px;color:var(--t3)}.context-option b{font-size:12px;color:var(--pri)}.context-picker p{line-height:1.6;margin:10px 2px 0}.invite{font-size:12px;text-align:center;margin:18px 0 0}</style>
