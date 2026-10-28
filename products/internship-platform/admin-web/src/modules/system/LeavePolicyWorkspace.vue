<template>
  <section>
    <p>默认由指导教师一级审核。发布后的新申请使用新版本，在办单据保持提交时的流程。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false"/>
    <el-alert v-if="receipt" :title="receipt" type="success" :closable="false"/>
    <el-form label-position="top" :disabled="saving" @submit.prevent="publish">
      <el-form-item label="适用实习批次" required><SystemObjectSelect :model-value="batchId" path="/batches" label="选择要配置的批次" @update:model-value="selectBatch"/></el-form-item>
      <template v-if="policy"><p>当前版本：{{ policy.version }}</p>
        <ol class="node-list"><li v-for="(node,index) in nodes" :key="index"><h3>第 {{ index+1 }} 级</h3><div class="node-fields"><el-form-item label="责任岗位"><el-select v-model="node.type" @change="changeType(node)"><el-option v-for="(label,key) in types" :key="key" :value="key" :label="label"/></el-select></el-form-item><el-form-item label="工作身份"><el-select v-model="node.roleCode" @change="preview = null"><el-option v-for="r in roles(node)" :key="r.code" :value="r.code" :label="r.name"/></el-select></el-form-item><el-form-item v-if="node.type === 'SCHOOL'" label="明确承办人（有多人时必选）"><SystemObjectSelect v-model="node.userId" path="/accounts" label="选择校级承办人" @update:model-value="preview = null"/></el-form-item></div><el-button v-if="canManage && nodes.length > 1" @click="nodes.splice(index,1);preview=null">移除这一级</el-button></li></ol>
        <el-button v-if="canManage && nodes.length < 3" @click="addNode">增加一级审批</el-button>
        <el-button v-if="canManage" :loading="busy" @click="check">预览实际责任人</el-button>
        <template v-if="preview"><h3>责任人核对</h3><p>共 {{ preview.total }} 位学生，责任缺口 {{ preview.errorCount }} 位。下表展示前100人。</p><el-table :data="preview.items"><el-table-column prop="studentNo" label="学号"/><el-table-column prop="studentName" label="姓名"/><el-table-column label="逐级承办人" min-width="300"><template #default="{row}">{{ row.steps.map(s => `${s.label}：${s.name}`).join(' → ') || row.error }}</template></el-table-column></el-table></template>
        <el-form-item v-if="canManage" label="发布原因" required><el-input v-model="reason" type="textarea" maxlength="500"/></el-form-item>
        <ConflictReview :conflict="policyConflict" :input="{approvalSteps:nodeLabels(nodes)}" @reviewed="reviewConflict"/><el-button v-if="canManage" type="primary" native-type="submit" :disabled="!preview?.canPublish || !!conflict" :loading="busy">发布新版本</el-button>
      </template>
      <el-empty v-else description="选择批次后配置；没有批次时仍可使用其他系统管理功能"/>
    </el-form>
  </section>
</template>
<script setup>
import { ElAlert, ElButton, ElEmpty, ElForm, ElFormItem, ElInput, ElOption, ElSelect, ElTable, ElTableColumn } from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/empty/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/option/style/css'
import 'element-plus/es/components/select/style/css'
import 'element-plus/es/components/table/style/css'

