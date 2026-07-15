<template>
  <ModulePageShell
    :title="pageMeta.title"
    :subtitle="pageMeta.subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn mp-btn--primary" @click="goApply">＋ 新增{{ pageMeta.title }}</button>
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
          <div class="mp-cell-sub">{{ row.fromStatus }} → {{ row.toStatus }}</div>
        </template>
        <template #cell-node="{ row }"><span>{{ nodeLabel(row.currentNode) }}</span></template>
        <template #cell-status="{ row }"><StatusTag :type="statusColor(row.status)" :label="statusLabel(row.status)" dot /></template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goDetail(row)">详情 / 审批</button>
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
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { STATUS_LABEL, NODE_LABEL, TYPE_PAGE_META, statusColor } from '@/modules/academicAffairs/constants/status-change'

const EMPTY = () => ({ status: '' })

export default {
  name: 'AaStatusChangeTypedListView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
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
      return Object.keys(m).map((k) => ({ key: k, label: STATUS_LABEL[k] || k, count: m[k] }))
    }
  },
  watch: {
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
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || s || '' },
    statusColor,
    nodeLabel(n) { return n ? (NODE_LABEL[n] || n) : '—' },
    goApply() { this.$router.push(`/admin/academic-affairs/status-changes/new?type=${this.changeType}`) },
    goDetail(row) { this.$router.push(`/admin/academic-affairs/status-changes/${row.changeId}`) },
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
.aa-chips { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.aa-chip { padding: 3px 10px; border-radius: 12px; background: var(--fill-100, #f2f3f5); font-size: 12px; color: var(--text-700, #4e5969); }
.aa-chips__note { font-size: 12px; color: var(--text-400, #8a9099); }
</style>
