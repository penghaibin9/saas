<template>
  <ModulePageShell title="指导巡访" subtitle="记录学生指导与企业沟通，跟进巡访和问题整改。"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppPermissionButton v-if="tab === 'guidance' || tab === 'visit'" :code="tab === 'visit' ? 'internship.visit.manage' : 'internship.guidance.manage'" :allowed="canBtn(tab === 'visit' ? 'internship.visit.manage' : 'internship.guidance.manage')" variant="primary" @click="goCreate">新增{{ tab === 'guidance' ? '指导' : '巡访' }}记录</AppPermissionButton>
      <AppPermissionButton v-else-if="tab === 'communication'" code="internship.communication.manage" :allowed="canBtn('internship.communication.manage')" variant="primary" @click="goCreate">登记沟通</AppPermissionButton>
      <AppPermissionButton v-else-if="tab === 'visit-plan'" code="internship.visit.plan.manage" :allowed="canBtn('internship.visit.plan.manage')" variant="primary" @click="goCreate">新建巡访计划</AppPermissionButton>
      <AppButton variant="ghost" @click="goGuidancePlan">指导计划</AppButton>
      <AppExportButton v-if="canExportTab" :export-fn="exportFn" @exported="onExported">导出 Excel 台账</AppExportButton>
    </template>

    <div class="mp-stack">
      <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />

      <ModuleSummaryStrip v-if="summaryMetrics.length" :metrics="summaryMetrics" />
      <div v-if="statsError" class="state is-err" role="alert">{{ statsError }} <button type="button" class="mp-link" @click="loadStats">重试统计</button></div>

      <div class="tabs">
        <button v-for="t in tabs" :key="t.key" type="button" class="tabs__btn" :class="{ 'is-active': tab === t.key }" @click="switchTab(t.key)">{{ t.label }}</button>
      </div>

      <div v-if="tab === 'guidance' || tab === 'visit'" class="bar">
        <AppSearchBox v-if="tab === 'guidance' || tab === 'visit'" v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
        <AppQuickFilterChips v-if="tab === 'visit'" v-model="rectifyFilter" :options="rectifyOptions" allow-clear @change="reload" />
      </div>

      <DualPaneWorkspace :aside-title="activeTabLabel" :aside-count="total">
        <!-- 左栏：记录队列（紧凑列表，连续处理） -->
        <template #aside>
          <div v-if="loading" class="state">加载中…</div>
          <div v-else-if="error" class="state is-err">{{ error }} <button type="button" class="mp-link" @click="load">重试</button></div>
          <div v-else-if="!rows.length" class="state">当前筛选下暂无记录</div>
          <ul v-else class="gv-list">
            <li v-for="r in rows" :key="r.id">
              <button type="button" class="gv-item" :class="{ 'is-active': String(r.id) === selectedId }" @click="select(r.id)">
                <div class="gv-item__row">
                  <span class="gv-item__name">{{ recordTitle(r) }}</span>
                  <template v-if="tab === 'guidance'">
                    <AppStatusTag v-if="r.toRisk" type="danger">已转风险</AppStatusTag>
                  </template>
                  <AppStatusTag v-else-if="tab === 'visit'" :type="rectifyTone(r.rectifyStatus)">{{ r.rectifyStatusLabel }}</AppStatusTag>
                  <AppStatusTag v-else-if="tab === 'visit-plan'">{{ r.statusLabel }}</AppStatusTag>
                </div>
                <div class="gv-item__sub">{{ recordMeta(r) }}</div>
                <div v-if="tab === 'guidance'" class="gv-item__sub">{{ [r.methodLabel, r.topic, r.createdAt].filter(Boolean).join(' · ') }}</div>
                <div v-else-if="tab === 'visit'" class="gv-item__sub">{{ [r.methodLabel, r.visitAt].filter(Boolean).join(' · ') }}</div>
              </button>
            </li>
          </ul>
        </template>
        <template #aside-foot>
          <AppPagination v-model:page="page" :page-size="pageSize" :total="total"
                        :show-total="false" :show-size-changer="false" :disabled="loading" @change="load" />
        </template>

        <!-- 右栏：当前记录详情（原详情弹窗内容 + 附件 + 审计 + 操作） -->
        <section class="mp-card gv-main">
          <template v-if="!selectedId">
            <EmptyState title="从左侧选择一条记录查看详情"
              :description="`选择${activeTabLabel}后，可在此查看内容与可用操作。`"><template #actions><AppButton variant="ghost" :disabled="loading" @click="load">刷新列表</AppButton></template></EmptyState>
          </template>
          <div v-else-if="detail.loading" class="state gv-main__state">详情加载中…</div>
          <div v-else-if="detail.error" class="state is-err gv-main__state">
            {{ detail.error }} <button type="button" class="mp-link" @click="loadDetail(selectedId)">重试</button>
          </div>
          <template v-else-if="detail.data">
            <div class="gv-main__body">
              <div class="gv-head">
                <span class="gv-head__name">{{ recordTitle(detail.data) }}</span>
                <AppStatusTag v-if="tab === 'guidance' && detail.data.toRisk" type="danger">已转风险</AppStatusTag>
                <AppStatusTag v-else-if="tab === 'visit' && detail.data.rectifyStatus" :type="rectifyTone(detail.data.rectifyStatus)">{{ detail.data.rectifyStatusLabel }}</AppStatusTag>
              </div>

              <div class="sec-t">{{ activeTabLabel }}详情</div>
              <AppDescriptionList :items="detailItems" :columns="2" />

              <template v-if="detail.data.attachment">
                <div class="sec-t">附件</div>
                <AppFilePreview :files="attachmentFiles" @download="downloadAtt" />
              </template>

              <div class="sec-t">操作留痕</div>
              <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无记录" />
            </div>

            <div v-if="tab === 'guidance' || detail.data.rectifyStatus === 'PENDING' || planActions.length" class="gv-foot">
              <AppPermissionButton v-if="tab === 'guidance'" code="internship.guidance.manage" :allowed="canBtn('internship.guidance.manage')" variant="ghost" :danger="true"
                @click="openVoid(detail.data)">撤销</AppPermissionButton>
              <AppPermissionButton v-if="tab === 'visit' && detail.data.rectifyStatus === 'PENDING'" code="internship.visit.manage" :allowed="canBtn('internship.visit.manage')" variant="secondary"
                @click="openRectify(detail.data)">整改跟进</AppPermissionButton>
              <!-- 巡访计划状态迁移：后端 transition 早就做好了并发保护，但此前前端没有任何入口，
                   计划建出来就只能停在草稿。 -->
              <AppPermissionButton v-for="a in planActions" :key="a.action" code="internship.visit.plan.manage"
                :allowed="canBtn('internship.visit.plan.manage')" :variant="a.variant" :danger="a.danger"
                @click="openPlanAction(a)">{{ a.label }}</AppPermissionButton>
            </div>
          </template>
        </section>
      </DualPaneWorkspace>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      :reason-label="cd.reasonLabel" :submitting="cd.submitting" :confirm-disabled="conflict.active" @confirm="onConfirm">
      <AppInlineAlert v-if="conflict.active" type="warning" title="记录已更新，本次操作已暂停"
        description="已保留填写内容。请取消后核对记录最新状态，再重新选择可用操作。">
        <p v-if="conflict.stale">最新详情加载失败，请关闭确认框后重试加载。</p>
        <AppDescriptionList v-else-if="conflict.latest.length" :items="conflict.latest" :columns="1" />
      </AppInlineAlert>
    </AppConfirmDialog>

    <AppDrawer :visible="commDlg.visible" title="登记企业沟通" mode="modal" size="large" @update:visible="!commDlg.submitting && (commDlg.visible = $event)">
      <p class="gv-form-hint">登记与当前批次学生相关的沟通，保存后查看记录详情。</p>
      <fieldset class="gv-form-fields" :disabled="commDlg.submitting">
      <AppFormItem label="企业" required>
        <AppInternshipEnterprisePicker v-model="commForm.enterpriseId" placeholder="按企业名称搜索" />
      </AppFormItem>
      <AppFormItem label="实习学生" required>
        <AppInternshipStudentPicker v-model="commForm.internshipId" :key="batchStore.selectedBatchId" :query="{ batchId: batchStore.selectedBatchId }" placeholder="按姓名 / 学号搜索"
          data-scope-hint="指导教师仅本人指导学生；管理员按数据范围" />
      </AppFormItem>
      <AppFormItem label="沟通方式">
        <AppSelect v-model="commForm.communicationType" :options="commTypeOptions" />
      </AppFormItem>
      <AppFormItem label="联系人"><AppTextInput v-model="commForm.contactName" placeholder="选填：本次沟通联系人" /></AppFormItem>
      <AppFormItem label="沟通摘要" required>
        <AppTextarea v-model="commForm.summary" placeholder="不少于 2 字，写清沟通事项与结论" :maxlength="500" />
      </AppFormItem>
      <AppFormItem label="沟通结果"><AppTextarea v-model="commForm.result" :rows="2" placeholder="选填：已达成的结论或后续安排" /></AppFormItem>
      </fieldset>
      <p v-if="commDlg.error" role="alert" class="gv-form-error">{{ commDlg.error }}</p>
      <template #footer>
        <AppButton variant="text" :disabled="commDlg.submitting" @click="commDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="commDlg.submitting" @click="submitCommunication">保存沟通记录</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="planDlg.visible" title="新建巡访计划" mode="modal" size="large" @update:visible="!planDlg.submitting && (planDlg.visible = $event)">
      <p class="gv-form-hint">先保存为草稿，核对安排后在详情中发布。</p>
      <fieldset class="gv-form-fields" :disabled="planDlg.submitting">
      <AppFormItem label="巡访企业">
        <AppInternshipEnterprisePicker v-model="planForm.enterpriseId" placeholder="按企业名称搜索（可留空）"
          @change="onPlanEnterpriseChange" />
      </AppFormItem>
      <div class="gv-form-grid">
        <AppFormItem label="计划日期"><AppDatePicker v-model="planForm.planDate" /></AppFormItem>
        <AppFormItem label="巡访方式"><AppSelect v-model="planForm.method" :options="planMethodOptions" /></AppFormItem>
      </div>
      <AppFormItem label="巡访地点"><AppTextInput v-model="planForm.location" placeholder="选填：企业地点或线上会议安排" /></AppFormItem>
      <AppFormItem label="巡访目标">
        <AppTextarea v-model="planForm.objective" placeholder="不少于 2 字；与企业至少填一项" :maxlength="500" />
      </AppFormItem>
      </fieldset>
      <p v-if="planDlg.error" role="alert" class="gv-form-error">{{ planDlg.error }}</p>
      <template #footer>
        <AppButton variant="text" :disabled="planDlg.submitting" @click="planDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="planDlg.submitting" @click="submitVisitPlan">保存草稿并查看</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/**
 * 指导巡访管理（双栏工作区）。
 * 左栏 = 指导 / 巡访记录队列（分页 + 搜索 + 整改筛选），右栏 = 选中记录详情 + 附件 + 审计 + 撤销 / 整改跟进。
 * 选中记录写入 query.id，刷新可恢复；新增记录走独立录入页 /admin/internship/guidance/new。
 */
