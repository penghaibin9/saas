<template>
  <ModulePageShell
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

      <AppSectionCard title="当前学期 Authority">
        <div v-if="governanceManaged" class="aa-authority-card">
          <div>
            <strong>全校统一治理已启用</strong>
            <p>{{ current.switchHint }}</p>
          </div>
          <AppButton variant="primary" @click="goGovernance">前往学年学期与业务日历</AppButton>
        </div>
        <p v-else class="mp-note">{{ current?.switchHint || '当前沿用教务学期兼容切换；后续启用全校学期治理后将统一从系统管理切换。' }}</p>
      </AppSectionCard>

      <AppSectionCard :title="governanceManaged ? '进行中学期' : '切换当前学期'">
        <p class="mp-note">
          {{ governanceManaged
            ? '这里仅展示教务侧进行中的学期。当前结论来自全校 ACTIVE 学期，不能在本页旁路切换。'
            : '仅「进行中（PUBLISHED）」学期可设为当前；冻结/归档学期须先在「学期状态」解冻。' }}
        </p>
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!candidates.length" title="暂无进行中的学期" />
        <ul v-else class="aa-current-list">
          <li v-for="t in candidates" :key="t.termId" class="aa-current-item">
            <div class="aa-current-item__main">
              <span>{{ t.yearCode }} 第 {{ t.termNo }} 学期</span>
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

const STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '进行中', FROZEN: '已冻结', ARCHIVED: '已归档' }
const STATUS_TYPE = { DRAFT: 'default', PUBLISHED: 'success', FROZEN: 'warning', ARCHIVED: 'info' }

export default {
  name: 'AaTermCurrentView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag, AppConfirmDialog, AppButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loadingCurrent: true,
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
    candidates() {
      return this.terms.filter((t) => t.status === 'PUBLISHED')
    },
    governanceManaged() {
      return this.current?.currentAuthority === 'CALENDAR_GOVERNANCE'
    },
    directSwitchAllowed() {
      return !this.governanceManaged && this.current?.canDirectSwitch !== false
    }
  },
  created() {
    this.loadCurrent()
    this.load()
  },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || s || '' },
    statusType(s) { return STATUS_TYPE[s] || 'default' },
    isResolvedCurrent(row) {
      return Boolean(this.current?.termId) && String(row.termId) === String(this.current.termId)
    },
    goGovernance() {
      this.$router.push(this.current?.switchRoute || '/admin/system/academic-calendar')
    },
    async loadCurrent() {
      this.loadingCurrent = true
      this.currentError = ''
      const res = await academicAffairsApi.getCurrentTerm()
      if (res.code === 0) {
        this.current = res.data || null
      } else {
        this.current = null
        this.currentError = res.message || '当前学期解析失败，请核对全校学期治理与教务学期数据'
      }
      this.loadingCurrent = false
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTerms({ page: 1, pageSize: 100 })
      if (res.code === 0) {
        this.terms = res.data.list
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    askSwitch(row) {
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
      if (!row || !this.directSwitchAllowed) return
      this.dialog.submitting = true
      this.switching = row.termId
      const res = await academicAffairsApi.setCurrentTerm(row.termId)
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
