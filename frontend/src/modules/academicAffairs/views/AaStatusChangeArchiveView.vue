<template>
  <ModulePageShell title="异动归档" subtitle="回查原申请与正式决定；归档封存结论以正式归档记录为准" :role-name="ctx.currentRole.roleName" :data-scope-name="ctx.dataScope.scopeName" show-subtitle-in-concise>
    <template #actions><AppButton @click="load">刷新</AppButton></template>
    <div class="sc-archive"><p class="sc-note">本页为原异动记录回查。已生效、已退回或已驳回不等于已归档；当前列表未提供封存版本与完整性结论。</p>
      <label>原申请结果<select v-model="status" @change="search"><option value="EFFECTIVE">已生效</option><option value="REJECTED">已驳回</option><option value="RETURNED">已退回</option><option value="APPROVED_PENDING_EFFECTIVE">已通过待生效</option><option value="SUBMITTED">已提交</option><option value="IN_REVIEW">审批中</option></select></label>
      <ErrorState v-if="error" :description="error" @retry="load" /><LoadingState v-else-if="loading" /><EmptyState v-else-if="!rows.length" title="当前筛选下暂无记录" description="此处无记录不代表归档完整性检查已通过。" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="changeId" :pagination="{page,pageSize,total}" @page-change="turnPage"><template #cell-student="{row}">{{ row.realName || '姓名待核对' }}</template><template #cell-type="{row}">{{ typeLabel(row.changeType) }}</template><template #cell-status="{row}"><StatusTag :label="statusLabel(row.status)" :type="statusColor(row.status)" /></template><template #cell-date="{row}">{{ row.effectiveDate || '未设置计划日期' }}</template><template #cell-archive>封存结论待查询</template><template #cell-material>材料版本未返回</template><template #cell-action="{row}"><button @click="goDetail(row)">原申请与绑定材料</button></template></DataTable>
      <p>异动记录按当前身份范围读取，尚无可靠学期归属。<router-link to="/admin/academic-affairs/archive/export">进入教务归档查询正式导出材料</router-link></p>
    </div>
  </ModulePageShell>
</template>
<script>
import {ModulePageShell,DataTable,StatusTag,LoadingState,ErrorState,EmptyState} from '@/components/business'
import {AppButton} from '@/components/ui'
import {academicAffairsApi as api} from '../api/academic-affairs.api'
import {currentUserFromToken} from '@/services/http/client'
import {TYPE_LABEL,STATUS_LABEL,statusColor} from '../constants/status-change'
import {gradeError} from './parallel-c/grade-review'
export default {
 name:'AaStatusChangeArchiveView',components:{ModulePageShell,DataTable,StatusTag,LoadingState,ErrorState,EmptyState,AppButton},props:{ctx:{type:Object,required:true}},
 data(){return {alive:true,seq:0,loading:true,error:'',rows:[],total:0,page:1,pageSize:20,status:'EFFECTIVE',columns:[{key:'student',title:'学生'},{key:'type',title:'异动类型'},{key:'status',title:'原申请结果'},{key:'date',title:'计划生效日期'},{key:'archive',title:'归档事实'},{key:'material',title:'材料版本'},{key:'action',title:'回查入口'}]}},
 computed:{identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])}},
 watch:{identity(){this.clear();this.page=1;this.load()}},created(){this.load()},beforeUnmount(){this.alive=false;this.clear()},
 methods:{
  statusColor,typeLabel(v){return TYPE_LABEL[v]||'类型待核对'},statusLabel(v){return STATUS_LABEL[v]||'状态待核对'},
  clear(){this.seq++;this.rows=[];this.total=0;this.error='';this.loading=false},
  search(){this.page=1;this.load()},turnPage(page){this.page=page;this.load()},goDetail(row){this.$router.push(`/admin/academic-affairs/status-changes/${encodeURIComponent(row.changeId)}`)},
  async load(){this.clear();const seq=this.seq,identity=this.identity,status=this.status;const valid=()=>this.alive&&seq===this.seq&&identity===this.identity&&status===this.status;this.loading=true;try{const res=await api.getStatusChanges({status,page:this.page,pageSize:this.pageSize});if(!valid())return;if(res?.code!==0)throw res;this.rows=res.data?.list||[];this.total=res.data?.total??this.rows.length}catch(err){if(valid())this.error=gradeError(err,'原异动记录读取失败，请重试。')}finally{if(valid())this.loading=false}}
 }
}
</script>
<style scoped>
.sc-archive{display:grid;gap:16px}.sc-note{padding:14px;border-radius:8px;background:var(--primary-50,#edf3ff);color:var(--primary-700,#244f91)}p{font-size:13px;line-height:1.7}label{display:flex;align-items:center;gap:12px;font-size:13px}select,button{border:1px solid var(--border-200,#d6e0ed);border-radius:7px;padding:8px 12px;background:var(--bg-white,#fff);color:inherit}button{cursor:pointer}
</style>
