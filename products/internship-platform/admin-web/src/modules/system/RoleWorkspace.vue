<template>
  <section>
    <p>角色决定能做什么；负责哪些院系、专业或班级，请在“管理范围与责任关系”中配置。每次只使用当前工作身份。</p>
    <el-alert v-if="error" type="error" :closable="false" :title="error" show-icon />
    <el-button v-if="canEdit" type="primary" @click="edit()">创建学校角色</el-button>
    <el-table v-if="!error" :data="data.items" v-loading="busy" row-key="id"><el-table-column prop="name" label="角色名称"/><el-table-column prop="baseLabel" label="身份类型"/><el-table-column prop="statusLabel" label="状态"/><el-table-column label="成员数"><template #default="{row}">{{ row.memberCount }}</template></el-table-column><el-table-column label="操作" min-width="230"><template #default="{row}"><el-button text @click="inspect(row)">角色工作区</el-button><el-button text @click="edit(row, !canEdit)">{{ canEdit ? '维护权限' : '查看权限' }}</el-button><el-button v-if="canEdit && row.baseRole !== 'STUDENT'" text @click="edit(row, false, true)">复制</el-button><el-button v-if="canEdit && row.baseRole !== 'STUDENT'" text @click="members(row)">维护成员</el-button></template></el-table-column></el-table>
    <el-dialog v-model="detailOpened" :title="detailRole?.name + ' · 角色工作区'" width="min(860px,95vw)">
      <nav class="toolbar"><el-button v-for="(label,key) in sections" :key="key" :type="detailSection===key?'primary':'default'" @click="detailSection=key;detailPage=1;loadDetail()">{{ label }}</el-button><el-button @click="edit(detailRole,!canEdit)">功能权限</el-button></nav>
      <el-alert v-if="detailError" :title="detailError" type="error" :closable="false"/>
      <el-table v-if="!detailError" :data="detail.items" v-loading="detailBusy"><el-table-column prop="name" :label="detailSection==='history'?'操作人':'成员姓名'"/><el-table-column v-if="detailSection==='members'" prop="loginName" label="登录账号"/><template v-if="detailSection==='scopes'"><el-table-column prop="kind" label="范围类型"/><el-table-column prop="object" label="负责对象"/></template><el-table-column v-if="detailSection==='history'" prop="reason" label="变更原因"/><el-table-column prop="statusLabel" label="状态／操作"/></el-table>
      <el-pagination v-if="detail.total>30" v-model:current-page="detailPage" :page-size="30" :total="detail.total" layout="prev,pager,next" @current-change="loadDetail"/>
      <p v-if="detailSection==='scopes'">当前负责对象按稳定编号授权；调整请进入管理范围与责任关系。</p>
    </el-dialog>
    <el-dialog v-model="opened" :title="readonly ? '查看角色权限' : form.id ? '维护角色权限' : '创建学校角色'" width="min(860px, 95vw)" :close-on-click-modal="false">
      <el-form label-position="top" :disabled="saving" @submit.prevent="submit"><div class="role-fields"><el-form-item label="角色名称" required><el-input v-model="form.name" :disabled="readonly" maxlength="100"/></el-form-item><el-form-item label="身份类型" required><el-select v-model="form.baseRole" :disabled="readonly || !!form.id"><el-option v-for="item in data.templates" :key="item.code" :value="item.code" :label="item.name"/></el-select></el-form-item><el-form-item label="状态"><el-select v-model="form.status" :disabled="readonly"><el-option value="ACTIVE" label="启用"/><el-option value="DISABLED" label="停用"/></el-select></el-form-item></div>
        <details v-if="preset" class="preset-review"><summary>与当前预配模板对照</summary>
          <p>对照身份：{{ preset.name }}。模板随当前安装版本提供，学校已有修改保持不变。逐项选择后仍须核对影响并保存，才会生效。</p>
          <h3>模板包含、当前未采用（{{ presetMissing.length }}项）</h3>
          <ul><li v-for="item in presetMissing" :key="item.code"><span>{{ item.name }}</span><el-button v-if="!readonly" text :disabled="saving || !!conflict" @click="choosePresetPermission(item.code,true)">加入本次调整</el-button></li></ul><p v-if="!presetMissing.length">当前已包含模板中的全部权限。</p>
          <h3>当前保留、模板未包含（{{ presetAdditional.length }}项）</h3>
          <ul><li v-for="item in presetAdditional" :key="item.code"><span>{{ item.name }}</span><el-button v-if="!readonly" text :disabled="saving || !!conflict" @click="choosePresetPermission(item.code,false)">列入本次撤销</el-button></li></ul><p v-if="!presetAdditional.length">当前没有模板以外的权限。</p>
          <p>模板之外的权限可能是学校的正常配置，不会自动撤销。敏感查看和密码重置仍须逐项确认。</p>
        </details>
        <fieldset :disabled="readonly"><legend>功能权限（敏感权限须逐项勾选）</legend><div class="permission-grid"><label v-for="item in catalog" :key="item.code"><input v-model="form.permissions" type="checkbox" :value="item.code" />{{ item.name }}</label></div></fieldset>
        <el-alert type="info" :closable="false" :title="`本次新增 ${added.length} 项、撤销 ${removed.length} 项；影响当前角色 ${affected} 名成员。保存后立即影响后续请求。`"/>
        <details v-if="added.length || removed.length"><summary>展开权限变更对比</summary><p>新增：{{ names(added) || '无' }}</p><p>撤销：{{ names(removed) || '无' }}</p></details>
        <template v-if="form.id"><p v-if="impactBusy" role="status">正在核对成员与在办事项…</p><RoleImpactSummary v-if="impact?.roleId===form.id" :impact="impact"/><el-button :loading="impactBusy" :disabled="saving" @click="refreshImpact()">重新核对在办影响</el-button></template>
        <el-checkbox v-if="!readonly" v-model="form.sensitiveConfirmed">已逐项核对本角色涉及的敏感查看与密码重置权限</el-checkbox>
        <el-form-item v-if="!readonly" label="调整原因" required><el-input v-model="form.reason" type="textarea" maxlength="500"/></el-form-item>
        <ConflictReview :conflict="conflict" :input="form" :permission-names="permissionNames" @reviewed="form.expectedVersion=$event;conflict=null;formError=''"/><el-alert v-if="formError" :title="formError" type="error" :closable="false"/>
        <el-button v-if="!readonly" native-type="submit" type="primary" :loading="saving" :disabled="impactBusy || (!!form.id && impact?.roleId!==form.id)">保存角色权限</el-button>
      </el-form>
    </el-dialog>
    <el-dialog v-model="memberOpened" title="维护角色成员" width="620px" :close-on-click-modal="false"><p>{{ target?.name }}；成员变更会立即生效，职责范围需另外指定。</p><SystemObjectSelect v-model="memberUser" path="/accounts" label="选择校内人员账号"/><el-radio-group v-model="memberEnabled"><el-radio :value="true">加入角色</el-radio><el-radio :value="false">撤销角色</el-radio></el-radio-group><el-input v-model="memberReason" placeholder="填写成员调整原因"/><el-button :loading="memberImpactBusy" :disabled="!memberUser || saving" @click="refreshImpact(true)">核对该人员在办影响</el-button><RoleImpactSummary v-if="memberImpactReady" :impact="memberImpact"/><p v-else>选定人员后请先核对在办影响，再确认成员变更。</p><ConflictReview :conflict="memberConflict" :input="target || {}" :permission-names="permissionNames" @reviewed="target.version=$event;memberConflict=null;formError=''"/><el-alert v-if="formError" :title="formError" type="error" :closable="false"/><template #footer><el-button type="primary" :loading="saving" :disabled="!!memberConflict || memberImpactBusy || !memberImpactReady" @click="saveMember">确认成员变更</el-button></template></el-dialog>
  </section>
