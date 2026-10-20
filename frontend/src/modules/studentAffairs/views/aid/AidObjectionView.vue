<template>
  <AppPageShell
    title="困难认定异议复核"
    subtitle="公示期内对认定结果提出异议并复核（成立则驳回申请 / 不成立则维持）。"
    :role-name="ctx?.currentRole?.roleName || ''"
    :data-scope-name="ctx?.dataScope?.scopeName || ''"
    watermark-purpose="困难认定异议复核"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载..." @retry="load"
                    @back="$router.push('/admin/student-affairs/aid')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <details class="ob-intake"><summary>登记公示异议 <span>{{ publicityPage.total }} 条公示申请</span></summary>
      <AppSectionCard title="选择公示申请">
        <DataTable v-if="publicity.length" :columns="publicityColumns" :rows="publicity" row-key="applyId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span></template>
          <template #cell-level="{ row }">{{ levelLabel(row.finalLevel || row.applyLevel) }}</template>
          <template #cell-actions="{ row }">
            <AppPermissionButton :allowed="canBtn('studentAffairs.aid.view')" code="studentAffairs.aid.view" size="sm" variant="secondary" :loading="acting===row.applyId" @click="objecte(row)">提异议</AppPermissionButton>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前无公示中的申请</p>
        <AppPagination v-model:page="publicityPage.page" v-model:pageSize="publicityPage.pageSize" :total="publicityPage.total" @change="load" />
      </AppSectionCard>
      </details>

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
            <AppPermissionButton :allowed="canBtn('studentAffairs.aid.approve') && row.allowedActions?.includes('REVIEW')" v-if="row.status === 'SUBMITTED'" code="studentAffairs.aid.approve" size="sm" :loading="acting===row.objectionId" @click="review(row)">复核</AppPermissionButton>
            <span v-else class="ob-dash">—</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无异议</p>
        <AppPagination v-model:page="objectionPage.page" v-model:pageSize="objectionPage.pageSize" :total="objectionPage.total" @change="load" />
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
      v-model:visible="revDlg.visible" :title="`复核异议 · ${revDlg.who || ''}`" type="primary"
      confirm-text="提交复核" require-reason :reason-min-length="5" reason-label="复核意见（≥5 字）"
      :submitting="acting === revDlg.objectionId" @confirm="submitReview"
    >
      <p class="ob-review-context">异议理由：{{ revDlg.reason }}</p>
      <AppFormItem label="复核结论" required>
        <AppSelect v-model="revDlg.result" :options="OBJECTION_RESULTS" />
      </AppFormItem>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton,
  AppSectionCard, AppSelect, AppStatusTag, AppTextInput, AppPagination
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { request } from '@/services/http/client'
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

async function reviewAidObjectionVersioned(objectionId, result, opinion, version) {
  try {
    const data = await request(`/student-affairs/aid/objections/${objectionId}/review`, {
      method: 'POST', body: { result, opinion, version }
    })
    return { code: 0, data, message: 'ok' }
  } catch (e) {
    return {
      code: e?.code || 1,
      bizCode: e?.bizCode || '',
      data: null,
      message: e?.message || '复核失败'
    }
  }
}

