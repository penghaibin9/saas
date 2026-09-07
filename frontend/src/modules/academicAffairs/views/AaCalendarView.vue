<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    title="校历安排"
    subtitle="安排教学、考试、实习与节假日，核对调休日期后统一发布。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">
          学期
          <AppTermEntityPicker v-model="termId" :options="termOptions" :clearable="false" :disabled="busy || termsLoading" @change="onTermChange" />
        </label>
      </div>

      <AppInlineAlert
        v-if="currentError"
        type="danger"
        :description="`当前学期暂不可用：${currentError}。可继续查看所选学期的校历，暂不能发布。`"
      />
      <AppInlineAlert
        v-else-if="governanceManaged"
        type="info"
        description="当前学期由学校统一设置。发布校历前，请核对所选学期与全校当前学期一致。"
      />

      <ErrorState v-if="catalogError" :description="catalogError" @retry="refreshTermCatalog" />
      <LoadingState v-else-if="termsLoading" />
      <EmptyState
        v-else-if="!terms.length"
        title="还没有学年学期"
        description="请先创建草稿学期，完善校历后再发布。"
      >
        <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/terms')">前往学年学期</AppButton>
      </EmptyState>

      <template v-else>
        <nav class="aa-tabs">
          <button v-for="t in tabs" :key="t.key" class="aa-tab" :class="{ 'is-active': tab === t.key }" :aria-current="tab === t.key ? 'page' : undefined" :disabled="busy"
                  @click="switchTab(t.key)">{{ t.label }}</button>
        </nav>

        <template v-if="['events', 'holiday', 'makeup'].includes(tab)">
          <AppInlineAlert v-if="selectedTerm && isLocked" type="warning"
                          description="所选学期已发布，校历事件保持锁定。如需调整，请联系教务处核对学校的变更流程。" />

          <details v-if="tab === 'events' && canEditCalendar && !isLocked" class="aa-calendar-copy">
            <summary>从历史学期复制校历</summary>
            <AaCalendarCopyPanel
            :terms="terms"
            :target-term-id="termId"
            :disabled="!canEditEvents || adding || saving || deleting || publishing"
            @applied="loadEvents"
            @busy="copying = $event"
            />
          </details>

          <AppSectionCard v-if="canEditCalendar && !isLocked" :title="addFormTitle">
            <fieldset class="aa-cal-form" :disabled="busy">
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
              <AppButton variant="primary" :disabled="!canEditEvents || busy" :loading="adding" @click="addEvent">添加</AppButton>
            </fieldset>
            <AppInlineAlert v-if="formError" type="danger" :description="formError" />
          </AppSectionCard>

          <AppSectionCard :title="listTitle">
            <ErrorState v-if="error" :description="error" @retry="loadEvents" />
            <LoadingState v-else-if="eventsLoading" />
            <EmptyState v-else-if="!filteredEvents.length" :title="emptyTitle" :description="emptyDesc" />
            <DataTable v-else :columns="eventColumns" :rows="filteredEvents" row-key="eventId">
              <template #cell-eventType="{ row }">
                <StatusTag :type="typeColor(row.eventType)" :label="EVENT_TYPES[row.eventType] || '类型待确认'" dot />
              </template>
              <template #cell-actions="{ row }">
                <button v-if="canEditCalendar && !isLocked" class="mp-link" :disabled="!canEditEvents || busy" @click="openEdit(row)">编辑</button>
                <button v-if="canEditCalendar && !isLocked" class="mp-link aa-danger" :disabled="!canEditEvents || busy" @click="confirmDelete(row)">删除</button>
                <span v-else class="mp-note">只读</span>
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
                <span class="aa-week-item__range">{{ calendarDate(w.startDate) }} 至 {{ calendarDate(w.endDate) }}</span>
                <StatusTag :type="weekTypeColor(w.weekType)" :label="WEEK_TYPES[w.weekType] || '类型待确认'" dot />
                <span v-if="w.holidays.length" class="aa-week-item__tag">假期：{{ w.holidays.map(h => h.remark || '假期').join('、') }}</span>
                <span v-if="w.swaps.length" class="aa-week-item__tag">调休：{{ w.swaps.length }} 项</span>
              </li>
            </ul>
          </AppSectionCard>
        </template>

        <template v-else-if="tab === 'publish'">
          <AppSectionCard title="校历发布">
            <p class="mp-note">发布后，本学期的校历事件将锁定。请先配置至少一个启用节次，并核对补课日期。{{ governanceManaged ? '全校当前学期保持学校的统一设置。' : '本次发布会同时将所选学期设为当前学期。' }}</p>
            <div v-if="selectedTerm" class="aa-status-row">
              <span>所选学期：{{ selectedTerm.yearCode }} 第 {{ selectedTerm.termNo }} 学期</span>
              <StatusTag :status="selectedTerm.status" />
              <StatusTag v-if="isSelectedResolvedCurrent" type="success" label="全校当前" dot />
            </div>
            <AppInlineAlert v-if="!canManageCalendar" type="info" description="当前身份没有校历发布权限，可查看发布状态。" />
            <AppInlineAlert v-if="currentError" type="danger" description="暂不能确定全校当前学期，请刷新或联系学校管理员核对后再发布。" />
            <AppInlineAlert
              v-else-if="governanceManaged && !isSelectedResolvedCurrent"
              type="warning"
              description="所选学期与全校当前学期不一致。请先在学校的统一学期设置中完成切换。"
            />
            <AppInlineAlert v-if="selectedTerm && selectedTerm.status !== 'DRAFT'" type="info"
                            :description="selectedTerm.status === 'PUBLISHED' ? '校历已发布。' : '当前学期状态不支持再次发布。'" />
            <AppButton v-if="canManageCalendar" variant="primary" :disabled="!canPublish || busy" :loading="publishing" @click="publishVisible = true">
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
            <AppButton v-if="hasPermission('academicAffairs.archive.view')" variant="primary" @click="$router.push('/admin/academic-affairs/archive')">前往教务归档</AppButton>
          </AppSectionCard>
        </template>
      </template>
    </div>

    <AppDrawer :visible="editVisible" title="编辑校历事件" mode="modal" size="large" @close="editVisible = false">
      <fieldset class="aa-cal-form aa-cal-form--drawer" v-if="editForm" :disabled="saving">
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
      </fieldset>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="editVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitEdit">保存</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" title="删除校历事件"
                      message="删除后，该安排将从校历移除。确认删除？" type="danger" :submitting="deleting" @confirm="doDelete" />
    <AppConfirmDialog v-model:visible="publishVisible" title="发布校历"
                      :message="governanceManaged ? '发布后校历事件将锁定，全校当前学期保持不变。确认发布？' : '发布后校历事件将锁定，并将所选学期设为当前学期。确认发布？'"
                      confirm-text="确认发布" :submitting="publishing" @confirm="doPublish" />
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
import { matchPermission } from '@/config/navPlan'

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
      catalogError: '', currentLoading: true,
      eventRequestVersion: 0, weekRequestVersion: 0,
      copying: false, deleting: false, publishVisible: false,
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
    busy() { return this.adding || this.saving || this.deleting || this.publishing || this.copying },
    canEditCalendar() { return this.hasPermission('academicAffairs.calendar.manage') },
    canEditEvents() { return this.canEditCalendar && this.selectedTerm?.status === 'DRAFT' && !this.termsLoading && !this.catalogError },
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
      return this.hasPermission('academicAffairs.calendarPublish.manage') && ['SCHOOL', 'TENANT_ALL'].includes(this.ctx.dataScope?.scope) && MGMT_ROLES.includes((this.ctx.currentRole?.roleCode || '').toUpperCase())
    },
    canPublish() {
      if (!this.canManageCalendar || !this.selectedTerm || this.selectedTerm.status !== 'DRAFT' || this.currentError || this.currentLoading || this.termsLoading || this.catalogError) return false
      if (this.governanceManaged) return this.isSelectedResolvedCurrent
      return this.currentContext?.canDirectSwitch === true
    },
    filteredEvents() {
      const t = TAB_EVENT_TYPE[this.tab]
      const rows = t ? this.events.filter((e) => e.eventType === t) : this.events
      return rows.map((e) => ({
        ...e,
        startDate: this.calendarDate(e.startDate), swapToDate: this.calendarDate(e.swapToDate),
        dateLabel: e.eventType === 'SWAP' ? `${this.calendarDate(e.startDate)} → ${this.calendarDate(e.swapToDate)}`
          : e.endDate && e.endDate !== e.startDate ? `${this.calendarDate(e.startDate)} 至 ${this.calendarDate(e.endDate)}` : this.calendarDate(e.startDate)
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
      if (!this.canEditEvents) return '该学期暂未登记此类安排。'
      return { events: '用上方表单添加教学/考试/假期等安排', holiday: '用上方表单添加国庆/寒暑假等节假日', makeup: '用上方表单添加调休补课安排（原停课日+调至日期成对登记）' }[this.tab] || ''
    }
  },
  created() {
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.resetDraft()
    this.refreshTermCatalog()
  },
  watch: {
    '$route.query.tab'(key) { this.switchTab(this.tabs.some(t => t.key === key) ? key : 'events') },
    '$route.query.termId'(id) {
      if (!this.busy && id && String(id) !== String(this.termId) && this.terms.some(t => String(t.termId) === String(id))) {
        this.termId = id; this.onTermChange()
      }
    }
  },
  beforeRouteUpdate(to, from, next) { if (this.busy) { toast.warning('正在保存校历，请稍候再切换'); next(false) } else next() },
  beforeUnmount() { this.eventRequestVersion++; this.weekRequestVersion++ },
  methods: {
    hasPermission(key) { return matchPermission(this.ctx.permissionPatterns || [], key) },
    calendarDate(value) { return value ? String(value).slice(0, 10) : '—' },
    statusLabel(s) {
      return { DRAFT: '草稿', PUBLISHED: '已发布', FROZEN: '已锁定', ARCHIVED: '已归档' }[s] || '状态待确认'
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
    resetDraft() {
      const fixedType = TAB_EVENT_TYPE[this.tab]
      this.draft = { eventType: fixedType || 'TEACHING', startDate: '', endDate: '', swapToDate: '', remark: '' }
      this.formError = ''
    },
    switchTab(key) {
      if (this.tab === key || this.busy) return
      this.tab = key
      this.syncQuery()
      this.resetDraft()
      this.loadForTab()
    },
    async refreshTermCatalog() {
      this.termsLoading = true
      this.catalogError = ''
      try {
        this.terms = await loadAcademicTermCatalog()
        await this.loadCurrentContext()
        const selected = this.terms.find((t) => String(t.termId) === String(this.termId || this.$route.query.termId))
        const resolved = this.terms.find((t) => this.isResolvedCurrent(t))
        const fallback = this.terms[0]
        const next = selected || resolved || fallback
        if (next) {
          this.termId = next.termId
          this.syncQuery()
          this.loadForTab()
        }
      } catch (error) {
        this.catalogError = error.message || '学期数据加载失败'
      }
      this.termsLoading = false
    },
    onTermChange() {
      this.eventRequestVersion++; this.weekRequestVersion++
      this.events = []; this.weekData = null
      this.resetDraft(); this.editVisible = false; this.confirmVisible = false; this.publishVisible = false
      this.syncQuery()
      this.loadForTab()
    },
    syncQuery() {
      if (this.termId && (String(this.$route.query.termId) !== String(this.termId) || this.$route.query.tab !== this.tab)) {
        this.$router.replace({ query: { ...this.$route.query, termId: String(this.termId), tab: this.tab } })
      }
    },
    loadForTab() {
      if (!this.termId) return
      if (this.tab === 'weekCalendar') { this.loadWeekCalendar(); return }
      if (this.tab === 'publish' || this.tab === 'archive') return
      this.loadEvents()
    },
    async loadEvents() {
      const version = ++this.eventRequestVersion
      if (!this.termId) return
      this.eventsLoading = true
      this.error = ''
      const res = await academicAffairsApi.getCalendar(this.termId)
      if (version !== this.eventRequestVersion) return
      if (res.code === 0) {
        this.events = res.data || []
      } else {
        this.error = res.message
      }
      this.eventsLoading = false
    },
    async addEvent() {
      if (this.busy || !this.canEditEvents) return
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
      if (eventType !== 'SWAP' && this.draft.endDate && this.draft.endDate < this.draft.startDate) { this.formError = '结束日期不能早于开始日期'; return }
      if (eventType === 'SWAP' && this.draft.startDate === this.draft.swapToDate) { this.formError = '补课日期不能与原停课日期相同'; return }
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
      if (this.busy || !this.canEditEvents) return
      this.editForm = { eventId: row.eventId, eventType: row.eventType, startDate: row.startDate ? row.startDate.slice(0, 10) : '',
        endDate: row.endDate ? row.endDate.slice(0, 10) : '', swapToDate: row.swapToDate && row.swapToDate !== '—' ? row.swapToDate.slice(0, 10) : '', remark: row.remark || '' }
      this.editError = ''
      this.editVisible = true
    },
    async submitEdit() {
      if (this.busy || !this.canEditEvents || !this.editForm) return
      if (!this.editForm.startDate) { this.editError = '请先选择日期'; return }
      if (this.editForm.eventType === 'SWAP' && !this.editForm.swapToDate) {
        this.editError = '补课日必须填写「调至日期」'
        return
      }
      this.saving = true
      const body = {
        eventType: this.editForm.eventType,
        startDate: this.editForm.startDate,
        endDate: this.editForm.eventType === 'SWAP' ? null : (this.editForm.endDate || this.editForm.startDate),
        swapToDate: this.editForm.eventType === 'SWAP' ? this.editForm.swapToDate : null,
        remark: this.editForm.remark || ''
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
      if (this.busy || !this.canEditEvents) return
      this.pendingDelete = row
      this.confirmVisible = true
    },
    async doDelete() {
      if (this.busy || !this.canEditEvents || !this.pendingDelete) return
      this.deleting = true
      const res = await academicAffairsApi.deleteCalendarEvent(this.termId, this.pendingDelete.eventId)
      if (res.code === 0) {
        toast.success('已删除')
        this.loadEvents()
      } else {
        toast.error(res.message || '删除失败')
      }
      this.pendingDelete = null
      this.confirmVisible = false
      this.deleting = false
    },
    async loadWeekCalendar() {
      const version = ++this.weekRequestVersion
      if (!this.termId) return
      this.weekLoading = true
      this.weekError = ''
      const res = await academicAffairsApi.getWeekCalendar(this.termId)
      if (version !== this.weekRequestVersion) return
      if (res.code === 0) {
        this.weekData = res.data
      } else {
        this.weekError = res.message
        this.weekData = null
      }
      this.weekLoading = false
    },
    async doPublish() {
      if (this.busy || !this.canPublish) {
        if (!this.canPublish) toast.warning(this.currentError || '当前学期或权限条件不支持发布，请刷新核对')
        return
      }
      this.publishing = true
      const res = await academicAffairsApi.publishCalendar(this.termId)
      this.publishing = false
      if (res.code === 0) {
        toast.success('校历已发布')
        this.publishVisible = false
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
@import '../styles/foundation-workspace.css';
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
.aa-calendar-copy > summary { cursor: pointer; width: fit-content; padding: 6px 0; color: var(--pri); font-size: 13px; }
.aa-calendar-copy[open] > summary { margin-bottom: 10px; }
.aa-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aa-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; margin: 0; padding: 0; border: 0; min-width: 0; }
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