import { ModulePageShell, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppFilePreview, AppPagination,
  AppFormItem, AppSelect, AppTextarea, AppTextInput, AppDatePicker, AppInlineAlert,
  AppInternshipEnterprisePicker, AppInternshipStudentPicker } from '@/components/common'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import ActionReceipt from './components/ActionReceipt.vue'
import { isConflict, captureConflict, emptyConflict } from '@/modules/internship/composables/conflictGuard'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

/* 右栏只渲染详情接口真实返回字段（/internship/guidances/{id}、/internship/visits/{id}） */
const DETAIL = {
  guidance: [
    { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '指导教师' }, { key: 'methodLabel', label: '方式' },
    { key: 'topic', label: '主题' }, { key: 'content', label: '指导内容' }, { key: 'problemType', label: '问题类型' },
    { key: 'suggestion', label: '处理建议' }, { key: 'nextFollowDate', label: '下次跟进' }
  ],
  visit: [
    { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '巡访教师' }, { key: 'enterpriseName', label: '企业' },
    { key: 'methodLabel', label: '方式' }, { key: 'enterpriseFeedback', label: '企业反馈' }, { key: 'studentFeedback', label: '学生反馈' },
    { key: 'safetyIssue', label: '安全隐患' }, { key: 'rectifyRequire', label: '整改要求' }, { key: 'rectifyDeadline', label: '整改截止' },
    { key: 'rectifyStatusLabel', label: '整改状态' }, { key: 'monthlyReport', label: '月度小结' }
  ],
  communication: [
    { key: 'communicationTypeLabel', label: '沟通方式' }, { key: 'contactName', label: '联系人' },
    { key: 'summary', label: '沟通摘要' }, { key: 'result', label: '沟通结果' },
    { key: 'advisorName', label: '记录人' }, { key: 'occurredAt', label: '沟通时间' },
    { key: 'followUpDueAt', label: '跟进截止' }
  ],
  'visit-plan': [
    { key: 'enterpriseName', label: '企业' }, { key: 'ownerName', label: '责任人' }, { key: 'planDate', label: '计划日期' },
    { key: 'method', label: '方式' }, { key: 'objective', label: '目标' }, { key: 'statusLabel', label: '状态' },
    { key: 'location', label: '地点' }, { key: 'studentScope', label: '学生范围' }
  ]
}
const RECTIFY_OPTIONS = [{ label: '整改中', value: 'PENDING' }, { label: '已整改', value: 'DONE' }, { label: '无需整改', value: 'NONE' }]
const PANEL_PRESETS = {
  plan: () => ({ redirect: '/admin/internship/guidance-plan' }),
  'insufficient-warning': () => ({ redirect: '/admin/internship/guidance-plan?insufficient=1' }),
  guidance: () => ({ tab: 'guidance', rectifyFilter: '' }),
  communication: () => ({ tab: 'communication', rectifyFilter: '' }),
  visit: () => ({ tab: 'visit', rectifyFilter: '' }),
  'visit-plan': () => ({ tab: 'visit-plan', rectifyFilter: '' }),
  'visit-issue': () => ({ tab: 'visit', rectifyFilter: 'PENDING' }),
  rectify: () => ({ tab: 'visit', rectifyFilter: 'PENDING' })
}
//: 巡访计划状态迁移，与后端 internship_visit_plan_service._TRANSITIONS 逐条对齐。
//: 取消是不可逆的，所以必填原因；发布/开始/完成是正常推进，不该逼老师编字。
const PLAN_ACTIONS = {
  DRAFT: [
    { action: 'PUBLISH', label: '发布计划', variant: 'primary', danger: false, requireReason: false },
    { action: 'CANCEL', label: '取消计划', variant: 'ghost', danger: true, requireReason: true }
  ],
  PUBLISHED: [
    { action: 'START', label: '开始巡访', variant: 'primary', danger: false, requireReason: false },
    { action: 'CANCEL', label: '取消计划', variant: 'ghost', danger: true, requireReason: true }
  ],
  IN_PROGRESS: [
    { action: 'COMPLETE', label: '完成巡访', variant: 'primary', danger: false, requireReason: false },
    { action: 'CANCEL', label: '取消计划', variant: 'ghost', danger: true, requireReason: true }
  ]
}

