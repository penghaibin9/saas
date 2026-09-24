<template>
  <ModulePageShell
    title="异动台账"
    subtitle="一张申请追踪审核、计划生效和历史事实"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/status-changes/new')">＋ 发起异动</AppButton>
    </template>

    <div class="mp-stack">
      <section class="aa-ledger-card">
        <header><div><h2>学籍异动申请 · 台账</h2><p>当前对象状态与审批节点均来自正式异动记录</p></div><span v-if="!loading && !error">共 {{ pagination.total }} 条</span></header>
        <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无学籍异动" description="点击右上角「发起异动」或从学籍名册对某学生发起" />
        <template v-else>
        <div class="aa-chips">
          <span v-for="c in pageStats" :key="c.key" class="aa-chip">{{ c.label }} {{ c.count }}</span>
          <span class="aa-chips__note">（本页 {{ rows.length }} 条统计）</span>
        </div>
        <DataTable
          :columns="columns"
          :rows="rows"
          row-key="changeId"
          :pagination="pagination"
          @page-change="onPageChange"
        >
          <template #cell-student="{ row }">
            <div class="mp-cell-main">{{ row.realName }}</div>
            <div class="mp-cell-sub">{{ studentStatus(row.fromStatus) }} → {{ studentStatus(row.toStatus) }}</div>
          </template>
          <template #cell-type="{ row }">
            <AppStatusTag type="primary">{{ row.changeTypeLabel }}</AppStatusTag>
          </template>
          <template #cell-node="{ row }">
            <span>{{ nodeLabel(row.currentNode) }}</span>
          </template>
          <template #cell-effective="{ row }">
            <div class="mp-cell-main">{{ effectiveDateText(row.effectiveDate, row.status) }}</div>
            <div v-if="row.status === 'APPROVED_PENDING_EFFECTIVE'" class="mp-cell-sub">终审已通过，等待到期生效</div>
          </template>
          <template #cell-status="{ row }">
            <AppStatusTag :type="statusColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
          </template>
          <template #cell-actions="{ row }">
            <AppButton size="small" variant="ghost" @click="goDetail(row)">详情 / 审批</AppButton>
          </template>
        </DataTable>
        </template>
      </section>
      <nav class="aa-ledger-flow" aria-label="异动关联办理">
        <span>关联办理 / 四级下钻</span>
        <button type="button" @click="$router.push('/admin/academic-affairs/status-changes/approval')">异动审批</button>
        <button type="button" @click="$router.push('/admin/academic-affairs/status-changes/effective')">异动生效</button>
        <button type="button" @click="$router.push('/admin/academic-affairs/roster')">学籍名册</button>
      </nav>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学籍异动列表（/admin/academic-affairs/status-changes）：GET /academic-affairs/status-changes。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AdvancedFilter } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag } from '@/components/common'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'
import { ACADEMIC_STUDENT_STATUS_LABELS } from '../config/academicStudentLabels'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TYPE_LABEL, STATUS_LABEL, NODE_LABEL, statusColor } from '@/modules/academicAffairs/constants/status-change'

