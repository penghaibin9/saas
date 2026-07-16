<template>
  <AppPageShell
    title="处分送达与申诉"
    subtitle="已生效处分的决定书送达登记，及学生申诉的复核（维持/变更/撤销）。"
    role-name="学工处 / 学院"
    data-scope-name="学院本院 / 学工处全校"
    watermark-purpose="处分送达与申诉复核"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载..." @retry="load"
                    @back="$router.push('/admin/student-affairs/discipline')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="已生效处分 · 送达 / 发起申诉">
        <table class="sa-table">
          <thead><tr><th>学生</th><th>处分类型</th><th>送达</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="c in effectiveCases" :key="c.caseId">
              <td><strong>{{ c.realName || ('学生#' + c.studentId) }}</strong></td>
              <td>{{ discLabel(c.discType) }}</td>
              <td>
                <template v-if="c.deliveredAt">{{ deliveryLabel(c.deliveryMethod) }} · <AppDateDisplay :value="c.deliveredAt" mode="date" /></template>
                <span v-else>未送达</span>
              </td>
              <td class="ap-ops">
                <AppPermissionButton v-if="!c.deliveredAt" code="studentAffairs.discipline.deliver" size="sm" :loading="acting===c.caseId" @click="deliver(c)">登记送达</AppPermissionButton>
                <AppPermissionButton code="studentAffairs.discipline.appeal.create" size="sm" variant="secondary" :loading="acting===c.caseId" @click="appeal(c)">发起申诉</AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!effectiveCases.length"><td colspan="4" class="sa-empty">暂无已生效处分</td></tr>
          </tbody>
        </table>
        <AppPagination v-if="effectiveCases.length" v-model:page="effectivePaging.page" v-model:pageSize="effectivePaging.pageSize"
                       :total="effectivePaging.total" @change="loadEffectivePage" />
      </AppSectionCard>

      <AppSectionCard title="申诉复核">
        <div class="ap-filters">
          <button v-for="f in appealFilters" :key="f.key" type="button" class="ap-chip"
                  :class="{ 'is-on': appealStatus === f.key }" @click="setAppealStatus(f.key)">{{ f.label }}</button>
        </div>
        <table class="sa-table">
          <thead><tr><th>学生</th><th>申诉理由</th><th>状态</th><th>复核意见</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="a in appeals" :key="a.appealId">
              <td>{{ a.realName || ('学生#' + a.studentId) }}</td>
              <td class="ap-reason">{{ a.reason }}</td>
              <td><StatusTag :type="appealType(a.status)" :label="a.statusLabel || a.status" dot /></td>
              <td class="ap-opinion">{{ a.reviewOpinion || '—' }}</td>
              <td>
                <AppPermissionButton v-if="['SUBMITTED','REVIEWING'].includes(a.status)" code="studentAffairs.discipline.appeal.review" size="sm" :loading="acting===a.appealId" @click="review(a)">复核</AppPermissionButton>
                <span v-else class="ap-dash">—</span>
              </td>
            </tr>
            <tr v-if="!appeals.length"><td colspan="5" class="sa-empty">暂无申诉</td></tr>
          </tbody>
        </table>
        <AppPagination v-if="appeals.length" v-model:page="appealsPaging.page" v-model:pageSize="appealsPaging.pageSize"
                       :total="appealsPaging.total" @change="loadAppealsPage" />
      </AppSectionCard>
    </AppGlobalState>

    <!-- 登记决定书送达：送达方式为固定枚举，用抽屉里的下拉承载 -->
    <AppDrawer v-model:visible="deliverDrawer.visible" title="登记决定书送达">
      <div class="sa-form">
        <AppFormItem label="送达方式" required>
          <AppSelect v-model="deliverDrawer.form.method" :options="deliveryOptions" :disabled="!!acting" />
        </AppFormItem>
        <AppInlineAlert v-if="deliverDrawer.errorMessage" type="danger" :description="deliverDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="ap-btn" :disabled="!!acting" @click="deliverDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.discipline.deliver" :loading="!!acting" @click="submitDeliver">
          登记送达
        </AppPermissionButton>
      </template>
    </AppDrawer>

    <!-- 发起申诉：单个申诉理由，走带原因校验的确认弹窗（后端 min_length=5 真实强校验） -->
    <AppConfirmDialog
      v-model:visible="appealDialog.visible"
      title="发起处分申诉"
      message="提交后进入学工处/学院申诉复核流程。"
      type="primary"
      confirm-text="提交申诉"
      require-reason
      reason-label="申诉理由（≥5字）"
      reason-placeholder="请客观陈述申诉理由，不少于 5 字"
      :reason-min-length="5"
      :submitting="!!acting"
      @confirm="submitAppeal"
    />

    <!-- 申诉复核：结论（枚举）+ 复核意见（≥5字），两个字段用抽屉承载 -->
    <AppDrawer v-model:visible="reviewDrawer.visible" title="申诉复核">
      <div class="sa-form">
        <AppFormItem label="复核结论" required>
          <AppSelect v-model="reviewDrawer.form.result" :options="resultOptions" :disabled="!!acting" />
        </AppFormItem>
        <AppFormItem label="复核意见（≥5字）" required :error="reviewDrawer.errors.opinion">
          <AppQuickPhrases scene-key="common.reviewOpinion" @pick="insertOpinionPhrase" />
          <AppTextarea ref="reviewOpinionTa" v-model="reviewDrawer.form.opinion" :rows="3" placeholder="请填写复核意见，不少于 5 字" :disabled="!!acting" />
        </AppFormItem>
        <AppInlineAlert v-if="reviewDrawer.errorMessage" type="danger" :description="reviewDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="ap-btn" :disabled="!!acting" @click="reviewDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.discipline.appeal.review" :loading="!!acting" @click="submitReview">
          提交复核
        </AppPermissionButton>
      </template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppDateDisplay, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard,
  AppPageShell, AppPagination, AppPermissionButton, AppQuickPhrases, AppSectionCard, AppSelect,
  AppStatusTag, AppTextarea
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'

