<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    :title="{ events: '校历管理', holiday: '节假日配置', makeup: '补课日配置', weekCalendar: '教学周日历', publish: '校历发布', archive: '校历归档' }[tab] || '校历管理'"
    :subtitle="tab === 'archive' ? '查看被归档学期采用的校历证据。' : tab === 'publish' ? '先核对日期、节次和调休配对，再正式发布。' : '安排教学、考试、实习与节假日，核对调休日期后统一发布。'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="$route.query.returnToken" :disabled="busy" @click="returnToOrigin">返回原位置</AppButton>
      <AppButton v-if="canEditEvents && ['events', 'holiday', 'makeup'].includes(tab)" variant="primary" :disabled="busy" @click="createVisible = true">{{ addFormTitle }}</AppButton>
      <AppButton v-if="tab === 'publish' && canManageCalendar" variant="primary" :disabled="!canPublish || busy" @click="askPublish">核验并发布校历</AppButton>
    </template>
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
        v-else-if="governanceManaged && tab !== 'archive'"
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

      <EmptyState v-else-if="!selectedTerm" title="请选择学期" description="从上方选择需要办理的正式学期；未解析当前学期时不会自动选中其他对象。" />
      <template v-else>
        <nav class="aa-tabs">
          <button v-for="t in tabs" :key="t.key" class="aa-tab" :class="{ 'is-active': tab === t.key }" :aria-current="tab === t.key ? 'page' : undefined" :disabled="busy"
                  @click="switchTab(t.key)">{{ t.label }}</button>
        </nav>

        <template v-if="['events', 'holiday', 'makeup'].includes(tab)">
          <AppInlineAlert v-if="selectedTerm && isLocked" type="warning"
                          description="所选学期已发布，校历事件保持锁定。如需调整，请联系教务处核对学校的变更流程。" />

          <AaCalendarMonth v-if="['events', 'makeup'].includes(tab)" :term="selectedTerm" :title="tab === 'makeup' ? '补课日与被替代教学日' : '校历管理'" :events="filteredEvents" :loading="eventsLoading" :error="error"
            :can-create="canEditEvents && !busy" :authority-hint="currentContext?.switchHint || currentError || '当前学期由学校管理方式决定，请先核对启用方式。'"
            @retry="loadEvents" @create="createVisible = true" />

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

          <AppDrawer v-if="canEditEvents" :visible="createVisible" :title="addFormTitle" mode="modal" size="medium" @close="createVisible = false">
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
          </AppDrawer>

          <AppSectionCard :title="listTitle">
            <ErrorState v-if="error" :description="error" @retry="loadEvents" />
            <LoadingState v-else-if="eventsLoading" />
            <EmptyState v-else-if="!filteredEvents.length" :title="emptyTitle" :description="emptyDesc" />
            <DataTable v-else :columns="eventColumns" :rows="filteredEvents" row-key="eventId">
              <template #cell-originalWeekday="{ row }">{{ weekdayLabel(row.startDate) }}</template>
              <template #cell-makeupWeekday="{ row }">{{ weekdayLabel(row.swapToDate) }}</template>
              <template #cell-pairStatus="{ row }">{{ row.startDate && row.swapToDate ? '已成对登记' : '配对待补齐' }}</template>
              <template #cell-remark="{ row }"><strong>{{ row.remark || EVENT_TYPES[row.eventType] || '校历事件' }}</strong><small class="aa-event-id">事件 {{ row.eventId }}</small></template>
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
          <AaCalendarMonth :term="selectedTerm" :weeks="weekData?.weeks || []" week-mode title="教学周日历" :loading="weekLoading" :error="weekError" @retry="loadWeekCalendar" />
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
          <section class="aa-publish-object" aria-label="当前发布对象">
            <div><strong>{{ termLabel(selectedTerm) }}</strong><p>校历 · 学期 {{ termId }} · {{ statusLabel(selectedTerm.status) }}</p><small>来源：学期定义与本学期正式校历事件</small></div>
            <div><small>当前责任岗位</small><strong>校历管理岗</strong></div>
            <div><small>发布后下一责任</small><strong>开课与排课责任岗读取正式时间底座</strong></div>
          </section>
          <ol class="aa-publish-stages" aria-label="校历办理阶段">
            <li v-for="(stage, index) in ['学期定义', '编制校历', '校验发布', '教学任务']" :key="stage" :aria-current="index === 2 ? 'step' : undefined">
              <span>{{ index + 1 }}</span><div><strong>{{ stage }}</strong><small>{{ index === 2 ? '当前办理环节' : index === 3 ? '发布后进入责任工作区' : '查看正式来源' }}</small></div>
            </li>
          </ol>
          <div class="aa-publish-layout">
            <aside class="aa-publish-queue" aria-label="学期队列">
              <h2>学期队列</h2><p>按学期核对发布状态</p>
              <div class="aa-publish-queue__items">
                <button v-for="term in terms" :key="term.termId" :aria-current="String(term.termId) === String(termId) ? 'true' : undefined" :disabled="busy" @click="selectPublishTerm(term)">
                  <strong>{{ termLabel(term) }}</strong><small>学期 {{ term.termId }}</small><StatusTag :status="term.status" />
                </button>
              </div>
            </aside>
            <div class="mp-stack">
              <AppSectionCard title="当前对象 · 发布核验依据">
                <div class="aa-publish-refresh"><span>正式提交时由服务端再次核验</span><AppButton :disabled="busy || publishLoading" :loading="publishLoading" @click="loadPublishEvidence">刷新核验依据</AppButton></div>
                <LoadingState v-if="publishLoading" />
                <ErrorState v-else-if="publishReadError" :description="publishReadError" @retry="loadPublishEvidence" />
                <div v-else class="aa-publish-evidence">
                  <section v-for="check in publishChecks" :key="check.title" :class="{ 'is-blocked': !check.ready && !check.readOnly }">
                    <div><strong>{{ check.title }}</strong><StatusTag :type="check.readOnly ? 'default' : check.ready ? 'success' : 'warning'" :label="check.readOnly ? '只读状态' : check.ready ? '已读取 · 符合条件' : '待处理'" /></div>
                    <p>{{ check.description }}</p><small>读取于 {{ publishEvidence?.readAt || '尚未读取' }}</small>
                    <button v-if="check.path && hasPermission(check.permission)" class="mp-link" :disabled="busy" @click="openPublishSource(check.path, check.tab)">查看正式来源</button>
                  </section>
                </div>
              </AppSectionCard>
              <AppSectionCard title="本岗位办理">
                <p class="aa-publish-target">办理对象：<strong>{{ termLabel(selectedTerm) }}</strong> · 学期 {{ termId }}</p>
                <p class="mp-note">{{ canManageCalendar ? '当前身份具备校历发布权限及全校范围；请核对以上依据后办理。' : '当前身份没有全校校历发布权限，可查看已授权的来源。' }}</p>
                <p class="mp-note">{{ publishImpact }}</p>
                <AppInlineAlert v-if="publishBlockers.length" type="warning" :description="publishBlockers.join('；')" />
                <AppInlineAlert v-else-if="isLocked && !activePublishReceipt" type="info" :description="`本学期${statusLabel(selectedTerm.status)}，不能重复发布；可核对正式来源与状态记录。`" />
                <AppInlineAlert v-if="activePublishReceipt" :type="activePublishReceipt.kind === 'COMMITTED' ? 'success' : activePublishReceipt.kind === 'REJECTED' ? 'danger' : 'warning'" :description="activePublishReceipt.message" />
                <div class="aa-publish-actions">
                  <AppButton v-if="canManageCalendar" variant="primary" :disabled="!canPublish || busy" :loading="publishing" @click="askPublish">核验并发布校历</AppButton>
                  <AppButton v-if="hasPermission('academicAffairs.calendar.view')" :disabled="busy" @click="switchTab('events')">返回本学期校历</AppButton>
                </div>
                <p class="mp-note">发布成功后，校历事件锁定；下一责任岗位读取正式校历继续开课与排课。具体经办人以相应业务任务的正式分派为准。</p>
              </AppSectionCard>
            </div>
          </div>
        </template>

        <template v-else-if="tab === 'archive'">
          <AaCalendarArchivePanel :term="selectedTerm" :ctx="ctx" />
        </template>
      </template>
      <nav v-if="selectedTerm" class="aa-calendar-related" aria-label="关联办理">
        <span>关联办理</span>
        <AppButton v-if="hasPermission('academicAffairs.term.view')" :disabled="busy" @click="openRelated('/admin/academic-affairs/terms')">学期管理</AppButton>
        <AppButton v-if="hasPermission('academicAffairs.timeslot.view')" :disabled="busy" @click="openRelated('/admin/academic-affairs/time-slots')">作息时间</AppButton>
        <AppButton :disabled="busy" @click="switchTab('events')">校历管理</AppButton>
        <AppButton v-if="canManageCalendar" :disabled="busy" @click="switchTab('publish')">校历发布</AppButton>
      </nav>
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
                      :message="pendingPublish ? `确认发布「${pendingPublish.label}」（学期 ${pendingPublish.termId}）？${pendingPublish.impact}` : ''"
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
import AaCalendarMonth from '@/modules/academicAffairs/components/AaCalendarMonth.vue'
import AaCalendarArchivePanel from '@/modules/academicAffairs/components/AaCalendarArchivePanel.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicAffairsTermDetailApi } from '@/modules/academicAffairs/api/academic-affairs-term-detail.api'
import { loadAcademicTermCatalog } from '@/modules/academicAffairs/pickerAdapters'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'
import { currentUserFromToken } from '@/services/http/client'