export default {
  name: 'AaStatusChangeListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AdvancedFilter },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      alive:true,readSeq:0,
      TYPE_LABEL,
      STATUS_LABEL,
      loading: true,
      error: '',
      rows: [],
      filters: { changeType: '', status: '' },
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'student', title: '学生 / 状态变化' },
        { key: 'type', title: '异动类型' },
        { key: 'node', title: '当前节点' },
        { key: 'effective', title: '计划生效' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '110px' }
      ]
    }
  },
  computed: {
    readerIdentity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])},
    filterFields() {
      return [
        {
          key: 'changeType',
          label: '异动类型',
          type: 'select',
          placeholder: '全部',
          options: Object.keys(TYPE_LABEL).map((val) => ({ value: val, label: TYPE_LABEL[val] }))
        },
        {
          key: 'status',
          label: '状态',
          type: 'select',
          placeholder: '全部',
          options: Object.keys(STATUS_LABEL).map((val) => ({ value: val, label: STATUS_LABEL[val] }))
        }
      ]
    },
    pageStats() {
      const m = {}
      for (const r of this.rows) m[r.status] = (m[r.status] || 0) + 1
      return Object.keys(m).map((k) => ({ key: k, label: STATUS_LABEL[k] || '状态待核对', count: m[k] }))
    }
  },
  watch:{
    readerIdentity(){this.clearRead();this.reset()},
    filters:{deep:true,flush:'sync',handler(){this.clearRead()}},
  },
  created() {
    this.load()
  },
  beforeUnmount(){this.alive=false;this.clearRead()},
  methods: {
    studentStatus(value){return ACADEMIC_STUDENT_STATUS_LABELS[value]||'学籍状态待核对'},
    clearRead(){this.readSeq++;this.rows=[];this.pagination.total=0;this.loading=false;this.error=''},
    statusLabel(s) { return STATUS_LABEL[s] || (s ? '状态待确认' : '') },
    statusColor,
    nodeLabel(n) { return n ? (NODE_LABEL[n] || '节点待核对') : '—' },
    effectiveDateText(value, status = '') {
      if (!value && status === 'APPROVED_PENDING_EFFECTIVE') return '计划时间缺失，待核对'
      if (!value) return '终审通过即生效'
      return String(value).replace('T', ' ').slice(0, 16)
    },
    goDetail(row) {
      this.$router.push(`/admin/academic-affairs/status-changes/${row.changeId}`)
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    reset() {
      this.filters.changeType = ''
      this.filters.status = ''
      this.search()
    },
    async load() {
      const identity=this.readerIdentity,seq=++this.readSeq,context=JSON.stringify([this.filters])
      const valid=()=>this.alive&&seq===this.readSeq&&identity===this.readerIdentity&&context===JSON.stringify([this.filters])
      this.loading=true;this.error='';this.rows=[];this.pagination.total=0
      try{const res=await academicAffairsApi.getStatusChanges({changeType:this.filters.changeType||undefined,status:this.filters.status||undefined,page:this.pagination.page,pageSize:this.pagination.pageSize});if(!valid())return;if(res?.code!==0)throw res;this.rows=res.data?.list||[];this.pagination.total=res.data?.total??this.rows.length}
      catch(err){if(valid())this.error=gradeError(err,'异动记录读取失败，请重试。')}finally{if(valid())this.loading=false}
    }
  }
}
</script>

<style scoped>
.aa-filter { display: flex; gap: 16px; align-items: center; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-select { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-chips { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.aa-chip { padding: 3px 10px; border-radius: 12px; background: var(--fill-100, #f2f3f5); font-size: 12px; color: var(--text-700, #4e5969); }
.aa-chips__note { font-size: 12px; color: var(--text-400, #8a9099); }
.aa-ledger-card { overflow: hidden; border: 1px solid var(--card-b,#dce5ef); border-radius: 12px; background:#fff; }
.aa-ledger-card>header { display:flex;align-items:center;justify-content:space-between;gap:16px;padding:15px 17px;border-bottom:1px solid var(--card-b,#dce5ef) }
.aa-ledger-card>header h2{margin:0;font-size:16px}.aa-ledger-card>header p,.aa-ledger-card>header span{margin:4px 0 0;color:var(--t3,#65778b);font-size:12px}
.aa-ledger-card :deep(.advanced-filter){margin:12px 16px}.aa-ledger-card :deep(.dt){border:0;border-radius:0;box-shadow:none}.aa-ledger-card .aa-chips{padding:0 16px 12px}
.aa-ledger-flow{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:12px 16px;border:1px solid var(--card-b,#dce5ef);border-radius:10px;background:#fff}.aa-ledger-flow span{margin-right:4px;color:var(--t3,#65778b);font-size:12px}.aa-ledger-flow button{padding:6px 10px;border:1px solid var(--card-b,#dce5ef);border-radius:7px;background:#fff;color:var(--pri,#2f66bd);cursor:pointer}
</style>
