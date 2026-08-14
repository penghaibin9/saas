<script setup>
import { computed, ref } from 'vue'
import { enterpriseInternshipApi } from '../../services/enterpriseInternshipApi'
const props=defineProps({ application:{type:Object,required:true}, campaignWritable:{type:Boolean,default:false} })
const emit=defineEmits(['changed'])
const loading=ref(''),error=ref(''),confirming=ref('')
const actions=[['REJECTED','不合适'],['INTERESTED','感兴趣'],['INTERVIEW','安排面试'],['ACCEPT_INTENT','拟接收']]
const lockedAccept=computed(()=>props.application.decisionStatus==='ACCEPT_INTENT' && props.application.volunteerGroupStatus==='LOCKED' && !props.application.acceptIntentReleased)
const baseDisabled=computed(()=>Boolean(loading.value)||!props.campaignWritable||lockedAccept.value||Boolean(props.application.decisionDisabled)||Boolean(props.application.decisionDisabledReason))
function requestDecision(status){
  error.value=''
  if(baseDisabled.value)return
  if(status==='ACCEPT_INTENT'){confirming.value=status;return}
  decide(status)
}
async function decide(status){
  if(!props.campaignWritable){error.value='招聘季已关闭或当前 RECRUITMENT 权限不可写';return}
  if(lockedAccept.value){error.value='当前申请已处于拟接收锁定，等待学校最终确认';return}
  if(props.application.decisionDisabledReason){error.value=props.application.decisionDisabledReason;return}
  loading.value=status;confirming.value='';error.value=''
  try{await enterpriseInternshipApi.decideApplication(props.application.id||props.application.applicationId,status);emit('changed')}
  catch(e){error.value=e.message||'处理失败'}finally{loading.value=''}
}
async function withdrawAccept(){if(!props.campaignWritable||!lockedAccept.value)return;loading.value='WITHDRAW_ACCEPT';error.value='';try{await enterpriseInternshipApi.withdrawAccept(props.application.id||props.application.applicationId);emit('changed')}catch(e){error.value=e.message||'撤回拟接收失败'}finally{loading.value=''}}
</script>
<template><div><div class="actions"><template v-if="lockedAccept"><span class="locked-copy">拟接收已生效，等待学校最终确认</span><button type="button" class="ep-btn" :disabled="Boolean(loading)||!campaignWritable" @click="withdrawAccept">{{ loading==='WITHDRAW_ACCEPT'?'撤回中…':'撤回拟接收' }}</button></template><template v-else><button v-for="item in actions" :key="item[0]" type="button" class="ep-btn" :class="{'ep-btn-primary':item[0]==='ACCEPT_INTENT','ep-btn-danger':item[0]==='REJECTED'}" :disabled="baseDisabled" @click="requestDecision(item[0])">{{ loading===item[0]?'处理中…':item[1] }}</button></template></div><div v-if="confirming==='ACCEPT_INTENT'" class="confirm"><div><strong>确认拟接收这名学生？</strong><p>确认后将进入学校最终确认链；在学校确认前这只是企业拟接收意向，不等于正式落岗。</p></div><div class="confirm-actions"><button type="button" class="ep-btn" :disabled="Boolean(loading)" @click="confirming=''">取消</button><button type="button" class="ep-btn ep-btn-primary" :disabled="Boolean(loading)" @click="decide('ACCEPT_INTENT')">确认拟接收</button></div></div><p v-if="error" class="error">{{ error }}</p><p v-if="!campaignWritable" class="reason">历史招聘季只读：企业 Decision 已关闭。</p><p v-else-if="application.decisionDisabledReason" class="reason">{{ application.decisionDisabledReason }}</p></div></template>
<style scoped>.actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.locked-copy{font-size:12px;color:var(--warn-fg);margin-right:auto}.confirm{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:10px;padding:12px 14px;border:1px solid var(--pri-100);background:var(--pri-50);border-radius:8px}.confirm strong{font-size:13px}.confirm p{margin:4px 0 0;color:var(--t3);font-size:12px;line-height:1.5}.confirm-actions{display:flex;gap:8px;flex:0 0 auto}.error,.reason{font-size:12px;margin:8px 0 0}.error{color:var(--danger-fg)}.reason{color:var(--t3)}@media(max-width:700px){.confirm{align-items:stretch;flex-direction:column}.confirm-actions{justify-content:flex-end}}</style>