const VIEW_TAB = { plan: 'visit-plan', record: 'visit', issue: 'visit', communication: 'communication' }
const TAB_PANEL = { guidance: 'guidance', visit: 'visit', communication: 'communication', 'visit-plan': 'visit-plan' }

export default {
  name: 'GuidanceVisitView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, EmptyState, DualPaneWorkspace, ModuleSummaryStrip, AppButton,
    AppDrawer, AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
    AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppFilePreview, AppPagination,
    AppFormItem, AppSelect, AppTextarea, AppTextInput, AppDatePicker,
    AppInternshipEnterprisePicker, AppInternshipStudentPicker, AppInlineAlert, ActionReceipt },
  data() {
    return {
      commDlg: { visible: false, submitting: false, error: '' },
      commForm: { enterpriseId: '', internshipId: '', summary: '', communicationType: 'PHONE', contactName: '', result: '' },
      commTypeOptions: [
        { value: 'PHONE', label: '电话沟通' }, { value: 'ONSITE', label: '实地走访' },
        { value: 'ONLINE', label: '线上会议' }, { value: 'OTHER', label: '其他' }
      ],
      planMethodOptions: [{ value: 'ONSITE', label: '现场巡访' }, { value: 'ONLINE', label: '线上巡访' }, { value: 'PHONE', label: '电话巡访' }],
      planDlg: { visible: false, submitting: false, error: '' },
      planForm: { enterpriseId: '', enterpriseName: '', objective: '', planDate: '', method: 'ONSITE', location: '' },
      tab: 'guidance',
      tabs: [
        { key: 'guidance', label: '指导记录' },
        { key: 'communication', label: '企业沟通' },
        { key: 'visit', label: '教师巡访' },
        { key: 'visit-plan', label: '巡访计划' }
      ],
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      listSequence: 0, statsSequence: 0, statsError: '',
      keyword: '', rectifyFilter: '', rectifyOptions: RECTIFY_OPTIONS,
      selectedId: '',
      detail: { loading: false, error: '', data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', reasonLabel: '说明', requireReason: true, submitting: false },
      conflict: emptyConflict(),
      pending: null,
      lastReceipt: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校',
      guidanceStats: null,
      visitStats: null
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    /** 当前选中的巡访计划还能做哪些状态迁移；非计划页签或终态时为空 */
    planActions() {
      if (this.tab !== 'visit-plan') return []
      const status = this.detail.data && this.detail.data.status
      return (status && PLAN_ACTIONS[status]) || []
    },
    statsCards() {
      if (this.tab === 'guidance' && this.guidanceStats) {
        const g = this.guidanceStats
        return [
          { label: '在岗学生', value: g.studentCount },
          { label: '人均指导次数', value: g.avgCount },
          { label: `不足 ${g.threshold} 次`, value: g.insufficientCount, warn: g.insufficientCount > 0 }
        ]
      }
      if (this.tab === 'visit' && this.visitStats) {
        const v = this.visitStats
        return [
          { label: '巡访记录', value: v.totalVisits },
          { label: '整改中', value: v.pendingRectify, warn: v.pendingRectify > 0 },
          { label: '已整改', value: v.doneRectify }
        ]
      }
      return []
    },
    summaryMetrics() {
      return this.statsCards.slice(0, 5).map((c) => ({ label: c.label, value: c.value }))
    },
    activeTabLabel() { return this.tabs.find((item) => item.key === this.tab)?.label || '指导巡访' },
    canExportTab() { return this.tab === 'guidance' || this.tab === 'visit' },
    detailFields() { return DETAIL[this.tab] || DETAIL.guidance },
    detailItems() { const d = this.detail.data || {}; return this.detailFields.map((f) => ({ label: f.label, value: d[f.key] })) },
    attachmentFiles() { const a = this.detail.data?.attachment; return a ? [{ id: a.fileId, name: a.fileName, sensitive: true }] : [] },
    auditRecords() {
      return (this.detail.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.note || t.detail.reason || ''), at: t.occurredAt
      }))
    }
  },
  beforeUnmount() { this.resetCreateDialogs() },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler() { this.syncPanelFromRoute() }
    },
    '$route.query.view': {
      immediate: true,
      handler() { this.syncPanelFromRoute() }
    },
    '$route.query.keyword': {
      immediate: true,
      handler(kw) {
        if (String(kw || '') !== this.keyword) {
          this.keyword = String(kw || '')
          this.page = 1
          this.load()
        }
      }
    },
    '$route.query.id': {
      immediate: true,
      handler(id) {
        const sid = (id || '').toString()
        if (sid === this.selectedId) return
        this.resetDetail()
        this.selectedId = sid
        if (sid) this.loadDetail(sid)
        else this.detail = { loading: false, error: '', data: null }
      }
    },
    'batchStore.selectedBatchId'() {
      this.resetCreateDialogs()
      this.page = 1
      this.clearSelection()
      this.loadStats()
      this.load()
    }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    /** 打开巡访计划的状态迁移确认框 */
    openPlanAction(a) {
      const d = this.detail.data
      if (!d || this.detail.loading || this.detail.error || this.cd.submitting || !this.canBtn('internship.visit.plan.manage') || !this.planActions.some(item => item.action === a.action)) return
      this.pending = { kind: 'plan-transition', id: this.selectedId, action: a.action,
        expectedVersion: d.version, objectLabel: d.enterpriseName || d.objective || '巡访计划' }
      this.conflict = emptyConflict()
      this.cd = {
        visible: true,
        title: `巡访计划 · ${a.label}`,
        content: `将「${d.enterpriseName || '该企业'}」${d.planDate || ''}的巡访计划「${a.label}」。`,
        danger: a.danger,
        confirmText: a.label,
        requireReason: a.requireReason,
        reasonLabel: a.action === 'CANCEL' ? '取消原因' : '说明（选填）',
        submitting: false
      }
    },
    syncPanelFromRoute() {
      const panel = (this.$route.query.panel || 'guidance').toString()
      const view = (this.$route.query.view || '').toString()
      // navPlan：panel=visit&view=plan|record|issue
      if (panel === 'visit' && VIEW_TAB[view]) {
        this.applyPanel(view === 'plan' ? 'visit-plan' : (view === 'issue' ? 'visit-issue' : 'visit'))
        return
      }
      this.applyPanel(panel)
    },
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.guidance
      const cfg = preset()
      if (cfg.redirect) {
        const [path, queryString] = cfg.redirect.split('?')
        const query = queryString === 'insufficient=1' ? { insufficient: '1' } : {}
        this.$router.replace({ path, query: this.batchStore.withBatchQuery(query) })
        return
      }
      const { tab, rectifyFilter } = cfg
      const changed = this.tab !== tab
      this.tab = tab
      if (changed) {
        this.resetCreateDialogs()
        this.resetDetail()
        this.selectedId = String(this.$route.query.id || '')
        if (this.selectedId) this.loadDetail(this.selectedId)
      }
      if (!this.$route.query.keyword) this.keyword = ''
      this.rectifyFilter = rectifyFilter
      this.page = 1
      this.loadStats()
      this.load()
    },
    recordTitle(row) {
      if (this.tab === 'communication') return row.summary || '企业沟通'
      if (this.tab === 'visit-plan') return row.enterpriseName || row.objective || '巡访计划'
      return row.studentName || '未提供学生姓名'
    },
    recordMeta(row) {
      if (this.tab === 'communication') return [row.communicationTypeLabel, row.contactName, row.advisorName, row.occurredAt].filter(Boolean).join(' · ')
      if (this.tab === 'visit-plan') return [row.ownerName, row.planDate, row.objective].filter(Boolean).join(' · ')
      return [row.studentNo, this.tab === 'guidance' ? row.advisorName : row.enterpriseName].filter(Boolean).join(' · ')
    },
    resetDetail() {
      this.detail = { loading: false, error: '', data: null }
      this.pending = null
      this.cd = { ...this.cd, visible: false, submitting: false }
      this.conflict = emptyConflict()
      this.lastReceipt = null
    },
    async loadStats() {
      const sequence = ++this.statsSequence
      const batchId = this.batchStore.selectedBatchId
      const tab = this.tab
      this.guidanceStats = null
      this.visitStats = null
      this.statsError = ''
      if (!batchId || !['guidance', 'visit'].includes(tab)) return
      const res = tab === 'guidance'
        ? await guidanceVisitApi.getGuidanceStats(2, { batchId })
        : await guidanceVisitApi.getVisitStats({ batchId })
      if (sequence !== this.statsSequence || batchId !== this.batchStore.selectedBatchId || tab !== this.tab) return
      if (res.code !== 0) { this.statsError = res.message || '统计加载失败'; return }
      if (tab === 'guidance') this.guidanceStats = res.data
      else this.visitStats = res.data
    },
    rectifyTone(s) { return s === 'PENDING' ? 'warning' : s === 'DONE' ? 'success' : 'default' },
    exportFn() {
      if (!this.batchStore.selectedBatchId) return Promise.resolve({ code: 1, message: '请先选择批次' })
      if (this.tab === 'guidance') return guidanceVisitApi.exportGuidances({ keyword: this.keyword, batchId: this.batchStore.selectedBatchId })
      if (this.tab === 'visit') return guidanceVisitApi.exportVisits({ keyword: this.keyword, batchId: this.batchStore.selectedBatchId })
      return Promise.reject(new Error('当前页签不支持导出'))
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    goGuidancePlan() { this.$router.push({ path: '/admin/internship/guidance-plan', query: this.batchStore.withBatchQuery() }) },
    onPlanEnterpriseChange(_value, item) {
      // 企业名称随选中项带出：后端建计划时按名称落库，不接受前端随手输的名字
      this.planForm.enterpriseName = item?.label || ''
    },
    async submitCommunication() {
      if (this.commDlg.submitting || !this.canBtn('internship.communication.manage')) return
      const dialog = this.commDlg
      const batchId = this.batchStore.selectedBatchId
      if (!batchId) { dialog.error = '请先选择批次'; return }
      const f = this.commForm
      if (!f.enterpriseId || !f.internshipId) { this.commDlg.error = '请选择企业与实习学生'; return }
      if ((f.summary || '').trim().length < 2) { this.commDlg.error = '沟通摘要不少于 2 字'; return }
      this.commDlg.submitting = true; this.commDlg.error = ''
      const res = await guidanceVisitApi.createCommunication({
        enterpriseId: String(f.enterpriseId),
        internshipId: String(f.internshipId),
        batchId, contactName: f.contactName.trim(), result: f.result.trim(),
        summary: f.summary.trim(),
        communicationType: f.communicationType || 'PHONE'
      })
      if (this.commDlg !== dialog || this.commForm !== f || batchId !== this.batchStore.selectedBatchId) return
      this.commDlg.submitting = false
      if (res.code !== 0) { this.commDlg.error = res.message || '登记失败'; return }
      this.commDlg.visible = false
      this.showCreatedRecord(res.data.id)
      this.lastReceipt = {
        id: res.data?.id, status: res.data?.status, statusLabel: res.data?.statusLabel || '沟通已登记',
        version: res.data?.version, actionLabel: '登记企业沟通',
        objectLabel: res.data?.summary || f.summary.trim(),
        auditText: '沟通记录与创建留痕已同事务提交', nextStep: res.data?.followUpRequired ? '按后续事项继续跟进' : '可继续登记或查看其他协作对象'
      }
      toast.success('沟通已登记'); this.reload()
    },
    async submitVisitPlan() {
      if (this.planDlg.submitting || !this.canBtn('internship.visit.plan.manage')) return
      const dialog = this.planDlg
      const batchId = this.batchStore.selectedBatchId
      if (!batchId) { dialog.error = '请先选择批次'; return }
      const f = this.planForm
      const objective = (f.objective || '').trim()
      const name = (f.enterpriseName || '').trim()
      if (objective.length < 2 && !name) { this.planDlg.error = '请至少选择企业或填写巡访目标'; return }
      this.planDlg.submitting = true; this.planDlg.error = ''
      const res = await guidanceVisitApi.createVisitPlan({
        batchId, enterpriseId: f.enterpriseId ? String(f.enterpriseId) : undefined,
        enterpriseName: name, objective: objective || name,
        planDate: f.planDate || '', method: f.method, location: f.location.trim()
      })
      if (this.planDlg !== dialog || this.planForm !== f || batchId !== this.batchStore.selectedBatchId) return
      this.planDlg.submitting = false
      if (res.code !== 0) { this.planDlg.error = res.message || '创建失败'; return }
      this.planDlg.visible = false
      this.showCreatedRecord(res.data.id)
      this.lastReceipt = {
        id: res.data?.id, status: res.data?.status, statusLabel: res.data?.statusLabel,
        version: res.data?.version, actionLabel: '创建巡访计划',
        objectLabel: res.data?.enterpriseName || res.data?.objective || '巡访计划',
        auditText: '巡访计划与创建留痕已同事务提交', nextStep: '进入计划详情发布并按状态连续推进'
      }
      toast.success('巡访计划已创建'); this.reload()
    },
    resetCreateDialogs() {
      this.commDlg = { visible: false, submitting: false, error: '' }
      this.planDlg = { visible: false, submitting: false, error: '' }
    },
    showCreatedRecord(id) {
      this.resetDetail()
      this.selectedId = String(id)
      const query = this.batchStore.withBatchQuery({ ...this.$route.query, id: this.selectedId })
      delete query.receipt
      this.$router.replace({ query })
      this.loadDetail(this.selectedId)
    },
    goCreate() {
      if (this.commDlg.submitting || this.planDlg.submitting) return
      if (this.tab === 'communication') {
        if (!this.batchStore.selectedBatchId) return toast.error('请先选择实习批次')
        this.commForm = { enterpriseId: '', internshipId: '', summary: '', communicationType: 'PHONE', contactName: '', result: '' }
        this.commDlg = { visible: true, submitting: false, error: '' }
        return
      }
      if (this.tab === 'visit-plan') {
        if (!this.batchStore.selectedBatchId) return toast.error('请先选择实习批次')
        this.planForm = { enterpriseId: '', enterpriseName: '', objective: '', planDate: '', method: 'ONSITE', location: '' }
        this.planDlg = { visible: true, submitting: false, error: '' }
        return
      }
      this.$router.push({ path: '/admin/internship/guidance/new', query: this.batchStore.withBatchQuery({ type: this.tab }) })
    },
    switchTab(k) {
      const panel = TAB_PANEL[k] || k
      const query = { ...this.$route.query, panel }
      delete query.id
      if (this.$route.query.panel !== panel) {
        this.$router.replace({ path: this.$route.path, query: this.batchStore.withBatchQuery(query) })
      } else if (this.$route.query.id) {
        this.$router.replace({ path: this.$route.path, query: this.batchStore.withBatchQuery(query) })
      } else {
        this.applyPanel(panel)
      }
    },
    reload() { this.page = 1; this.load() },
    async load() {
      const sequence = ++this.listSequence
      const batchId = this.batchStore.selectedBatchId
      const tab = this.tab
      this.rows = []; this.total = 0
      if (!this.batchStore.selectedBatchId) {
        this.loading = false; this.error = '请先选择批次'; this.rows = []; this.total = 0
        return
      }
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword, batchId: this.batchStore.selectedBatchId }
      let res
      if (this.tab === 'guidance') res = await guidanceVisitApi.getGuidances(params)
      else if (this.tab === 'communication') res = await guidanceVisitApi.getCommunications(params)
      else if (this.tab === 'visit-plan') res = await guidanceVisitApi.getVisitPlans(params)
      else { if (this.rectifyFilter) params.rectify = this.rectifyFilter; res = await guidanceVisitApi.getVisits(params) }
      if (sequence !== this.listSequence || batchId !== this.batchStore.selectedBatchId || tab !== this.tab) return
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
      const pc = Math.max(1, Math.ceil(this.total / this.pageSize))
      if (!this.rows.length && this.total > 0 && this.page > pc) { this.page = pc; return this.load() }
    },
    select(id) {
      const sid = String(id)
      if (String(this.$route.query.id || '') === sid) {
        if (this.selectedId !== sid) { this.selectedId = sid; this.loadDetail(sid) }
        return
      }
      this.$router.replace({ query: this.batchStore.withBatchQuery({ ...this.$route.query, id: sid }) })
    },
    clearSelection() {
      this.selectedId = ''
      this.resetDetail()
      const query = { ...this.$route.query }
      delete query.id
      this.$router.replace({ query: this.batchStore.withBatchQuery(query) })
    },
    async loadDetail(id) {
      this.detail = { loading: true, error: '', data: null }
      const workspace = this.detail
      const tab = this.tab
      const batchId = this.batchStore.selectedBatchId
      let res
      if (this.tab === 'guidance') res = await guidanceVisitApi.getGuidanceDetail(id)
      else if (this.tab === 'communication') res = await guidanceVisitApi.getCommunicationDetail(id)
      else if (this.tab === 'visit-plan') res = await guidanceVisitApi.getVisitPlanDetail(id)
      else res = await guidanceVisitApi.getVisitDetail(id)
      if (this.detail !== workspace || tab !== this.tab || batchId !== this.batchStore.selectedBatchId || String(this.selectedId) !== String(id)) return
      this.detail.loading = false
      if (res.code !== 0) { this.detail.error = res.message || '详情加载失败'; return }
      this.detail.data = res.data
      if (this.$route.query.receipt === 'created' && String(this.$route.query.id || '') === String(id)) {
        const d = res.data
        this.lastReceipt = {
          id: d.id, status: d.status || d.rectifyStatus,
          statusLabel: this.tab === 'guidance' ? '指导记录已创建' : '巡访记录已创建',
          version: d.version,
          actionLabel: this.tab === 'guidance' ? '新增指导记录' : '新增巡访记录',
          objectLabel: `${d.studentName || '学生'} · ${this.tab === 'guidance' ? (d.topic || '指导记录') : '教师巡访'}`,
          auditText: '记录与创建留痕已同事务提交',
          nextStep: d.toRisk ? '风险线索已联动，继续进入风险工作台跟进' : d.rectifyStatus === 'PENDING' ? '安全隐患已进入整改队列' : '可继续查看详情或新增下一条记录'
        }
        const query = { ...this.$route.query }
        delete query.receipt
        this.$router.replace({ query: this.batchStore.withBatchQuery(query) })
      }
    },
    async downloadAtt() {
      const a = this.detail.data?.attachment
      if (!a) return
      try { await guidanceVisitApi.downloadAttachment(a.fileId, a.fileName) } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    openVoid(d) {
      if (this.tab !== 'guidance' || !d || this.detail.loading || this.detail.error || this.cd.submitting || !this.canBtn('internship.guidance.manage')) return
      this.conflict = emptyConflict()
      this.pending = { kind: 'void', id: this.selectedId, expectedVersion: d.version,
        objectLabel: `${d.studentName || '学生'} · ${d.topic || '指导记录'}` }
      this.cd = { visible: true, title: '撤销指导记录', content: `撤销「${d.studentName}」的指导记录，撤销原因将写入审计。`,
        danger: true, confirmText: '撤销', reasonLabel: '撤销原因', requireReason: true, submitting: false }
    },
    openRectify(d) {
      if (this.tab !== 'visit' || !d || d.rectifyStatus !== 'PENDING' || this.detail.loading || this.detail.error || this.cd.submitting || !this.canBtn('internship.visit.manage')) return
      this.conflict = emptyConflict()
      this.pending = { kind: 'rectify', id: this.selectedId, expectedVersion: d.version,
        objectLabel: `${d.studentName || '学生'} · 巡访整改` }
      this.cd = { visible: true, title: '巡访整改跟进', content: `将「${d.studentName}」的安全隐患整改标记为「已整改」，跟进说明将写入审计。`,
        danger: false, confirmText: '标记已整改', reasonLabel: '整改跟进说明', requireReason: true, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      if (!p || this.cd.submitting || this.conflict.active || this.detail.loading || this.detail.error) return
      const permission = { void: 'internship.guidance.manage', rectify: 'internship.visit.manage', 'plan-transition': 'internship.visit.plan.manage' }[p.kind]
      if (!permission || !this.canBtn(permission) || String(p.id) !== String(this.selectedId)) return
      const dialog = this.cd
      this.cd.submitting = true
      let res
      if (p.kind === 'plan-transition') {
        res = await guidanceVisitApi.transitionVisitPlan(p.id, p.action, {
          reason: reason || '', expectedVersion: p.expectedVersion
        })
      } else if (p.kind === 'void') {
        res = await guidanceVisitApi.voidGuidance(p.id, { reason, expectedVersion: p.expectedVersion })
      } else {
        res = await guidanceVisitApi.rectifyVisit(p.id, {
          status: 'DONE', note: reason, expectedVersion: p.expectedVersion
        })
      }
      if (this.pending !== p || this.cd !== dialog) return
      this.cd.submitting = false
      if (isConflict(res)) {
        // 先阻止重提，再回读最新详情；原确认单的版本保持不变。
        this.conflict = { ...emptyConflict(), active: true, kept: reason || '' }
        const captured = await captureConflict({
          res,
          kept: reason || '',
          refresh: async () => {
            await this.loadDetail(p.id)
            if (this.detail.error) throw new Error(this.detail.error)
          },
          latest: () => {
            const d = this.detail.data
            if (!d) throw new Error('最新详情未拉回')
            if (this.pending !== p) throw new Error('当前记录已切换')
            return [
              { label: '最新状态', value: d.statusLabel || d.rectifyStatusLabel || d.status || '' },
              { label: '负责人', value: d.ownerName || d.advisorName || '' },
              { label: '取消原因', value: d.cancelReason || '' }
            ]
          }
        })
        if (this.pending === p && this.cd === dialog) this.conflict = captured
        return
      }
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false
      this.conflict = emptyConflict()
      if (p.kind === 'void') this.clearSelection()
      this.lastReceipt = {
        id: res.data?.id, status: res.data?.status || res.data?.rectifyStatus,
        statusLabel: res.data?.statusLabel || res.data?.rectifyStatusLabel || (p.kind === 'void' ? '已撤销' : '操作成功'),
        version: res.data?.version,
        actionLabel: p.kind === 'plan-transition' ? `巡访计划${this.cd.confirmText}` : p.kind === 'void' ? '撤销指导记录' : '完成巡访整改',
        objectLabel: p.objectLabel,
        auditText: '状态更新与操作留痕已同事务提交',
        nextStep: p.kind === 'rectify' ? '整改已闭环，可查看完整审计记录' : '按最新服务端状态继续下一合法动作'
      }
      toast.success('操作成功，已写审计')
      this.loadStats(); this.load()
      if (p.kind !== 'void') this.loadDetail(p.id)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gv-form-fields { border: 0; padding: 0; margin: 0; min-width: 0; }
.gv-form-hint { margin: 0 0 20px; color: var(--text-secondary); font-size: 13px; }
.gv-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
@media (max-width: 600px) { .gv-form-grid { grid-template-columns: 1fr; gap: 0; } }
.gv-form-error { color: var(--danger-600, #d92d20); margin: var(--space-2) 0 0; }


.tabs { display: flex; gap: var(--space-2); border-bottom: 1px solid var(--border-light); }
.tabs__btn { border: none; background: none; padding: var(--space-2) var(--space-3); cursor: pointer; color: var(--text-secondary); font-size: var(--font-size-sm); border-bottom: 2px solid transparent; }
.tabs__btn.is-active { color: var(--primary-700); border-bottom-color: var(--primary-600); font-weight: var(--font-weight-medium); }
.bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); margin: var(--space-3); }
.state.is-err { color: var(--danger-600); }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-4) 0 var(--space-2); }

/* 左栏紧凑列表 */
.gv-list { list-style: none; margin: 0; padding: var(--space-2); display: flex; flex-direction: column; gap: var(--space-1); }
.gv-item { display: block; width: 100%; text-align: left; font: inherit; cursor: pointer; background: transparent; border: 1px solid transparent; border-radius: var(--radius-md, 8px); padding: var(--space-2) var(--space-3); transition: background 0.12s ease, border-color 0.12s ease; }
.gv-item:hover { background: var(--primary-50, #eff6ff); }
.gv-item.is-active { background: var(--primary-50, #eff6ff); border-color: var(--primary-600, #2563eb); }
.gv-item__row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.gv-item__name { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.gv-item__sub { margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }

/* 右栏详情与固定操作区 */
.gv-main { display: flex; flex-direction: column; min-height: 320px; }
.gv-main__body { flex: 1; padding: var(--space-4); min-width: 0; }
.gv-main__state { margin: var(--space-4); }
.gv-head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.gv-head__name { font-size: var(--font-size-md, 15px); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.gv-foot { position: sticky; bottom: 0; display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); background: var(--bg-card, #fff); border-radius: 0 0 var(--r, 12px) var(--r, 12px); }
</style>
