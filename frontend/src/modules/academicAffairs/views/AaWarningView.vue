<template>
  <ModulePageShell class="aa-warning-workspace" title="预警扫描与列表" subtitle="由正式学业事实扫描生成，再交责任老师跟进" :role-name="ctx.currentRole.roleName" :data-scope-name="ctx.dataScope.scopeName" show-subtitle-in-concise>
    <template #actions><AppButton v-if="canScan" variant="primary" :disabled="scanning || !!pending" @click="scan">执行挂科预警扫描</AppButton><AppButton :disabled="scanning || !!pending" @click="goHandle">前往跟进控制台</AppButton></template>
    <div class="warning-page">
      <section class="warning-scope"><strong>只处理当前岗位和当前范围的对象</strong><span>由正式学业事实扫描生成，再交责任老师跟进</span></section>
      <section v-if="receipt" class="warning-receipt" role="status"><b>{{ receipt.verified ? '扫描回执与当前名单已读取' : '扫描结果待核实' }}</b><p>{{ receipt.message }}</p><AppButton v-if="pending" :disabled="scanning || checking" @click="verify">只读核对当前预警</AppButton></section>
      <p v-if="actionError" role="alert" class="warning-error">{{ actionError }}</p>
      <section class="warning-ledger"><header><div><h2>学业预警 · 责任队列</h2><p>当前列表来自正式预警台账</p></div><span v-if="!loading && !error">共 {{ pagination.total }} 条</span></header><div class="warning-filter"><label>预警级别<AppSelect v-model="filters.level" :options="levelOptions" :disabled="scanning || !!pending" @change="search" /></label><AppButton :disabled="scanning || !!pending" @click="search">查询</AppButton></div>
      <ErrorState v-if="error" :description="error" @retry="load" /><LoadingState v-else-if="loading" /><EmptyState v-else-if="!rows.length" title="当前范围暂无预警" description="无记录不代表所有规则已扫描或全部风险已排除。" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="warningId" :pagination="pagination" @page-change="onPageChange"><template #cell-level="{row}"><AppStatusTag :type="warningColor(row.level)" dot>{{ levelLabel(row.level) }}</AppStatusTag></template><template #cell-source="{row}">{{ sourceLabel(row.sourceCode) }}</template><template #cell-action="{row}"><button :disabled="scanning || !!pending" @click="goHandle(row)">原预警与跟进记录</button></template></DataTable>
      </section><p>此入口扫描挂科规则；其它来源可在控制台查询。通知生成、送达和已读是不同结果，以通知台账为准。</p>
    </div>
    <AppConfirmDialog v-model:visible="confirmVisible" title="确认执行挂科预警扫描" :message="confirmMessage" :submitting="scanning" :confirm-disabled="!!pending" @confirm="confirmScan" />
  </ModulePageShell>
