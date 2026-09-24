<template>
  <ModulePageShell title="异动审批" subtitle="本节点审核不代替终审生效；先核对来源、材料与当前节点" :role-name="ctx.currentRole.roleName" :data-scope-name="ctx.dataScope.scopeName" show-subtitle-in-concise>
    <div class="sc-stack">
      <fieldset :disabled="busy"><label>状态<select v-model="status" @change="search"><option value="SUBMITTED">已提交</option><option value="IN_REVIEW">审批中</option></select></label><label>异动类型<select v-model="changeType" @change="search"><option value="">全部类型</option><option v-for="(label,value) in types" :key="value" :value="value">{{ label }}</option></select></label><button @click="load">刷新队列</button></fieldset>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-if="loading" />
      <EmptyState v-else-if="!rows.length && !error" title="当前筛选下暂无申请" description="列表按当前数据范围查询，具体节点动作在选中申请后核对。" />
      <div v-else class="sc-workbench">
        <aside><h3>申请队列 <small>{{ total }} 条</small></h3><button v-for="row in rows" :key="row.changeId" :disabled="busy" :class="{selected:String(active?.changeId)===String(row.changeId)}" @click="select(row)"><b>{{ row.realName }}</b><span>{{ types[row.changeType] || '异动类型待核对' }} · {{ nodeLabel(row.currentNode) }}</span><span>{{ statusLabel(row.status) }}</span></button><div class="sc-pages"><button :disabled="busy || page<=1" @click="turnPage(page-1)">上一页</button><span>{{ page }}</span><button :disabled="busy || page*pageSize>=total" @click="turnPage(page+1)">下一页</button></div></aside>
        <main><StatusChangeReview v-if="active" :key="active.changeId" :change="active" :ctx="ctx" @updated="updateFormal" @denied="denied" @busy="busy=$event" /><button v-if="active" class="sc-detail" :disabled="busy" @click="goDetail(active)">查看正式材料与申请详情</button></main>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import StatusChangeReview from './parallel-c/StatusChangeReview.vue'
import { academicAffairsApi as api } from '../api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { TYPE_LABEL, NODE_LABEL, STATUS_LABEL } from '../constants/status-change'
import { gradeError } from './parallel-c/grade-review'
export default {
  name: 'AaStatusChangeApprovalView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusChangeReview },
  props: { ctx: { type: Object, required: true } },
  data() { return { alive:true,seq:0,loading:true,error:'',busy:false,rows:[],active:null,total:0,page:1,pageSize:20,status:'SUBMITTED',changeType:'',types:TYPE_LABEL } },
  computed: { identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])} },
  watch: { identity(){this.clear();this.busy=false;this.page=1;this.load()} },
  created(){this.load()},
  beforeUnmount(){this.alive=false;this.clear()},
  methods: {
    nodeLabel(v){return NODE_LABEL[v]||(v?'节点待核对':'暂无审批节点')},statusLabel(v){return STATUS_LABEL[v]||'状态待核对'},
    clear(){this.seq++;this.rows=[];this.active=null;this.total=0;this.error='';this.loading=false},
    denied(){this.clear();this.busy=false;this.error='当前身份无权读取此申请，请返回责任队列。'},
    select(row){if(!this.busy)this.active={...row}},
    updateFormal(row){if(String(this.active?.changeId)!==String(row.changeId))return;this.active={...row};const found=this.rows.find(r=>String(r.changeId)===String(row.changeId));if(found)Object.assign(found,row)},
    goDetail(row){if(!this.busy)this.$router.push(`/admin/academic-affairs/status-changes/${encodeURIComponent(row.changeId)}`)},
    search(){if(this.busy)return;this.page=1;this.load()},turnPage(page){if(this.busy)return;this.page=page;this.load()},
    async load(){
      if(this.busy)return
      this.clear();const seq=this.seq,identity=this.identity,query={status:this.status,changeType:this.changeType||undefined,page:this.page,pageSize:this.pageSize}
      const valid=()=>this.alive&&seq===this.seq&&identity===this.identity
      this.loading=true
      try{const res=await api.getStatusChanges(query);if(!valid())return;if(res?.code!==0)throw res;this.rows=res.data?.list||[];this.total=res.data?.total??this.rows.length;this.active=this.rows.length?{...this.rows[0]}:null}
      catch(err){if(valid())this.error=gradeError(err,'待审申请读取失败，请重试。')}finally{if(valid())this.loading=false}
    }
  }
}
</script>

<style scoped>
.sc-stack{display:grid;gap:16px}fieldset{display:flex;align-items:center;gap:16px;padding:14px;border:1px solid var(--border-200,#e1e7ef);border-radius:8px;background:var(--bg-white,#fff)}label{display:flex;align-items:center;gap:8px;font-size:13px}select,button{padding:8px 12px;border:1px solid var(--border-200,#d6e0ed);border-radius:7px;background:var(--bg-white,#fff);color:inherit}button{cursor:pointer}button:disabled{opacity:.5;cursor:default}.sc-workbench{display:grid;grid-template-columns:260px minmax(0,1fr);gap:16px}aside{border:1px solid var(--border-200,#e1e7ef);border-radius:9px;overflow:hidden;background:var(--bg-white,#fff)}aside h3{font-size:14px;padding:16px;margin:0}small{font-weight:400}aside>button{display:grid;gap:9px;text-align:left;width:100%;border:0;border-top:1px solid var(--border-200,#e1e7ef);border-radius:0;padding:16px}aside>button.selected{background:var(--primary-50,#edf3ff);box-shadow:inset 3px 0 var(--primary-500,#3564b4)}aside span{font-size:12px;color:var(--text-500,#607087)}main{min-width:0}.sc-pages{display:flex;gap:8px;align-items:center;justify-content:center;padding:12px}.sc-detail{margin-top:14px;color:var(--primary-600,#285aab)}@media(max-width:900px){.sc-workbench{grid-template-columns:1fr}fieldset{flex-wrap:wrap}}
</style>
