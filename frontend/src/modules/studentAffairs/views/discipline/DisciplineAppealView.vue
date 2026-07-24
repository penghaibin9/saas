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
        <DataTable v-if="effectiveCases.length" :columns="caseColumns" :rows="effectiveCases" row-key="caseId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span></template>
          <template #cell-discType="{ row }">{{ discLabel(row.discType) }}</template>
          <template #cell-delivered="{ row }">{{ row.deliveredAt ? (deliveryLabel(row.deliveryMethod) + ' · ' + row.deliveredAt.slice(0,10)) : '未送达' }}</template>
          <template #cell-actions="{ row }">
            <div class="ap-ops">
              <AppPermissionButton :allowed="canBtn('studentAffairs.discipline.deliver')" v-if="!row.deliveredAt" code="studentAffairs.discipline.deliver" size="sm" :loading="acting===row.caseId" @click="deliver(row)">登记送达</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.discipline.appeal.create')" code="studentAffairs.discipline.appeal.create" size="sm" variant="secondary" :loading="acting===row.caseId" @click="appeal(row)">发起申诉</AppPermissionButton>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无已生效处分</p>
      </AppSectionCard>

      <AppSectionCard title="申诉复核">
        <div class="ap-filters">
          <button v-for="f in appealFilters" :key="f.key" type="button" class="ap-chip"
                  :class="{ 'is-on': appealStatus === f.key }" @click="setAppealStatus(f.key)">{{ f.label }}</button>
        </div>
        <DataTable v-if="appeals.length" :columns="appealColumns" :rows="appeals" row-key="appealId">
          <template #cell-student="{ row }">{{ row.realName || ('学生#' + row.studentId) }}</template>
          <template #cell-reason="{ row }"><span class="ap-reason">{{ row.reason }}</span></template>
          <template #cell-status="{ row }"><StatusTag :type="appealType(row.status)" :label="row.statusLabel || row.status" dot /></template>
          <template #cell-opinion="{ row }"><span class="ap-opinion">{{ row.reviewOpinion || '—' }}</span></template>
          <template #cell-actions="{ row }">
            <AppPermissionButton :allowed="canBtn('studentAffairs.discipline.appeal.review')" v-if="['SUBMITTED','REVIEWING'].includes(row.status)" code="studentAffairs.discipline.appeal.review" size="sm" :loading="acting===row.appealId" @click="review(row)">复核</AppPermissionButton>
            <span v-else class="ap-dash">—</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无申诉</p>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 登记送达：原要手打 DIRECT/MAIL/PUBLIC/LEAVE -->
    <AppConfirmDialog
      v-model:visible="delDlg.visible" title="登记处分送达" type="primary" confirm-text="确认登记"
      :submitting="acting === delDlg.caseId" @confirm="submitDeliver"
    >
      <AppFormItem label="送达方式" required>
        <AppSelect v-model="delDlg.method" :options="DELIVERY_OPTIONS" />
      </AppFormItem>
    </AppConfirmDialog>

    <!-- 提交申诉：申诉理由由申诉人自述，不挂模板 -->
    <AppConfirmDialog
      v-model:visible="apDlg.visible" title="提交申诉" type="warning" confirm-text="提交申诉"
      require-reason :reason-min-length="5" reason-label="申诉理由（≥5 字）"
      description="申诉将进入复核流程，由处分复核组核查后给出维持/变更/撤销结论。"
      :submitting="acting === apDlg.caseId" @confirm="submitAppeal"
    />

    <!-- 复核申诉：结论原要手打 UPHELD/REVISED/REVOKED。
         挂 common.reviewOpinion——该词库四条恰为「维持原决定 / 部分成立予以更正 / 原决定撤销 /
         补充核实」，正好覆盖本页三种结论，是其对口场景。 -->
    <AppConfirmDialog
      v-model:visible="revDlg.visible" title="复核申诉" type="primary" confirm-text="提交复核"
      require-reason :reason-min-length="5" reason-label="复核意见（≥5 字）"
      phrase-scene-key="common.reviewOpinion" :submitting="acting === revDlg.appealId" @confirm="submitReview"
    >
      <AppFormItem label="复核结论" required>
        <AppSelect v-model="revDlg.result" :options="RESULT_OPTIONS" />
      </AppFormItem>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton,
  AppSectionCard, AppSelect, AppStatusTag
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'


