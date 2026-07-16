<template>
  <AppPageShell
    title="困难认定异议复核"
    subtitle="公示期内对认定结果提出异议并复核（成立则驳回申请 / 不成立则维持）。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（辅导员限本班）"
    watermark-purpose="困难认定异议复核"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载..." @retry="load"
                    @back="$router.push('/admin/student-affairs/aid')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="公示中申请 · 可提异议">
        <table class="sa-table">
          <thead><tr><th>学生</th><th>拟认定等级</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="a in publicity" :key="a.applyId">
              <td><strong>{{ a.realName || ('学生#' + a.studentId) }}</strong></td>
              <td>{{ levelLabel(a.finalLevel || a.applyLevel) }}</td>
              <td><AppPermissionButton code="studentAffairs.aid.view" size="sm" variant="secondary" :loading="acting===a.applyId" @click="openObjectDrawer(a)">提异议</AppPermissionButton></td>
            </tr>
            <tr v-if="!publicity.length"><td colspan="3" class="sa-empty">当前无公示中的申请</td></tr>
          </tbody>
        </table>
        <AppPagination v-model:page="pubPagination.page" v-model:pageSize="pubPagination.pageSize"
                       :total="pubPagination.total" @change="load" />
      </AppSectionCard>

      <AppSectionCard title="异议复核">
        <div class="ob-filters">
          <button v-for="f in statusFilters" :key="f.key" type="button" class="ob-chip"
                  :class="{ 'is-on': objStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
        </div>
        <table class="sa-table">
          <thead><tr><th>被异议学生</th><th>异议人</th><th>异议理由</th><th>状态/结论</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="o in objections" :key="o.objectionId">
              <td>{{ o.realName || ('学生#' + o.studentId) }}</td>
              <td>{{ o.objectorName || '匿名' }}</td>
              <td class="ob-reason">{{ o.reason }}</td>
              <td>
                <StatusTag :type="objType(o)" :label="o.status === 'CLOSED' ? (o.resultLabel || '已复核') : (o.statusLabel || o.status)" dot />
                <em v-if="o.reviewOpinion" class="ob-opinion">{{ o.reviewOpinion }}</em>
              </td>
              <td>
                <AppPermissionButton v-if="o.status === 'SUBMITTED'" code="studentAffairs.aid.approve" size="sm" :loading="acting===o.objectionId" @click="openReviewDrawer(o)">复核</AppPermissionButton>
                <span v-else class="ob-dash">—</span>
              </td>
            </tr>
            <tr v-if="!objections.length"><td colspan="5" class="sa-empty">暂无异议</td></tr>
          </tbody>
        </table>
        <AppPagination v-model:page="objPagination.page" v-model:pageSize="objPagination.pageSize"
                       :total="objPagination.total" @change="load" />
      </AppSectionCard>
    </AppGlobalState>

    <!-- 提异议 -->
    <AppDrawer v-model:visible="objectDrawer.visible" :title="`提异议 · ${objectDrawer.studentLabel}`">
      <div class="ob-form">
        <AppFormItem label="异议理由" required :error="objectDrawer.errors.reason">
          <AppTextarea v-model="objectDrawer.form.reason" :rows="3" placeholder="请说明异议理由，不少于 5 字"
                       :disabled="!!acting" />
        </AppFormItem>
        <AppFormItem label="异议人">
          <AppTextInput v-model="objectDrawer.form.objectorName" placeholder="可空 / 匿名" :disabled="!!acting" />
        </AppFormItem>
        <AppInlineAlert v-if="objectDrawer.errorMessage" type="danger" :description="objectDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="ob-btn" :disabled="!!acting" @click="objectDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.aid.view" :loading="!!acting" @click="submitObjectDrawer">提交异议</AppPermissionButton>
      </template>
    </AppDrawer>

    <!-- 异议复核 -->
    <AppDrawer v-model:visible="reviewDrawer.visible" title="异议复核">
      <div class="ob-form">
        <AppFormItem label="复核结论" required>
          <AppSelect v-model="reviewDrawer.form.result" :options="resultOptions" :disabled="!!acting" />
        </AppFormItem>
        <AppFormItem label="复核意见" required :error="reviewDrawer.errors.opinion">
          <AppQuickPhrases scene-key="common.reviewOpinion" @pick="onPickReviewOpinion" />
          <AppTextarea ref="reviewOpinionTa" v-model="reviewDrawer.form.opinion" :rows="3" placeholder="请说明复核意见，不少于 5 字"
                       :disabled="!!acting" />
        </AppFormItem>
        <AppInlineAlert v-if="reviewDrawer.errorMessage" type="danger" :description="reviewDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="ob-btn" :disabled="!!acting" @click="reviewDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.aid.approve" :loading="!!acting" @click="submitReviewDrawer">提交复核</AppPermissionButton>
      </template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppInlineAlert, AppFormItem, AppMetricCard, AppPageShell, AppPagination,
        AppPermissionButton, AppQuickPhrases, AppSectionCard, AppSelect, AppStatusTag, AppTextarea, AppTextInput } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { toast } from '@/utils/toast'