</template>
<script setup>
import { ElAlert, ElButton, ElCheckbox, ElDialog, ElForm, ElFormItem, ElInput, ElOption, ElRadio, ElRadioGroup, ElSelect, ElTable, ElTableColumn, ElLoading, ElPagination } from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/checkbox/style/css'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/option/style/css'
import 'element-plus/es/components/radio/style/css'
import 'element-plus/es/components/radio-group/style/css'
import 'element-plus/es/components/select/style/css'
import 'element-plus/es/components/table/style/css'
import 'element-plus/es/components/loading/style/css'
import 'element-plus/es/components/pagination/style/css'
const vLoading = ElLoading.directive

import { computed, ref, onMounted } from 'vue'
import { get, save } from './systemApi'
import { getPermissionPatterns } from '@/security/permissionGate'
import { matchPermission } from '@/config/navPlan'
import SystemObjectSelect from './SystemObjectSelect.vue'
import ConflictReview from './ConflictReview.vue'
import RoleImpactSummary from './RoleImpactSummary.vue'
const conflict=ref(null),memberConflict=ref(null)
const permissionNames=computed(()=>Object.fromEntries(catalog.value.map(p=>[p.code,p.name])))
const data = ref({ items: [], catalog: [], templates: [] }), busy = ref(false), saving = ref(false), error = ref(''), formError = ref('')
const canEdit = computed(() => matchPermission(getPermissionPatterns(), 'system.role.manage'))
const catalog = computed(() => data.value.catalog.filter(p => !p.code.includes('*')))
const form = ref({ permissions: [] }), original = ref([]), affected = ref(0), opened = ref(false), readonly = ref(false)
const preset = computed(() => data.value.templates.find(item => item.code===form.value.baseRole && Array.isArray(item.permissions)))
const presetMissing = computed(() => preset.value ? catalog.value.filter(item => preset.value.permissions.includes(item.code) && !form.value.permissions.includes(item.code)) : [])
const presetAdditional = computed(() => preset.value ? catalog.value.filter(item => form.value.permissions.includes(item.code) && !preset.value.permissions.includes(item.code)) : [])
function choosePresetPermission(code, include) {
  if(readonly.value || !canEdit.value || saving.value || conflict.value)return
  const choices=include ? presetMissing.value : presetAdditional.value
  if(!choices.some(item=>item.code===code))return
  form.value.permissions=include ? [...form.value.permissions,code] : form.value.permissions.filter(item=>item!==code)
  form.value.sensitiveConfirmed=false
}
const added = computed(() => form.value.permissions.filter(p => !original.value.includes(p))), removed = computed(() => original.value.filter(p => !form.value.permissions.includes(p)))
const target = ref(null), memberOpened = ref(false), memberUser = ref(''), memberEnabled = ref(true), memberReason = ref('')
const impact=ref(null),impactBusy=ref(false),memberImpact=ref(null),memberImpactBusy=ref(false)
const memberImpactReady=computed(()=>memberImpact.value?.roleId===target.value?.id && memberImpact.value?.userId===memberUser.value)
let impactRun=0,memberImpactRun=0
async function refreshImpact(member=false){
  const id=member ? target.value?.id : form.value.id, userId=member ? memberUser.value : ''
  if(!id || (member && !userId) || saving.value)return
  const ticket=member ? ++memberImpactRun : ++impactRun, resultRef=member ? memberImpact : impact, loading=member ? memberImpactBusy : impactBusy
  resultRef.value=null;loading.value=true;formError.value=''
  try{const result=await get(`/roles/${id}/impact`,{userId});if(ticket===(member ? memberImpactRun : impactRun)){resultRef.value=result;if(!member)affected.value=result.memberCount}}
  catch(e){if(ticket===(member ? memberImpactRun : impactRun))formError.value=e.message}
  finally{if(ticket===(member ? memberImpactRun : impactRun))loading.value=false}
}
const names = codes => codes.map(code => catalog.value.find(p => p.code === code)?.name || '历史授权').join('、')
async function load() { busy.value = true; error.value = ''; try { data.value = await get('/roles') } catch (e) { error.value = e.message } finally { busy.value = false } }
async function edit(row, read = false, copy = false) {
  if(saving.value)return
  ++impactRun;impact.value=null;impactBusy.value=false
  conflict.value=null; readonly.value = read || row?.baseRole === 'STUDENT'; affected.value = copy ? 0 : row?.memberCount || 0
  const effective = catalog.value.filter(p => matchPermission(row?.permissions || [], p.code)).map(p => p.code)
  original.value = copy ? [] : effective
  form.value = { id: copy ? '' : row?.id, expectedVersion: copy ? 0 : row?.version || 0, name: copy ? `${row.name}副本` : row?.name || '', baseRole: row?.baseRole || 'INTERN_MENTOR', permissions: effective, status: row?.status || 'ACTIVE', sensitiveConfirmed: false, reason: '' }
  formError.value = ''; opened.value = true
  if(form.value.id)await refreshImpact()
}
async function submit() { if(saving.value || conflict.value || readonly.value || impactBusy.value || (form.value.id && impact.value?.roleId!==form.value.id))return; saving.value = true; formError.value = ''; try { const { id, ...body } = form.value; await save(`/roles${id ? '/'+id : ''}`, body, id ? 'PUT' : 'POST'); opened.value = false; await load() } catch (e) { formError.value = e.message;conflict.value=e.details?.current ? e.details : null } finally { saving.value = false } }
function members(row) { if(saving.value)return; ++memberImpactRun;memberImpact.value=null;memberImpactBusy.value=false;memberConflict.value=null; target.value = {...row}; memberUser.value = ''; memberReason.value = ''; memberEnabled.value = true; formError.value = ''; memberOpened.value = true }
async function saveMember() { if(saving.value || memberConflict.value || memberImpactBusy.value || !memberImpactReady.value)return; saving.value = true; formError.value = ''; try { await save(`/roles/${target.value.id}/members`, { userId: memberUser.value, enabled: memberEnabled.value, expectedVersion: target.value.version, reason: memberReason.value }); memberOpened.value = false; await load() } catch (e) { formError.value = e.message; memberConflict.value=e.details?.current ? e.details : null } finally { saving.value = false } }
const sections={members:'成员',scopes:'负责范围',history:'变更记录'}
const detailOpened=ref(false),detailRole=ref(null),detailSection=ref('members'),detailPage=ref(1),detail=ref({items:[],total:0}),detailBusy=ref(false),detailError=ref('')
let detailRun=0
async function loadDetail(){const run=++detailRun;detailBusy.value=true;detailError.value='';try{const result=await get(`/roles/${detailRole.value.id}/${detailSection.value}`,{page:detailPage.value});if(run===detailRun)detail.value=result}catch(e){if(run===detailRun){detail.value={items:[],total:0};detailError.value=e.message}}finally{if(run===detailRun)detailBusy.value=false}}
function inspect(row){detailRole.value=row;detailSection.value='members';detailPage.value=1;detailOpened.value=true;loadDetail()}
onMounted(load)
</script>
<style scoped>.role-fields{display:grid;grid-template-columns:2fr 2fr 1fr;gap:16px}.permission-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;max-height:330px;overflow:auto;padding:12px 0}.permission-grid label{display:flex;gap:6px;align-items:center}fieldset{border:1px solid var(--line);border-radius:8px;margin:12px 0}.el-alert,details,.el-checkbox{margin:12px 0}.el-input,.el-radio-group{margin:8px 0}.preset-review ul{list-style:none;padding:0;max-height:220px;overflow:auto}.preset-review li{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:4px 8px;border-bottom:1px solid var(--line)}.preset-review li span{overflow-wrap:anywhere}.preset-review li .el-button{flex-shrink:0}@media(max-width:700px){.role-fields,.permission-grid{grid-template-columns:1fr}}</style>
