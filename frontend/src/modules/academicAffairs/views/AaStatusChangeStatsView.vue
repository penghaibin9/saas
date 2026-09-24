<template>
  <ModulePageShell title="异动统计" subtitle="终审待生效与正式生效分开统计，明细保持当前身份范围" :role-name="ctx.currentRole.roleName" :data-scope-name="ctx.dataScope.scopeName" show-subtitle-in-concise>
    <template #actions><AppButton @click="load">刷新</AppButton></template>
    <ErrorState v-if="error" :description="error" @retry="load" /><LoadingState v-else-if="loading" />
    <div v-else class="sc-stats"><p>当前身份范围 · 全部可查询记录。尚未提供可靠学期归属和周期趋势，不以本学期样例替代。</p><div class="sc-metrics"><AppMetricCard title="累计异动" :value="data.total ?? '待核对'" accent="primary" /><AppMetricCard title="在途待审" :value="data.pending ?? '待核对'" accent="warning" /><AppMetricCard title="已通过待生效" :value="pendingEffective ?? '待核对'" accent="warning" /><AppMetricCard title="已正式生效" :value="data.effective ?? '待核对'" accent="success" /></div>
      <div class="sc-distribution"><AppSectionCard title="按异动类型"><p v-if="data.byType===null">类型统计未返回</p><EmptyState v-else-if="!data.byType.length" title="暂无类型数据" /><template v-else><AppG2Chart :spec="byTypeSpec" :height="240" /><button v-for="g in data.byType" :key="g.key" @click="drill('changeType',g.key)">{{ typeLabel(g.key) }} · {{ g.count ?? '待核对' }} · 查看明细</button></template></AppSectionCard><AppSectionCard title="按正式状态"><p v-if="data.byStatus===null">状态统计未返回</p><EmptyState v-else-if="!data.byStatus.length" title="暂无状态数据" /><template v-else><AppG2Chart :spec="byStatusSpec" :height="240" /><button v-for="g in data.byStatus" :key="g.key" @click="drill('status',g.key)">{{ statusLabel(g.key) }} · {{ g.count ?? '待核对' }} · 查看明细</button></template></AppSectionCard></div>
      <AppSectionCard title="同范围明细下钻"><p v-if="!detailFilter">选择上方类型或状态后读取明细。</p><template v-else><p>{{ detailLabel }}</p><ErrorState v-if="detailError" :description="detailError" @retry="loadDetail" /><LoadingState v-else-if="detailLoading" /><EmptyState v-else-if="!detailRows.length" title="当前范围暂无明细" /><DataTable v-else :columns="columns" :rows="detailRows" row-key="changeId" :pagination="{page:detailPage,pageSize:20,total:detailTotal}" @page-change="turnDetail"><template #cell-type="{row}">{{ typeLabel(row.changeType) }}</template><template #cell-status="{row}"><StatusTag :label="statusLabel(row.status)" :type="statusColor(row.status)" /></template><template #cell-action="{row}"><button @click="goDetail(row)">原申请详情</button></template></DataTable></template></AppSectionCard>
    </div>
  </ModulePageShell>
