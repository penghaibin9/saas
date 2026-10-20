<template>
  <ModulePageShell
    :title="pageMeta.title"
    :subtitle="pageMeta.subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton variant="primary" @click="goApply">＋ 新增{{ pageMeta.title }}</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aa-chips" v-if="rows.length">
        <span v-for="c in pageStats" :key="c.key" class="aa-chip">{{ c.label }} {{ c.count }}</span>
        <span class="aa-chips__note">（本页 {{ rows.length }} 条统计，全量以「异动统计」为准）</span>
      </div>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="`暂无${pageMeta.title}记录`" :description="`点击右上角「＋ 新增${pageMeta.title}」创建`" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="changeId"
                 :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.realName }}</div>
          <div class="mp-cell-sub">{{ studentStatus(row.fromStatus) }} → {{ studentStatus(row.toStatus) }}</div>
        </template>
        <template #cell-node="{ row }"><span>{{ nodeLabel(row.currentNode) }}</span></template>
        <template #cell-status="{ row }"><StatusTag :type="statusColor(row.status)" :label="statusLabel(row.status)" dot /></template>
        <template #cell-actions="{ row }">
          <AppButton size="small" variant="ghost" @click="goDetail(row)">详情 / 审批</AppButton>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 学籍异动 · 分类申请入口（Tier1 R1：休学/复学/退学/转专业四个独立三级菜单叶子共用本组件）。
 * 路由 meta.changeType 区分具体类型；GET /academic-affairs/status-changes?changeType=X 复用既有列表接口。
 * 新增申请复用既有「发起异动」表单页（?type=X 预设并锁定类型，逻辑与既有 SC1-8 全链路测试完全一致）。
 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'
import { ACADEMIC_STUDENT_STATUS_LABELS } from '../config/academicStudentLabels'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { STATUS_LABEL, NODE_LABEL, TYPE_PAGE_META, statusColor } from '@/modules/academicAffairs/constants/status-change'

const EMPTY = () => ({ status: '' })

export default {
  name: 'AaStatusChangeTypedListView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      alive:true,readSeq:0,
      loading: true, error: '', rows: [], page: 1, pageSize: 20, total: 0, filters: EMPTY(),
      columns: [
        { key: 'student', title: '学生 / 状态变化' },
        { key: 'node', title: '当前节点' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '110px' }
      ]
    }
  },
  computed: {
    readerIdentity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])},
    changeType() { return this.$route.meta.changeType },
    pageMeta() { return TYPE_PAGE_META[this.changeType] || { title: '学籍异动申请', subtitle: '' } },
    filterFields() {
      return [
        { key: 'status', label: '状态', type: 'select', options: Object.keys(STATUS_LABEL).map((v) => ({ value: v, label: STATUS_LABEL[v] })) }
      ]
    },
    pageStats() {
      const m = {}
      for (const r of this.rows) m[r.status] = (m[r.status] || 0) + 1
      return Object.keys(m).map((k) => ({ key: k, label: STATUS_LABEL[k] || '状态待核对', count: m[k] }))
    }
  },
  watch: {
    readerIdentity(){this.clearRead();this.reset()},
    filters:{deep:true,flush:'sync',handler(){this.clearRead()}},

    // 四个类型共用同一组件实例时（用户在侧栏切换叶子），路由变化需重新拉取
    '$route.meta.changeType'() {
      this.page = 1
      this.filters = EMPTY()
      this.load()
    }
  },
  created() {
    this.load()
  },
  beforeUnmount(){this.alive=false;this.clearRead()},
  methods: {
    studentStatus(value){return ACADEMIC_STUDENT_STATUS_LABELS[value]||'学籍状态待核对'},
    clearRead(){this.readSeq++;this.rows=[];this.total=0;this.loading=false;this.error=''},
    statusLabel(s) { return STATUS_LABEL[s] || (s ? '状态待确认' : '') },
    statusColor,
    nodeLabel(n) { return n ? (NODE_LABEL[n] || '节点待核对') : '—' },
    goApply() { this.$router.push(`/admin/academic-affairs/status-changes/new?type=${this.changeType}`) },
    goDetail(row) { this.$router.push(`/admin/academic-affairs/status-changes/${row.changeId}`) },
    turnPage(p) { this.page = p; this.load() },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY(); this.page = 1; this.load() },
    async load() {
      const identity=this.readerIdentity,seq=++this.readSeq,context=JSON.stringify([this.filters,this.changeType,this.phase])
      const valid=()=>this.alive&&seq===this.readSeq&&identity===this.readerIdentity&&context===JSON.stringify([this.filters,this.changeType,this.phase])
      this.loading=true;this.error='';this.rows=[];this.total=0;if(this.pagination)this.pagination.total=0
      try{const res=await academicAffairsApi.getStatusChanges({changeType:this.changeType,status:this.filters.status||undefined,page:this.page,pageSize:this.pageSize});if(!valid())return;if(res?.code!==0)throw res;this.rows=res.data?.list||[];this.total=res.data?.total??this.rows.length}
      catch(err){if(valid())this.error=gradeError(err,'异动记录读取失败，请重试。')}finally{if(valid())this.loading=false}
    }
  }
}
</script>

<style scoped>
.aa-chips { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.aa-chip { padding: 3px 10px; border-radius: 12px; background: var(--fill-100, #f2f3f5); font-size: 12px; color: var(--text-700, #4e5969); }
.aa-chips__note { font-size: 12px; color: var(--text-400, #8a9099); }
</style>
