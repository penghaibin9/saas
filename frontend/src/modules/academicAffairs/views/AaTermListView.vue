<template>
  <ModulePageShell
    title="学年学期"
    subtitle="学期是教务全流程的时间基座 · 新建 → 发布（设为当前）后，看板与后续教学过程据此运行"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn mp-btn--primary" @click="goCreate">＋ 新建学期</button>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">
          状态
          <select v-model="filters.status" class="aa-select" @change="search">
            <option value="">全部</option>
            <option value="DRAFT">草稿</option>
            <option value="PUBLISHED">进行中</option>
          </select>
        </label>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="还没有学年学期"
        description="点击右上角「新建学期」创建第一个学期，发布后即成为当前学期"
      />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="termId"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-term="{ row }">
          <div class="mp-cell-main">{{ row.yearCode }} 第 {{ row.termNo }} 学期</div>
          <div class="mp-cell-sub">{{ row.termName || '未命名' }}</div>
        </template>
        <template #cell-range="{ row }">
          <span v-if="row.startDate && row.endDate">{{ row.startDate }} ~ {{ row.endDate }}</span>
          <span v-else class="mp-cell-sub">未设置</span>
        </template>
        <template #cell-weeks="{ row }">
          <span v-if="row.teachingWeeks">{{ row.teachingWeeks }} 周</span>
          <span v-else class="mp-cell-sub">—</span>
        </template>
        <template #cell-current="{ row }">
          <AppStatusTag v-if="row.isCurrent" type="success" dot>当前学期</AppStatusTag>
          <span v-else class="mp-cell-sub">—</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button
            v-if="row.status === 'DRAFT'"
            class="mp-link"
            @click="askPublish(row)"
          >发布并设为当前</button>
          <button
            v-else-if="!row.isCurrent"
            class="mp-link"
            @click="askPublish(row)"
          >设为当前学期</button>
          <span v-else class="mp-cell-sub">当前进行中</span>
        </template>
      </DataTable>

      <p class="mp-note">发布幂等：重复发布不会报错；发布某学期会自动取消其它学期的「当前」标记。学期编辑/冻结/归档为后续波次交付。</p>
    </div>

    <AppConfirmDialog
      v-model:visible="publishDialog.visible"
      title="发布学期"
      :message="publishDialog.message"
      type="primary"
      confirm-text="确认发布并设为当前"
      :submitting="publishDialog.submitting"
      @confirm="doPublish"
    />
  </ModulePageShell>
</template>

<script>
/** 学年学期列表（/admin/academic-affairs/terms）：GET /academic-affairs/terms + POST /terms/{id}/publish。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '进行中' }

export default {
  name: 'AaTermListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: { status: '' },
      pagination: { page: 1, pageSize: 20, total: 0 },
      publishDialog: { visible: false, submitting: false, row: null, message: '' },
      columns: [
        { key: 'term', title: '学年学期' },
        { key: 'range', title: '起止日期' },
        { key: 'weeks', title: '教学周' },
        { key: 'current', title: '当前学期' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '160px' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    statusLabel(s) {
      return STATUS_LABEL[s] || s || ''
    },
    goCreate() {
      this.$router.push('/admin/academic-affairs/terms/new')
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    askPublish(row) {
      this.publishDialog = {
        visible: true,
        submitting: false,
        row,
        message: `确认将「${row.yearCode} 第 ${row.termNo} 学期」发布为当前学期？其它学期的「当前」标记会被自动取消。`
      }
    },
    async doPublish() {
      const row = this.publishDialog.row
      if (!row) return
      this.publishDialog.submitting = true
      const res = await academicAffairsApi.publishTerm(row.termId)
      this.publishDialog.submitting = false
      if (res.code === 0) {
        this.publishDialog.visible = false
        toast.success(`已发布：${row.yearCode} 第 ${row.termNo} 学期为当前学期`)
        this.load()
      } else {
        toast.error(res.message || '发布失败')
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTerms({
        status: this.filters.status || undefined,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
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
.aa-filter {
  display: flex;
  gap: 16px;
  align-items: center;
}
.aa-filter__item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-700, #4e5969);
}
.aa-select {
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9);
  border-radius: 6px;
  background: var(--bg-white, #fff);
  color: var(--text-900, #1f2329);
  font-size: 13px;
}
</style>