</template>
<script>
import {ModulePageShell,DataTable,StatusTag,LoadingState,ErrorState,EmptyState} from '@/components/business'
import {AppButton} from '@/components/ui'
import {AppSectionCard,AppMetricCard,AppG2Chart} from '@/components/common'
import {academicAffairsApi as api} from '../api/academic-affairs.api'
import {currentUserFromToken} from '@/services/http/client'
import {TYPE_LABEL,STATUS_LABEL,statusColor} from '../constants/status-change'
import {gradeError} from './parallel-c/grade-review'
const EMPTY=()=>({total:null,pending:null,effective:null,byType:null,byStatus:null})
export default {
 name:'AaStatusChangeStatsView',components:{ModulePageShell,DataTable,StatusTag,LoadingState,ErrorState,EmptyState,AppButton,AppSectionCard,AppMetricCard,AppG2Chart},props:{ctx:{type:Object,required:true}},
 data(){return {alive:true,seq:0,detailSeq:0,loading:true,error:'',data:EMPTY(),detailFilter:null,detailRows:[],detailTotal:0,detailPage:1,detailLoading:false,detailError:'',columns:[{key:'realName',title:'学生'},{key:'type',title:'异动类型'},{key:'status',title:'正式状态'},{key:'effectiveDate',title:'计划生效日期'},{key:'action',title:'回查入口'}]}},
 computed:{
  identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])},
  pendingEffective(){if(this.data.byStatus===null)return null;const row=this.data.byStatus.find(r=>r.key==='APPROVED_PENDING_EFFECTIVE');return row?row.count??null:0},
  byTypeSpec(){return this.chart((this.data.byType||[]).filter(r=>r.count!=null).map(r=>({name:this.typeLabel(r.key),value:r.count})))},
  byStatusSpec(){return this.chart((this.data.byStatus||[]).filter(r=>r.count!=null).map(r=>({name:this.statusLabel(r.key),value:r.count})))},
  detailLabel(){return this.detailFilter?.status?this.statusLabel(this.detailFilter.status):this.typeLabel(this.detailFilter?.changeType)}
 },
 watch:{identity(){this.clear();this.load()}},created(){this.load()},beforeUnmount(){this.alive=false;this.clear()},
 methods:{
  statusColor,typeLabel(v){return TYPE_LABEL[v]||'类型待核对'},statusLabel(v){return STATUS_LABEL[v]||'状态待核对'},
  chart(data){return {type:'interval',data,encode:{x:'name',y:'value'},axis:{y:{title:null}},style:{radiusTopLeft:4,radiusTopRight:4}}},
  clearDetail(){this.detailSeq++;this.detailRows=[];this.detailTotal=0;this.detailLoading=false;this.detailError=''},
  clear(){this.seq++;this.data=EMPTY();this.loading=false;this.error='';this.detailFilter=null;this.clearDetail()},
  async load(){this.clear();const seq=this.seq,identity=this.identity;const valid=()=>this.alive&&seq===this.seq&&identity===this.identity;this.loading=true;try{const res=await api.getStatusChangeStats();if(!valid())return;if(res?.code!==0)throw res;this.data={...EMPTY(),...res.data}}catch(err){if(valid())this.error=gradeError(err,'异动统计读取失败，请重试。')}finally{if(valid())this.loading=false}},
  drill(key,value){if(this.loading||this.error||!((key==='status'&&STATUS_LABEL[value])||(key==='changeType'&&TYPE_LABEL[value])))return;this.detailFilter={[key]:value};this.detailPage=1;this.loadDetail()},
  turnDetail(page){this.detailPage=page;this.loadDetail()},goDetail(row){this.$router.push(`/admin/academic-affairs/status-changes/${encodeURIComponent(row.changeId)}`)},
  async loadDetail(){if(!this.detailFilter)return;this.clearDetail();const seq=this.detailSeq,parent=this.seq,identity=this.identity,filter=JSON.stringify(this.detailFilter);const valid=()=>this.alive&&seq===this.detailSeq&&parent===this.seq&&identity===this.identity&&filter===JSON.stringify(this.detailFilter);this.detailLoading=true;try{const res=await api.getStatusChanges({...this.detailFilter,page:this.detailPage,pageSize:20});if(!valid())return;if(res?.code!==0)throw res;this.detailRows=res.data?.list||[];this.detailTotal=res.data?.total??this.detailRows.length}catch(err){if(valid()){if(/403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' '))){this.clear();this.error=gradeError(err)}else this.detailError=gradeError(err,'明细读取失败，请重试。')}}finally{if(valid())this.detailLoading=false}}
 }
}
</script>
<style scoped>
.sc-stats{display:grid;gap:18px}.sc-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.sc-distribution{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}p{font-size:13px;line-height:1.7;color:var(--text-500,#607087)}button{padding:7px 10px;margin:3px;border:1px solid var(--border-200,#d6e0ed);border-radius:6px;background:var(--bg-white,#fff);color:var(--primary-600,#285aab);cursor:pointer}@media(max-width:900px){.sc-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.sc-distribution{grid-template-columns:1fr}}
</style>
