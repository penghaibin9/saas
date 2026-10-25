<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    title="当前学期"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <LoadingState v-if="loadingCurrent" />
      <ErrorState v-else-if="currentError" :description="currentError" @retry="loadCurrent" />
      <EmptyState
        v-else-if="!current || !current.termId"
        title="尚未设置当前学期"
        :description="current?.switchHint || '请先在「学年学期」发布一个学期'"
      >
        <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/terms')">前往学年学期</AppButton>
      </EmptyState>
      <div v-else class="aa-current-card">
        <div class="aa-current-card__title">{{ current.yearCode }} 第 {{ current.termNo }} 学期</div>
        <AppStatusTag type="success" dot>当前学期</AppStatusTag>
        <span v-if="current.startDate && current.endDate" class="aa-current-card__meta">{{ dateText(current.startDate) }} 至 {{ dateText(current.endDate) }}</span>
        <span v-if="current.teachingWeeks" class="aa-current-card__meta">教学周 {{ current.teachingWeeks }} 周</span>
        <AppStatusTag :type="statusType(current.status)" dot>{{ statusLabel(current.status) }}</AppStatusTag>
      </div>

      <div v-if="governanceManaged" class="aa-authority-card">
        <div>
          <strong>全校统一治理已启用</strong>
          <p>学期切换由学校治理入口统一办理。</p>
        </div>
        <AppButton v-if="canViewGovernance" variant="primary" @click="goGovernance">前往学年学期与业务日历</AppButton>
      </div>

      <AppSectionCard v-else-if="!loadingCurrent && !currentError" title="已发布学期" subtitle="仅已发布学期可设为当前；冻结学期需先解冻，已归档学期只读。">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!candidates.length" title="暂无已发布学期" />
        <ul v-else class="aa-current-list">
          <li v-for="t in candidates" :key="t.termId" class="aa-current-item">
            <div class="aa-current-item__main">
              <button type="button" class="mp-link" @click="openTerm(t)">{{ t.yearCode }} 第 {{ t.termNo }} 学期</button>
              <AppStatusTag v-if="isResolvedCurrent(t)" type="success" dot>当前学期</AppStatusTag>
            </div>
            <AppButton
              v-if="!isResolvedCurrent(t) && directSwitchAllowed"
              size="small"
              variant="primary"
              :loading="switching === t.termId"
              @click="askSwitch(t)"
            >设为当前</AppButton>
            <span v-else-if="!isResolvedCurrent(t) && governanceManaged" class="aa-current-item__managed">统一治理切换</span>
          </li>
        </ul>
      </AppSectionCard>

      <AppSectionCard v-if="current && current.termId" title="操作说明与最近切换记录" collapsible default-collapsed compact>
        <dl class="aa-current-facts">
          <div><dt>最近切换</dt><dd>{{ latestActivation ? `${formatTime(latestActivation.occurredAt)} · ${latestActivation.operator || '系统'}` : '暂无切换记录' }}</dd></div>
        </dl>
        <ul class="aa-current-rules">
          <li v-if="governanceManaged">发布学期不会自动成为当前学期，需在学校治理入口启用。</li>
          <li>冻结的学期可按原因解冻；已归档的学期只能走纠错流程，不能直接解冻。</li>
        </ul>
      </AppSectionCard>
    </div>

    <AppConfirmDialog
      v-model:visible="dialog.visible"
      title="切换当前学期"
      :message="dialog.message"
      type="primary"
      confirm-text="确认切换"
      :submitting="dialog.submitting"
      @confirm="doSwitch"
    />
  </ModulePageShell>
</template>