export default {
  name: 'AidObjectionView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton,
    AppSectionCard, AppSelect, AppTextInput, StatusTag: AppStatusTag, DataTable, AppPagination
  },
  data() {
    return {
      publicityColumns: PUBLICITY_COLUMNS,
      objectionColumns: OBJECTION_COLUMNS,
      loading: true, acting: '', errorMessage: '', publicity: [], objections: [], statusCounts: null, objStatus: '', statusFilters: STATUS_FILTERS,
      loadSeq: 0,
      publicityPage: { page: 1, pageSize: 10, total: 0 }, objectionPage: { page: 1, pageSize: 20, total: 0 },
      objDlg: { visible: false, applyId: '', who: '', objectorName: '' },
      revDlg: { visible: false, objectionId: '', result: 'OVERRULED', version: 0 }
    }
  },
  computed: {
    OBJECTION_RESULTS: () => OBJECTION_RESULTS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      return [
        { key: 'p', label: '公示中申请', value: this.publicityPage.total, accent: 'primary' },
        { key: 'w', label: '待复核异议', value: this.statusCounts === null ? '—' : (this.statusCounts.SUBMITTED || 0), accent: 'warning' },
        { key: 's', label: '已复核异议', value: this.statusCounts === null ? '—' : (this.statusCounts.CLOSED || 0), accent: 'primary' }
      ]
    }
  },
  mounted() { this.load() },
  beforeUnmount() { this.loadSeq += 1 },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      const seq = ++this.loadSeq
      const status = this.objStatus
      this.loading = true; this.errorMessage = ''
      try {
        const [pu, ob, pending, closed] = await Promise.all([
          studentAffairsApi.getAidApplications({ status: 'PUBLICITY', page: this.publicityPage.page, pageSize: this.publicityPage.pageSize }),
          studentAffairsApi.getAidObjections({ status, page: this.objectionPage.page, pageSize: this.objectionPage.pageSize }),
          studentAffairsApi.getAidObjections({ status: 'SUBMITTED', pageSize: 1 }),
          studentAffairsApi.getAidObjections({ status: 'CLOSED', pageSize: 1 })
        ])
        if (seq !== this.loadSeq) return
        if (pu.code !== 0 || !pu.data) throw new Error(pu.message || '公示申请加载失败')
        if (ob.code !== 0 || !ob.data) throw new Error(ob.message || '异议加载失败，请重试')
        this.publicity = pu.data.items || []; this.publicityPage.total = Number(pu.data.total || 0)
        this.objections = ob.data.items || []; this.objectionPage.total = Number(ob.data.total || 0)
        this.statusCounts = pending.code === 0 && closed.code === 0 ? { SUBMITTED: pending.data.total, CLOSED: closed.data.total } : null
      } catch (e) { if (seq === this.loadSeq) this.errorMessage = e.message || '加载失败，请重试' }
      finally { if (seq === this.loadSeq) this.loading = false }
    },
    setStatus(k) { if (this.objStatus === k) return; this.objStatus = k; this.objectionPage.page = 1; this.load() },
    objecte(a) {
      this.objDlg = { visible: true, applyId: a.applyId, who: a.realName || a.studentNo || '该生', objectorName: '' }
    },
    async submitObjection({ reason }) {
      if (this.acting) return
      const d = this.objDlg
      this.acting = d.applyId
      try {
        const res = await studentAffairsApi.submitAidObjection(d.applyId, {
          reason: reason.trim(), objectorName: d.objectorName.trim() || undefined
        })
        if (res.code === 0) { d.visible = false; toast.success('异议已提交'); await this.load() } else toast.error(res.message || '提交失败')
      } catch (e) { toast.error(e.message || '请求结果暂不确定，请刷新核对') }
      finally { this.acting = '' }
    },
    review(o) {
      if (this.acting || !o.allowedActions?.includes('REVIEW')) return
      this.revDlg = {
        visible: true,
        objectionId: o.objectionId,
        who: o.realName || o.studentNo || '该生', reason: o.reason,
        result: 'OVERRULED',
        version: Number(o.version || 0)
      }
    },
    async submitReview({ reason }) {
      if (this.acting) return
      const d = this.revDlg
      this.acting = d.objectionId
      const res = await reviewAidObjectionVersioned(d.objectionId, d.result, reason.trim(), d.version)
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
.ob-intake { margin: 12px 0 20px; border: 1px solid var(--border-light); border-radius: 10px; padding: 12px 16px; background: var(--bg-card); }.ob-intake summary { cursor: pointer; font-weight: 600; }.ob-intake summary span { margin-left: 12px; color: var(--text-tertiary); font-size: 12px; font-weight: 400; }.ob-intake[open] summary { margin-bottom: 16px; }.ob-review-context { line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
