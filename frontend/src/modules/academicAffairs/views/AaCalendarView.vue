<template>
  <ModulePageShell
    title="校历节次 · 校历"
    subtitle="按学期维护教学 / 考试 / 实习 / 节假日 / 补课日安排；校历发布会触及当前学期 Authority"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">
          学期
          <AppTermEntityPicker v-model="termId" :options="termOptions" @change="onTermChange" />
        </label>
      </div>

      <AppInlineAlert
        v-if="currentError"
        type="danger"
        :description="`当前学期解析失败：${currentError}。校历仍可按显式学期查看，但发布已安全禁用。`"
      />
      <AppInlineAlert
        v-else-if="governanceManaged"
        type="info"
        :description="currentContext.switchHint || '全校统一学期治理已启用；校历页不能通过发布其它学期旁路切换当前学期。'"
      />

      <EmptyState
        v-if="!termsLoading && !terms.length"
        title="还没有学年学期"
        description="校历依附于学期，请先到「学年学期」创建并发布一个学期"
      >
        <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/terms')">前往学年学期</AppButton>
      </EmptyState>

      <template v-else>
        <nav class="aa-tabs">
          <button v-for="t in tabs" :key="t.key" class="aa-tab" :class="{ 'is-active': tab === t.key }"
                  @click="switchTab(t.key)">{{ t.label }}</button>
        </nav>

        <template v-if="['events', 'holiday', 'makeup'].includes(tab)">
          <AppInlineAlert v-if="selectedTerm && isLocked" type="warning"
                          description="校历已发布，事件已锁定；如需调整请到「校历归档」页确认状态，或联系教务处走线下变更流程。" />

          <AaCalendarCopyPanel
            v-if="tab === 'events'"
            :terms="terms"
            :target-term-id="termId"
            :disabled="isLocked"
            @applied="loadEvents"
          />

          <AppSectionCard :title="addFormTitle">
            <div class="aa-cal-form">
              <label v-if="tab === 'events'" class="aa-cal-form__item">
                类型
                <AppSelect v-model="draft.eventType" :options="eventTypeOptions" />
              </label>
              <label class="aa-cal-form__item">
                {{ tab === 'makeup' ? '原停课日期' : '开始日期' }}
                <AppDatePicker v-model="draft.startDate" />
              </label>
              <label v-if="tab !== 'makeup' && draft.eventType !== 'SWAP'" class="aa-cal-form__item">
                结束日期
                <AppDatePicker v-model="draft.endDate" />
              </label>
              <label v-if="tab === 'makeup' || draft.eventType === 'SWAP'" class="aa-cal-form__item">
                调至日期（补课日）
                <AppDatePicker v-model="draft.swapToDate" />
              </label>
              <label class="aa-cal-form__item aa-cal-form__item--grow">
                备注
                <AppTextInput v-model="draft.remark" placeholder="选填，如 国庆假期 / 国庆调休" :maxlength="60" />
              </label>
              <AppButton variant="primary" :disabled="isLocked" :loading="adding" @click="addEvent">添加</AppButton>
            </div>
            <AppInlineAlert v-if="formError" type="danger" :description="formError" />
          </AppSectionCard>

          <AppSectionCard :title="listTitle">
            <ErrorState v-if="error" :description="error" @retry="loadEvents" />
            <LoadingState v-else-if="eventsLoading" />
            <EmptyState v-else-if="!filteredEvents.length" :title="emptyTitle" :description="emptyDesc" />
            <DataTable v-else :columns="eventColumns" :rows="filteredEvents" row-key="eventId">
              <template #cell-eventType="{ row }">
                <StatusTag :type="typeColor(row.eventType)" :label="EVENT_TYPES[row.eventType] || row.eventType" dot />
              </template>
              <template #cell-actions="{ row }">
                <button class="mp-link" :disabled="isLocked" @click="openEdit(row)">编辑</button>
                <button class="mp-link aa-danger" :disabled="isLocked" @click="confirmDelete(row)">删除</button>
              </template>
            </DataTable>
          </AppSectionCard>
        </template>

        <template v-else-if="tab === 'weekCalendar'">
          <AppSectionCard title="教学周日历">
            <ErrorState v-if="weekError" :description="weekError" @retry="loadWeekCalendar" />
            <LoadingState v-else-if="weekLoading" />
            <EmptyState v-else-if="!weekData || !weekData.weeks.length" title="暂无教学周数据"
                        description="请先在「学年学期」维护起止日期与教学周数" />
            <ul v-else class="aa-week-list">
              <li v-for="w in weekData.weeks" :key="w.weekNo" class="aa-week-item">
                <span class="aa-week-item__no">第 {{ w.weekNo }} 周</span>
                <span class="aa-week-item__range">{{ w.startDate }} ~ {{ w.endDate }}</span>
                <StatusTag :type="weekTypeColor(w.weekType)" :label="WEEK_TYPES[w.weekType] || w.weekType" dot />
                <span v-if="w.holidays.length" class="aa-week-item__tag">假期：{{ w.holidays.map(h => h.remark || '假期').join('、') }}</span>
                <span v-if="w.swaps.length" class="aa-week-item__tag">调休：{{ w.swaps.length }} 项</span>
              </li>
            </ul>
          </AppSectionCard>
        </template>

        <template v-else-if="tab === 'publish'">
          <AppSectionCard title="校历发布">
            <p class="mp-note">发布后校历事件（教学/考试/实习/节假日/补课日）锁定，不可再增删改；该动作同时会把所属学期设为当前，因此必须服从 A-C1 当前学期 Authority。</p>
            <div v-if="selectedTerm" class="aa-status-row">
              <span>所选学期：{{ selectedTerm.yearCode }} 第 {{ selectedTerm.termNo }} 学期</span>
              <StatusTag :status="selectedTerm.status" />
              <StatusTag v-if="isSelectedResolvedCurrent" type="success" label="全校当前" dot />
            </div>
            <AppInlineAlert v-if="!canManageCalendar" type="info" description="仅教务处 / 学校管理员可执行发布，当前身份可查看但按钮已禁用。" />
            <AppInlineAlert v-if="currentError" type="danger" description="当前学期 Authority 无法解析，发布已 fail-closed；请先修复学期治理数据。" />
            <AppInlineAlert
              v-else-if="governanceManaged && !isSelectedResolvedCurrent"
              type="warning"
              :description="currentContext.switchHint || '所选学期不是全校 ACTIVE 学期，禁止通过校历发布旁路切换；请先从统一治理入口切换。'"
            />
            <AppInlineAlert v-if="selectedTerm && selectedTerm.status !== 'DRAFT'" type="info"
                            :description="selectedTerm.status === 'PUBLISHED' ? '校历已发布。' : '当前学期状态不支持再次发布。'" />
            <AppButton variant="primary" :disabled="!canPublish" :loading="publishing" @click="doPublish">
              {{ publishing ? '发布中…' : '发布校历' }}
            </AppButton>
          </AppSectionCard>
        </template>

        <template v-else-if="tab === 'archive'">
          <AppSectionCard title="校历归档">
            <p class="mp-note">归档校历是全模块级动作，需通过「教务归档」的批次 + 数据完整性检查确认，本页仅供状态查看。</p>
            <div v-if="selectedTerm" class="aa-status-row">
              <span>所选学期：{{ selectedTerm.yearCode }} 第 {{ selectedTerm.termNo }} 学期</span>
              <StatusTag :status="selectedTerm.status" />
              <StatusTag v-if="isSelectedResolvedCurrent" type="success" label="全校当前" dot />
            </div>
            <AppInlineAlert v-if="selectedTerm && selectedTerm.status === 'DRAFT'" type="warning" description="校历尚未发布，请先到「校历发布」页发布。" />
            <AppInlineAlert v-if="selectedTerm && selectedTerm.status === 'ARCHIVED'" type="success" description="该学期已归档，全部写操作已锁定。" />
            <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/archive')">前往教务归档</AppButton>
          </AppSectionCard>
        </template>
      </template>
    </div>

    <AppDrawer :visible="editVisible" title="编辑校历事件" mode="modal" size="large" @close="editVisible = false">
      <div class="aa-cal-form aa-cal-form--drawer" v-if="editForm">
        <AppFormItem label="类型" v-if="tab === 'events'">
          <AppSelect v-model="editForm.eventType" :options="eventTypeOptions" />
        </AppFormItem>
        <AppFormItem :label="editForm.eventType === 'SWAP' ? '原停课日期' : '开始日期'" required>
          <AppDatePicker v-model="editForm.startDate" />
        </AppFormItem>
        <AppFormItem label="结束日期" v-if="editForm.eventType !== 'SWAP'">
          <AppDatePicker v-model="editForm.endDate" />
        </AppFormItem>
        <AppFormItem label="调至日期（补课日）" v-if="editForm.eventType === 'SWAP'" required>
          <AppDatePicker v-model="editForm.swapToDate" />
        </AppFormItem>
        <AppFormItem label="备注">
          <AppTextInput v-model="editForm.remark" :maxlength="60" />
        </AppFormItem>
        <AppInlineAlert v-if="editError" type="danger" :description="editError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="editVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitEdit">保存</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" title="删除校历事件"
                      message="删除后不可恢复，确认删除该事件？" type="danger" @confirm="doDelete" />
  </ModulePageShell>
