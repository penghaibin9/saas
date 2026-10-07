<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    title="当前学期"
    subtitle="查看全校当前学期；已启用统一治理时，切换必须从“学年学期与业务日历”执行"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aa-authority-layout"><div class="mp-stack">
      <AppSectionCard title="当前权威事实">
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
          <div class="aa-current-card__main">
            <div class="aa-current-card__title">{{ current.yearCode }} 第 {{ current.termNo }} 学期</div>
            <div class="aa-current-card__sub">{{ current.termName || '未命名' }}</div>
          </div>
          <div class="aa-current-card__meta">
            <span v-if="current.startDate && current.endDate">{{ dateText(current.startDate) }} ~ {{ dateText(current.endDate) }}</span>
            <span v-if="current.teachingWeeks">教学周 {{ current.teachingWeeks }} 周</span>
            <AppStatusTag :type="statusType(current.status)" dot>{{ statusLabel(current.status) }}</AppStatusTag>
          </div>
          <dl class="aa-authority-facts">
            <div><dt>权威来源</dt><dd>{{ governanceManaged ? '全校学期治理' : current.canDirectSwitch === true ? '教务学期兼容管理' : '待核对' }}</dd></div>
            <div><dt>教务侧直接切换</dt><dd>{{ directSwitchAllowed ? '当前身份可按正式命令切换' : governanceManaged ? '由治理岗位统一激活' : '当前身份不可直接切换' }}</dd></div>
            <div><dt>生效时间</dt><dd>{{ latestActivation?.occurredAt ? formatTime(latestActivation.occurredAt) : '尚无可核对的切换流水' }}</dd></div>
            <div><dt>最近切换记录</dt><dd>{{ latestActivation ? `${latestActivation.operator || '系统'} · ${latestActivation.sourceLabel}` : '未记录' }}</dd></div>
          </dl>
        </div>
      </AppSectionCard>

      <AppSectionCard title="学期启用方式">
        <div v-if="governanceManaged" class="aa-authority-card">
          <div>
            <strong>全校统一治理已启用</strong>
            <p>{{ current.switchHint }}</p>
          </div>
          <AppButton v-if="canViewGovernance" variant="primary" @click="goGovernance">前往学年学期与业务日历</AppButton>
        </div>
        <p v-else class="mp-note">{{ loadingCurrent ? '正在核对学校的学期设置…' : currentError ? '当前学期读取失败，请在上方重试。' : '校级教务可将已发布学期设为全校当前学期。' }}</p>
      </AppSectionCard>

      <AppSectionCard title="定义、当前与归档关系">
        <p class="mp-note">
          {{ governanceManaged
            ? '学校在「学年学期与业务日历」统一启用当前学期。'
            : '仅已发布学期可设为当前。冻结学期需先解冻，已归档学期保持只读。' }}
        </p>
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
    </div><aside class="aa-authority-boundary">
      <h2>可理解的操作边界</h2>
      <section><strong>发布定义</strong><p>学校启用统一治理后，发布学期定义不自动激活为当前。</p></section>
      <section><strong>激活当前</strong><p>由实际治理入口和授权岗位执行；所有端读取同一当前学期结论。</p></section>
      <section><strong>冻结与封存</strong><p>冻结可以按原因解冻；已归档数据必须走受控纠错，不能普通解冻。</p></section>
    </aside></div>

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
.aa-current-card { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; padding: 4px 0; }
.aa-current-card__title { font-size: 16px; font-weight: 600; color: var(--text-900, #1f2329); }
.aa-current-card__sub { font-size: 13px; color: var(--text-500, #646a73); margin-top: 2px; }
.aa-current-card__meta { display: flex; align-items: center; gap: 14px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-authority-card { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 16px; border: 1px solid var(--primary-200, #b8d7ff); border-radius: 10px; background: var(--primary-50, #f2f7ff); }
.aa-authority-card strong { display: block; color: var(--text-900, #1f2329); font-size: 14px; }
.aa-authority-card p { margin: 5px 0 0; color: var(--text-600, #646a73); font-size: 12px; line-height: 1.6; }
.aa-current-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.aa-current-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 4px; border-bottom: 1px solid var(--border-100, #f0f1f2); }
.aa-current-item__main { display: flex; align-items: center; gap: 10px; font-size: 14px; color: var(--text-900, #1f2329); }
.aa-current-item__managed { color: var(--text-500, #646a73); font-size: 12px; }
.aa-authority-layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; align-items: start; gap: 16px; }
.aa-authority-facts { display: grid; grid-template-columns: 1fr 1fr; width: 100%; gap: 12px; margin: 4px 0; }
.aa-authority-facts div { padding: 12px; border: 1px solid var(--border-base); border-radius: 8px; }
.aa-authority-facts dt { color: var(--text-secondary); font-size: 12px; }
.aa-authority-facts dd { margin: 8px 0 0; font-size: 13px; font-weight: 600; }
.aa-authority-boundary { border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.aa-authority-boundary h2 { font-size: 14px; margin: 0; padding: 16px; border-bottom: 1px solid var(--border-base); }
.aa-authority-boundary section { padding: 0 16px; margin: 20px 0; font-size: 13px; }
.aa-authority-boundary p { color: var(--text-secondary); font-size: 12px; line-height: 1.7; }
.mp-link { border: 0; background: transparent; color: var(--pri); font: inherit; cursor: pointer; }
@media (max-width: 1100px) { .aa-authority-layout { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 760px) { .aa-authority-card { align-items: stretch; flex-direction: column; } }
</style>
