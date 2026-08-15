<script setup>
import { computed, ref } from 'vue'
import { enterpriseInternshipApi } from '../../services/enterpriseInternshipApi'
const props=defineProps({ applicationId:{type:[String,Number],required:true}, contactPolicy:{type:Object,default:()=>({})} })
const loading=ref(false),error=ref(''),revealed=ref('')
const allowed=computed(()=>props.contactPolicy?.allowed===true)
async function reveal(){
  if(!allowed.value){error.value='联系方式未授权';return}
  loading.value=true;error.value=''
  try{const data=await enterpriseInternshipApi.revealContact(props.applicationId);revealed.value=data?.contact || data?.phone || data?.value || ''}
  catch(e){error.value=e.message||'联系方式未授权'}finally{loading.value=false}
}
</script>
<template><div class="contact"><div v-if="revealed" class="revealed"><span>已授权联系方式</span><strong>{{ revealed }}</strong></div><template v-else><div class="masked">{{ contactPolicy.masked_value || contactPolicy.maskedValue || '联系方式已脱敏' }}</div><button type="button" class="ep-btn" :disabled="loading || !allowed" @click="reveal">{{ loading?'授权校验中…':(allowed?'查看联系方式':'联系方式未授权') }}</button></template><p v-if="error" class="error">{{ error }}</p><p class="hint">真实查看必须由后端显式授权并写审计；缺少 allowed=true 时保持禁用，前端不读取学生主档手机号字段。</p></div></template>
<style scoped>.contact{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.masked{font-family:monospace;color:var(--t2)}.revealed{display:flex;flex-direction:column;gap:3px}.revealed span,.hint{font-size:12px;color:var(--t3)}.hint{width:100%;margin:0}.error{width:100%;margin:0;color:var(--danger-fg);font-size:12px}</style>
