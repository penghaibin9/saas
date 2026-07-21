<template>
  <ModulePageShell
    title="当前学期设置"
    subtitle="查看当前学期，并在多个进行中学期间切换「当前」标记（不改变学期状态）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AppSectionCard title="当前学期">
        <LoadingState v-if="loadingCurrent" />
        <EmptyState
          v-else-if="!current || !current.termId"
          title="尚未设置当前学期"
          description="请先在「学年学期」发布一个学期，发布后自动成为当前学期"
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

      <AppSectionCard title="切换当前学期">
        <p class="mp-note">仅「进行中（PUBLISHED）」学期可设为当前；冻结/归档学期须先在「学期状态」解冻。</p>
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!candidates.length" title="暂无可切换的进行中学期" />
        <ul v-else class="aa-current-list">
          <li v-for="t in candidates" :key="t.termId" class="aa-current-item">
            <div class="aa-current-item__main">
              <span>{{ t.yearCode }} 第 {{ t.termNo }} 学期</span>
              <AppStatusTag v-if="t.isCurrent" type="success" dot>当前学期</AppStatusTag>
            </div>
            <AppButton
              v-if="!t.isCurrent"
              size="small"
              variant="primary"
              :loading="switching === t.termId"
              @click="askSwitch(t)"
            >设为当前</AppButton>
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
/** 当前学期设置（/admin/academic-affairs/terms/current）：GET /terms/current + POST /terms/{id}/set-current。 */
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
    }
  },
  created() {
    this.loadCurrent()
    this.load()
  },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || s || '' },
    statusType(s) { return STATUS_TYPE[s] || 'default' },
    async loadCurrent() {
      this.loadingCurrent = true
      const res = await academicAffairsApi.getCurrentTerm()
      this.current = res.code === 0 ? res.data : null
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
      this.dialog = {
        visible: true,
        submitting: false,
        row,
        message: `确认将「${row.yearCode} 第 ${row.termNo} 学期」设为当前学期？其它学期的「当前」标记会被取消。`
      }
    },
    async doSwitch() {
      const row = this.dialog.row
      if (!row) return
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
.aa-current-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.aa-current-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 4px; border-bottom: 1px solid var(--border-100, #f0f1f2); }
.aa-current-item__main { display: flex; align-items: center; gap: 10px; font-size: 14px; color: var(--text-900, #1f2329); }
</style>
