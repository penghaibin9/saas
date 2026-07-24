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
        <DataTable v-if="publicity.length" :columns="publicityColumns" :rows="publicity" row-key="applyId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span></template>
          <template #cell-level="{ row }">{{ levelLabel(row.finalLevel || row.applyLevel) }}</template>
          <template #cell-actions="{ row }">
            <AppPermissionButton :allowed="canBtn('studentAffairs.aid.view')" code="studentAffairs.aid.view" size="sm" variant="secondary" :loading="acting===row.applyId" @click="objecte(row)">提异议</AppPermissionButton>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前无公示中的申请</p>
      </AppSectionCard>

      <AppSectionCard title="异议复核">
        <div class="ob-filters">
          <button v-for="f in statusFilters" :key="f.key" type="button" class="ob-chip"
                  :class="{ 'is-on': objStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
        </div>
        <DataTable v-if="objections.length" :columns="objectionColumns" :rows="objections" row-key="objectionId">
          <template #cell-student="{ row }">{{ row.realName || ('学生#' + row.studentId) }}</template>
          <template #cell-objector="{ row }">{{ row.objectorName || '匿名' }}</template>
          <template #cell-reason="{ row }"><span class="ob-reason">{{ row.reason }}</span></template>
          <template #cell-status="{ row }">
            <StatusTag :type="objType(row)" :label="row.status === 'CLOSED' ? (row.resultLabel || '已复核') : (row.statusLabel || row.status)" dot />
            <em v-if="row.reviewOpinion" class="ob-opinion">{{ row.reviewOpinion }}</em>
          </template>
          <template #cell-actions="{ row }">
            <AppPermissionButton :allowed="canBtn('studentAffairs.aid.approve')" v-if="row.status === 'SUBMITTED'" code="studentAffairs.aid.approve" size="sm" :loading="acting===row.objectionId" @click="review(row)">复核</AppPermissionButton>
            <span v-else class="ob-dash">—</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无异议</p>
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
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'


/** 与后端复核结论取值一一对应；括号内为对原认定的影响，避免只看英文码选反。 */
const OBJECTION_RESULTS = [
  { value: 'OVERRULED', label: '不成立 —— 维持原认定结果' },
  { value: 'SUSTAINED', label: '成立 —— 驳回原认定结果' }
]

const LEVELS = { SPECIAL: '特别困难', DIFFICULT: '困难', GENERAL: '一般困难' }
const STATUS_FILTERS = [
  { key: '', label: '全部' }, { key: 'SUBMITTED', label: '待复核' }, { key: 'CLOSED', label: '已复核' }
]
const PUBLICITY_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'level', title: '拟认定等级' },
  { key: 'actions', title: '操作', align: 'right', width: '120px' }
]
const OBJECTION_COLUMNS = [
  { key: 'student', title: '被异议学生' },
  { key: 'objector', title: '异议人' },
  { key: 'reason', title: '异议理由' },
  { key: 'status', title: '状态/结论' },
  { key: 'actions', title: '操作', align: 'right', width: '100px' }
]

export default {
  name: 'AidObjectionView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton,
    AppSectionCard, AppSelect, AppTextInput, StatusTag: AppStatusTag, DataTable
  },
  data() {
    return {
      publicityColumns: PUBLICITY_COLUMNS,
      objectionColumns: OBJECTION_COLUMNS,
      loading: true, acting: '', errorMessage: '', publicity: [], objections: [], statusCounts: null, objStatus: '', statusFilters: STATUS_FILTERS,
      objDlg: { visible: false, applyId: '', who: '', objectorName: '' },
      revDlg: { visible: false, objectionId: '', result: 'OVERRULED' }
    }
  },
  computed: {
    OBJECTION_RESULTS: () => OBJECTION_RESULTS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      return [
        { key: 'p', label: '公示中申请', value: '—', accent: 'primary' },
        { key: 'w', label: '待复核异议', value: this.statusCounts === null ? '—' : (this.statusCounts.SUBMITTED || 0), accent: 'warning' },
        { key: 's', label: '异议成立(已驳回)', value: '—', accent: 'risk' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true; this.errorMessage = ''
      // 待服务端全量统计：复核工作台仅加载各接口单页上限。
      const [pu, ob] = await Promise.all([
        studentAffairsApi.getAidApplications({ status: 'PUBLICITY', pageSize: 200 }),
        studentAffairsApi.getAidObjections({ status: this.objStatus, pageSize: 200 })
      ])
      if (pu.code === 0 && pu.data) this.publicity = pu.data.items || []
      else this.errorMessage = pu.message || '加载失败'
      this.objections = (ob.code === 0 && ob.data) ? (ob.data.items || []) : []
      this.statusCounts = (ob.code === 0 && ob.data) ? (ob.data.statusCounts || null) : null
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
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.ob-reason { color: var(--text-secondary); font-size: var(--font-size-sm); max-width: 240px; }
.ob-opinion { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); font-style: normal; }
.ob-dash { color: var(--text-tertiary); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