const DISC = { WARNING: '警告', SERIOUS_WARNING: '严重警告', DEMERIT: '记过', PROBATION: '留校察看', EXPEL: '开除' }
const DELIVERY = { DIRECT: '直接送达', MAIL: '邮寄', PUBLIC: '公告', LEAVE: '留置' }
const RESULT = { UPHELD: '维持原处分', REVISED: '变更处分', REVOKED: '撤销处分' }
/** 下拉选项直接由页面既有的 DELIVERY / RESULT 映射派生，不另造一份，避免两处取值走散。 */
const DELIVERY_OPTIONS = Object.entries(DELIVERY).map(([value, label]) => ({ value, label }))
const RESULT_OPTIONS = Object.entries(RESULT).map(([value, label]) => ({ value, label }))
const APPEAL_FILTERS = [
  { key: '', label: '全部' }, { key: 'SUBMITTED', label: '待复核' },
  { key: 'UPHELD', label: '已维持' }, { key: 'REVISED', label: '已变更' }, { key: 'REVOKED', label: '已撤销' }
]
const CASE_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'discType', title: '处分类型' },
  { key: 'delivered', title: '送达' },
  { key: 'actions', title: '操作', align: 'right', width: '200px' }
]
const APPEAL_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'reason', title: '申诉理由' },
  { key: 'status', title: '状态' },
  { key: 'opinion', title: '复核意见' },
  { key: 'actions', title: '操作', align: 'right', width: '100px' }
]

export default {
  name: 'DisciplineAppealView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton,
    AppSectionCard, AppSelect, StatusTag: AppStatusTag, DataTable
  },
  data() {
    return {
      caseColumns: CASE_COLUMNS,
      appealColumns: APPEAL_COLUMNS,
      loading: true, acting: '', errorMessage: '', effectiveCases: [], appeals: [], statusCounts: null, appealStatus: '', appealFilters: APPEAL_FILTERS,
      delDlg: { visible: false, caseId: '', method: 'DIRECT' },
      apDlg: { visible: false, caseId: '' },
      revDlg: { visible: false, appealId: '', result: 'UPHELD' }
    }
  },
  computed: {
    DELIVERY_OPTIONS: () => DELIVERY_OPTIONS,
    RESULT_OPTIONS: () => RESULT_OPTIONS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      return [
        { key: 'e', label: '已生效处分', value: '—', accent: 'primary' },
        { key: 'u', label: '待送达', value: '—', accent: 'warning' },
        { key: 'p', label: '待复核申诉', value: this.statusCounts === null ? '—' : (this.statusCounts.SUBMITTED || 0), accent: 'warning' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true; this.errorMessage = ''
      // 待服务端全量统计：申诉复核仅加载各接口单页上限。
      const [cs, ap] = await Promise.all([
        studentAffairsApi.getDisciplineCases({ status: 'EFFECTIVE', pageSize: 200 }),
        studentAffairsApi.getDisciplineAppeals({ status: this.appealStatus, pageSize: 200 })
      ])
      if (cs.code === 0 && cs.data) this.effectiveCases = cs.data.items || []
      else this.errorMessage = cs.message || '加载失败'
      this.appeals = (ap.code === 0 && ap.data) ? (ap.data.items || []) : []
      this.statusCounts = (ap.code === 0 && ap.data) ? (ap.data.statusCounts || null) : null
      this.loading = false
    },
    setAppealStatus(k) { if (this.appealStatus === k) return; this.appealStatus = k; this.load() },
    deliver(c) { this.delDlg = { visible: true, caseId: c.caseId, method: 'DIRECT' } },
    async submitDeliver() {
      const d = this.delDlg
      this.acting = d.caseId
      const res = await studentAffairsApi.deliverDiscipline(d.caseId, { method: d.method })
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已登记送达'); this.load() } else toast.error(res.message || '送达失败')
    },
    appeal(c) { this.apDlg = { visible: true, caseId: c.caseId } },
    async submitAppeal({ reason }) {
      const d = this.apDlg
      this.acting = d.caseId
      const res = await studentAffairsApi.submitDisciplineAppeal(d.caseId, reason.trim())
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('申诉已提交'); this.load() } else toast.error(res.message || '申诉失败')
    },
    review(a) { this.revDlg = { visible: true, appealId: a.appealId, result: 'UPHELD' } },
    async submitReview({ reason }) {
      const d = this.revDlg
      this.acting = d.appealId
      const res = await studentAffairsApi.reviewDisciplineAppeal(d.appealId, d.result, reason.trim())
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已复核'); this.load() } else toast.error(res.message || '复核失败')
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
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.ap-reason, .ap-opinion { color: var(--text-secondary); font-size: var(--font-size-sm); max-width: 260px; }
.ap-ops { display: flex; gap: 6px; }
.ap-dash { color: var(--text-tertiary); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
