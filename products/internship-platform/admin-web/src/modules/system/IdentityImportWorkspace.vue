<template>
  <section class="identity-import">
    <p>{{ kind==='organizations' ? '仅维护组织目录。先核对新增组织清单，再确认导入；不会创建账号。' : '批量创建师生账号统一在这里办理。请先核对组织、人员和绑定关系，再确认开通。' }} 按当前身份与负责范围校验；身份或授权变化后须重新预检。</p>
    <div class="toolbar"><el-radio-group v-if="!fixedKind" :model-value="kind" @update:model-value="switchKind"><el-radio-button value="students">学生开户</el-radio-button><el-radio-button value="staff">教师开户</el-radio-button></el-radio-group><el-button @click="run(() => download(`/identity-import/${kind}/template`, '师生开户模板.xlsx'))">下载填写模板</el-button><label v-if="canEdit" class="upload">上传并预检<input type="file" accept=".xlsx" :disabled="busy" @change="selectFile" /></label></div>
    <el-alert v-if="error" type="error" :closable="false" :title="error" show-icon />
    <p v-if="busy" role="status">正在处理，请勿重复提交……</p>
    <template v-if="preview">
      <div class="receipt"><h3>{{ preview.fileName }}</h3><p>{{ preview.statusLabel }} · 共 {{ preview.total }} 行 · 错误 {{ preview.invalidRows }} 行</p><p>预检和回执有效期：{{ formatDate(preview.expiresAt) }}</p></div>
      <el-alert v-if="preview.status === 'IMPORTED'" type="success" :closable="false" :title="kind==='organizations' ? '组织导入完成，可回到组织列表查看。' : '本批资料处理已完成，请下载受控回执核对结果。新开通账号须首次登录修改临时密码；已有账号的密码和角色保持不变。'" />
      <el-alert v-if="preview.invalidRows" type="warning" :closable="false" title="存在错误，不能确认开通。请按下方原因修正原文件后重新上传。" />
      <el-alert v-if="preview.message" type="warning" :closable="false" :title="preview.message"/><el-alert v-if="preview.status==='QUEUED'" type="info" :closable="false" title="任务已持久保存，正在排队或整批处理。可以离开页面，稍后从导入导出任务返回；整个批次完成后才生效。"/><el-button v-if="preview.status==='QUEUED'" @click="readPage(preview.page)">刷新任务结果</el-button><div v-if="preview.newOrganizations.length"><h3>{{ preview.status==='IMPORTED' ? '本页已确认新增的组织' : '本页拟新增的组织' }}（全批次 {{ preview.newOrganizationCount }} 个）</h3><el-tag v-for="org in preview.newOrganizations" :key="org.kind+org.code">{{ org.name }}（{{ org.code }}）</el-tag></div>
      <el-table :data="preview.entries" row-key="row"><el-table-column prop="row" label="表格行" width="80"/><el-table-column prop="number" :label="kind==='organizations' ? '组织代码' : '学号／工号'"/><el-table-column prop="name" :label="kind==='organizations' ? '组织名称' : '姓名'"/><el-table-column prop="operation" label="人员处理"/><el-table-column prop="accountAction" label="账号处理"/><el-table-column label="核对结果" min-width="260"><template #default="{row}"><span v-if="!row.errors.length">预检通过</span><p v-for="message in row.errors" :key="message" class="error-text">{{ message }}</p></template></el-table-column></el-table>
      <el-pagination v-if="preview.total > 100" :current-page="preview.page" :page-size="100" :total="preview.total" layout="prev, pager, next" @current-change="readPage" />
      <el-button v-if="preview.invalidRows" @click="run(() => download(`/identity-import/jobs/${preview.id}/errors`, '师生导入错误行.xlsx'))">下载全部错误行</el-button><div class="confirm-area" v-if="canEdit && (preview.status === 'VALIDATED' || preview.status === 'FAILED' && !preview.invalidRows)"><el-checkbox v-model="confirmed">{{ kind==='organizations' ? '我已核对新增与复用组织清单' : '我已核对新增组织、人员更新和账号绑定清单' }}</el-checkbox><el-button type="primary" :disabled="!confirmed" :loading="busy" @click="confirm">{{ kind==='organizations' ? '确认导入组织' : '确认开通本批师生账号' }}</el-button></div>
      <el-button v-if="canEdit && preview.receiptAvailable" type="primary" :loading="busy" @click="run(() => download(`/identity-import/jobs/${preview.id}/receipt`, '师生开户回执.xlsx'))">下载受控开户回执</el-button>
    </template>
    <el-empty v-else-if="!busy && !error" description="下载模板并上传，即可预检；预检阶段不会创建账号" />
  </section>
