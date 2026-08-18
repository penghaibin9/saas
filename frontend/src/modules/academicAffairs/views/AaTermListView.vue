<template>
  <ModulePageShell
    title="学年学期"
    subtitle="学期是教务全流程的时间基座 · 新建 → 发布后，看板与后续教学过程据全校当前学期运行"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="goCreate">＋ 新建学期</AppButton>
    </template>

    <div class="mp-stack">
      <AdvancedFilter
        v-model="filters"
        :fields="filterFields"
        @search="search"
        @reset="reset"
      />

      <p v-if="currentError" class="mp-note aa-authority-note is-error">
        当前学期解析失败：{{ currentError }}。历史学期仍可查看，但发布/切换当前学期已安全禁用。
      </p>
      <p v-else-if="governanceManaged" class="mp-note aa-authority-note">
        全校统一学期治理已启用。这里保留学期台账查看；任何会改变“当前学期”的操作请从“学年学期与业务日历”执行。
        <button class="mp-link" type="button" @click="goGovernance">前往统一治理</button>
      </p>
      <p v-else class="mp-note aa-authority-note">
        当前沿用教务学期兼容切换；发布/设为当前会同步更新全校当前学期结论。
      </p>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="还没有学年学期"
        description="点击右上角「新建学期」创建第一个学期；是否可直接设为当前由全校学期 Authority 决定"
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
          <span v-else class="mp-cell-sub">未配置</span>
        </template>
        <template #cell-current="{ row }">
          <AppStatusTag v-if="isResolvedCurrent(row)" type="success" dot>当前学期</AppStatusTag>
          <span v-else-if="currentError" class="mp-cell-sub">待核对</span>
          <span v-else class="mp-cell-sub">—</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <span v-if="isResolvedCurrent(row)" class="mp-cell-sub">当前进行中</span>
          <button
            v-else-if="row.status === 'DRAFT' && directSwitchAllowed"
            class="mp-link"
            type="button"
            @click="askPublish(row)"
          >发布并设为当前</button>
          <button
            v-else-if="row.status === 'PUBLISHED' && directSwitchAllowed"
            class="mp-link"
            type="button"
            @click="askPublish(row)"
          >设为当前学期</button>
          <button
            v-else-if="governanceManaged && ['DRAFT', 'PUBLISHED'].includes(row.status)"
            class="mp-link"
            type="button"
            @click="goGovernance"
          >统一治理切换</button>
          <span v-else-if="currentError" class="mp-cell-sub">已禁用</span>
          <span v-else-if="row.status === 'FROZEN'" class="mp-cell-sub">请先解冻</span>
          <span v-else class="mp-cell-sub">—</span>
        </template>
      </DataTable>

      <p class="mp-note">历史学期列表始终可读；只有 A-C1 明确允许教务兼容切换时，本页才提供“发布并设为当前 / 设为当前学期”。</p>
    </div>

    <AppConfirmDialog
      v-model:visible="publishDialog.visible"
      title="发布或切换学期"
      :message="publishDialog.message"
      type="primary"
      confirm-text="确认并设为当前"
      :submitting="publishDialog.submitting"
      @confirm="doPublish"
    />
  </ModulePageShell>
</template>

<script>
/** 学年学期列表（/admin/academic-affairs/terms）。
 * A-W1：历史列表可读；所有会改变 current 的按钮必须消费 /terms/current 的 A-C1 结论。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AdvancedFilter } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '进行中', FROZEN: '已冻结', ARCHIVED: '已归档' }

export default {
  name: 'AaTermListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AdvancedFilter, AppButton, AppStatusTag, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      currentContext: null,
      currentError: '',
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
  computed: {
    governanceManaged() {
      return this.currentContext?.currentAuthority === 'CALENDAR_GOVERNANCE'
    },
    directSwitchAllowed() {
      return !this.currentError && this.currentContext?.canDirectSwitch !== false
    },
    filterFields() {
      return [
        {
          key: 'status',
          label: '状态',
          type: 'select',
          placeholder: '全部',
          options: [
            { value: '', label: '全部' },
            { value: 'DRAFT', label: '草稿' },
            { value: 'PUBLISHED', label: '进行中' },
            { value: 'FROZEN', label: '已冻结' },
            { value: 'ARCHIVED', label: '已归档' }
          ]
        }
      ]
    }
  },
  created() {
    this.loadCurrentContext()
    this.load()
  },
  methods: {
    statusLabel(s) {
      return STATUS_LABEL[s] || s || ''
    },
    isResolvedCurrent(row) {
      return Boolean(this.currentContext?.termId) && String(row.termId) === String(this.currentContext.termId)
    },
    goCreate() {
      this.$router.push('/admin/academic-affairs/terms/new')
    },
    goGovernance() {
      this.$router.push(this.currentContext?.switchRoute || '/admin/system/academic-calendar')
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
      this.filters.status = ''
      this.search()
    },
    askPublish(row) {
      if (!this.directSwitchAllowed) {
        toast.warning(this.currentContext?.switchHint || this.currentError || '当前学期由统一治理控制，禁止从学期台账旁路切换')
        return
      }
      if (!['DRAFT', 'PUBLISHED'].includes(row.status)) {
        toast.warning('只有草稿或进行中学期可从本页发布/切换；冻结学期请先解冻')
        return
      }
      this.publishDialog = {
        visible: true,
        submitting: false,
        row,
        message: `确认将「${row.yearCode} 第 ${row.termNo} 学期」${row.status === 'DRAFT' ? '发布并' : ''}设为当前学期？其它学期的“当前”结论会被取消。`
      }
    },
    async doPublish() {
      const row = this.publishDialog.row
      if (!row || !this.directSwitchAllowed) return
      this.publishDialog.submitting = true
      const res = await academicAffairsApi.publishTerm(row.termId)
      this.publishDialog.submitting = false
      if (res.code === 0) {
        this.publishDialog.visible = false
        toast.success(`已处理：${row.yearCode} 第 ${row.termNo} 学期为当前学期`)
        await Promise.all([this.loadCurrentContext(), this.load()])
      } else {
        toast.error(res.message || '发布/切换失败')
        await this.loadCurrentContext()
      }
    },
    async loadCurrentContext() {
      this.currentError = ''
      const res = await academicAffairsApi.getCurrentTerm()
      if (res.code === 0) {
        this.currentContext = res.data || null
      } else {
        this.currentContext = null
        this.currentError = res.message || '当前学期解析失败，请核对全校学期治理与教务学期数据'
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
.aa-authority-note { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.aa-authority-note.is-error { color: var(--danger-600, #d92d20); }
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
