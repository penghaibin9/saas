<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    title="当前学期"
    subtitle="查看全校当前学期；已启用统一治理时，切换必须从“学年学期与业务日历”执行"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AppSectionCard title="当前学期">
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
            <span v-if="current.startDate && current.endDate">{{ current.startDate }} ~ {{ current.endDate }}</span>
            <span v-if="current.teachingWeeks">教学周 {{ current.teachingWeeks }} 周</span>
            <AppStatusTag :type="statusType(current.status)" dot>{{ statusLabel(current.status) }}</AppStatusTag>
          </div>
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
        <p v-else class="mp-note">{{ loadingCurrent ? '正在核对学校的学期设置…' : currentError ? '当前学期读取失败，请在上方重试。' : (current?.switchHint || '校级教务可将已发布学期设为全校当前学期。') }}</p>
      </AppSectionCard>

      <AppSectionCard title="已发布学期">
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
              <button type="button" class="mp-link" @click="$router.push({ name: 'aa-term-detail', params: { termId: t.termId } })">{{ t.yearCode }} 第 {{ t.termNo }} 学期</button>
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
  data() {
    return {
      loadingCurrent: true,
      currentRequestId: 0,
      termsRequestId: 0,
      termViewDisposed: false,
      currentError: '',
      current: null,
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
    }
  },
  created() {
    this.loadCurrent()
    this.load()
  },
  beforeUnmount() {
    this.termViewDisposed = true
    this.currentRequestId += 1
    this.termsRequestId += 1
  },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || (s ? '状态待确认' : '') },
    statusType(s) { return STATUS_TYPE[s] || 'default' },
    isResolvedCurrent(row) {
      return Boolean(this.current?.termId) && String(row.termId) === String(this.current.termId)
    },
    goGovernance() {
      this.$router.push(this.current?.switchRoute || '/admin/system/academic-calendar')
    },
    async loadCurrent() {
      if (this.termViewDisposed) return
      const requestId = ++this.currentRequestId
      this.loadingCurrent = true
      this.currentError = ''
      this.current = null
      try {
        const res = await academicAffairsApi.getCurrentTerm()
        if (requestId !== this.currentRequestId) return
        if (res?.code !== 0) throw new Error(res?.message || '当前学期解析失败，请核对全校学期治理与教务学期数据')
        if (!res.data || typeof res.data !== 'object' || Array.isArray(res.data)) {
          throw new Error('当前学期响应不完整，请刷新后重新核对')
        }
        this.current = res.data
      } catch (exception) {
        if (requestId !== this.currentRequestId) return
        this.current = null
        this.currentError = exception?.message || '当前学期读取失败，请刷新后重试'
      } finally {
        if (requestId === this.currentRequestId) this.loadingCurrent = false
      }
    },
    async load() {
      if (this.termViewDisposed) return
      const requestId = ++this.termsRequestId
      this.loading = true
      this.error = ''
      this.terms = []
      try {
        const res = await academicAffairsApi.getTerms({ page: 1, pageSize: 100 })
        if (requestId !== this.termsRequestId) return
        if (res?.code !== 0) throw new Error(res?.message || '学期列表读取失败，请刷新后重试')
        if (!Array.isArray(res.data?.list)) throw new Error('学期列表响应不完整，请刷新后重试')
        this.terms = res.data.list
      } catch (exception) {
        if (requestId !== this.termsRequestId) return
        this.terms = []
        this.error = exception?.message || '学期列表读取失败，请刷新后重试'
      } finally {
        if (requestId === this.termsRequestId) this.loading = false
      }
    },
    askSwitch(row) {
      if (this.dialog.submitting || row.status !== 'PUBLISHED' || this.isResolvedCurrent(row)) return
      if (!this.directSwitchAllowed) {
        toast.warning(this.current?.switchHint || '当前学校已启用全校学期治理，请从统一治理入口切换')
        return
      }
      this.dialog = {
        visible: true,
        submitting: false,
        row,
        message: `确认将「${row.yearCode} 第 ${row.termNo} 学期」设为当前学期？其它学期的「当前」标记会被取消。`
      }
    },
    async doSwitch() {
      const row = this.dialog.row
      if (!row || this.dialog.submitting || !this.directSwitchAllowed) return
      this.dialog.submitting = true
      this.switching = row.termId
      try {
        const res = await academicAffairsApi.setCurrentTerm(row.termId)
        if (this.termViewDisposed) return
        if (res?.code !== 0) throw new Error(res?.message || '切换失败')
        this.dialog.visible = false
        toast.success(`已切换：${row.yearCode} 第 ${row.termNo} 学期为当前学期`)
      } catch (exception) {
        // A timeout does not prove the server rolled back. Read back; never replay the write.
        if (!this.termViewDisposed) toast.error(exception?.message || '切换结果暂未确认，请核对刷新后的当前学期')
      } finally {
        if (!this.termViewDisposed) {
          await Promise.all([this.loadCurrent(), this.load()])
          if (!this.termViewDisposed) {
            this.dialog.submitting = false
            this.switching = ''
          }
        }
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
@media (max-width: 760px) { .aa-authority-card { align-items: stretch; flex-direction: column; } }
</style>
