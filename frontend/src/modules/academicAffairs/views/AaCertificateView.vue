<template>
  <ModulePageShell
    title="毕业证书管理"
    subtitle="证书只从正式终审结论生成；登记发放与作废均锁定当前证书并回读正式台账"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions><AppButton variant="primary" :disabled="!canManage || !!pendingCommand" @click="openGenerate">批量生成证书</AppButton></template>

    <div class="aacert-stack">
      <GraduationStageRail :active="5" />
      <section class="aacert-metrics" aria-label="证书正式台账概览">
        <article><span>证书总数</span><strong>{{ metrics.total }}</strong><small>当前权限范围内正式记录</small></article>
        <article><span>已生成</span><strong>{{ metrics.generated }}</strong><small>等待登记发放</small></article>
        <article><span>已发放</span><strong>{{ metrics.issued }}</strong><small>已完成发放登记</small></article>
        <article><span>已作废</span><strong>{{ metrics.voided }}</strong><small>编号保留且不可回收</small></article>
      </section>
      <section class="aacert-context">
        <div><span>对象来源</span><strong>毕业资格正式终审结果</strong><small>毕业与结业结论分别生成对应证书</small></div>
        <div><span>当前责任</span><strong>证书管理岗</strong><small>核对编号、电子注册号与签发信息</small></div>
        <div><span>当前阻断</span><strong>{{ metrics.generated ? `${metrics.generated} 张待发放` : '当前无待发放证书' }}</strong><small>作废后须重新走正式生成命令</small></div>
        <div><span>下一岗位</span><strong>学生领取 / 受控纠错</strong><small>完成后返回证书台账原页</small></div>
      </section>
      <section v-if="actionReceipt" :class="['aacert-receipt', { 'is-pending': !actionReceipt.verified }]" role="status">
        <div><strong>{{ actionReceipt.verified ? '✓' : '…' }} {{ actionReceipt.title }}</strong><span>{{ actionReceipt.subject }}</span></div>
        <div><small>正式结果</small><b>{{ actionReceipt.result }}</b></div>
        <div><small>下一责任</small><b>{{ actionReceipt.next }}</b></div>
      </section>
      <AppInlineAlert v-if="pendingCommand" type="warning" description="上一次写操作结果待核实，请勿重复提交；请保留当前页面并由有权限人员核对正式证书台账。" />

      <div class="aacert-bar">
        <AppTextInput v-model="keyword" placeholder="学号 / 姓名 / 证书编号" style="max-width:240px" @change="search" />
        <AppSelect v-model="statusFilter" :options="statusOptions" style="max-width:150px" @change="search" />
        <AppSelect v-model="typeFilter" :options="typeOptions" style="max-width:150px" @change="search" />
      </div>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无证书" description="从已形成毕业或结业正式终审结论的审核批次生成" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="certificateId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }"><div class="mp-cell-main">{{ row.studentName || `学生 ${row.studentId}` }}</div><div class="mp-cell-sub">{{ row.studentNo || row.studentId }} · {{ row.majorName || '专业待确认' }}</div></template>
        <template #cell-cert="{ row }"><div class="mp-cell-main">{{ row.certNo }}</div><div class="mp-cell-sub">{{ row.eRegNo ? `电子注册号 ${row.eRegNo}` : '无电子注册号' }}</div></template>
        <template #cell-source="{ row }"><div class="mp-cell-main">审核批次 #{{ row.auditBatchId || '—' }}</div><div class="mp-cell-sub">签发 {{ row.issueDate || row.issueYear || '待确认' }}</div></template>
        <template #cell-type="{ row }"><StatusTag :type="row.certType === 'GRADUATION' ? 'success' : 'warning'" :label="row.certType === 'GRADUATION' ? '毕业证' : '结业证'" dot /></template>
        <template #cell-status="{ row }"><StatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot /></template>
        <template #cell-ops="{ row }">
          <button v-if="row.status === 'GENERATED'" class="mp-link" :disabled="!canManage || !!pendingCommand" @click="issue(row)">登记发放</button>
          <button v-if="row.status !== 'VOIDED'" class="mp-link is-danger" :disabled="!canManage || !!pendingCommand" @click="openVoid(row)">作废</button>
          <span v-if="row.status === 'VOIDED'" class="mp-cell-sub">{{ row.voidReason || '作废原因待确认' }}</span>
        </template>
      </DataTable>
    </div>

    <AppDrawer :visible="genVisible" title="从正式终审批次生成证书" mode="modal" size="large" @close="closeGenerate">
      <div class="aacert-form">
        <AppFormItem label="毕业审核批次" required><AppGraduationBatchPicker v-model="genForm.batchId" :query="{ status: 'FINALIZED' }" placeholder="选择已终审批次" :disabled="saving" /></AppFormItem>
        <AppFormItem label="编号前缀（学校代码）" required><AppTextInput v-model="genForm.prefix" placeholder="如 13899" :disabled="saving" /></AppFormItem>
        <AppFormItem label="签发年份" required><AppTextInput v-model="genForm.year" placeholder="如 2026" :disabled="saving" /></AppFormItem>
        <AppFormItem label="电子注册号前缀"><AppTextInput v-model="genForm.eRegPrefix" placeholder="选填；空=不生成电子注册号" :disabled="saving" /></AppFormItem>
        <AppFormItem label="签发日期"><AppDatePicker v-model="genForm.issueDate" :disabled="saving" /></AppFormItem>
        <AppInlineAlert type="info" description="正式规则：毕业结论生成毕业证，结业结论生成结业证；已有未作废证书自动跳过，证书编号连续且永久不回收。" />
        <AppInlineAlert v-if="genError" type="danger" :description="genError" />
      </div>
      <template #footer><AppButton variant="ghost" :disabled="saving" @click="closeGenerate">取消</AppButton><AppButton variant="primary" :loading="saving" :disabled="!!pendingCommand" @click="submitGenerate">生成并回读</AppButton></template>
    </AppDrawer>
    <AppDrawer :visible="voidVisible" :title="`作废证书 · ${voidRow ? voidRow.certNo : ''}`" mode="modal" size="small" @close="closeVoid">
      <div class="aacert-form">
        <AppInlineAlert v-if="voidRow" type="warning" :description="`当前锁定：${voidRow.studentName || voidRow.studentNo} · ${voidRow.certNo}；作废后编号不回收。`" />
        <AppFormItem label="作废原因（≥5字）" required><AppTextarea v-model="voidReason" placeholder="如：打印信息有误需补发" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="voidError" type="danger" :description="voidError" />
      </div>
      <template #footer><AppButton variant="ghost" :disabled="saving" @click="closeVoid">取消</AppButton><AppButton variant="danger" :loading="saving" :disabled="!!pendingCommand" @click="submitVoid">作废并回读</AppButton></template>
    </AppDrawer>
    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" :submitting="saving" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect, AppGraduationBatchPicker, AppDatePicker } from '@/components/common'
import { academicAffairsApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import GraduationStageRail from '@/modules/academicAffairs/components/graduation/GraduationStageRail.vue'
import { currentUserFromToken } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'

const exactId = value => typeof value === 'string' && /^[1-9]\d*$/.test(value) ? value : (typeof value === 'number' && Number.isSafeInteger(value) && value > 0 ? String(value) : '')
const failureText = (err, fallback) => err?.message || ({ 403: '无权读取或办理当前数据范围', 409: '正式状态已变化，请重新加载', 422: '提交内容不符合业务规则' }[Number(err?.code)]) || fallback

export default {
  name: 'AaCertificateView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppTextInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect, AppGraduationBatchPicker, AppDatePicker, GraduationStageRail },
  props: { ctx: { type: Object, required: true } },
  data() { return {
    alive: true, scope: 0, listSeq: 0, pendingCommand: null,
    loading: true, error: '', rows: [], keyword: '', statusFilter: '', typeFilter: '',
    pagination: { page: 1, pageSize: 20, total: 0 }, metrics: { total: 0, generated: 0, issued: 0, voided: 0 },
    statusOptions: [{ label: '全部状态', value: '' }, { label: '已生成', value: 'GENERATED' }, { label: '已发放', value: 'ISSUED' }, { label: '已作废', value: 'VOIDED' }],
    typeOptions: [{ label: '全部类型', value: '' }, { label: '毕业证', value: 'GRADUATION' }, { label: '结业证', value: 'COMPLETION' }],
    columns: [{ key: 'student', title: '学生对象' }, { key: 'cert', title: '证书编号' }, { key: 'source', title: '正式来源' }, { key: 'type', title: '类型' }, { key: 'status', title: '状态' }, { key: 'ops', title: '当前主动作', width: '170px' }],
    genVisible: false, genForm: { batchId: '', prefix: '', year: '', eRegPrefix: '', issueDate: '' }, genError: '',
    voidVisible: false, voidRow: null, voidReason: '', voidError: '', saving: false,
    confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null, actionReceipt: null
  } },
  computed: {
    identity(){const user=currentUserFromToken()||{};return JSON.stringify([user.tenantId,user.userId,user.activeContextId,user.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])},
    canManage(){return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.graduationCert.manage')}
  },
  watch: { identity(){this.reloadForIdentity()} },
  async created(){await this.load();await this.loadMetrics()},
  beforeUnmount(){this.alive=false;this.invalidate()},
  methods: {
    statusLabel(status){return {GENERATED:'已生成',ISSUED:'已发放',VOIDED:'已作废'}[status]||'状态待确认'},
    statusTone(status){return status==='ISSUED'?'success':status==='VOIDED'?'danger':'primary'},
    denied(err){return /403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' '))},
    invalidate(){this.scope++;this.listSeq++;this.rows=[];this.error='';this.loading=false;this.pendingCommand=null;this.pendingAction=null;this.confirmVisible=false;this.genVisible=false;this.voidVisible=false;this.actionReceipt=null},
    current(token){return this.alive&&token.scope===this.scope&&token.identity===this.identity},
    async reloadForIdentity(){this.invalidate();await this.load();if(this.alive)await this.loadMetrics()},
    fail(err,fallback){if(this.denied(err))this.invalidate();return failureText(err,fallback)},
    signature(row){return JSON.stringify([String(row?.certificateId||''),String(row?.auditBatchId||''),row?.studentNo||'',row?.certNo||'',row?.status||'',row?.voidReason||''])},
    search(){this.pagination.page=1;this.load()},
    onPageChange(page){if(!page||page===this.pagination.page||this.loading)return;this.pagination.page=page;this.load()},
    async load(){const token={scope:this.scope,identity:this.identity,seq:++this.listSeq,page:this.pagination.page};this.loading=true;this.error='';try{const params={page:token.page,pageSize:this.pagination.pageSize,keyword:this.keyword||undefined,status:this.statusFilter||undefined,certType:this.typeFilter||undefined};const res=await api.listCertificates(params);if(!this.current(token)||token.seq!==this.listSeq||token.page!==this.pagination.page)return;if(res?.code!==0||!Array.isArray(res.data?.list))throw res;this.rows=res.data.list;this.pagination.total=Number(res.data.total||0)}catch(err){if(this.current(token)&&token.seq===this.listSeq)this.error=this.fail(err,'证书台账加载失败')}finally{if(this.current(token)&&token.seq===this.listSeq)this.loading=false}},
    async loadMetrics(){const token={scope:this.scope,identity:this.identity};try{const values=[];for(const status of ['','GENERATED','ISSUED','VOIDED']){const res=await api.listCertificates({page:1,pageSize:1,status:status||undefined});if(!this.current(token))return;if(res?.code!==0)throw res;values.push(Number(res.data?.total||0))}[this.metrics.total,this.metrics.generated,this.metrics.issued,this.metrics.voided]=values}catch(err){if(this.denied(err)&&this.current(token))this.invalidate()}},
    async readCertificate(snapshot){const id=exactId(snapshot?.certificateId);if(!id||!snapshot?.certNo)return null;const res=await api.listCertificates({keyword:snapshot.certNo,page:1,pageSize:100});if(res?.code!==0||!Array.isArray(res.data?.list))throw res;return res.data.list.find(row=>exactId(row.certificateId)===id&&row.certNo===snapshot.certNo)||null},
    openGenerate(){if(!this.canManage||this.pendingCommand)return;this.genForm={batchId:'',prefix:'',year:'',eRegPrefix:'',issueDate:''};this.genError='';this.genVisible=true},
    closeGenerate(){if(this.saving)return;this.genVisible=false;this.genError=''},
    async submitGenerate(){
      if(!this.canManage||this.saving||this.pendingCommand)return
      const batchId=exactId(this.genForm.batchId),prefix=this.genForm.prefix.trim(),year=this.genForm.year.trim();if(!batchId||!prefix||!/^\d{4}$/.test(year)){this.genError='请选择正式批次，并填写编号前缀与四位签发年份';return}
      const token={scope:this.scope,identity:this.identity},body={prefix,year,eRegPrefix:this.genForm.eRegPrefix.trim()||undefined,issueDate:this.genForm.issueDate||undefined};this.saving=true
      try{const before=await api.listCertificates({batchId,page:1,pageSize:1});if(!this.current(token))return;if(before?.code!==0)throw before;const beforeTotal=Number(before.data?.total||0);this.pendingCommand={kind:'generate',batchId,prefix,year};let result;try{result=await api.generateCertificates(batchId,body)}catch(err){result=err}if(!this.current(token))return;if(result?.code!==0&&/403|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([result?.code,result?.bizCode].join(' '))){this.pendingCommand=null;throw result}const after=await api.listCertificates({batchId,page:1,pageSize:1});if(!this.current(token))return;const created=Number(result?.data?.created),skipped=Number(result?.data?.skipped),afterTotal=Number(after?.data?.total);if(result?.code===0&&Number.isFinite(created)&&Number.isFinite(skipped)&&after?.code===0&&afterTotal>=beforeTotal+created){this.pendingCommand=null;this.genVisible=false;this.actionReceipt={verified:true,title:'证书生成完成',subject:`审核批次 #${batchId}`,result:`生成 ${created} 张 · 跳过已有 ${skipped} 张`,next:'证书管理岗核对编号并登记发放'};toast.success('已回读正式证书台账');await Promise.all([this.load(),this.loadMetrics()])}else{this.actionReceipt={verified:false,title:'生成结果待核实',subject:`审核批次 #${batchId}`,result:'当前回读不足以证明本次命令完成',next:'请勿重复生成，由有权限人员核对正式台账'}}}
      catch(err){if(this.current(token))this.genError=this.fail(err,'证书生成失败')}finally{if(this.current(token))this.saving=false}
    },
    issue(row){if(!this.canManage||this.saving||this.pendingCommand||row.status!=='GENERATED')return;const snapshot=JSON.parse(JSON.stringify(row));this.confirmTitle='登记发放';this.confirmMessage=`锁定证书 ${snapshot.certNo}，确认登记发放给「${snapshot.studentName||snapshot.studentNo}」？`;this.pendingAction=()=>this.performCertificateWrite('issue',snapshot,()=>api.issueCertificate(snapshot.certificateId),fresh=>fresh.status==='ISSUED',{title:'证书已登记发放',result:'正式台账状态：已发放',next:'学生领取；异常改走受控作废补发'});this.confirmVisible=true},
    openVoid(row){if(!this.canManage||this.saving||this.pendingCommand||row.status==='VOIDED')return;this.voidRow=JSON.parse(JSON.stringify(row));this.voidReason='';this.voidError='';this.voidVisible=true},
    closeVoid(){if(this.saving)return;this.voidVisible=false;this.voidRow=null;this.voidError=''},
    async submitVoid(){if(!this.canManage||this.saving||this.pendingCommand||!this.voidRow)return;const reason=this.voidReason.trim();if(reason.length<5){this.voidError='作废原因至少 5 字';return}const ok=await this.performCertificateWrite('void',this.voidRow,()=>api.voidCertificate(this.voidRow.certificateId,reason),fresh=>fresh.status==='VOIDED'&&fresh.voidReason===reason,{title:'证书已作废',result:`正式原因：${reason}`,next:'编号保留；补发须重新执行正式生成命令'});if(ok)this.closeVoid()},
    async performCertificateWrite(kind,snapshot,send,verify,receipt){
      if(this.pendingCommand||this.saving)return false;const token={scope:this.scope,identity:this.identity};this.saving=true
      try{const before=await this.readCertificate(snapshot);if(!this.current(token))return false;if(!before||this.signature(before)!==this.signature(snapshot))throw {code:409,message:'证书状态已变化，请重新加载'};this.pendingCommand={kind,certificateId:snapshot.certificateId,signature:this.signature(snapshot)};let result;try{result=await send()}catch(err){result=err}if(!this.current(token))return false;if(result?.code!==0&&/403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([result?.code,result?.bizCode].join(' '))){this.pendingCommand=null;throw result}const after=await this.readCertificate(snapshot);if(!this.current(token))return false;if(result?.code===0&&after&&verify(after)){this.pendingCommand=null;this.actionReceipt={verified:true,...receipt,subject:`${after.studentName||after.studentNo} · ${after.certNo}`};toast.success(receipt.title);await Promise.all([this.load(),this.loadMetrics()]);return true}this.actionReceipt={verified:false,title:'证书操作待核实',subject:`${snapshot.studentName||snapshot.studentNo} · ${snapshot.certNo}`,result:'当前回读不足以证明本次命令完成',next:'请勿重复操作，由证书管理岗核对正式台账'};return false}
      catch(err){if(this.current(token))toast.error(this.fail(err,'证书操作失败'));return false}finally{if(this.current(token))this.saving=false}
    },
    onConfirm(){const action=this.pendingAction;this.pendingAction=null;if(action)action()}
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aacert-stack { display: grid; gap: 14px; }
.aacert-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.aacert-metrics article { display: grid; gap: 5px; padding: 16px 18px; border: 1px solid #dce6f3; border-radius: 11px; background: #fff; }
.aacert-metrics span, .aacert-metrics small, .aacert-context span, .aacert-context small, .aacert-receipt span, .aacert-receipt small { color: #748299; font-size: 12px; }
.aacert-metrics strong { color: #1d4f98; font-size: 25px; }
.aacert-context { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); overflow: hidden; border: 1px solid #dce6f3; border-radius: 11px; background: #fff; }
.aacert-context > div { display: grid; gap: 5px; padding: 14px 16px; border-right: 1px solid #e8eef6; }
.aacert-context > div:last-child { border-right: 0; }.aacert-context strong { color: #193961; font-size: 14px; }
.aacert-receipt { display: grid; grid-template-columns: minmax(0,1fr) auto minmax(220px,auto); gap: 18px; align-items: center; padding: 13px 15px; border: 1px solid #a7d7b4; border-radius: 11px; background: #f3fbf5; }
.aacert-receipt.is-pending { border-color: #efd19a; background: #fff9ed; }.aacert-receipt strong, .aacert-receipt b, .aacert-receipt span, .aacert-receipt small { display: block; }.aacert-receipt strong { color: #16803c; }.aacert-receipt.is-pending strong { color: #a45d05; }.aacert-receipt b { margin-top: 4px; font-size: 12px; }
.aacert-bar { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px; border: 1px solid #dce6f3; border-radius: 11px; background: #fff; }.aacert-form { display: flex; flex-direction: column; gap: 12px; }
@media (max-width: 900px) { .aacert-metrics, .aacert-context { grid-template-columns: repeat(2, minmax(0, 1fr)); } .aacert-context > div:nth-child(2) { border-right: 0; } }
@media (max-width: 620px) { .aacert-metrics, .aacert-context, .aacert-receipt { grid-template-columns: 1fr; } .aacert-context > div { border-right: 0; border-bottom: 1px solid #e8eef6; } }
</style>