</template>
<script>
import {ModulePageShell,DataTable,LoadingState,ErrorState,EmptyState} from '@/components/business'
import {AppButton} from '@/components/ui'
import {AppStatusTag,AppSelect,AppConfirmDialog} from '@/components/common'
import {academicAffairsApi,academicAffairsWarningApi} from '../api/academic-affairs.api'
import {WARNING_LEVEL,WARNING_SOURCE,warningColor} from '../constants/grade-graduation'
import {currentUserFromToken} from '@/services/http/client'
import {matchPermission} from '@/config/navPlan'
import {gradeError} from './parallel-c/grade-review'
export default {
 name:'AaWarningView',components:{ModulePageShell,DataTable,LoadingState,ErrorState,EmptyState,AppButton,AppStatusTag,AppSelect,AppConfirmDialog},props:{ctx:{type:Object,required:true}},
 data(){return {alive:true,scope:0,seq:0,loading:true,error:'',actionError:'',rows:[],scanning:false,checking:false,pending:null,receipt:null,command:null,confirmVisible:false,filters:{level:''},pagination:{page:1,pageSize:20,total:0},columns:[{key:'studentName',title:'学生'},{key:'level',title:'级别'},{key:'reason',title:'预警原因'},{key:'source',title:'来源'},{key:'action',title:'跟进入口'}]}},
 computed:{identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])},canScan(){return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.warning.rule.manage')},levelOptions(){return [{value:'',label:'全部级别'},...Object.entries(WARNING_LEVEL).map(([value,label])=>({value,label}))]},confirmMessage(){return this.command?`当前岗位范围内按「${this.command.rule.label}」扫描，阈值 ${this.command.rule.value}。符合规则时可能生成或更新预警及通知；操作后重新查询台账。`:''}},
 watch:{identity(){this.clear();this.load()}},created(){this.load()},beforeUnmount(){this.alive=false;this.clear()},
 methods:{
  warningColor,levelLabel(v){return WARNING_LEVEL[v]||'级别待核对'},sourceLabel(v){return WARNING_SOURCE[v]||({ATTENDANCE_ABSENT:'旷课预警',OTHER:'其它预警'})[v]||'来源待核对'},
  capture(){return {scope:this.scope,identity:this.identity}},valid(c){return this.alive&&c.scope===this.scope&&c.identity===this.identity},
  clear(){this.scope++;this.seq++;this.rows=[];this.pagination.total=0;this.pending=null;this.receipt=null;this.command=null;this.confirmVisible=false;this.loading=false;this.scanning=false;this.checking=false;this.error='';this.actionError=''},
  fail(err,fallback){if(/403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' ')))this.clear();this.actionError=gradeError(err,fallback)},
  goHandle(row){if(this.scanning||this.pending)return;this.$router.push({path:'/admin/academic-affairs/warnings/console',query:row?.warningId?{tab:'followup',warningId:String(row.warningId)}:{tab:'followup'}})},
  search(){if(this.scanning||this.pending)return;this.pagination.page=1;this.command=null;this.confirmVisible=false;this.load()},onPageChange(page){if(this.scanning||this.pending)return;this.pagination.page=page;this.command=null;this.confirmVisible=false;this.load()},
  async load(){const c=this.capture(),seq=++this.seq;this.loading=true;this.error='';this.rows=[];this.pagination.total=0;try{const res=await academicAffairsApi.getWarnings({level:this.filters.level||undefined,page:this.pagination.page,pageSize:20});if(!this.valid(c)||seq!==this.seq)return false;if(res?.code!==0)throw res;if(!Array.isArray(res.data?.list))throw {code:503};this.rows=res.data.list;this.pagination.total=res.data.total??this.rows.length;return true}catch(err){if(this.valid(c)&&seq===this.seq){this.fail(err,'预警列表读取失败，请重试。');this.error=gradeError(err,'预警列表读取失败，请重试。')}return false}finally{if(this.valid(c)&&seq===this.seq)this.loading=false}},
  async readRule(c){const res=await academicAffairsWarningApi.getRules();if(!this.valid(c))return null;if(res?.code!==0)throw res;const rule=res.data?.items?.find(r=>r.key==='warning_fail_threshold');if(!rule||!Number.isFinite(rule.value))throw {code:503};return rule},
  async scan(){if(!this.canScan||this.scanning||this.pending)return;const c=this.capture();this.scanning=true;this.actionError='';try{const rule=await this.readRule(c);if(!this.valid(c))return;this.command={...c,rule:{...rule}};this.confirmVisible=true}catch(err){if(this.valid(c))this.fail(err,'当前扫描规则读取失败，请重试。')}finally{if(this.valid(c))this.scanning=false}},
  async confirmScan(){const c=this.command;if(!c||!this.valid(c)||!this.canScan||this.scanning||this.pending)return;this.scanning=true;try{const rule=await this.readRule(c);if(!this.valid(c))return;if(rule.value!==c.rule.value)throw {code:409};this.pending=c;this.receipt={verified:false,message:'本次扫描结果待核实，请勿重复执行。'};let res;try{res=await academicAffairsApi.scanWarnings()}catch(err){res=err}if(!this.valid(c))return;if(res?.code!==0&&/403|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pending=null;this.receipt=null;throw res}c.ack=res?.code===0&&Number.isFinite(res.data?.created)&&Number.isFinite(res.data?.updated)?res.data:null;this.confirmVisible=false;this.command=null;await this.verify()}catch(err){if(this.valid(c)){this.command=null;this.confirmVisible=false;this.fail(err,'扫描未确认，请核对原规则与办理范围。')}}finally{if(this.valid(c))this.scanning=false}},
  async verify(){const c=this.pending;if(!c||!this.valid(c)||this.checking)return;this.checking=true;try{const read=await this.load();if(!this.valid(c)||!read)return;if(!c.ack){this.actionError='当前预警列表已回读，但不能证明本次扫描是否执行，请勿重复扫描。';return}const notification=c.ack.notificationState==='VERIFIED'&&Number.isFinite(c.ack.notified)?`通知对象 ${c.ack.notified} 个（送达与已读仍以通知台账为准）`:'通知结果待核对';this.receipt={verified:true,message:`扫描回执：新增 ${c.ack.created} 条、更新 ${c.ack.updated} 条；${notification}。已重新读取当前筛选下的正式名单。`};this.pending=null;this.actionError=''}finally{if(this.valid(c))this.checking=false}}
 }
}
</script>
<style scoped>
.warning-page{display:grid;gap:16px}.warning-scope{display:grid;gap:3px;padding:13px 16px;border:1px solid #d7e4fb;border-radius:10px;background:#edf3ff;color:#285aab}.warning-scope span{font-size:12px}.warning-receipt{padding:14px;background:var(--primary-50,#edf3ff);border-radius:8px}.warning-ledger{overflow:hidden;border:1px solid var(--card-b,#dce5ef);border-radius:12px;background:#fff}.warning-ledger>header{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:15px 17px;border-bottom:1px solid var(--card-b,#dce5ef)}.warning-ledger h2{margin:0;font-size:16px}.warning-ledger header p,.warning-ledger header span{margin:4px 0 0;color:var(--t3,#65778b);font-size:12px}.warning-filter{padding:12px 16px}.warning-filter,.warning-filter label{display:flex;align-items:center;gap:12px}.warning-ledger :deep(.dt){border:0;border-radius:0;box-shadow:none}.warning-error{color:var(--danger-600,#b42318)}p{font-size:13px;line-height:1.7}button{cursor:pointer}
</style>
