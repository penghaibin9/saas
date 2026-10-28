<script setup>
import { computed, ref } from 'vue'
import { enterpriseInternshipApi } from '../../services/enterpriseInternshipApi'
const props=defineProps({ applicationId:{type:[String,Number],required:true}, contactPolicy:{type:Object,default:()=>({})} })
const loading=ref(false),error=ref(''),revealed=ref(null)
const mode=computed(()=>String(props.contactPolicy?.mode||'').toUpperCase())
const revealableMode=computed(()=>['AFTER_INTERVIEW','AFTER_ACCEPT_INTENT','IMMEDIATE'].includes(mode.value))
const policyLabel=computed(()=>({MASKED_ONLY:'仅保留脱敏联系方式',AFTER_INTERVIEW:'面试后可按授权查看',AFTER_ACCEPT_INTENT:'拟接收后可按授权查看',IMMEDIATE:'可按授权直接查看'}[mode.value]||'联系方式授权方式待校验'))
async function reveal(){
  if(!revealableMode.value){error.value='当前授权方式不允许查看完整联系方式';return}
  loading.value=true;error.value=''
  try{
    const data=await enterpriseInternshipApi.revealContact(props.applicationId)
    const phone=String(data?.phone||''),email=String(data?.email||'')
    if(!phone&&!email){error.value='当前没有可显示的已验证联系方式';revealed.value=null;return}
    revealed.value={phone,email}
  }catch(e){error.value=e.message||'当前处理阶段暂不能查看联系方式';revealed.value=null}finally{loading.value=false}
}
</script>
<template><div class="contact"><div v-if="revealed" class="revealed"><span>已授权联系方式</span><strong v-if="revealed.phone">{{ revealed.phone }}</strong><strong v-if="revealed.email">{{ revealed.email }}</strong></div><template v-else><div class="masked">{{ policyLabel }}</div><button type="button" class="ep-btn" :disabled="loading || !revealableMode" @click="reveal">{{ loading?'授权校验中…':(revealableMode?'查看联系方式':'不可查看完整联系方式') }}</button></template><p v-if="error" class="error">{{ error }}</p><p class="hint">页面不会自行判断是否已达到查看阶段；点击后由学校系统按学生授权、当前处理状态和企业范围再次校验，并自动记录查看行为。</p></div></template>
<style scoped>.contact{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.masked{color:var(--t2)}.revealed{display:flex;flex-direction:column;gap:3px}.revealed span,.hint{font-size:12px;color:var(--t3)}.hint{width:100%;margin:0}.error{width:100%;margin:0;color:var(--danger-fg);font-size:12px}</style>
