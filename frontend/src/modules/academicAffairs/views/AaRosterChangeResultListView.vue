<template>
  <ModulePageShell
    :title="pageMeta.title"
    :subtitle="pageMeta.subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <p class="mp-note">
        本页为学籍名册的分类结果视图（只读），数据取自「学籍异动」审批流水；
        如需发起新的{{ pageMeta.title }}申请，请前往
        <button class="mp-link" @click="goApply">学籍异动 · {{ pageMeta.title }}申请</button>。
      </p>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="`暂无${pageMeta.title}记录`" description="调整筛选条件后重试，或确认尚无符合条件的学生" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="changeId"
                 :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.realName }}</div>
          <div class="mp-cell-sub">学号 {{ row.studentNo || '—' }} · {{ row.fromStatus }} → {{ row.toStatus }}</div>
        </template>
        <template #cell-status="{ row }"><StatusTag :type="statusColor(row.status)" :label="statusLabel(row.status)" dot /></template>
        <template #cell-effectiveDate="{ row }">{{ row.effectiveDate ? row.effectiveDate.slice(0, 10) : '—' }}</template>
        <template #cell-reason="{ row }">{{ row.reason || '—' }}</template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goRoster(row)">学籍档案</button>
          <button class="mp-link" @click="goDetail(row)">异动详情</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 学籍管理 · 分类结果视图（Tier1 R3：复学学生/转专业学生，休学/复学/退学/转专业学生统一入口章节）。
 * 路由 meta.changeType 区分具体类型；GET /academic-affairs/status-changes?changeType=X 复用既有列表接口
 * （与「学籍异动」台账同一后端只读端点，权限 academicAffairs.statusChange.view 同源）。
 *
 * 与「学籍异动」模块 AaStatusChangeTypedListView（休学/复学/退学/转专业「申请入口」，apply 语义）的区别：
 * 本页是「学籍管理」模块下的只读结果名册（roster 语义）——默认只看已生效（EFFECTIVE）结果，
 * 操作列指向「学籍档案」而非「审批」，不提供发起入口（发起仍归口学籍异动，避免重复实现审批链）。
 *
 * 休学学生/退学学生走 roster?status= 名册过滤（见 AaRosterListView）；复学/转专业因终态回到 REGISTERED、
 * 无法用 student_status 区分，只能从异动流水按 changeType 取「结果」，故走本页而非名册过滤。
 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { STATUS_LABEL, NODE_LABEL, statusColor } from '@/modules/academicAffairs/constants/status-change'

const PAGE_META = {
  RESUME: { title: '复学学生', subtitle: '休学后已完成复学（学籍异动·复学，终审生效）的学生结果名单' },
  TRANSFER_MAJOR: { title: '转专业学生', subtitle: '已完成转专业（学籍异动·转专业，终审生效并迁移院系班）的学生结果名单' }
}
const APPLY_PATH = { RESUME: '/admin/academic-affairs/status-changes/resume',
                     TRANSFER_MAJOR: '/admin/academic-affairs/status-changes/transfer-major' }
const EMPTY = () => ({ status: 'EFFECTIVE' })

export default {
  name: 'AaRosterChangeResultListView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], page: 1, pageSize: 20, total: 0, filters: EMPTY(),
      columns: [
        { key: 'student', title: '学生 / 状态变化' },
        { key: 'status', title: '异动状态' },
        { key: 'effectiveDate', title: '生效日期' },
        { key: 'reason', title: '原因' },
        { key: 'actions', title: '操作', width: '150px' }
      ]
    }
  },
  computed: {
    changeType() { return this.$route.meta.changeType },
    pageMeta() { return PAGE_META[this.changeType] || { title: '学籍异动结果', subtitle: '' } },
    filterFields() {
      return [
        { key: 'status', label: '异动状态', type: 'select', options: Object.keys(STATUS_LABEL).map((v) => ({ value: v, label: STATUS_LABEL[v] })) }
      ]
    }
  },
  watch: {
    // 复学学生/转专业学生共用同一组件实例时（侧栏切叶子），路由变化需重新拉取
    '$route.meta.changeType'() {
      this.page = 1
      this.filters = EMPTY()
      this.load()
    }
  },
  created() {
    this.load()
  },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || s || '' },
    statusColor,
    nodeLabel(n) { return n ? (NODE_LABEL[n] || n) : '—' },
    goApply() { this.$router.push(APPLY_PATH[this.changeType] || '/admin/academic-affairs/status-changes/new') },
    goDetail(row) { this.$router.push(`/admin/academic-affairs/status-changes/${row.changeId}`) },
    goRoster(row) { this.$router.push(`/admin/academic-affairs/roster/${row.studentId}`) },
    turnPage(p) { this.page = p; this.load() },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY(); this.page = 1; this.load() },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getStatusChanges({
        changeType: this.changeType,
        status: this.filters.status || undefined,
        page: this.page,
        pageSize: this.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list
        this.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
