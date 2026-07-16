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
              <td><AppPermissionButton code="studentAffairs.aid.view" size="sm" variant="secondary" :loading="acting===a.applyId" @click="objecte(a)">提异议</AppPermissionButton></td>
            </tr>
            <tr v-if="!publicity.length"><td colspan="3" class="sa-empty">当前无公示中的申请</td></tr>
          </tbody>
        </table>
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
                <AppPermissionButton v-if="o.status === 'SUBMITTED'" code="studentAffairs.aid.approve" size="sm" :loading="acting===o.objectionId" @click="review(o)">复核</AppPermissionButton>
                <span v-else class="ob-dash">—</span>
              </td>
            </tr>
            <tr v-if="!objections.length"><td colspan="5" class="sa-empty">暂无异议</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 提交异议：原为「异议理由→异议人」2 连原生弹窗。
         此处不挂快捷用语——现有 sa.aid.reject 是「驳回资助申请」口径，
         与「对公示结果提异议」不是一回事；异议理由本就该由异议人自述，套模板反而失真。 -->
    <AppConfirmDialog
      v-model:visible="objDlg.visible" :title="`对公示提出异议 · ${objDlg.who}`" type="warning"
      confirm-text="提交异议" require-reason :reason-min-length="5" reason-label="异议理由（≥5 字）"
      description="异议将进入复核流程，由资助工作组核查后给出成立/不成立结论。"
      :submitting="acting === objDlg.applyId" @confirm="submitObjection"
    >
      <AppFormItem label="异议人">
        <AppTextInput v-model="objDlg.objectorName" placeholder="可空；留空按匿名异议处理" />
      </AppFormItem>
    </AppConfirmDialog>

    <!-- 复核异议：原为「结论码 SUSTAINED/OVERRULED→复核意见」2 连弹窗，结论要手打英文 -->
    <AppConfirmDialog
      v-model:visible="revDlg.visible" title="复核异议" type="primary"
      confirm-text="提交复核" require-reason :reason-min-length="5" reason-label="复核意见（≥5 字）"
      :submitting="acting === revDlg.objectionId" @confirm="submitReview"
    >
      <AppFormItem label="复核结论" required>
        <AppSelect v-model="revDlg.result" :options="OBJECTION_RESULTS" />
      </AppFormItem>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton,
  AppSectionCard, AppSelect, AppStatusTag, AppTextInput
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

/** 与后端复核结论取值一一对应；括号内为对原认定的影响，避免只看英文码选反。 */
const OBJECTION_RESULTS = [
  { value: 'OVERRULED', label: '不成立 —— 维持原认定结果' },
  { value: 'SUSTAINED', label: '成立 —— 驳回原认定结果' }
]

const LEVELS = { SPECIAL: '特别困难', DIFFICULT: '困难', GENERAL: '一般困难' }
const STATUS_FILTERS = [
  { key: '', label: '全部' }, { key: 'SUBMITTED', label: '待复核' }, { key: 'CLOSED', label: '已复核' }
]

export default {
  name: 'AidObjectionView',
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton,
    AppSectionCard, AppSelect, AppTextInput, StatusTag: AppStatusTag
  },
  data() {
    return {
      loading: true, acting: '', errorMessage: '', publicity: [], objections: [], objStatus: '', statusFilters: STATUS_FILTERS,
      objDlg: { visible: false, applyId: '', who: '', objectorName: '' },
      revDlg: { visible: false, objectionId: '', result: 'OVERRULED' }
    }
  },
  computed: {
    OBJECTION_RESULTS: () => OBJECTION_RESULTS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const pending = this.objections.filter((o) => o.status === 'SUBMITTED').length
      const sustained = this.objections.filter((o) => o.result === 'SUSTAINED').length
      return [
        { key: 'p', label: '公示中申请', value: this.publicity.length, accent: 'primary' },
        { key: 'w', label: '待复核异议', value: pending, accent: pending ? 'warning' : 'success' },
        { key: 's', label: '异议成立(已驳回)', value: sustained, accent: 'risk' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const [pu, ob] = await Promise.all([
        studentAffairsApi.getAidApplications({ status: 'PUBLICITY', pageSize: 300 }),
        studentAffairsApi.getAidObjections({ status: this.objStatus, pageSize: 300 })
      ])
      if (pu.code === 0 && pu.data) this.publicity = pu.data.items || []
      else this.errorMessage = pu.message || '加载失败'
      this.objections = (ob.code === 0 && ob.data) ? (ob.data.items || []) : []
      this.loading = false
    },
    setStatus(k) { if (this.objStatus === k) return; this.objStatus = k; this.load() },
    objecte(a) {
      this.objDlg = { visible: true, applyId: a.applyId, who: a.realName || a.studentNo || '该生', objectorName: '' }
    },
    async submitObjection({ reason }) {
      const d = this.objDlg
      this.acting = d.applyId
      const res = await studentAffairsApi.submitAidObjection(d.applyId, {
        reason: reason.trim(), objectorName: d.objectorName.trim() || undefined
      })
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('异议已提交'); this.load() } else toast.error(res.message || '提交失败')
    },
    review(o) {
      this.revDlg = { visible: true, objectionId: o.objectionId, result: 'OVERRULED' }
    },
    async submitReview({ reason }) {
      const d = this.revDlg
      this.acting = d.objectionId
      const res = await studentAffairsApi.reviewAidObjection(d.objectionId, d.result, reason.trim())
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已复核'); this.load() } else toast.error(res.message || '复核失败')
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
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
</style>