const EVENT_TYPES = { TEACHING: '教学', EXAM: '考试', INTERNSHIP: '实习', HOLIDAY: '节假日', SWAP: '补课日' }
const TYPE_COLOR = { TEACHING: 'primary', EXAM: 'danger', INTERNSHIP: 'warning', HOLIDAY: 'success', SWAP: 'default' }
const WEEK_TYPES = { TEACHING: '教学周', EXAM: '考试周', HOLIDAY: '假期周', INTERNSHIP: '实习周' }
const WEEK_TYPE_COLOR = { TEACHING: 'default', EXAM: 'danger', HOLIDAY: 'success', INTERNSHIP: 'warning' }
const MGMT_ROLES = ['ACADEMIC_ADMIN', 'SCHOOL_ADMIN', 'PLATFORM_SUPER_ADMIN']
const TAB_EVENT_TYPE = { events: '', holiday: 'HOLIDAY', makeup: 'SWAP' }

// Same-tab recovery only; this records uncertainty, never substitutes for a server receipt.
function calendarReceiptStorageKey() {
  const user = currentUserFromToken()
  return user?.tenantId && user?.userId ? `aa.calendar.publish.${user.tenantId}.${user.userId}` : ''
}
function readCalendarReceipts(key) {
  try {
    const receipts = key ? JSON.parse(sessionStorage.getItem(key) || '{}') : {}
    return receipts && typeof receipts === 'object' && !Array.isArray(receipts) ? receipts : {}
  } catch { return {} }
}