</template>
<script setup>
import { ElAlert, ElButton, ElCheckbox, ElEmpty, ElPagination, ElRadioButton, ElRadioGroup, ElTable, ElTableColumn, ElTag } from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/checkbox/style/css'
import 'element-plus/es/components/empty/style/css'
import 'element-plus/es/components/pagination/style/css'
import 'element-plus/es/components/radio-button/style/css'
import 'element-plus/es/components/radio-group/style/css'
import 'element-plus/es/components/table/style/css'
import 'element-plus/es/components/tag/style/css'

import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, save, upload, download } from './systemApi'
import { getPermissionPatterns } from '@/security/permissionGate'
import { matchPermission } from '@/config/navPlan'
const props=defineProps({fixedKind:{type:String,default:''}})
const canEdit = computed(() => matchPermission(getPermissionPatterns(), props.fixedKind==='organizations' ? 'system.org.manage' : 'system.identity-import.manage'))
const route = useRoute(), router = useRouter(), kind = computed(() => props.fixedKind || route.params.kind || 'students')
let sequence=0,refreshTimer,disposed=false
onBeforeUnmount(()=>{sequence++;disposed=true;clearTimeout(refreshTimer)})
function refreshQueued(){clearTimeout(refreshTimer);if(!disposed && preview.value?.status==='QUEUED')refreshTimer=setTimeout(async()=>{await readPage(preview.value?.page || 1);refreshQueued()},3000)}
const preview = ref(null), error = ref(''), busy = ref(false), confirmed = ref(false)
watch(()=>[preview.value?.id,preview.value?.status],refreshQueued)
const formatDate = value => value ? new Date(/Z$|[+-]\d\d:\d\d$/.test(value) ? value : value+'Z').toLocaleString('zh-CN') : '—'
async function run(action) {
  if (busy.value) return
  const current=sequence;busy.value = true;error.value = ''
  try { await action() } catch (e) {
    if(current===sequence){
      error.value = e.message || '操作失败，请重试'
      if([403,404].includes(e.httpStatus) || ['NO_PERMISSION','NO_DATA_SCOPE','NOT_FOUND'].includes(e.bizCode)){
        preview.value=null;confirmed.value=false;clearTimeout(refreshTimer)
      }
    }
  } finally { if(current===sequence)busy.value = false }
}
function switchKind(value) { router.push(`/admin/system/identity-import/${value}`) }
async function selectFile(event) { const file = event.target.files?.[0]; if (!file) return; confirmed.value = false; await run(async () => { const run=sequence;const value = await upload(kind.value, file);if(run!==sequence)return; preview.value = value; await router.replace({ query: { ...route.query, jobId: value.id } }) }); event.target.value = '' }
async function confirm() { if(!canEdit.value || !confirmed.value || !preview.value || preview.value.invalidRows || !['VALIDATED','FAILED'].includes(preview.value.status))return;await run(async () => { const run=sequence;const value=await save(`/identity-import/jobs/${preview.value.id}/confirm`, { expectedVersion: preview.value.version });if(run===sequence){preview.value=value;confirmed.value=false} }) }
async function readPage(page) { await run(async () => { const run=sequence;const value=await get(`/identity-import/jobs/${route.query.jobId}`, { page });if(run!==sequence)return;if(value.kind!==kind.value)throw new Error('任务类型与当前入口不一致，请从导入导出任务重新进入');preview.value=value }) }
async function changeContext([selectedKind,jobId],previous=[]){
  if(selectedKind===previous[0] && jobId && String(preview.value?.id)===String(jobId))return
  sequence++;clearTimeout(refreshTimer);preview.value=null;error.value='';confirmed.value=false;busy.value=false
  if(jobId)await readPage(1)
}
watch(() => [kind.value, route.query.jobId], changeContext, { immediate: true })
</script>
<style scoped>.toolbar,.confirm-area{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:20px 0}.upload{display:inline-flex;align-items:center;gap:12px;padding:9px 14px;border:1px solid var(--line);border-radius:8px}.upload input{max-width:230px}.receipt{padding:16px 0}.error-text{color:#b42318;margin:3px 0}.el-tag{margin:4px}.el-pagination{margin:18px 0}</style>
