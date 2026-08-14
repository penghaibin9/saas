<script setup>
import { ref } from 'vue'
import { enterpriseInternshipApi } from '../../services/enterpriseInternshipApi'
const props=defineProps({ application:{type:Object,required:true} })
const emit=defineEmits(['changed'])
const loading=ref(''),error=ref('')
const actions=[['REJECTED','不合适'],['INTERESTED','感兴趣'],['INTERVIEW','安排面试'],['ACCEPT_INTENT','拟接收']]
async function decide(status){loading.value=status;error.value='';try{await enterpriseInternshipApi.decideApplication(props.application.id||props.application.application_id||props.application.applicationId,status);emit('changed')}catch(e){error.value=e.message||'处理失败'}finally{loading.value=''}}
</script>
<template><div><div class="actions"><button v-for="item in actions" :key="item[0]" type="button" class="ep-btn" :class="{'ep-btn-primary':item[0]==='ACCEPT_INTENT','ep-btn-danger':item[0]==='REJECTED'}" :disabled="Boolean(loading) || application.decision_disabled || application.decisionDisabled" @click="decide(item[0])">{{ loading===item[0]?'处理中…':item[1] }}</button></div><p v-if="error" class="error">{{ error }}</p><p v-if="application.decision_disabled_reason || application.decisionDisabledReason" class="reason">{{ application.decision_disabled_reason || application.decisionDisabledReason }}</p></div></template>
<style scoped>.actions{display:flex;gap:8px;flex-wrap:wrap}.error,.reason{font-size:12px;margin:8px 0 0}.error{color:var(--danger-fg)}.reason{color:var(--t3)}</style>