export default {
  name: 'AaCalendarView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppSectionCard, AppSelect, AppTextInput, AppFormItem, AppDatePicker, AppTermEntityPicker,
    AppConfirmDialog, AppInlineAlert, AaCalendarCopyPanel, AaCalendarMonth, AaCalendarArchivePanel
  },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    const publishReceiptStorageKey = calendarReceiptStorageKey()
    return {
      EVENT_TYPES, WEEK_TYPES,
      eventTypeOptions: Object.entries(EVENT_TYPES).map(([value, label]) => ({ value, label })),
      termsLoading: true,
      catalogError: '', currentLoading: true,
      eventRequestVersion: 0, weekRequestVersion: 0, currentRequestVersion: 0,
      publishReviewVersion: 0, publishLoading: false, publishReadError: '', publishEvidence: null,
      pendingPublish: null, publishReceiptStorageKey, publishReceipts: readCalendarReceipts(publishReceiptStorageKey),
      copying: false, deleting: false, publishVisible: false, createVisible: false, disposed: false, catalogVersion: 0,
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
    contextKey() { return JSON.stringify([this.ctx.currentRole, this.ctx.dataScope, this.ctx.permissionPatterns]) },
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
      if (this.publishLoading || this.publishReadError || !this.publishEvidence || ['COMMITTED', 'UNKNOWN'].includes(this.activePublishReceipt?.kind)) return false
      if (!this.publishChecks.every(check => check.ready)) return false
      if (this.governanceManaged) return this.isSelectedResolvedCurrent
      return this.currentContext?.canDirectSwitch === true
    },
    activePublishReceipt() { return this.publishReceipts[String(this.termId)] || null },
    publishImpact() {
      if (this.isLocked) return '本学期校历事件已锁定，当前学期仍以学校的正式启用结论为准。'
      if (this.currentLoading || this.currentError || !this.currentContext) return '当前学期的启用方式尚未确认，暂不能发布。'
      return this.governanceManaged ? '发布后校历事件将锁定，全校当前学期保持学校的统一设置。' : '发布后校历事件将锁定，并将所选学期设为当前学期。'
    },
    publishChecks() {
      const evidence = this.publishEvidence
      if (!evidence) return []
      const term = evidence.term, swaps = evidence.events.filter(event => event.eventType === 'SWAP')
      const unpaired = swaps.filter(event => !event.swapToDate)
      const slots = evidence.slots.filter(slot => slot.status === 'ENABLED')
      const authorityReady = !this.currentError && !this.currentLoading && (this.governanceManaged ? this.isSelectedResolvedCurrent : this.currentContext?.canDirectSwitch === true)
      return [
        { title: '来源对象与版本', ready: String(term.termId) === String(this.termId), description: `学期 ${term.termId} · ${this.calendarDate(term.startDate)} 至 ${this.calendarDate(term.endDate)} · 版本 ${term.version ?? '未提供'}`, path: `/admin/academic-affairs/terms/${term.termId}`, permission: 'academicAffairs.term.view' },
        { title: '正式节次', ready: slots.length > 0, description: `全校已启用 ${slots.length} 个节次。发布要求至少一个启用节次；时段与引用影响请在作息时间中核对。`, path: '/admin/academic-affairs/time-slots', permission: 'academicAffairs.timeslot.view' },
        { title: '校历事件与调休配对', ready: !unpaired.length, description: `本学期 ${evidence.events.length} 项事件，调休 ${swaps.length} 项；${unpaired.length ? `未配对 ${unpaired.length} 项，事件 ${unpaired.map(event => event.eventId).join('、')}` : '未发现缺少补课日期的记录'}。`, path: '/admin/academic-affairs/calendar', tab: 'makeup', permission: 'academicAffairs.calendar.view' },
        { title: '全校当前学期', ready: authorityReady, description: this.currentError || (this.governanceManaged ? `学校统一治理，当前学期 ${this.currentContext?.termId || '未解析'}。${this.isSelectedResolvedCurrent ? '所选学期一致。' : '所选学期不一致，请先由学校统一切换。'}` : this.currentContext?.canDirectSwitch === true ? '教务兼容方式：本次发布同时切换当前学期。' : '当前学期尚未解析，不能确认切换方式。'), path: '/admin/academic-affairs/terms/current', permission: 'academicAffairs.term.view' },
        { title: '状态与办理权限', ready: term.status === 'DRAFT' && this.canManageCalendar, readOnly: ['PUBLISHED', 'FROZEN', 'ARCHIVED'].includes(term.status), description: `当前状态：${this.statusLabel(term.status)}。${this.canManageCalendar ? '具备全校校历发布权限。' : '当前身份或范围不支持发布。'}` },
        { title: '证据新鲜度', ready: String(term.termId) === String(this.termId), description: '本次读取学期、事件、节次与当前学期结论。来源不是同一事务快照；提交时服务端重新锁定学期并核验状态、节次和调休配对。' }
      ]
    },
    publishBlockers() { return this.isLocked ? [] : this.publishChecks.filter(check => !check.ready).map(check => check.description) },
    filteredEvents() {
      const t = TAB_EVENT_TYPE[this.tab]
      const rows = t ? this.events.filter((e) => e.eventType === t) : this.events
      return rows.map((e) => ({
        ...e,
        startDate: this.calendarDate(e.startDate), endDateLabel: this.calendarDate(e.endDate || e.startDate), swapToDate: this.calendarDate(e.swapToDate),
        dateLabel: e.eventType === 'SWAP' ? `${this.calendarDate(e.startDate)} → ${this.calendarDate(e.swapToDate)}`
          : e.endDate && e.endDate !== e.startDate ? `${this.calendarDate(e.startDate)} 至 ${this.calendarDate(e.endDate)}` : this.calendarDate(e.startDate)
      }))
    },
    eventColumns() {
      if (this.tab === 'holiday') {
        return [
          { key: 'remark', title: '名称' },
          { key: 'startDate', title: '开始日期' },
          { key: 'endDateLabel', title: '结束日期' },
          { key: 'actions', title: '办理入口' }
        ]
      }
      if (this.tab === 'makeup') {
        return [
          { key: 'startDate', title: '原停课日期' },
          { key: 'swapToDate', title: '调至日期（补课日）' },
          { key: 'originalWeekday', title: '原日星期' },
          { key: 'makeupWeekday', title: '补课日星期' },
          { key: 'pairStatus', title: '配对情况' },
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
      return { events: '校历事件', holiday: '节假日事件 · 台账', makeup: '补课日配对 · 台账' }[this.tab] || '列表'
    },
    emptyTitle() {
      return { events: '本学期暂无校历事件', holiday: '本学期暂无节假日', makeup: '本学期暂无补课日' }[this.tab] || '暂无数据'
    },
    emptyDesc() {
      if (!this.canEditEvents) return '该学期暂未登记此类安排。'
      return { events: '点击「新增校历事件」登记教学、考试或假期安排。', holiday: '点击「新增节假日」登记正式假期日期。', makeup: '点击「新增补课日」成对登记原停课日与调至日期。' }[this.tab] || ''
    }
  },
  created() {
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.resetDraft()
    this.refreshTermCatalog()
  },
  watch: {
    contextKey() {
      this.catalogVersion++; this.currentRequestVersion++; this.eventRequestVersion++; this.weekRequestVersion++
      this.invalidatePublishReview()
      this.publishReceiptStorageKey = calendarReceiptStorageKey()
      this.publishReceipts = readCalendarReceipts(this.publishReceiptStorageKey)
      this.terms = []; this.events = []; this.weekData = null
      this.refreshTermCatalog()
    },
    '$route.query.tab'(key) { this.switchTab(this.tabs.some(t => t.key === key) ? key : 'events') },
    '$route.query.termId'(id) {
      if (!this.busy && String(id || '') !== String(this.termId || '')) {
        if (typeof id !== 'string' || !this.terms.some(t => String(t.termId) === id)) {
          this.invalidatePublishReview()
          this.termId = ''; this.events = []; this.weekData = null
          this.eventRequestVersion++; this.weekRequestVersion++
          this.catalogError = '入口指定的学期不可用，请重新选择学期。'; return
        }
        this.termId = id; this.onTermChange()
      }
    }
  },
  beforeRouteUpdate(to, from, next) { if (this.busy) { toast.warning('正在保存校历，请稍候再切换'); next(false) } else next() },
  beforeUnmount() { this.disposed = true; this.catalogVersion++; this.currentRequestVersion++; this.eventRequestVersion++; this.weekRequestVersion++; this.invalidatePublishReview() },
  methods: {
    weekdayLabel(value) { const day = new Date(`${String(value || '').slice(0, 10)}T00:00:00Z`).getUTCDay(); return ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][day] || '待核对' },
    storePublishReceipt(termId, receipt) {
      this.publishReceipts[termId] = receipt
      try { if (this.publishReceiptStorageKey) sessionStorage.setItem(this.publishReceiptStorageKey, JSON.stringify(this.publishReceipts)) } catch { /* Memory still prevents replay on the current page. */ }
    },
    termLabel(term) { return term?.termName || `${term?.yearCode || '学年待确认'} 第 ${term?.termNo || '—'} 学期` },
    selectPublishTerm(term) {
      if (this.busy || String(term.termId) === String(this.termId)) return
      this.termId = String(term.termId); this.onTermChange()
    },
    openPublishSource(path, tab) {
      const returnToken = this.academicFlow?.captureReturn()
      this.$router.push({ path, query: { ...(tab ? { tab, termId: String(this.termId) } : {}), ...(returnToken ? { returnToken } : {}) } })
    },
    invalidatePublishReview() {
      this.publishReviewVersion++; this.publishEvidence = null; this.publishReadError = ''; this.publishLoading = false
      this.publishVisible = false; this.pendingPublish = null
    },
    returnToOrigin() { this.academicFlow?.back(this.$route.query.returnToken, '/admin/academic-affairs/terms') },
    openRelated(path) { const returnToken = this.academicFlow?.captureReturn(); this.$router.push({ path, query: returnToken ? { returnToken } : {} }) },
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
      const version = ++this.currentRequestVersion, context = this.contextKey
      this.currentLoading = true
      this.currentContext = null
      this.currentError = ''
      const res = await academicAffairsApi.getCurrentTerm()
      if (version !== this.currentRequestVersion || context !== this.contextKey || this.disposed) return
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
      this.invalidatePublishReview()
      this.tab = key
      this.createVisible = false
      this.syncQuery()
      this.resetDraft()
      this.loadForTab()
    },
    async refreshTermCatalog() {
      const version = ++this.catalogVersion
      this.termsLoading = true
      this.catalogError = ''
      try {
        const terms = await loadAcademicTermCatalog()
        if (version !== this.catalogVersion || this.disposed) return
        this.terms = terms
        await this.loadCurrentContext()
        if (version !== this.catalogVersion || this.disposed) return
        const requested = this.termId || this.$route.query.termId
        const selected = typeof requested === 'string' ? this.terms.find((t) => String(t.termId) === requested) : null
        const resolved = this.terms.find((t) => this.isResolvedCurrent(t))
        if (requested && !selected) {
          this.termId = ''; this.events = []; this.weekData = null
          this.catalogError = '入口指定的学期不可用，请重新选择学期。'; this.termsLoading = false; return
        }
        const next = selected || resolved
        if (next) {
          this.termId = next.termId
          this.syncQuery()
          this.loadForTab()
        }
      } catch (error) {
        if (version !== this.catalogVersion || this.disposed) return
        this.catalogError = error.message || '学期数据加载失败'
      }
      this.termsLoading = false
      if (['publish', 'archive'].includes(this.tab)) this.academicFlow?.restorePosition?.()
    },
    onTermChange() {
      this.invalidatePublishReview()
      this.catalogError = ''
      this.createVisible = false
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
      if (this.tab === 'publish') { this.loadPublishEvidence(); return }
      if (this.tab === 'archive') return
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
      this.academicFlow?.restorePosition?.()
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
        this.createVisible = false
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
      this.academicFlow?.restorePosition?.()
    },
    async loadPublishEvidence() {
      if (!this.termId || this.publishing) return
      this.invalidatePublishReview()
      const version = this.publishReviewVersion, termId = String(this.termId), context = this.contextKey
      const currentVersion = ++this.currentRequestVersion
      this.publishLoading = true; this.currentLoading = true
      try {
        const [term, events, slots, current] = await Promise.all([
          academicAffairsTermDetailApi.get(termId), academicAffairsApi.getCalendar(termId),
          academicAffairsApi.getTimeSlots(), academicAffairsApi.getCurrentTerm()
        ])
        if (version !== this.publishReviewVersion || context !== this.contextKey || termId !== String(this.termId) || this.disposed) return
        if (currentVersion === this.currentRequestVersion) {
          this.currentContext = current.code === 0 ? current.data : null
          this.currentError = current.code === 0 ? '' : current.message || '当前学期解析失败'
          this.currentLoading = false
        }
        const sources = [[term, '学期'], [events, '校历事件'], [slots, '作息节次']]
        const failures = sources.filter(([result]) => result.code !== 0).map(([result, label]) => `${label}：${result.message || '读取失败'}`)
        if (failures.length) { this.publishReadError = failures.join('；'); return }
        if (String(term.data?.termId) !== termId || !Array.isArray(events.data) || !Array.isArray(slots.data)) {
          this.publishReadError = '返回的发布依据不完整或与所选学期不一致，请刷新核对。'; return
        }
        this.terms = this.terms.map(row => String(row.termId) === termId ? term.data : row)
        this.publishEvidence = { term: term.data, events: events.data, slots: slots.data, readAt: new Date().toLocaleString('zh-CN', { hour12: false }) }
      } catch (error) {
        if (version === this.publishReviewVersion && !this.disposed) this.publishReadError = error.message || '发布依据读取失败'
      } finally {
        if (version === this.publishReviewVersion && !this.disposed) {
          this.publishLoading = false
          if (currentVersion === this.currentRequestVersion) this.currentLoading = false
          this.academicFlow?.restorePosition?.()
        }
      }
    },
    askPublish() {
      if (this.busy || !this.canPublish) return
      this.pendingPublish = Object.freeze({ termId: String(this.termId), label: this.termLabel(this.selectedTerm),
        context: this.contextKey, reviewVersion: this.publishReviewVersion, impact: this.publishImpact })
      this.publishVisible = true
    },
    async doPublish() {
      const target = this.pendingPublish
      if (this.busy || !this.canPublish || !target || target.context !== this.contextKey || target.termId !== String(this.termId) || target.reviewVersion !== this.publishReviewVersion) return
      this.publishing = true
      this.storePublishReceipt(target.termId, { kind: 'UNKNOWN', message: `学期 ${target.termId} 的发布请求已提交，尚未收到正式回执；请先核对正式状态与操作记录，暂停重复发布。` })
      try {
        const res = await academicAffairsApi.publishCalendar(target.termId)
        if (this.disposed || target.context !== this.contextKey) return
        const prefix = `「${target.label}」（学期 ${target.termId}）：`
        const committed = res.code === 0 && String(res.data?.termId) === target.termId && res.data?.status === 'PUBLISHED'
        const rejected = res.code !== 0 && ['NO_PERMISSION', 'NO_DATA_SCOPE', 'DATA_CONFLICT', 'VALIDATION_ERROR', 'DATA_NOT_FOUND'].includes(res.bizCode)
        this.storePublishReceipt(target.termId, {
          kind: committed ? 'COMMITTED' : rejected ? 'REJECTED' : 'UNKNOWN',
          message: prefix + (committed ? '正式接口已确认校历发布，事件已锁定。请由开课与排课责任岗继续办理。'
            : rejected ? `发布被拒绝，${res.message || '请核对办理条件'}。刷新依据后再处理。`
              : '发布结果尚未确认。请刷新正式状态并核对操作记录，本页暂停重复发布；查询到已发布也不能据此认定是本次请求完成。')
        })
        if (committed) this.terms = this.terms.map(row => String(row.termId) === target.termId ? res.data : row)
      } catch {
        if (!this.disposed && target.context === this.contextKey) this.storePublishReceipt(target.termId, {
          kind: 'UNKNOWN', message: `学期 ${target.termId} 的发布结果尚未确认，请核对正式状态与操作记录；本页暂停重复发布。`
        })
      } finally {
        this.publishing = false
        this.publishVisible = false
        this.pendingPublish = null
        if (!this.disposed && target.context === this.contextKey && target.termId === String(this.termId)) await this.loadPublishEvidence()
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
.mp-link { border: 0; padding: 0; margin-right: 12px; background: transparent; color: var(--pri); font: inherit; cursor: pointer; }
.mp-link:disabled { opacity: .55; cursor: not-allowed; }
.aa-week-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.aa-week-item { display: flex; align-items: center; gap: 14px; padding: 10px 4px; border-bottom: 1px solid var(--border-100, #f0f1f2); flex-wrap: wrap; }
.aa-week-item__no { font-weight: 600; min-width: 64px; }
.aa-week-item__range { color: var(--text-500, #646a73); font-size: 13px; min-width: 180px; }
.aa-week-item__tag { font-size: 12px; color: var(--text-500, #646a73); }
.aa-status-row { display: flex; align-items: center; gap: 10px; margin: 12px 0; font-size: 14px; flex-wrap: wrap; }
.aa-calendar-related { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 16px; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.aa-calendar-related > span, .aa-event-id { font-size: 12px; color: var(--text-secondary); }
.aa-event-id { display: block; margin-top: 5px; }
.aa-publish-object { display: flex; align-items: center; gap: 28px; padding: 18px; border: 1px solid var(--border-base); border-left: 3px solid var(--pri); border-radius: 10px; background: var(--bg-card); }
.aa-publish-object > div:first-child { flex: 1; }
.aa-publish-object strong, .aa-publish-object small { display: block; }
.aa-publish-object strong { font-size: 13px; line-height: 1.6; }
.aa-publish-object > div:first-child > strong { font-size: 16px; }
.aa-publish-object p, .aa-publish-object small { color: var(--text-secondary); font-size: 12px; margin: 5px 0; }
.aa-publish-stages { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); list-style: none; margin: 0; padding: 18px; gap: 18px; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.aa-publish-stages li { display: flex; gap: 8px; font-size: 12px; }
.aa-publish-stages li > span { display: grid; place-items: center; flex-shrink: 0; width: 24px; height: 24px; border-radius: 50%; border: 1px solid var(--border-base); }
.aa-publish-stages li[aria-current] > span { background: var(--pri); color: white; }
.aa-publish-stages li[aria-current] strong { color: var(--pri); }
.aa-publish-stages small { display: block; color: var(--text-secondary); line-height: 1.6; margin-top: 8px; }
.aa-publish-layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); align-items: start; gap: 16px; }
.aa-publish-queue { border: 1px solid var(--border-base); border-radius: 10px; overflow: hidden; background: var(--bg-card); }
.aa-publish-queue h2 { font-size: 14px; margin: 16px 14px 6px; }
.aa-publish-queue > p { color: var(--text-secondary); font-size: 12px; margin: 0 14px 14px; }
.aa-publish-queue__items { max-height: 560px; overflow-y: auto; }
.aa-publish-queue button { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; width: 100%; padding: 16px 12px; border: 0; border-top: 1px solid var(--border-base); border-left: 3px solid transparent; background: transparent; color: inherit; text-align: left; cursor: pointer; }
.aa-publish-queue button[aria-current] { border-left-color: var(--pri); background: var(--primary-50, #eef4ff); }
.aa-publish-queue button:disabled { cursor: not-allowed; opacity: .6; }
.aa-publish-queue small { color: var(--text-secondary); }
.aa-publish-refresh, .aa-publish-evidence section > div { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.aa-publish-refresh { margin-bottom: 16px; font-size: 12px; color: var(--text-secondary); }
.aa-publish-evidence { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.aa-publish-evidence section { padding: 14px; border: 1px solid var(--border-base); border-radius: 8px; min-width: 0; }
.aa-publish-evidence section.is-blocked { border-color: var(--warning-300, #f5d08c); background: var(--warning-50, #fffcf5); }
.aa-publish-evidence strong { font-size: 13px; }
.aa-publish-evidence p { margin: 12px 0 8px; font-size: 12px; line-height: 1.8; color: var(--text-secondary); overflow-wrap: anywhere; }
.aa-publish-evidence small { display: block; font-size: 11px; color: var(--text-secondary); }
.aa-publish-evidence .mp-link { margin-top: 12px; font-size: 12px; }
.aa-publish-target { font-size: 13px; margin: 0 0 12px; }
.aa-publish-actions { display: flex; gap: 10px; flex-wrap: wrap; margin: 16px 0; }
@media (max-width: 1100px) { .aa-publish-layout { grid-template-columns: 210px minmax(0, 1fr); } .aa-publish-object { flex-wrap: wrap; } }
@media (max-width: 760px) { .aa-publish-layout, .aa-publish-evidence { grid-template-columns: minmax(0, 1fr); } .aa-publish-stages { grid-template-columns: repeat(2, minmax(0, 1fr)); } .aa-publish-queue__items { max-height: 220px; } }
</style>
