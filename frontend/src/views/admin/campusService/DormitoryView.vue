<template>
  <ModulePageShell
    title="宿舍服务"
    :subtitle="'住宿 ' + dormTotal + ' 条 · 异常 ' + exceptionTotal + ' 条'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <div class="mp-tabs">
        <button class="mp-tab" :class="{ 'is-active': tab === 'dorm' }" @click="switchTab('dorm')">住宿台账</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'exception' }" @click="switchTab('exception')">异常管理</button>
      </div>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading && !rows.length" />
      <EmptyState
        v-else-if="!rows.length"
        :title="tab === 'dorm' ? '没有符合条件的住宿记录' : '没有符合条件的异常记录'"
        description="可调整筛选条件，或确认当前角色所辖楼栋范围"
      />

      <!-- 住宿台账：列表＋详情双栏主工作区（第一批交互改造） -->
      <SplitWorkspace v-else-if="tab === 'dorm'" :has-selection="!!selectedId">
        <template #left>
          <div class="dmv-queue">
            <div class="dmv-queue__bar">
              <span>第 {{ positionText }} 条</span>
            </div>
            <div class="dmv-queue__list" ref="list">
              <div
                v-for="row in rows"
                :key="row.id"
                class="dmv-item"
                :class="{ 'is-active': row.id === selectedId }"
                :data-row-id="row.id"
                @click="select(row.id)"
              >
                <div class="dmv-item__line1">
                  <span class="dmv-item__name">{{ row.name }}</span>
                  <span class="dmv-item__sub">{{ row.className }}</span>
                  <StatusTag :type="row.status === 'IN' ? 'success' : 'default'" :label="dormStatusLabel(row.status)" dot />
                </div>
                <div class="dmv-item__line2">{{ row.building }} · {{ row.room }}-{{ row.bed }}</div>
                <div class="dmv-item__line3">
                  入住 {{ row.checkinDate || '未设置' }}
                  <StatusTag v-if="row.exceptionCount" type="warning" :label="'近30天异常 ' + row.exceptionCount + ' 次'" />
                </div>
              </div>
            </div>
            <div class="dmv-queue__pager">
              <button class="mp-link" :class="{ 'is-disabled': pagination.page <= 1 }" @click="gotoPage(pagination.page - 1)">上一页</button>
              <span class="mp-note">第 {{ pagination.page }} / {{ maxPage }} 页 · 共 {{ pagination.total }} 条</span>
              <button class="mp-link" :class="{ 'is-disabled': pagination.page >= maxPage }" @click="gotoPage(pagination.page + 1)">下一页</button>
            </div>
          </div>
        </template>
        <template #detail="{ narrow }">
          <div v-if="!selectedRecord" class="mp-card dmv-placeholder">
            <div class="mp-card__body"><p class="mp-note">从左侧选择一条住宿记录查看详情</p></div>
          </div>
          <div v-else>
            <div class="dmv-detail__head">
              <button v-if="narrow" class="mp-link" @click="backToListPane">← 返回列表</button>
              <div class="dmv-detail__title">{{ selectedRecord.name }} · {{ selectedRecord.room }}-{{ selectedRecord.bed }}</div>
              <div class="dmv-detail__nav">
                <AppButton variant="ghost" :disabled="!hasPrev" @click="step(-1)">上一条</AppButton>
                <AppButton variant="ghost" :disabled="!hasNext" @click="step(1)">下一条</AppButton>
              </div>
            </div>
            <DormRecordDetail :record="selectedRecord" :exceptions="exceptions" :exceptions-loading="exceptionsLoading" :ctx="ctx">
              <template #actions>
                <AppButton variant="primary" :disabled="!can('campus.dorm.edit')" :title="reason('campus.dorm.edit')" @click="openEdit(selectedRecord)">编辑住宿信息</AppButton>
                <AppButton variant="warning" :disabled="!can('campus.dorm.markException')" :title="reason('campus.dorm.markException')" @click="openMark(selectedRecord)">标记异常</AppButton>
                <AppButton variant="ghost" @click="$router.push('/admin/campus-service/students/' + selectedRecord.studentId)">学生服务</AppButton>
                <AppButton variant="ghost" @click="openDeepLink(selectedRecord)">独立详情页</AppButton>
              </template>
            </DormRecordDetail>
          </div>
        </template>
      </SplitWorkspace>

      <!-- 异常管理：台账表格（连续核实工作区随宿舍与公寓模块施工，属第二批） -->
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :status="row.status" :label="exStatusLabel(row.status)" dot />
        </template>
        <template #cell-type="{ row }">
          <StatusTag :type="['NIGHT_OUT', 'NO_RETURN', 'DISCIPLINE'].includes(row.type) ? 'danger' : 'warning'" :label="row.typeLabel" />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/campus-service/students/' + row.studentId)">学生服务</button>
          <button
            v-if="row.status !== 'COMPLETED'"
            class="mp-link"
            :class="{ 'is-disabled': !can('campus.dorm.handle') }"
            :title="reason('campus.dorm.handle')"
            @click="openHandle(row)"
          >
            跟进处理
          </button>
          <span v-else class="mp-note">{{ row.handler }}</span>
        </template>
      </DataTable>

      <p class="mp-note">
        住宿台账来自后勤同步/导入；晚归、夜不归宿由门禁数据自动生成并支持人工标记。异常处理留痕，严重违纪可转违纪处分流程。导出住宿名单默认脱敏并含水印。
      </p>
    </div>

    <FormDrawer
      v-model:visible="dormForm.visible"
      v-model="dormForm.model"
      :title="dormForm.mode === 'create' ? '新增住宿记录' : '编辑住宿信息（' + dormForm.model.name + '）'"
      :fields="dormFields"
      :submitting="dormForm.submitting"
      @submit="submitDormForm"
    />

    <FormDrawer
      v-model:visible="markForm.visible"
      v-model="markForm.model"
      :title="'标记宿舍异常（' + markForm.name + '）'"
      :fields="markFields"
      :submitting="markForm.submitting"
      submit-text="确认标记"
      note="异常标记会生成待处理记录并通知辅导员；连续/严重异常建议转违纪处分或关怀转介。"
      @submit="submitMark"
    />

    <AppConfirmDialog
      v-model:visible="handleDialog.visible"
      type="primary"
      title="跟进处理宿舍异常"
      :message="(handleDialog.row ? handleDialog.row.code + ' · ' + handleDialog.row.typeLabel : '') + '：填写处理说明后可选择继续跟进或直接办结。'"
      confirm-text="提交处理"
      require-reason
      reason-label="处理说明"
      reason-placeholder="请填写处理过程与结果（如已联系学生/已维修验收），不少于 5 个字"
      show-notify
      notify-label="办结（勾选后状态置为已办结）"
      :submitting="handleDialog.submitting"
      @confirm="submitHandle"
    />

    <ImportDrawer v-model:visible="importVisible" :template="importTemplate" :validate-fn="importValidateFn" :confirm-fn="importConfirmFn" @done="load" />
    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="0" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
  </ModulePageShell>