const DISC = { WARNING: '警告', SERIOUS_WARNING: '严重警告', DEMERIT: '记过', PROBATION: '留校察看', EXPEL: '开除' }
const DELIVERY = { DIRECT: '直接送达', MAIL: '邮寄', PUBLIC: '公告', LEAVE: '留置' }
const RESULT = { UPHELD: '维持原处分', REVISED: '变更处分', REVOKED: '撤销处分' }
const APPEAL_FILTERS = [
  { key: '', label: '全部' }, { key: 'SUBMITTED', label: '待复核' },
  { key: 'UPHELD', label: '已维持' }, { key: 'REVISED', label: '已变更' }, { key: 'REVOKED', label: '已撤销' }
]

export default {
  name: 'DisciplineAppealView',
  components: {
    AppConfirmDialog, AppDateDisplay, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard,
    AppPageShell, AppPagination, AppPermissionButton, AppQuickPhrases, AppSectionCard, AppSelect,
    StatusTag: AppStatusTag, AppTextarea
  },
  data() {
    return {
      loading: true, acting: '', errorMessage: '',
      // 「已生效处分」「申诉」各拆成两路请求：*MetricsAll 保持与旧版一致的大 pageSize 全量快照，只喂头部统计卡；
      // 表格本体（effectiveCases / appeals）改走真实 page/pageSize，翻页不影响统计卡数字。
      effectiveMetricsAll: [], effectiveCases: [], effectivePaging: { page: 1, pageSize: 20, total: 0 },
      appealsMetricsAll: [], appeals: [], appealsPaging: { page: 1, pageSize: 20, total: 0 },
      appealStatus: '', appealFilters: APPEAL_FILTERS,
      deliveryOptions: Object.entries(DELIVERY).map(([value, label]) => ({ value, label })),
      resultOptions: Object.entries(RESULT).map(([value, label]) => ({ value, label })),
      deliverDrawer: { visible: false, caseId: '', form: { method: 'DIRECT' }, errorMessage: '' },
      appealDialog: { visible: false, caseId: '' },
      reviewDrawer: { visible: false, appealId: '', form: { result: 'UPHELD', opinion: '' }, errors: {}, errorMessage: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const undelivered = this.effectiveMetricsAll.filter((c) => !c.deliveredAt).length
      const pending = this.appealsMetricsAll.filter((a) => ['SUBMITTED', 'REVIEWING'].includes(a.status)).length
      return [
        { key: 'e', label: '已生效处分', value: this.effectiveMetricsAll.length, accent: 'primary' },
        { key: 'u', label: '待送达', value: undelivered, accent: undelivered ? 'warning' : 'success' },
        { key: 'p', label: '待复核申诉', value: pending, accent: pending ? 'warning' : 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    insertOpinionPhrase(text) {
      const el = this.$refs.reviewOpinionTa?.$refs?.el
      const { value, selStart, selEnd } = insertAtCursor(el, this.reviewDrawer.form.opinion, text)
      this.reviewDrawer.form.opinion = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    async load() {
      this.loading = true; this.errorMessage = ''
      const [effMeta, apMeta] = await Promise.all([
        studentAffairsApi.getDisciplineCases({ status: 'EFFECTIVE', pageSize: 300 }),
        studentAffairsApi.getDisciplineAppeals({ status: this.appealStatus, pageSize: 300 })
      ])
      if (effMeta.code === 0 && effMeta.data) this.effectiveMetricsAll = effMeta.data.items || []
      else this.errorMessage = effMeta.message || '加载失败'
      this.appealsMetricsAll = (apMeta.code === 0 && apMeta.data) ? (apMeta.data.items || []) : []
      await Promise.all([this.loadEffectivePage(), this.loadAppealsPage()])
      this.loading = false
    },
    async loadEffectivePage() {
      const res = await studentAffairsApi.getDisciplineCases({
        status: 'EFFECTIVE', page: this.effectivePaging.page, pageSize: this.effectivePaging.pageSize
      })
      if (res.code === 0 && res.data) {
        this.effectiveCases = res.data.items || []
        this.effectivePaging.total = res.data.total || 0
      }
    },
    async loadAppealsPage() {
      const res = await studentAffairsApi.getDisciplineAppeals({
        status: this.appealStatus, page: this.appealsPaging.page, pageSize: this.appealsPaging.pageSize
      })
      if (res.code === 0 && res.data) {
        this.appeals = res.data.items || []
        this.appealsPaging.total = res.data.total || 0
      }
    },
    setAppealStatus(k) {
      if (this.appealStatus === k) return
      this.appealStatus = k
      this.appealsPaging.page = 1
      this.reloadAppeals()
    },
    async reloadAppeals() {
      const apMeta = await studentAffairsApi.getDisciplineAppeals({ status: this.appealStatus, pageSize: 300 })
      this.appealsMetricsAll = (apMeta.code === 0 && apMeta.data) ? (apMeta.data.items || []) : []
      await this.loadAppealsPage()
    },
    deliver(c) {
      this.deliverDrawer = { visible: true, caseId: c.caseId, form: { method: 'DIRECT' }, errorMessage: '' }
    },
    async submitDeliver() {
      const { caseId, form } = this.deliverDrawer
      this.acting = caseId
      this.deliverDrawer.errorMessage = ''
      const res = await studentAffairsApi.deliverDiscipline(caseId, { method: form.method })
      this.acting = ''
      if (res.code === 0) {
        toast.success('已登记送达')
        this.deliverDrawer.visible = false
        this.load()
      } else {
        this.deliverDrawer.errorMessage = res.message || '送达失败'
      }
    },
    appeal(c) {
      this.appealDialog = { visible: true, caseId: c.caseId }
    },
    async submitAppeal(payload) {
      const reason = (payload && payload.reason) || ''
      const caseId = this.appealDialog.caseId
      this.acting = caseId
      const res = await studentAffairsApi.submitDisciplineAppeal(caseId, reason)
      this.acting = ''
      if (res.code === 0) {
        toast.success('申诉已提交')
        this.appealDialog.visible = false
        this.load()
      } else {
        toast.error(res.message || '申诉失败')
      }
    },
    review(a) {
      this.reviewDrawer = { visible: true, appealId: a.appealId, form: { result: 'UPHELD', opinion: '' }, errors: {}, errorMessage: '' }
    },
    async submitReview() {
      const { appealId, form, errors } = this.reviewDrawer
      errors.opinion = (form.opinion || '').trim().length >= 5 ? '' : '复核意见不能少于 5 个字'
      if (errors.opinion) return
      this.acting = appealId
      this.reviewDrawer.errorMessage = ''
      const res = await studentAffairsApi.reviewDisciplineAppeal(appealId, form.result, form.opinion.trim())
      this.acting = ''
      if (res.code === 0) {
        toast.success('已复核')
        this.reviewDrawer.visible = false
        this.load()
      } else {
        this.reviewDrawer.errorMessage = res.message || '复核失败'
      }
    },
    discLabel(t) { return DISC[t] || t },
    deliveryLabel(m) { return DELIVERY[m] || m },
    appealType(s) { return ({ SUBMITTED: 'warning', REVIEWING: 'processing', UPHELD: 'default', REVISED: 'success', REVOKED: 'success', WITHDRAWN: 'default' })[s] || 'default' }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.ap-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.ap-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.ap-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.ap-reason, .ap-opinion { color: var(--text-secondary); font-size: var(--font-size-sm); max-width: 260px; }
.ap-ops { display: flex; gap: 6px; }
.ap-dash { color: var(--text-tertiary); }
.sa-table + .app-pagination { margin-top: var(--space-3); }
.sa-form { display: flex; flex-direction: column; gap: var(--space-4); }
.ap-btn { height: 34px; padding: 0 var(--space-4); border-radius: var(--radius-base); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-base); cursor: pointer; }
.ap-btn:hover { border-color: var(--border-dark); }
.ap-btn:disabled { opacity: 0.6; cursor: not-allowed; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
</style>
