<template>
  <ModulePageShell
    title="异动生效"
    subtitle="区分已批决定、计划生效日期和正式生效结果"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <div class="mp-stack">
      <div class="aa-phase"><button :class="{selected:phase==='APPROVED_PENDING_EFFECTIVE'}" @click="setPhase('APPROVED_PENDING_EFFECTIVE')">已通过待生效</button><button :class="{selected:phase==='EFFECTIVE'}" @click="setPhase('EFFECTIVE')">已生效</button><label>学生<AppStudentPicker v-model="filters.studentId" /></label></div>
      <p>{{ phase === 'APPROVED_PENDING_EFFECTIVE' ? '终审已通过，当前学籍尚未改变；以服务器实际生效结果为准。' : '以下决定已正式生效；点击学籍档案核对该学生当前状态。' }}</p>
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="phase === 'EFFECTIVE' ? '暂无已生效异动' : '暂无已通过待生效异动'" description="终审通过的休学/复学/退学/转专业/留级申请将在此展示" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="changeId"
                 :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-student="{ row }"><div class="mp-cell-main">{{ row.realName }}</div></template>
        <template #cell-type="{ row }"><StatusTag type="primary" :label="row.changeTypeLabel" dot /></template>
        <template #cell-change="{ row }">
          <span class="mp-cell-sub">{{ studentStatus(row.fromStatus) }} → <b>{{ studentStatus(row.toStatus) }}</b></span>
        </template>
        <template #cell-status="{ row }"><StatusTag :label="statusLabel(row.status)" :type="row.status==='EFFECTIVE'?'success':'warning'" /></template>
        <template #cell-effectiveDate="{ row }">{{ row.effectiveDate || '—' }}</template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goDetail(row)">异动详情</button>
          <button class="mp-link" style="margin-left: var(--space-2)" @click="goArchive(row)">学籍档案</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 学籍异动生效台账（Tier1「异动生效」，/admin/academic-affairs/status-changes/effective）。
 * 只读：复用既有 GET /status-changes 分别查询待生效与已生效记录。生效结果由
 * change_student_status() 单一入口原子写入学籍主档 + StudentStageEvent，本页不重复任何写操作，
 * 仅做「生效结果」的检索与佐证跳转）。
 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'
import { ACADEMIC_STUDENT_STATUS_LABELS } from '../config/academicStudentLabels'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { AppStudentPicker } from '@/components/common'
import { TYPE_LABEL, STATUS_LABEL } from '@/modules/academicAffairs/constants/status-change'

const EMPTY = () => ({ changeType: '', studentId: '', dateStart: '', dateEnd: '' })

export default {
  name: 'AaStatusChangeEffectiveView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppStudentPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      alive:true,readSeq:0,phase:'EFFECTIVE',
      loading: true, error: '', rows: [], page: 1, pageSize: 20, total: 0, filters: EMPTY(),
      columns: [
        { key: 'student', title: '学生' },
        { key: 'type', title: '异动类型' },
        { key: 'change', title: '学籍状态变化' },
        { key: 'effectiveDate', title: '计划生效日期' },
        { key: 'status', title: '正式执行状态' },
        { key: 'actions', title: '操作', width: '180px' }
      ]
    }
  },
  computed: {
    readerIdentity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])},
    filterFields() {
      return [
        { key: 'changeType', label: '类型', type: 'select', options: Object.keys(TYPE_LABEL).map((v) => ({ value: v, label: TYPE_LABEL[v] })) },
        { key: 'date', label: '生效时间', type: 'daterange',
          startKey: 'dateStart', endKey: 'dateEnd',
          memoryKey: 'academicAffairs.statusChangeEffective.dateRange', emptyLabel: '全部时间' }
      ]
    }
  },
  watch:{
    readerIdentity(){this.clearRead();this.reset()},
    filters:{deep:true,flush:'sync',handler(){this.clearRead()}},
  },
  created() { this.load() },
  beforeUnmount(){this.alive=false;this.clearRead()},
  methods: {
    statusLabel(v){return STATUS_LABEL[v]||'状态待核对'},
    studentStatus(value){return ACADEMIC_STUDENT_STATUS_LABELS[value]||'学籍状态待核对'},
    clearRead(){this.readSeq++;this.rows=[];this.total=0;this.loading=false;this.error=''},
    setPhase(phase){if(!['EFFECTIVE','APPROVED_PENDING_EFFECTIVE'].includes(phase)||this.phase===phase)return;this.phase=phase;this.clearRead();this.page=1;this.load()},
    goDetail(row) { this.$router.push(`/admin/academic-affairs/status-changes/${row.changeId}`) },
    goArchive(row) { if(row.studentId)this.$router.push(`/admin/academic-affairs/roster/${encodeURIComponent(row.studentId)}`) },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    async load() {
      const identity=this.readerIdentity,seq=++this.readSeq,context=JSON.stringify([this.filters,this.changeType,this.phase])
      const valid=()=>this.alive&&seq===this.readSeq&&identity===this.readerIdentity&&context===JSON.stringify([this.filters,this.changeType,this.phase])
      this.loading=true;this.error='';this.rows=[];this.total=0;if(this.pagination)this.pagination.total=0
      try{const res=await academicAffairsApi.getStatusChanges({changeType:this.filters.changeType||undefined,studentId:this.filters.studentId||undefined,dateFrom:this.filters.dateStart||undefined,dateTo:this.filters.dateEnd||undefined,status:this.phase,page:this.page,pageSize:this.pageSize});if(!valid())return;if(res?.code!==0)throw res;this.rows=res.data?.list||[];this.total=res.data?.total??this.rows.length}
      catch(err){if(valid())this.error=gradeError(err,'异动记录读取失败，请重试。')}finally{if(valid())this.loading=false}
    }
  }
}
</script>

<style scoped>
.aa-phase{display:flex;gap:12px;align-items:center}.aa-phase button{padding:8px 16px;border:1px solid #dce4ef;border-radius:8px;background:#fff;color:#304866;cursor:pointer}.aa-phase button.selected{background:#eaf2ff;border-color:#4776bd}.aa-phase label{display:flex;gap:10px;align-items:center}
</style>
