<template>
  <div class="aa-print">
    <div class="aa-print__bar">
      <span>{{ printTime }} · 操作人：{{ operator }}</span>
      <AppPrintButton variant="primary" :handler="doPrint" :disabled="loading || !!error || !change || printing" />
    </div>

    <LoadingState v-if="loading" />
    <div v-else-if="error" class="aa-print__err">{{ error }}</div>
    <div v-else-if="change" class="aa-print__sheet">
      <h1 class="aa-print__title">{{ schoolName }}</h1>
      <h2 class="aa-print__subtitle">学籍异动审批表</h2>
      <table class="aa-print__table">
        <tbody>
          <tr><th>学生姓名</th><td>{{ change.realName }}</td><th>正式申请状态</th><td>{{ statusLabel(change.status) }}</td></tr>
          <tr><th>异动类型</th><td>{{ change.changeTypeLabel }}</td><th>状态变化</th><td>{{ studentStatus(change.fromStatus) }} → {{ studentStatus(change.toStatus) }}</td></tr>
          <tr><th>当前状态</th><td>{{ statusLabel(change.status) }}</td><th>当前节点</th><td>{{ nodeLabel(change.currentNode) }}</td></tr>
          <tr><th>生效方式</th><td>{{ change.effectiveDate ? '指定日期' : '终审通过立即生效' }}</td><th>计划生效时间</th><td>{{ change.effectiveDate || '—' }}</td></tr>
          <tr v-if="change.expireDate"><th>休学到期</th><td colspan="3">{{ change.expireDate }}</td></tr>
          <tr><th>申请原因</th><td colspan="3">{{ change.reason || '（无）' }}</td></tr>
        </tbody>
      </table>
      <div class="aa-print__flow">
        <p v-if="change.status==='APPROVED_PENDING_EFFECTIVE'">终审已通过，当前学籍尚未变更；计划日期不代表已经生效。</p><div class="aa-print__flow-title">审批路径参考（空白签字栏不代表已审批）</div>
        <div v-for="(n, i) in flowNodes" :key="n" class="aa-print__flow-node">
          <span>{{ i + 1 }}. {{ nodeLabel(n) }}</span>
          <span class="aa-print__sign">签字 / 日期：____________</span>
        </div>
      </div>
      <div class="aa-print__seal">教务处（盖章）：____________  日期：__________</div>
    </div>
  </div>
</template>

<script>
/** 学籍异动审批表打印页（/admin/academic-affairs/print/status-change/:id）：D7 独立打印路由，无导航布局。 */
import {currentUserFromToken} from '@/services/http/client'
import {gradeError} from './parallel-c/grade-review'
import {ACADEMIC_STUDENT_STATUS_LABELS} from '../config/academicStudentLabels'
import { LoadingState } from '@/components/business'
import { AppPrintButton } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { STATUS_LABEL, NODE_LABEL, CHANGE_FLOW_NODES } from '@/modules/academicAffairs/constants/status-change'

export default {
  name: 'AaStatusChangePrintView',
  components: { LoadingState, AppPrintButton },
  data() {
    return { alive:true,seq:0,printing:false,loading:true,error:'',change:null,schoolName:'',operator:'',printTime:'' }
  },
  computed: {
    identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode])},
    changeId(){return String(this.$route.params.id||'')},
    flowNodes() { return this.change ? (CHANGE_FLOW_NODES[this.change.changeType] || []) : [] }
  },
  watch:{identity(){this.clear();this.load()},changeId(){this.clear();this.load()}},
  created(){this.load()},beforeUnmount(){this.alive=false;this.clear()},
  methods:{
    statusLabel(v){return STATUS_LABEL[v]||'状态待核对'},nodeLabel(v){return NODE_LABEL[v]||(v?'节点待核对':'暂无审批节点')},studentStatus(v){return ACADEMIC_STUDENT_STATUS_LABELS[v]||'学籍状态待核对'},
    clear(){this.seq++;this.printing=false;this.loading=false;this.error='';this.change=null;this.schoolName='';this.operator='';this.printTime=''},
    async load(){
      this.clear();const seq=this.seq,identity=this.identity,id=this.changeId;const valid=()=>this.alive&&seq===this.seq&&identity===this.identity&&id===this.changeId;this.loading=true
      try{const [ctx,res]=await Promise.all([academicAffairsApi.getContext(),academicAffairsApi.getStatusChange(id)]);if(!valid())return;if(ctx?.code!==0)throw ctx;if(res?.code!==0)throw res;if(String(res.data?.changeId)!==id)throw {code:409};this.schoolName=ctx.data?.tenantBrandConfig?.schoolName||'学校名称待核对';this.operator=ctx.data?.currentRole?.roleName||'当前岗位';this.change=res.data;this.printTime=new Date().toLocaleString('zh-CN')}
      catch(err){if(valid())this.error=gradeError(err,'打印内容读取失败，请重新打开。')}finally{if(valid())this.loading=false}
    },
    async doPrint(){if(this.loading||this.printing||!this.change)return;const identity=this.identity,id=this.changeId,task=this.load(),seq=this.seq;this.printing=true;try{await task;await this.$nextTick();if(this.alive&&seq===this.seq&&identity===this.identity&&id===this.changeId&&!this.error&&this.change)window.print()}finally{if(seq===this.seq)this.printing=false}}
  }
}
</script>

<style scoped>

.aa-print { padding: 24px; max-width: 800px; margin: 0 auto; color: #000; background: #fff; }
.aa-print__bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; font-size: 12px; color: #666; }
.aa-print__err { color: var(--danger-600, #f53f3f); }
.aa-print__title { text-align: center; font-size: 22px; margin: 0 0 4px; }
.aa-print__subtitle { text-align: center; font-size: 16px; font-weight: 500; margin: 0 0 20px; }
.aa-print__table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
.aa-print__table th, .aa-print__table td { border: 1px solid #333; padding: 8px 12px; font-size: 14px; text-align: left; }
.aa-print__table th { background: #f5f5f5; width: 100px; font-weight: 500; }
.aa-print__flow-title { font-weight: 600; margin-bottom: 8px; }
.aa-print__flow-node { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px dashed #999; font-size: 14px; }
.aa-print__sign { color: #666; }
.aa-print__seal { margin-top: 32px; text-align: right; font-size: 14px; }
@media print {
  .aa-print__bar { display: none; }
  .aa-print { padding: 0; }
  @page { size: A4; margin: 1.5cm; }
}
</style>