<script>
/** 当前学期（/admin/academic-affairs/terms/current）：GET /terms/current。
 * A-C1：SYS-12 已 ACTIVE 时这里只展示统一治理结论；未启用治理的历史学校才保留
 * POST /terms/{id}/set-current 兼容入口。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag, AppConfirmDialog } from '@/components/common'
import { AppButton } from '@/components/ui'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'

const STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '已发布', FROZEN: '已冻结', ARCHIVED: '已归档' }
const STATUS_TYPE = { DRAFT: 'default', PUBLISHED: 'success', FROZEN: 'warning', ARCHIVED: 'info' }

export default {
  name: 'AaTermCurrentView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag, AppConfirmDialog, AppButton },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      loadingCurrent: true, disposed: false, currentVersion: 0, listVersion: 0, scopeVersion: 0,
      currentError: '',
      current: null,
      switchLog: [],
      loading: true,
      error: '',
      terms: [],
      switching: '',
      dialog: { visible: false, submitting: false, row: null, message: '' }
    }
  },
  computed: {
    canManageSchoolTerm() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.term.manage') && ['SCHOOL', 'TENANT_ALL'].includes(this.ctx.dataScope?.scope) },
    canViewGovernance() { return matchPermission(this.ctx.permissionPatterns || [], 'systemAdmin.academicCalendar.view') },
    candidates() {
      return this.terms.filter((t) => t.status === 'PUBLISHED')
    },
    governanceManaged() {
      return this.current?.currentAuthority === 'CALENDAR_GOVERNANCE'
    },
    directSwitchAllowed() {
      return this.canManageSchoolTerm && !this.loadingCurrent && !this.currentError && !this.governanceManaged && this.current?.canDirectSwitch === true
    },
    latestActivation() { return this.switchLog.find(row => String(row.toTermId) === String(this.current?.termId)) || null }
  },
  created() {
    this.loadCurrent()
    this.load()
  },
  watch: { ctx: { deep: true, handler() { this.scopeVersion++; this.dialog.visible = false; this.switching = ''; this.loadCurrent(); this.load() } } },
  beforeUnmount() { this.disposed = true; this.currentVersion++; this.listVersion++ },
  methods: {
    contextKey() { return JSON.stringify([this.disposed, this.scopeVersion, this.academicFlow?.identity() || JSON.stringify(this.ctx), this.$route?.fullPath]) },
    openTerm(row) { const returnToken = this.academicFlow?.captureReturn(); this.$router.push({ name: 'aa-term-detail', params: { termId: row.termId }, query: returnToken ? { returnToken } : {} }) },
    statusLabel(s) { return STATUS_LABEL[s] || (s ? '状态待确认' : '') },
    statusType(s) { return STATUS_TYPE[s] || 'default' },
    dateText(value) { return value ? String(value).slice(0, 10) : '—' },
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '—' },
    isResolvedCurrent(row) {
      return Boolean(this.current?.termId) && String(row.termId) === String(this.current.termId)
    },
    goGovernance() {
      this.$router.push(this.current?.switchRoute || '/admin/system/academic-calendar')
    },
    async loadCurrent() {
      const version = ++this.currentVersion, context = this.contextKey()
      this.loadingCurrent = true
      this.currentError = ''
      this.current = null
      const [res, log] = await Promise.all([
        academicAffairsApi.getCurrentTerm(),
        academicAffairsApi.getTermSwitchLog({ page: 1, pageSize: 50 })
      ])
      if (version !== this.currentVersion || context !== this.contextKey()) return
      if (res.code === 0) {
        this.current = res.data || null
        this.switchLog = log.code === 0 ? (log.data?.list || []) : []
      } else {
        this.current = null
        this.switchLog = []
        this.currentError = res.message || '当前学期解析失败，请核对全校学期治理与教务学期数据'
      }
      this.loadingCurrent = false
      if (!this.loading) this.academicFlow?.restorePosition?.()
    },
    async load() {
      const version = ++this.listVersion, context = this.contextKey()
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTerms({ page: 1, pageSize: 100 })
      if (version !== this.listVersion || context !== this.contextKey()) return
      if (res.code === 0) {
        this.terms = res.data.list
      } else {
        this.error = res.message
      }
      this.loading = false
      if (!this.loadingCurrent) this.academicFlow?.restorePosition?.()
    },
    askSwitch(row) {
      if (row.status !== 'PUBLISHED' || this.isResolvedCurrent(row)) return
      if (!this.directSwitchAllowed) {
        toast.warning(this.current?.switchHint || '当前学校已启用全校学期治理，请从统一治理入口切换')
        return
      }
      this.dialog = {
        visible: true,
        submitting: false,
        row: { ...row }, context: this.contextKey(),
        message: `确认将「${row.yearCode} 第 ${row.termNo} 学期」设为当前学期？其它学期的「当前」标记会被取消。`
      }
    },
    async doSwitch() {
      const row = this.dialog.row
      if (!row || this.dialog.submitting || !this.directSwitchAllowed || this.dialog.context !== this.contextKey()) return
      const context = this.dialog.context
      this.dialog.submitting = true
      this.switching = row.termId
      const res = await academicAffairsApi.setCurrentTerm(row.termId)
      if (context !== this.contextKey()) return
      this.dialog.submitting = false
      this.switching = ''
      if (res.code === 0) {
        this.dialog.visible = false
        toast.success(`已切换：${row.yearCode} 第 ${row.termNo} 学期为当前学期`)
        this.loadCurrent()
        this.load()
      } else {
        toast.error(res.message || '切换失败')
        this.loadCurrent()
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/foundation-workspace.css';
.aa-current-card { display: flex; align-items: center; flex-wrap: wrap; gap: 12px 18px; padding: 16px 20px; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.aa-current-card__title { font-size: 17px; font-weight: 600; color: var(--text-900, #1f2329); }
.aa-current-card__meta { font-size: 13px; color: var(--text-700, #4e5969); padding-left: 18px; border-left: 1px solid var(--border-base); }
.aa-authority-card { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 20px; border: 1px solid var(--primary-200, #b8d7ff); border-radius: 10px; background: var(--primary-50, #f2f7ff); }
.aa-authority-card strong { display: block; color: var(--text-900, #1f2329); font-size: 14px; }
.aa-authority-card p { margin: 5px 0 0; color: var(--text-600, #646a73); font-size: 12px; line-height: 1.6; }
.aa-current-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.aa-current-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 4px; border-bottom: 1px solid var(--border-100, #f0f1f2); }
.aa-current-item__main { display: flex; align-items: center; gap: 10px; font-size: 14px; color: var(--text-900, #1f2329); }
.aa-current-item__managed { color: var(--text-500, #646a73); font-size: 12px; }
.aa-current-facts { margin: 0 0 8px; font-size: 13px; }
.aa-current-facts div { display: flex; gap: 12px; }
.aa-current-facts dt { color: var(--text-secondary); }
.aa-current-facts dd { margin: 0; }
.aa-current-rules { margin: 0; padding-left: 18px; color: var(--text-secondary); font-size: 12px; line-height: 1.8; }
.mp-link { border: 0; background: transparent; color: var(--pri); font: inherit; cursor: pointer; }
@media (max-width: 760px) { .aa-authority-card { align-items: stretch; flex-direction: column; } .aa-current-card__meta { padding-left: 0; border-left: 0; } }
</style>
