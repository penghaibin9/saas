<template>
  <details :open="expanded" @toggle="open"><summary>在办请假责任交接</summary>
    <p>选择批次与原责任人，核对在办节点后逐项交接。指导教师先从实习学生名单完成导师分配；已办结的意见始终保留。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false"/><el-alert v-if="receipt" :title="receipt" type="success" :closable="false"/>
    <div class="handoff-controls"><SystemObjectSelect :model-value="batchId" path="/batches" label="选择交接批次" @update:model-value="value=>setContext(value,source)"/><SystemObjectSelect :model-value="source" path="/accounts" label="原责任人" @update:model-value="value=>setContext(batchId,value)"/><el-button :disabled="!batchId || !source" @click="load">读取交接清单</el-button></div>
    <p v-if="taskId">当前仅核对此原请假节点；交接完成后可返回异常清单确认。<el-button text @click="setContext(batchId,source)">查看该责任人的全部节点</el-button></p>
    <el-table :data="items" v-loading="loading" :empty-text="taskId ? '此节点已不在原责任人待办中，请刷新异常清单核对' : '当前选择下没有在办请假节点'"><el-table-column prop="studentName" label="学生"/><el-table-column prop="step" label="审批级次"/><el-table-column prop="statusLabel" label="节点状态"/><el-table-column label="操作"><template #default="{row}"><el-button v-if="canEdit" text @click="selected=row;recipient='';roleCode=row.roleCode;reason=''">指定接收人</el-button></template></el-table-column></el-table>
    <el-pagination v-if="total>30" :current-page="page" :page-size="30" :total="total" layout="prev,pager,next" @current-change="value=>setContext(batchId,source,value)"/>
    <el-form v-if="selected" label-position="top" @submit.prevent="transfer"><h3>{{ selected.studentName }} · 第{{ selected.step }}级审批</h3><el-form-item label="接收人"><SystemObjectSelect v-model="recipient" path="/accounts" label="接收人账号"/></el-form-item><el-form-item label="接收身份"><el-select v-model="roleCode"><el-option v-for="r in options.roles" :key="r.code" :value="r.code" :label="r.name"/></el-select></el-form-item><el-form-item label="交接原因"><el-input v-model="reason" type="textarea" maxlength="500"/></el-form-item><el-button type="primary" native-type="submit" :loading="saving">核对并交接该节点</el-button><el-button @click="selected=null">取消</el-button></el-form>
  </details>
</template>
<script setup>
import { ElAlert, ElButton, ElForm, ElFormItem, ElInput, ElOption, ElPagination, ElSelect, ElTable, ElTableColumn, ElLoading } from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/option/style/css'
import 'element-plus/es/components/pagination/style/css'
import 'element-plus/es/components/select/style/css'
import 'element-plus/es/components/table/style/css'
import 'element-plus/es/components/loading/style/css'
const vLoading = ElLoading.directive

import {ref,watch,onBeforeUnmount} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {get,save} from './systemApi'
import SystemObjectSelect from './SystemObjectSelect.vue'
defineProps({canEdit:Boolean})
const emit=defineEmits(['transferred'])
const route=useRoute(),router=useRouter(),expanded=ref(false)
const taskId=ref('')
const options=ref({roles:[]}),batchId=ref(''),source=ref(''),items=ref([]),page=ref(1),total=ref(0),error=ref(''),receipt=ref(''),loading=ref(false),saving=ref(false),selected=ref(null),recipient=ref(''),roleCode=ref(''),reason=ref('')
let sequence=0
onBeforeUnmount(()=>{sequence++})
async function open(event){expanded.value=event.target.open;if(!expanded.value)return;try{options.value=await get('/handoff-options')}catch(e){error.value=e.message}}
function setContext(batch,actor,nextPage=1){return router.replace({query:{...route.query,handoffBatchId:batch || undefined,handoffSourceId:actor || undefined,handoffPage:nextPage>1?String(nextPage):undefined,handoffTaskId:undefined}})}
function restoreContext([batch,actor,nextPage,task]){
  batchId.value=typeof batch==='string' && /^\d+$/.test(batch)?batch:''
  source.value=typeof actor==='string' && /^\d+$/.test(actor)?actor:''
  taskId.value=typeof task==='string' && /^\d+$/.test(task)?task:''
  const value=Number(nextPage);page.value=Number.isSafeInteger(value) && value>0?value:1
  selected.value=null;receipt.value='';expanded.value=Boolean(batchId.value || source.value)
  return load()
}
async function load(){const run=++sequence;items.value=[];total.value=0;loading.value=false;error.value='';if(!batchId.value||!source.value)return;loading.value=true;try{const result=await get('/handoffs',{batchId:batchId.value,userId:source.value,page:page.value,...(taskId.value?{taskId:taskId.value}:{})});if(run===sequence){items.value=result.items;total.value=result.total}}catch(e){if(run===sequence)error.value=e.message}finally{if(run===sequence)loading.value=false}}
async function transfer(){if(saving.value||!selected.value)return;const run=sequence;saving.value=true;error.value='';try{const result=await save('/handoffs/'+selected.value.id,{batchId:batchId.value,userId:recipient.value,roleCode:roleCode.value,reason:reason.value,expectedVersion:selected.value.version});if(run!==sequence)return;selected.value=null;receipt.value=result.message;emit('transferred');await load()}catch(e){if(run===sequence)error.value=e.message||'交接失败，输入已保留'}finally{saving.value=false}}
watch([()=>route.query.handoffBatchId,()=>route.query.handoffSourceId,()=>route.query.handoffPage,()=>route.query.handoffTaskId],restoreContext,{immediate:true})
</script>
<style scoped>details{margin:20px 0;padding:20px;border:1px solid var(--line);border-radius:10px}summary{cursor:pointer;font-weight:600}.handoff-controls{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}.el-form{max-width:600px;margin-top:20px}.el-select{width:240px}.el-alert{margin:14px 0}</style>
