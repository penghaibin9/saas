<template>
  <el-dialog v-model="opened" title="核对并纠正学生账号绑定" width="min(720px,95vw)" :close-on-click-modal="false">
    <p>{{ student.name }} · 学号 {{ student.number }}。请选择该学生本人的登录账号。</p>
    <SystemObjectSelect v-model="accountId" path="/accounts" label="学生本人账号" @update:model-value="review=null"/>
    <el-button :loading="busy" :disabled="!accountId" @click="preview">预览绑定影响</el-button>
    <el-alert v-if="error" :title="error" type="error" :closable="false"/>
    <template v-if="review">
      <h3>拟建立的本人绑定</h3><p>{{ review.studentName }}（{{ review.studentNo }}） → {{ review.accountName }}（{{ review.loginName }}）</p>
      <h3>当前涉及的绑定</h3><el-table :data="review.current" empty-text="当前没有有效绑定"><el-table-column prop="studentName" label="学生"/><el-table-column prop="studentNo" label="学号"/><el-table-column prop="loginName" label="登录账号"/></el-table>
      <el-alert :title="review.note" type="warning" :closable="false"/>
      <template v-if="!review.unchanged">
        <el-input v-model="reason" type="textarea" placeholder="填写误绑原因及身份核对依据" aria-label="绑定纠正依据" maxlength="500"/>
        <el-checkbox v-model="confirmed">已核对本人身份与受影响的旧绑定</el-checkbox>
        <el-button type="primary" :loading="busy" :disabled="!confirmed || reason.trim().length<5" @click="submit">确认纠正绑定</el-button>
      </template>
    </template>
  </el-dialog>
</template>
<script setup>
import { computed,ref,watch } from 'vue'
import { ElDialog,ElButton,ElAlert,ElTable,ElTableColumn,ElInput,ElCheckbox } from 'element-plus'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/table/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/checkbox/style/css'
import SystemObjectSelect from './SystemObjectSelect.vue'
import {get,save} from './systemApi'
const props=defineProps({modelValue:Boolean,student:{type:Object,required:true}})
const emit=defineEmits(['update:modelValue','saved'])
const opened=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const accountId=ref(''),review=ref(null),reason=ref(''),confirmed=ref(false),error=ref(''),busy=ref(false)
let sequence=0
watch(()=>props.modelValue,()=>{sequence++;busy.value=false;accountId.value=props.student.userId || '';review.value=null;reason.value='';confirmed.value=false;error.value=''},{immediate:true})
async function preview(){const run=++sequence;const target=accountId.value;busy.value=true;error.value='';confirmed.value=false;review.value=null;try{const value=await get(`/people/student/${props.student.id}/binding-preview`,{userId:target});if(run===sequence && target===accountId.value)review.value=value}catch(e){if(run===sequence)error.value=e.message}finally{if(run===sequence)busy.value=false}}
async function submit(){if(busy.value || !review.value || !confirmed.value)return;const run=sequence;busy.value=true;error.value='';try{const result=await save(`/people/student/${props.student.id}/binding`,{userId:accountId.value,fingerprint:review.value.fingerprint,expectedVersion:review.value.expectedVersion,reason:reason.value});if(run===sequence){emit('saved',result.message);opened.value=false}}catch(e){if(run===sequence){error.value=e.message;review.value=null;confirmed.value=false}}finally{busy.value=false}}
</script>
<style scoped>.el-alert,.el-input,.el-checkbox{margin:14px 0}.el-select{width:320px;margin-right:12px}h3{font-size:16px}</style>