import { ref,onMounted,computed,watch,onBeforeUnmount } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import { get,save } from './systemApi'
import { getPermissionPatterns } from '@/security/permissionGate'
import { matchPermission } from '@/config/navPlan'
import SystemObjectSelect from './SystemObjectSelect.vue'
import ConflictReview from './ConflictReview.vue'
const types={GUIDE:'指导教师',COLLEGE:'院系责任人',SCHOOL:'校级责任人'},bases={GUIDE:'INTERN_MENTOR',COLLEGE:'COLLEGE_ADMIN',SCHOOL:'SCHOOL_ADMIN'}
const route=useRoute(),router=useRouter()
const options=ref({roles:[]}),batchId=ref(''),policy=ref(null),nodes=ref([]),preview=ref(null),reason=ref(''),loading=ref(false),checking=ref(false),saving=ref(false),conflict=ref(null),error=ref(''),receipt=ref('')
const busy=computed(()=>loading.value||checking.value||saving.value)
const canManage=computed(()=>matchPermission(getPermissionPatterns(),'system.leave-policy.manage'))
const roles=node=>options.value.roles.filter(r=>r.baseRole===bases[node.type])
function changeType(node){node.roleCode=roles(node)[0]?.code||'';node.userId='';preview.value=null}
function addNode(){const type=['GUIDE','COLLEGE','SCHOOL'].find(k=>!nodes.value.some(n=>n.type===k));const node={type,roleCode:'',userId:''};changeType(node);nodes.value.push(node);nodes.value.sort((a,b)=>Object.keys(types).indexOf(a.type)-Object.keys(types).indexOf(b.type))}
let sequence=0,checkSequence=0
onBeforeUnmount(()=>{sequence++;checkSequence++})
function invalidatePreview(){checkSequence++;checking.value=false;preview.value=null}
function nodeLabels(value){return value.map(n=>`${types[n.type] || '未知岗位'} · ${options.value.roles.find(r=>r.code===n.roleCode)?.name || '历史身份'}${n.userId ? ` · 承办人编号 ${n.userId}` : ' · 按实际责任关系确定'}`)}
const policyConflict=computed(()=>conflict.value ? {...conflict.value,current:{approvalSteps:nodeLabels(conflict.value.current.nodes)}} : null)
function reviewConflict(version){policy.value.expectedVersion=version;conflict.value=null;error.value='';invalidatePreview()}
function selectBatch(value){return router.replace({query:{...route.query,batchId:value || undefined}})}
function restoreBatch(value){const id=typeof value==='string' && /^\d+$/.test(value)?value:'';if(batchId.value===id)return;batchId.value=id;return loadPolicy()}
async function loadPolicy(){const run=++sequence;loading.value=false;policy.value=null;error.value='';receipt.value='';reason.value='';conflict.value=null;invalidatePreview();if(!batchId.value)return;loading.value=true;try{const result=await get(`/leave-policies/${batchId.value}`);if(run!==sequence)return;policy.value=result;nodes.value=result.nodes.map(n=>({...n}))}catch(e){if(run===sequence)error.value=e.message}finally{if(run===sequence)loading.value=false}}
async function check(){if(busy.value||!policy.value||!canManage.value)return;const run=sequence,ticket=++checkSequence;checking.value=true;error.value='';preview.value=null;try{const result=await save(`/leave-policies/${batchId.value}/preview`,{nodes:nodes.value.map(n=>({...n}))});if(run===sequence&&ticket===checkSequence)preview.value=result}catch(e){if(run===sequence&&ticket===checkSequence)error.value=e.message}finally{if(ticket===checkSequence)checking.value=false}}
async function publish(){if(busy.value||conflict.value||!preview.value?.canPublish||!policy.value||!canManage.value)return;const run=sequence;saving.value=true;error.value='';receipt.value='';try{const result=await save(`/leave-policies/${batchId.value}/publish`,{nodes:nodes.value.map(n=>({...n})),expectedVersion:policy.value.expectedVersion,reason:reason.value});if(run!==sequence)return;policy.value={...policy.value,...result};receipt.value=`新版本已发布，已核对${result.checkedStudents}位学生的责任人。`;reason.value='';invalidatePreview()}catch(e){if(run===sequence){error.value=e.message;conflict.value=e.details?.current?.nodes ? e.details : null;invalidatePreview()}}finally{saving.value=false}}
watch(nodes,invalidatePreview,{deep:true,flush:'sync'})
watch(()=>route.query.batchId,restoreBatch,{immediate:true})
onMounted(async()=>{try{options.value=await get('/leave-policies/options')}catch(e){error.value=e.message}})
</script>
<style scoped>.el-form{max-width:1100px}.el-select{width:100%}.node-list{padding-left:24px}.node-list li{padding:12px 18px;border:1px solid var(--line);border-radius:10px;margin:12px 0}.node-fields{display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px}.el-alert,.el-form-item{margin:18px 0}h3{font-size:16px}@media(max-width:800px){.node-fields{grid-template-columns:1fr}}</style>