const LEVELS = { SPECIAL: '特别困难', DIFFICULT: '困难', GENERAL: '一般困难' }
const STATUS_FILTERS = [
  { key: '', label: '全部' }, { key: 'SUBMITTED', label: '待复核' }, { key: 'CLOSED', label: '已复核' }
]
const RESULT_OPTIONS = [
  { label: '成立（驳回申请）', value: 'SUSTAINED' },
  { label: '不成立（维持原认定）', value: 'OVERRULED' }
]

function freshObjectForm() {
  return { reason: '', objectorName: '' }
}
function freshReviewForm() {
  return { result: 'OVERRULED', opinion: '' }
}

export default {
  name: 'AidObjectionView',
  components: { AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppPageShell, AppPagination,
               AppPermissionButton, AppQuickPhrases, AppSectionCard, AppSelect, StatusTag: AppStatusTag, AppTextarea, AppTextInput },
  data() {
    return {
      loading: true, acting: '', errorMessage: '', publicity: [], objections: [], objStatsAll: [],
      objStatus: '', statusFilters: STATUS_FILTERS, resultOptions: RESULT_OPTIONS,
      pubPagination: { page: 1, pageSize: 20, total: 0 },
      objPagination: { page: 1, pageSize: 20, total: 0 },
      objectDrawer: { visible: false, applyId: '', studentLabel: '', form: freshObjectForm(), errors: {}, errorMessage: '' },
      reviewDrawer: { visible: false, objectionId: '', form: freshReviewForm(), errors: {}, errorMessage: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const pending = this.objStatsAll.filter((o) => o.status === 'SUBMITTED').length
      const sustained = this.objStatsAll.filter((o) => o.result === 'SUSTAINED').length
      return [
        { key: 'p', label: '公示中申请', value: this.pubPagination.total, accent: 'primary' },
        { key: 'w', label: '待复核异议', value: pending, accent: pending ? 'warning' : 'success' },
        { key: 's', label: '异议成立(已驳回)', value: sustained, accent: 'risk' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const [pu, ob, obStats] = await Promise.all([
        studentAffairsApi.getAidApplications({ status: 'PUBLICITY', page: this.pubPagination.page, pageSize: this.pubPagination.pageSize }),
        studentAffairsApi.getAidObjections({ status: this.objStatus, page: this.objPagination.page, pageSize: this.objPagination.pageSize }),
        // 独立于当前筛选/分页的全量口径，仅用于「待复核」「已成立」两张统计卡，避免筛选/翻页时把统计卡也带偏
        studentAffairsApi.getAidObjections({ pageSize: 200 })
      ])
      if (pu.code === 0 && pu.data) {
        this.publicity = pu.data.items || []
        this.pubPagination.total = pu.data.total != null ? pu.data.total : this.publicity.length
      } else {
        this.errorMessage = pu.message || '加载失败'
      }
      if (ob.code === 0 && ob.data) {
        this.objections = ob.data.items || []
        this.objPagination.total = ob.data.total != null ? ob.data.total : this.objections.length
      } else {
        this.objections = []
      }
      this.objStatsAll = (obStats.code === 0 && obStats.data) ? (obStats.data.items || []) : []
      this.loading = false
    },
    setStatus(k) {
      if (this.objStatus === k) return
      this.objStatus = k
      this.objPagination.page = 1
      this.load()
    },
    openObjectDrawer(a) {
      this.objectDrawer.applyId = a.applyId
      this.objectDrawer.studentLabel = a.realName || ('学生#' + a.studentId)
      this.objectDrawer.form = freshObjectForm()
      this.objectDrawer.errors = {}
      this.objectDrawer.errorMessage = ''
      this.objectDrawer.visible = true
    },
    async submitObjectDrawer() {
      const { form, errors, applyId } = this.objectDrawer
      const reason = (form.reason || '').trim()
      errors.reason = reason.length >= 5 ? '' : '异议理由不少于 5 字'
      if (errors.reason) return
      this.acting = applyId
      this.objectDrawer.errorMessage = ''
      const res = await studentAffairsApi.submitAidObjection(applyId, { reason, objectorName: (form.objectorName || '').trim() || undefined })
      this.acting = ''
      if (res.code === 0) {
        toast.success('异议已提交')
        this.objectDrawer.visible = false
        this.load()
      } else {
        this.objectDrawer.errorMessage = res.message || '提交失败'
        toast.error(res.message || '提交失败')
      }
    },
    openReviewDrawer(o) {
      this.reviewDrawer.objectionId = o.objectionId
      this.reviewDrawer.form = freshReviewForm()
      this.reviewDrawer.errors = {}
      this.reviewDrawer.errorMessage = ''
      this.reviewDrawer.visible = true
    },
    onPickReviewOpinion(text) {
      const el = this.$refs.reviewOpinionTa?.$refs?.el
      const { value, selStart, selEnd } = insertAtCursor(el, this.reviewDrawer.form.opinion, text)
      this.reviewDrawer.form.opinion = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    async submitReviewDrawer() {
      const { form, errors, objectionId } = this.reviewDrawer
      const opinion = (form.opinion || '').trim()
      errors.opinion = opinion.length >= 5 ? '' : '复核意见不少于 5 字'
      if (errors.opinion) return
      this.acting = objectionId
      this.reviewDrawer.errorMessage = ''
      const res = await studentAffairsApi.reviewAidObjection(objectionId, form.result, opinion)
      this.acting = ''
      if (res.code === 0) {
        toast.success('已复核')
        this.reviewDrawer.visible = false
        this.load()
      } else {
        this.reviewDrawer.errorMessage = res.message || '复核失败'
        toast.error(res.message || '复核失败')
      }
    },
    levelLabel(l) { return LEVELS[l] || l || '—' },
    objType(o) {
      if (o.status !== 'CLOSED') return 'warning'
      return o.result === 'SUSTAINED' ? 'danger' : 'success'
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.ob-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.ob-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.ob-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.ob-reason { color: var(--text-secondary); font-size: var(--font-size-sm); max-width: 240px; }
.ob-opinion { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); font-style: normal; }
.ob-dash { color: var(--text-tertiary); }
.ob-form { display: flex; flex-direction: column; gap: var(--space-4); }
.ob-btn { height: 34px; padding: 0 var(--space-4); border-radius: var(--radius-base); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-base); cursor: pointer; }
.ob-btn:hover { border-color: var(--border-dark); }
.ob-btn:disabled { opacity: 0.6; cursor: not-allowed; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
</style>