</template>

<script>
/**
 * 宿舍服务（/admin/campus-service/dormitory）— 2026-07-10 第一批交互改造。
 * 统一口径：住宿台账主工作区=列表＋详情双栏（日常连续查看/处理）；单条住宿记录另有独立详情深链接
 * （/dormitory/records/:recordId，双栏与独立页复用 DormRecordDetail 同一业务详情组件）。
 * 编辑住宿信息/标记异常仍为轻量抽屉（字段≤6，符合抽屉适用范围）；异常跟进为确认弹窗（说明必填）。
 * 页签、筛选、页码、选中项同步路由 query；接口与权限零改动，不虚构房源/调宿数据。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppButton } from '@/components/ui'
import { ImportDrawer, ExportDrawer, FormDrawer, SplitWorkspace, DormRecordDetail, readListState, writeListState } from '@/modules/campusService/components'
import {
  getDormitoryRecords, createDormitoryRecord, updateDormitoryRecord, getDormitoryExceptions, markDormException, handleDormException,
  getImportTemplate, getExportOptions, validateImport, confirmImport, createExport, getServiceStudents
} from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'

const FILTER_KEYS = ['keyword', 'buildingId', 'status', 'type']
const EMPTY_FILTERS = () => ({ keyword: '', buildingId: '', status: '', type: '' })

export default {
  name: 'DormitoryView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, AppButton, ImportDrawer, ExportDrawer, FormDrawer, SplitWorkspace, DormRecordDetail
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'dorm',
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      dormTotal: 0,
      exceptionTotal: 0,
      selectedId: '',
      exceptions: [],
      exceptionsLoading: false,
      studentsOptions: [],
      dormForm: { visible: false, mode: 'create', submitting: false, model: {} },
      markForm: { visible: false, submitting: false, name: '', model: {}, row: null },
      handleDialog: { visible: false, submitting: false, row: null },
      importVisible: false,
      importTemplate: null,
      exportVisible: false,
      exportOpts: null
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx.statusOptions
      const f = this.ctx.filterOptions
      const base = [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生 / 房间 / 编号' },
        { key: 'buildingId', label: '楼栋', type: 'select', options: f.buildings }
      ]
      if (this.tab === 'dorm') return [...base, { key: 'status', label: '住宿状态', type: 'select', options: o.dormStatus }]
      return [
        ...base,
        { key: 'type', label: '异常类型', type: 'select', options: o.dormExceptionType },
        { key: 'status', label: '处理状态', type: 'select', options: o.dormExceptionStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      const list = [
        { key: 'create', permission: 'campus.dorm.create', label: '＋ 新增住宿记录', variant: 'primary', onlyDorm: true },
        { key: 'mark', permission: 'campus.dorm.markException', label: '标记异常', onlyException: true },
        { key: 'import', permission: 'campus.record.import', label: '导入住宿名单', onlyDorm: true },
        { key: 'export', permission: 'campus.dorm.export', label: '导出住宿名单' }
      ].filter((a) => (!a.onlyDorm || this.tab === 'dorm') && (!a.onlyException || this.tab === 'exception'))
      return list
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    },
    columns() {
      return [
        { key: 'code', title: '异常编号' },
        { key: 'name', title: '学生' },
        { key: 'building', title: '楼栋 / 房间' },
        { key: 'type', title: '类型' },
        { key: 'happenTime', title: '发生时间' },
        { key: 'detail', title: '情况说明' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '180px' }
      ]
    },
    dormFields() {
      const f = this.ctx.filterOptions
      const fields = [
        { key: 'buildingId', label: '楼栋', type: 'select', required: true, options: f.buildings },
        { key: 'room', label: '房间', type: 'text', required: true, placeholder: '如 312' },
        { key: 'bed', label: '床位', type: 'text', required: true, placeholder: '如 2' },
        { key: 'checkinDate', label: '入住日期', type: 'date' }
      ]
      if (this.dormForm.mode === 'create') {
        return [{ key: 'studentId', label: '学生', type: 'select', required: true, options: this.studentsOptions }, ...fields]
      }
      return [...fields, { key: 'status', label: '住宿状态', type: 'select', required: true, options: this.ctx.statusOptions.dormStatus }]
    },
    markFields() {
      const fields = [
        { key: 'type', label: '异常类型', type: 'select', required: true, options: this.ctx.statusOptions.dormExceptionType },
        { key: 'detail', label: '情况说明', type: 'textarea', required: true, placeholder: '请描述异常情况（不少于 5 个字）' }
      ]
      if (!this.markForm.row) {
        return [{ key: 'studentId', label: '学生', type: 'select', required: true, options: this.studentsOptions }, ...fields]
      }
      return fields
    },
    maxPage() {
      return Math.max(1, Math.ceil(this.pagination.total / this.pagination.pageSize))
    },
    selectedRecord() {
      return this.rows.find((r) => r.id === this.selectedId) || null
    },
    selectedIndex() {
      return this.rows.findIndex((r) => r.id === this.selectedId)
    },
    positionText() {
      const idx = this.selectedIndex
      const abs = idx >= 0 ? (this.pagination.page - 1) * this.pagination.pageSize + idx + 1 : 0
      return `${abs || '—'} / ${this.pagination.total}`
    },
    hasPrev() {
      return this.selectedIndex > 0 || this.pagination.page > 1
    },
    hasNext() {
      return (this.selectedIndex >= 0 && this.selectedIndex < this.rows.length - 1) || this.pagination.page < this.maxPage
    }
  },
  async created() {
    const st = readListState(this.$route, FILTER_KEYS)
    if (st.tab === 'exception') this.tab = 'exception'
    this.filters = { ...EMPTY_FILTERS(), ...st.filters }
    this.pagination.page = st.page
    this.selectedId = st.selectedId
    this.loadTotals()
    this.load()
  },
  methods: {
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    dormStatusLabel(v) {
      return (this.ctx.statusOptions.dormStatus.find((o) => o.value === v) || {}).label || v
    },
    exStatusLabel(v) {
      return (this.ctx.statusOptions.dormExceptionStatus.find((o) => o.value === v) || {}).label || v
    },
    syncQuery() {
      writeListState(this.$router, this.$route, {
        page: this.pagination.page,
        filters: this.filters,
        selectedId: this.tab === 'dorm' ? this.selectedId : '',
        tab: this.tab === 'exception' ? 'exception' : '',
        filterKeys: FILTER_KEYS
      })
    },
    switchTab(tab) {
      this.tab = tab
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.selectedId = ''
      this.load()
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    async gotoPage(page) {
      if (page < 1 || page > this.maxPage) return
      this.pagination.page = page
      await this.load({ select: 'first' })
    },
    async step(delta) {
      const idx = this.selectedIndex
      const next = idx + delta
      if (next >= 0 && next < this.rows.length) {
        this.select(this.rows[next].id)
      } else if (delta > 0 && this.pagination.page < this.maxPage) {
        this.pagination.page += 1
        await this.load({ select: 'first' })
      } else if (delta < 0 && this.pagination.page > 1) {
        this.pagination.page -= 1
        await this.load({ select: 'last' })
      }
    },
    search() {
      this.pagination.page = 1
      this.selectedId = ''
      this.load({ select: 'first' })
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.selectedId = ''
      this.load({ select: 'first' })
    },
    async loadTotals() {
      const [d, e] = await Promise.all([getDormitoryRecords({ pageSize: 1 }), getDormitoryExceptions({ pageSize: 1 })])
      if (d.code === 0) this.dormTotal = d.data.total
      if (e.code === 0) this.exceptionTotal = e.data.total
    },
    async load({ select = 'keep' } = {}) {
      this.loading = true
      this.error = ''
      this.syncQuery()
      const fn = this.tab === 'dorm' ? getDormitoryRecords : getDormitoryExceptions
      const res = await fn({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
        if (this.tab === 'dorm') this.ensureSelection(select)
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    ensureSelection(mode) {
      if (!this.rows.length) {
        this.selectedId = ''
        this.exceptions = []
        this.syncQuery()
        return
      }
      let target = this.rows.find((r) => r.id === this.selectedId)
      if (!target || mode === 'first') target = mode === 'last' ? this.rows[this.rows.length - 1] : this.rows[0]
      this.select(target.id)
    },
    select(id) {
      this.selectedId = id
      this.syncQuery()
      this.loadExceptions()
      this.$nextTick(() => {
        const el = this.$refs.list && this.$refs.list.querySelector(`[data-row-id="${id}"]`)
        if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' })
      })
    },
    backToListPane() {
      this.selectedId = ''
      this.exceptions = []
      this.syncQuery()
    },
    async loadExceptions() {
      const rec = this.selectedRecord
      if (!rec) return
      this.exceptionsLoading = true
      const res = await getDormitoryExceptions({ keyword: rec.name, pageSize: 20 })
      this.exceptions = res.code === 0 ? (res.data.list || []).filter((e) => e.studentId === rec.studentId) : []
      this.exceptionsLoading = false
    },
    openDeepLink(rec) {
      this.$router.push({ path: '/admin/campus-service/dormitory/records/' + rec.id, query: { stu: rec.name } })
    },
    async ensureStudents() {
      if (!this.studentsOptions.length) {
        const res = await getServiceStudents({ pageSize: 100 })
        if (res.code === 0) this.studentsOptions = res.data.list.map((s) => ({ value: s.id, label: `${s.name}（${s.className}）` }))
      }
    },
    async onToolbar(key) {
      if (key === 'create') {
        await this.ensureStudents()
        this.dormForm = { visible: true, mode: 'create', submitting: false, model: {} }
      } else if (key === 'mark') {
        await this.ensureStudents()
        this.markForm = { visible: true, submitting: false, name: '选择学生', model: {}, row: null }
      } else if (key === 'import') {
        if (!this.importTemplate) {
          const res = await getImportTemplate('dormList')
          if (res.code === 0) this.importTemplate = res.data
        }
        this.importVisible = true
      } else if (key === 'export') {
        if (!this.exportOpts) {
          const res = await getExportOptions('dormList')
          if (res.code === 0) this.exportOpts = res.data
        }
        this.exportVisible = true
      }
    },
    openEdit(row) {
      if (!this.can('campus.dorm.edit')) return
      this.dormForm = {
        visible: true,
        mode: 'edit',
        submitting: false,
        model: { id: row.id, name: row.name, buildingId: row.buildingId, room: row.room, bed: row.bed, checkinDate: row.checkinDate, status: row.status }
      }
    },
    async submitDormForm() {
      this.dormForm.submitting = true
      const m = this.dormForm.model
      const res =
        this.dormForm.mode === 'create'
          ? await createDormitoryRecord(m)
          : await updateDormitoryRecord(m.id, { buildingId: m.buildingId, room: m.room, bed: m.bed, checkinDate: m.checkinDate, status: m.status })
      this.dormForm.submitting = false
      if (res.code === 0) {
        toast.success(this.dormForm.mode === 'create' ? '住宿记录已新增，已写入审计日志' : '住宿信息已更新，变更已留痕')
        this.dormForm.visible = false
        this.loadTotals()
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async openMark(row) {
      if (!this.can('campus.dorm.markException')) return
      this.markForm = { visible: true, submitting: false, name: row.name, model: { studentId: row.studentId }, row }
    },
    async submitMark() {
      this.markForm.submitting = true
      const res = await markDormException(this.markForm.model)
      this.markForm.submitting = false
      if (res.code === 0) {
        toast.success('异常已标记并生成待处理记录（已通知辅导员，已留痕）')
        this.markForm.visible = false
        this.loadTotals()
        if (this.tab === 'exception') this.load()
        else this.loadExceptions()
      } else {
        toast.error(res.message)
      }
    },
    openHandle(row) {
      if (!this.can('campus.dorm.handle')) return
      this.handleDialog = { visible: true, submitting: false, row }
    },
    async submitHandle({ reason, notify }) {
      this.handleDialog.submitting = true
      const res = await handleDormException(this.handleDialog.row.id, { note: reason, complete: notify })
      this.handleDialog.submitting = false
      if (res.code === 0) {
        toast.success(notify ? '异常已办结，处理说明已留痕' : '跟进已记录，状态更新为跟进中')
        this.handleDialog.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    importValidateFn(fileName) {
      return validateImport('dormList', fileName)
    },
    importConfirmFn(payload) {
      return confirmImport('dormList', payload)
    },
    exportFn(payload) {
      return createExport('dormList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
.mp-link.is-disabled {
  pointer-events: none;
  opacity: 0.5;
}
.dmv-queue {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
}
.dmv-queue__bar {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  font-size: var(--font-size-sm);
}
.dmv-queue__list {
  max-height: 560px;
  overflow: auto;
}
.dmv-item {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
}
.dmv-item:hover {
  background: var(--bg-section-blue, var(--primary-50));
}
.dmv-item.is-active {
  background: var(--primary-50);
  box-shadow: inset 2px 0 0 var(--primary-500);
}
.dmv-item__line1 {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.dmv-item__name {
  font-weight: var(--font-weight-semibold);
}
.dmv-item__sub {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.dmv-item__line2 {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-top: 2px;
}
.dmv-item__line3 {
  font-size: var(--font-size-xs, 12px);
  color: var(--text-tertiary, var(--text-secondary));
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.dmv-queue__pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
}
.dmv-detail__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.dmv-detail__title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}
.dmv-detail__nav {
  margin-left: auto;
  display: flex;
  gap: var(--space-2);
}
.dmv-placeholder {
  text-align: center;
}
</style>