</template>

<script>
/** 校历节次 · 校历（/admin/academic-affairs/calendar）。
 * A-W1：publishCalendar 会改变 current，必须先消费 /terms/current 的 A-C1 结论；
 * 历史校历浏览不因 current resolver 失败而被阻断。
 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppSectionCard, AppSelect, AppTextInput, AppFormItem, AppDatePicker, AppTermEntityPicker, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import AaCalendarCopyPanel from '@/modules/academicAffairs/components/AaCalendarCopyPanel.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { loadAcademicTermCatalog } from '@/modules/academicAffairs/pickerAdapters'
import { toast } from '@/utils/toast'

const EVENT_TYPES = { TEACHING: '教学', EXAM: '考试', INTERNSHIP: '实习', HOLIDAY: '节假日', SWAP: '补课日' }
const TYPE_COLOR = { TEACHING: 'primary', EXAM: 'danger', INTERNSHIP: 'warning', HOLIDAY: 'success', SWAP: 'default' }
const WEEK_TYPES = { TEACHING: '教学周', EXAM: '考试周', HOLIDAY: '假期周', INTERNSHIP: '实习周' }
const WEEK_TYPE_COLOR = { TEACHING: 'default', EXAM: 'danger', HOLIDAY: 'success', INTERNSHIP: 'warning' }
const MGMT_ROLES = ['ACADEMIC_ADMIN', 'SCHOOL_ADMIN', 'PLATFORM_SUPER_ADMIN']
const TAB_EVENT_TYPE = { events: '', holiday: 'HOLIDAY', makeup: 'SWAP' }

export default {
  name: 'AaCalendarView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppSectionCard, AppSelect, AppTextInput, AppFormItem, AppDatePicker, AppTermEntityPicker,
    AppConfirmDialog, AppInlineAlert, AaCalendarCopyPanel
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      EVENT_TYPES, WEEK_TYPES,
      eventTypeOptions: Object.entries(EVENT_TYPES).map(([value, label]) => ({ value, label })),
      termsLoading: true,
      terms: [],
      termId: '',
      currentContext: null,
      currentError: '',
      tab: 'events',
      tabs: [
        { key: 'events', label: '校历管理' },
        { key: 'holiday', label: '节假日配置' },
        { key: 'makeup', label: '补课日配置' },
        { key: 'weekCalendar', label: '教学周日历' },
        { key: 'publish', label: '校历发布' },
        { key: 'archive', label: '校历归档' }
      ],
      eventsLoading: false,
      error: '',
      events: [],
      adding: false,
      formError: '',
      draft: { eventType: 'TEACHING', startDate: '', endDate: '', swapToDate: '', remark: '' },
      editVisible: false,
      editForm: null,
      editError: '',
      saving: false,
      confirmVisible: false,
      pendingDelete: null,
      weekLoading: false,
      weekError: '',
      weekData: null,
      publishing: false
    }
  },
  computed: {
    governanceManaged() {
      return this.currentContext?.currentAuthority === 'CALENDAR_GOVERNANCE'
    },
    termOptions() {
      return this.terms.map((t) => ({
        value: t.termId,
        label: `${t.yearCode} 第 ${t.termNo} 学期${this.isResolvedCurrent(t) ? '（全校当前）' : ''} · ${this.statusLabel(t.status)}`
      }))
    },
    selectedTerm() {
      return this.terms.find((t) => String(t.termId) === String(this.termId)) || null
    },
    isSelectedResolvedCurrent() {
      return this.isResolvedCurrent(this.selectedTerm)
    },
    isLocked() {
      return !!this.selectedTerm && ['PUBLISHED', 'FROZEN', 'ARCHIVED'].includes(this.selectedTerm.status)
    },
    canManageCalendar() {
      return MGMT_ROLES.includes((this.ctx.currentRole && this.ctx.currentRole.roleCode || '').toUpperCase())
    },
    canPublish() {
      if (!this.canManageCalendar || !this.selectedTerm || this.selectedTerm.status !== 'DRAFT' || this.currentError) return false
      if (this.governanceManaged) return this.isSelectedResolvedCurrent
      return this.currentContext?.canDirectSwitch !== false
    },
    filteredEvents() {
      const t = TAB_EVENT_TYPE[this.tab]
      const rows = t ? this.events.filter((e) => e.eventType === t) : this.events
      return rows.map((e) => ({
        ...e,
        dateLabel: e.endDate && e.endDate !== e.startDate ? `${e.startDate || '—'} ~ ${e.endDate}` : (e.startDate || '—')
      }))
    },
    eventColumns() {
      if (this.tab === 'holiday') {
        return [
          { key: 'dateLabel', title: '节假日期' },
          { key: 'remark', title: '备注' },
          { key: 'actions', title: '操作' }
        ]
      }
      if (this.tab === 'makeup') {
        return [
          { key: 'startDate', title: '原停课日期' },
          { key: 'swapToDate', title: '调至日期（补课日）' },
          { key: 'remark', title: '备注' },
          { key: 'actions', title: '操作' }
        ]
      }
      return [
        { key: 'eventType', title: '类型' },
        { key: 'dateLabel', title: '日期' },
        { key: 'remark', title: '备注' },
        { key: 'actions', title: '操作' }
      ]
    },
    addFormTitle() {
      return { events: '新增校历事件', holiday: '新增节假日', makeup: '新增补课日（调休）' }[this.tab] || '新增'
    },
    listTitle() {
      return { events: '校历事件', holiday: '节假日列表', makeup: '补课日列表' }[this.tab] || '列表'
    },
    emptyTitle() {
      return { events: '本学期暂无校历事件', holiday: '本学期暂无节假日', makeup: '本学期暂无补课日' }[this.tab] || '暂无数据'
    },
    emptyDesc() {
      return { events: '用上方表单添加教学/考试/假期等安排', holiday: '用上方表单添加国庆/寒暑假等节假日', makeup: '用上方表单添加调休补课安排（原停课日+调至日期成对登记）' }[this.tab] || ''
    }
  },
  created() {
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.resetDraft()
    this.refreshTermCatalog()
  },
  methods: {
    statusLabel(s) {
      return { DRAFT: '草稿', PUBLISHED: '已发布', FROZEN: '已锁定', ARCHIVED: '已归档' }[s] || s
    },
    typeColor(t) {
      return TYPE_COLOR[t] || 'default'
    },
    weekTypeColor(t) {
      return WEEK_TYPE_COLOR[t] || 'default'
    },
    isResolvedCurrent(term) {
      return Boolean(term && this.currentContext?.termId) && String(term.termId) === String(this.currentContext.termId)
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
    resetDraft() {
      const fixedType = TAB_EVENT_TYPE[this.tab]
      this.draft = { eventType: fixedType || 'TEACHING', startDate: '', endDate: '', swapToDate: '', remark: '' }
      this.formError = ''
    },
    switchTab(key) {
      if (this.tab === key) return
      this.tab = key
      this.resetDraft()
      this.loadForTab()
    },
    async refreshTermCatalog() {
      this.termsLoading = true
      try {
        this.terms = await loadAcademicTermCatalog()
        await this.loadCurrentContext()
        const selected = this.terms.find((t) => String(t.termId) === String(this.termId))
        const resolved = this.terms.find((t) => this.isResolvedCurrent(t))
        const fallback = this.terms[0]
        const next = selected || resolved || fallback
        if (next) {
          this.termId = next.termId
          this.loadForTab()
        }
      } catch (error) {
        this.error = error.message || '学期数据加载失败'
      }
      this.termsLoading = false
    },
    onTermChange() {
      this.loadForTab()
    },
    loadForTab() {
      if (!this.termId) return
      if (this.tab === 'weekCalendar') { this.loadWeekCalendar(); return }
      if (this.tab === 'publish' || this.tab === 'archive') return
      this.loadEvents()
    },
    async loadEvents() {
      if (!this.termId) return
      this.eventsLoading = true
      this.error = ''
      const res = await academicAffairsApi.getCalendar(this.termId)
      if (res.code === 0) {
        this.events = res.data || []
      } else {
        this.error = res.message
      }
      this.eventsLoading = false
    },
    async addEvent() {
      if (this.adding || !this.termId) return
      this.formError = ''
      const eventType = TAB_EVENT_TYPE[this.tab] || this.draft.eventType
      if (!this.draft.startDate) {
        this.formError = this.tab === 'makeup' ? '请先选择原停课日期' : '请先选择开始日期'
        return
      }
      if ((eventType === 'SWAP') && !this.draft.swapToDate) {
        this.formError = '补课日必须填写「调至日期」，节假日与补课日须成对登记'
        return
      }
      this.adding = true
      const body = {
        eventType,
        startDate: this.draft.startDate,
        endDate: eventType === 'SWAP' ? undefined : (this.draft.endDate || this.draft.startDate),
        swapToDate: eventType === 'SWAP' ? this.draft.swapToDate : undefined,
        remark: this.draft.remark || undefined
      }
      const res = await academicAffairsApi.addCalendarEvent(this.termId, body)
      this.adding = false
      if (res.code === 0) {
        toast.success('已添加')
        this.resetDraft()
        this.loadEvents()
      } else {
        this.formError = res.message || '添加失败'
      }
    },
    openEdit(row) {
      this.editForm = { eventId: row.eventId, eventType: row.eventType, startDate: row.startDate || '',
        endDate: row.endDate || '', swapToDate: row.swapToDate || '', remark: row.remark || '' }
      this.editError = ''
      this.editVisible = true
    },
    async submitEdit() {
      if (this.saving || !this.editForm) return
      if (!this.editForm.startDate) { this.editError = '请先选择日期'; return }
      if (this.editForm.eventType === 'SWAP' && !this.editForm.swapToDate) {
        this.editError = '补课日必须填写「调至日期」'
        return
      }
      this.saving = true
      const body = {
        eventType: this.editForm.eventType,
        startDate: this.editForm.startDate,
        endDate: this.editForm.eventType === 'SWAP' ? undefined : (this.editForm.endDate || this.editForm.startDate),
        swapToDate: this.editForm.eventType === 'SWAP' ? this.editForm.swapToDate : undefined,
        remark: this.editForm.remark || undefined
      }
      const res = await academicAffairsApi.updateCalendarEvent(this.termId, this.editForm.eventId, body)
      this.saving = false
      if (res.code === 0) {
        toast.success('已保存')
        this.editVisible = false
        this.loadEvents()
      } else {
        this.editError = res.message || '保存失败'
      }
    },
    confirmDelete(row) {
      this.pendingDelete = row
      this.confirmVisible = true
    },
    async doDelete() {
      if (!this.pendingDelete) return
      const res = await academicAffairsApi.deleteCalendarEvent(this.termId, this.pendingDelete.eventId)
      if (res.code === 0) {
        toast.success('已删除')
        this.loadEvents()
      } else {
        toast.error(res.message || '删除失败')
      }
      this.pendingDelete = null
    },
    async loadWeekCalendar() {
      if (!this.termId) return
      this.weekLoading = true
      this.weekError = ''
      const res = await academicAffairsApi.getWeekCalendar(this.termId)
      if (res.code === 0) {
        this.weekData = res.data
      } else {
        this.weekError = res.message
        this.weekData = null
      }
      this.weekLoading = false
    },
    async doPublish() {
      if (this.publishing || !this.canPublish) {
        if (!this.canPublish) toast.warning(this.currentContext?.switchHint || this.currentError || '当前学期 Authority 不允许从校历页发布并切换')
        return
      }
      this.publishing = true
      const res = await academicAffairsApi.publishCalendar(this.termId)
      this.publishing = false
      if (res.code === 0) {
        toast.success('校历已发布')
        this.refreshTermCatalog()
      } else {
        toast.error(res.message || '发布失败')
        this.loadCurrentContext()
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; }
.aa-filter__item, .aa-cal-form__item {
  display: inline-flex; flex-direction: column; gap: 6px;
  font-size: 13px; color: var(--text-700, #4e5969);
}
.aa-filter__item { flex-direction: row; align-items: center; gap: 8px; }
.aa-select {
  height: 34px; padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px;
  box-sizing: border-box;
}
.aa-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); flex-wrap: wrap; }
.aa-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aa-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form--drawer { flex-direction: column; align-items: stretch; }
.aa-cal-form__item--grow { flex: 1; min-width: 200px; }
.mp-link.aa-danger { color: var(--danger-600, #f53f3f); }
.aa-week-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.aa-week-item { display: flex; align-items: center; gap: 14px; padding: 10px 4px; border-bottom: 1px solid var(--border-100, #f0f1f2); flex-wrap: wrap; }
.aa-week-item__no { font-weight: 600; min-width: 64px; }
.aa-week-item__range { color: var(--text-500, #646a73); font-size: 13px; min-width: 180px; }
.aa-week-item__tag { font-size: 12px; color: var(--text-500, #646a73); }
.aa-status-row { display: flex; align-items: center; gap: 10px; margin: 12px 0; font-size: 14px; flex-wrap: wrap; }
</style>
