<script setup>
import { computed, ref } from 'vue'
import { enterpriseInternshipApi } from '../../services/enterpriseInternshipApi'
const props=defineProps({ application:{type:Object,required:true}, campaignWritable:{type:Boolean,default:false} })
const emit=defineEmits(['changed'])
const loading=ref(''),error=ref(''),confirming=ref(''),withdrawReason=ref(''),interviewAt=ref(''),interviewNote=ref('')
const actions=[['REJECTED','不合适'],['INTERESTED','感兴趣'],['INTERVIEW','安排面试'],['ACCEPT_INTENT','拟接收']]
const activeAcceptIntent=computed(()=>props.application.decisionStatus==='ACCEPT_INTENT'&&props.application.decisionEffectStatus==='ACTIVE')
const inactiveDecision=computed(()=>Boolean(props.application.decisionEffectStatus)&&props.application.decisionEffectStatus!=='ACTIVE')
const baseDisabled=computed(()=>Boolean(loading.value)||!props.campaignWritable||activeAcceptIntent.value||inactiveDecision.value||Boolean(props.application.decisionDisabled)||Boolean(props.application.decisionDisabledReason))
function requestDecision(status){
  error.value=''
  if(baseDisabled.value)return
  if(status==='ACCEPT_INTENT'){confirming.value=status;return}
  if(status==='INTERVIEW'){interviewAt.value='';interviewNote.value='';confirming.value=status;return}
  decide(status)
}
async function decide(status,payload={}){
  if(!props.campaignWritable){error.value='当前招聘季未开放企业处理权限';return}
  if(activeAcceptIntent.value){error.value='当前申请已处于拟接收状态，等待学校最终确认';return}
  if(inactiveDecision.value){error.value='当前企业处理记录已失效或进入后续流程，不能继续修改';return}
  if(props.application.decisionDisabledReason){error.value=props.application.decisionDisabledReason;return}
  loading.value=status;confirming.value='';error.value=''
  try{await enterpriseInternshipApi.decideApplication(props.application.id||props.application.applicationId,status,payload);emit('changed')}
  catch(e){error.value=e.message||'处理失败'}finally{loading.value=''}
}
async function confirmInterview(){
  if(!interviewAt.value){error.value='请先填写面试时间';return}
  await decide('INTERVIEW',{interviewAt:interviewAt.value,interviewNote:interviewNote.value.trim()||undefined})
}
function requestWithdrawAccept(){
  if(!props.campaignWritable||!activeAcceptIntent.value)return
  error.value='';withdrawReason.value='';confirming.value='WITHDRAW_ACCEPT'
}
async function withdrawAccept(){
  if(!props.campaignWritable||!activeAcceptIntent.value)return
  const reason=withdrawReason.value.trim()
  if(reason.length<2){error.value='撤回拟接收必须填写原因';return}
  loading.value='WITHDRAW_ACCEPT';error.value=''
  try{
    await enterpriseInternshipApi.withdrawAccept(props.application.id||props.application.applicationId,reason)
    confirming.value='';withdrawReason.value='';emit('changed')
  }catch(e){error.value=e.message||'撤回拟接收失败'}finally{loading.value=''}
}
</script>
<template><div><div class="actions"><template v-if="activeAcceptIntent"><span class="locked-copy">拟接收已生效，等待学校最终确认</span><button type="button" class="ep-btn" :disabled="Boolean(loading)||!campaignWritable" @click="requestWithdrawAccept">撤回拟接收</button></template><template v-else><button v-for="item in actions" :key="item[0]" type="button" class="ep-btn" :class="{'ep-btn-primary':item[0]==='ACCEPT_INTENT','ep-btn-danger':item[0]==='REJECTED'}" :disabled="baseDisabled" @click="requestDecision(item[0])">{{ loading===item[0]?'处理中…':item[1] }}</button></template></div><div v-if="confirming==='ACCEPT_INTENT'" class="confirm"><div><strong>确认拟接收这名学生？</strong><p>确认后将进入学校最终确认流程；在学校确认前，这只是企业拟接收意向，不等于正式落岗。</p></div><div class="confirm-actions"><button type="button" class="ep-btn" :disabled="Boolean(loading)" @click="confirming=''">取消</button><button type="button" class="ep-btn ep-btn-primary" :disabled="Boolean(loading)" @click="decide('ACCEPT_INTENT')">确认拟接收</button></div></div><div v-if="confirming==='INTERVIEW'" class="withdraw-confirm"><div><strong>安排面试</strong><p>面试时间为必填项，提交后由学校系统再次校验当前招聘季企业处理窗口。</p></div><label>面试时间<input v-model="interviewAt" class="withdraw-reason" type="datetime-local" /></label><label>面试说明<textarea v-model.trim="interviewNote" class="withdraw-reason" rows="2" maxlength="1000" placeholder="可填写面试地点、方式或注意事项" /></label><div class="confirm-actions"><button type="button" class="ep-btn" :disabled="Boolean(loading)" @click="confirming=''">取消</button><button type="button" class="ep-btn ep-btn-primary" :disabled="Boolean(loading)||!interviewAt" @click="confirmInterview">确认安排面试</button></div></div><div v-if="confirming==='WITHDRAW_ACCEPT'" class="withdraw-confirm"><div><strong>撤回拟接收并转为不合适？</strong><p>系统会保留本次处理历史并释放对应志愿锁；撤回原因会记录在企业处理历史中。</p></div><label>撤回原因<textarea v-model.trim="withdrawReason" class="withdraw-reason" rows="3" maxlength="1000" placeholder="请填写撤回拟接收的业务原因（至少 2 个字符）" /></label><div class="confirm-actions"><button type="button" class="ep-btn" :disabled="Boolean(loading)" @click="confirming='';withdrawReason=''">取消</button><button type="button" class="ep-btn ep-btn-danger" :disabled="Boolean(loading)||withdrawReason.trim().length<2" @click="withdrawAccept">{{ loading==='WITHDRAW_ACCEPT'?'撤回中…':'确认撤回并标记不合适' }}</button></div></div><p v-if="error" class="error">{{ error }}</p><p v-if="!campaignWritable" class="reason">当前招聘季只读：新的企业处理动作尚未开放。</p><p v-else-if="inactiveDecision" class="reason">当前企业处理记录已失效或进入后续流程，不能继续修改。</p><p v-else-if="application.decisionDisabledReason" class="reason">{{ application.decisionDisabledReason }}</p></div></template>
<style scoped>.actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.locked-copy{font-size:12px;color:var(--warn-fg);margin-right:auto}.confirm,.withdraw-confirm{margin-top:10px;padding:12px 14px;border:1px solid var(--pri-100);background:var(--pri-50);border-radius:8px}.confirm{display:flex;justify-content:space-between;align-items:center;gap:16px}.confirm strong,.withdraw-confirm strong{font-size:13px}.confirm p,.withdraw-confirm p{margin:4px 0 0;color:var(--t3);font-size:12px;line-height:1.5}.withdraw-confirm label{display:flex;flex-direction:column;gap:6px;margin-top:12px;font-size:12px;color:var(--t2)}.withdraw-reason{width:100%;resize:vertical;border:1px solid var(--line);border-radius:7px;padding:9px 10px;font:inherit;background:#fff;box-sizing:border-box}.confirm-actions{display:flex;gap:8px;justify-content:flex-end;flex:0 0 auto;margin-top:12px}.confirm>.confirm-actions{margin-top:0}.error,.reason{font-size:12px;margin:8px 0 0}.error{color:var(--danger-fg)}.reason{color:var(--t3)}@media(max-width:700px){.confirm{align-items:stretch;flex-direction:column}.confirm>.confirm-actions{margin-top:12px}}</style>
