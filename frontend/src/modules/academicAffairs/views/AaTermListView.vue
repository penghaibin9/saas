<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    title="学年学期"
    subtitle="维护学校教学时间，衔接校历、教学任务与学期收尾。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="canManage" variant="primary" @click="goCreate">新建学期</AppButton>
    </template>

    <div class="mp-stack">
      <section class="aa-term-summary" aria-label="当前学期概况" :aria-busy="currentLoading">
        <div class="aa-term-summary__main">
          <span class="aa-term-summary__eyebrow">全校当前学期</span>
          <h2>{{ currentLoading ? '正在核对当前学期…' : currentError ? '当前学期待核对' : currentContext?.termId ? `${currentContext.yearCode} 第 ${currentContext.termNo} 学期` : '尚未设置当前学期' }}</h2>
          <p>{{ currentContext?.termName || '师生校历与教学安排使用学校统一的当前学期。' }}</p>
        </div>
        <dl v-if="!currentLoading && !currentError && currentContext?.termId" class="aa-term-summary__facts">
          <div><dt>起止日期</dt><dd>{{ dateText(currentContext.startDate) }} — {{ dateText(currentContext.endDate) }}</dd></div>
          <div><dt>教学安排</dt><dd>{{ currentContext.teachingWeeks ? `${currentContext.teachingWeeks} 周` : '周数未配置' }}</dd></div>
        </dl>
        <AppButton v-if="!currentLoading && !currentError && currentContext?.termId" variant="ghost" @click="goDetail(currentContext)">查看详情</AppButton>
      </section>

      <div class="aa-foundation-section-heading"><h2>学期台账</h2><span>共 {{ pagination.total }} 个学期</span></div>
      <AdvancedFilter
        v-model="filters"
        :fields="filterFields"
        @search="search"
        @reset="reset"
      />

      <p v-if="currentError" class="mp-note aa-authority-note is-error">
        当前学期读取失败：{{ currentError }}。核对完成前暂不能发布或切换学期。
        <button class="mp-link" type="button" @click="loadCurrentContext">重新加载</button>
      </p>
      <p v-else-if="governanceManaged" class="mp-note aa-authority-note">
        学期发布后，由学校在「学年学期与业务日历」统一启用为当前学期。
        <button v-if="canViewGovernance" class="mp-link" type="button" @click="goGovernance">前往统一治理</button>
      </p>
      <p v-else-if="directSwitchAllowed" class="mp-note aa-authority-note">
        本校发布学期时会同步设为当前学期，请在操作前核对日期与教学周。
      </p>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        :title="filters.status ? '没有符合条件的学期' : '还没有学年学期'"
        :description="filters.status ? '调整状态筛选后重试。' : canManage ? '新建学期后，补齐日期与教学周，再发布使用。' : '学校建立学期后，可在这里查看。'"
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
          <button class="mp-link aa-term-name" type="button" @click="goDetail(row)">{{ row.yearCode }} 第 {{ row.termNo }} 学期</button>
          <div class="mp-cell-sub">{{ row.termName || '未命名' }}</div>
        </template>
        <template #cell-range="{ row }">
          <span v-if="row.startDate && row.endDate">{{ dateText(row.startDate) }} — {{ dateText(row.endDate) }}</span>
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
          <span v-if="isResolvedCurrent(row)" class="mp-cell-sub">当前学期</span>
          <button
            v-else-if="row.status === 'DRAFT' && publishAllowed"
            class="mp-link"
            type="button"
            @click="askPublish(row)"
          >{{ governanceManaged ? '发布学期' : '发布并设为当前' }}</button>
          <button
            v-else-if="row.status === 'PUBLISHED' && directSwitchAllowed"
            class="mp-link"
            type="button"
            @click="askPublish(row)"
          >设为当前学期</button>
          <button
            v-else-if="canViewGovernance && governanceManaged && row.status === 'PUBLISHED'"
            class="mp-link"
            type="button"
            @click="goGovernance"
          >统一治理切换</button>
          <span v-else-if="currentError" class="mp-cell-sub">已禁用</span>
          <span v-else-if="row.status === 'FROZEN'" class="mp-cell-sub">请先解冻</span>
          <span v-else class="mp-cell-sub">—</span>
        </template>
      </DataTable>

      <p class="mp-note">历史学期列表始终可读。点击学期名称可查看基本信息、关联业务和状态记录。</p>
    </div>

    <AppConfirmDialog
      v-model:visible="publishDialog.visible"
      :title="publishDialog.title"
      :message="publishDialog.message"
      type="primary"
      :confirm-text="publishDialog.title"
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
import { matchPermission } from '@/config/navPlan'

const STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '已发布', FROZEN: '已冻结', ARCHIVED: '已归档' }

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
      currentLoading: true,
      currentRequestStarted: false,
      currentError: '',
      requestVersion: 0,
      filters: { status: '' },
      pagination: { page: 1, pageSize: 20, total: 0 },
      publishDialog: { visible: false, submitting: false, row: null, message: '', title: '' },
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
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.term.manage') },
    canManageSchoolTerm() { return this.canManage && ['SCHOOL', 'TENANT_ALL'].includes(this.ctx.dataScope?.scope) },
    canViewGovernance() { return matchPermission(this.ctx.permissionPatterns || [], 'systemAdmin.academicCalendar.view') },
    governanceManaged() {
      return this.currentContext?.currentAuthority === 'CALENDAR_GOVERNANCE'
    },
    directSwitchAllowed() {
      return this.canManageSchoolTerm && !this.currentLoading && !this.currentError && !this.governanceManaged && this.currentContext?.canDirectSwitch === true
    },
    publishAllowed() { return this.canManageSchoolTerm && !this.currentLoading && !this.currentError && (this.governanceManaged || this.directSwitchAllowed) },
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
            { value: 'PUBLISHED', label: '已发布' },
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
    dateText(value) { return value ? String(value).slice(0, 10) : '未设置' },
    goDetail(row) { this.$router.push({ name: 'aa-term-detail', params: { termId: row.termId } }) },
    statusLabel(s) {
      return STATUS_LABEL[s] || (s ? '状态待确认' : '')
    },
    isResolvedCurrent(row) {
      return Boolean(this.currentContext?.termId) && String(row.termId) === String(this.currentContext.termId)
    },
    goCreate() {
      if (!this.canManage) return
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
      if (!(row.status === 'DRAFT' ? this.publishAllowed : this.directSwitchAllowed)) {
        toast.warning(this.currentContext?.switchHint || this.currentError || '当前学期由统一治理控制，禁止从学期台账旁路切换')
        return
      }
      if (!['DRAFT', 'PUBLISHED'].includes(row.status)) {
        toast.warning('只有草稿或已发布学期可从本页发布或切换；冻结学期请先解冻')
        return
      }
      this.publishDialog = {
        visible: true,
        submitting: false,
        row,
        title: this.governanceManaged ? '发布学期' : row.status === 'DRAFT' ? '发布并设为当前' : '设为当前学期',
        message: this.governanceManaged
          ? `发布「${row.yearCode} 第 ${row.termNo} 学期」后，日期与教学周将锁定。学校当前学期仍由统一治理设置。`
          : `确认将「${row.yearCode} 第 ${row.termNo} 学期」${row.status === 'DRAFT' ? '发布并' : ''}设为当前学期？其它学期的“当前”结论会被取消。`
      }
    },
    async doPublish() {
      const row = this.publishDialog.row
      if (!row || this.publishDialog.submitting || !(row.status === 'DRAFT' ? this.publishAllowed : this.directSwitchAllowed)) return
      this.publishDialog.submitting = true
      const res = row.status === 'DRAFT'
        ? await academicAffairsApi.publishTerm(row.termId)
        : await academicAffairsApi.setCurrentTerm(row.termId)
      this.publishDialog.submitting = false
      if (res.code === 0) {
        this.publishDialog.visible = false
        toast.success(this.governanceManaged ? '学期已发布' : '当前学期已更新')
        await Promise.all([this.loadCurrentContext(), this.load()])
      } else {
        toast.error(res.message || '发布/切换失败')
        await this.loadCurrentContext()
      }
    },
    async loadCurrentContext() {
      if (this.currentLoading && this.currentRequestStarted) return
      this.currentRequestStarted = true
      this.currentLoading = true
      this.currentContext = null
      this.currentError = ''
      const res = await academicAffairsApi.getCurrentTerm()
      if (res.code === 0) {
        this.currentContext = res.data || null
      } else {
        this.currentContext = null
        this.currentError = res.message || '当前学期解析失败，请核对全校学期治理与教务学期数据'
      }
      this.currentLoading = false
    },
    async load() {
      const version = ++this.requestVersion
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTerms({
        status: this.filters.status || undefined,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (version !== this.requestVersion) return
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
@import '../styles/foundation-workspace.css';
.aa-term-summary { display: flex; align-items: center; flex-wrap: wrap; gap: 12px 18px; padding: 13px 16px; border: 1px solid var(--border-base); border-left: 3px solid var(--pri); border-radius: var(--radius-md); background: var(--bg-card); }
.aa-term-summary__main { flex: 1; min-width: 220px; }
.aa-term-summary__eyebrow { color: var(--pri); font-size: 12px; font-weight: 600; }
.aa-term-summary h2 { margin: 3px 0; font-size: 18px; line-height: 1.35; color: var(--text-primary); }
.aa-term-summary p { margin: 0; font-size: 13px; color: var(--text-secondary); }
.aa-term-summary__facts { display: flex; flex-wrap: wrap; gap: 18px; margin: 0; }
.aa-term-summary__facts dt { color: var(--text-tertiary); font-size: 12px; margin-bottom: 3px; }
.aa-term-summary__facts dd { margin: 0; color: var(--text-primary); font-size: 13px; }
.aa-term-name { text-align: left; font-weight: 600; line-height: 1.7; }
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
