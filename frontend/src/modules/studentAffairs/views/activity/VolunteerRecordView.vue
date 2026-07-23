<template>
  <AppPageShell
    title="志愿服务时长"
    subtitle="校外/线下志愿时长补录与认定；认定后计入第二课堂志愿时长（进学生画像，供评优只读引用）。"
    role-name="团委 / 学工处"
    data-scope-name="按数据范围（辅导员限本班）"
    watermark-purpose="志愿服务时长认定"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载志愿记录..." @retry="load"
                    @back="$router.push('/admin/student-affairs/activity')">
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton :allowed="canBtn('studentAffairs.activity.create')" code="studentAffairs.activity.create" :loading="saving" @click="openForm">补录时长</AppPermissionButton>
      </div>

      <AppSectionCard v-if="formVisible" title="补录志愿时长">
        <div class="vf-grid">
          <div class="vf-field"><span>学生 *</span><AppStudentPicker v-model="form.studentId" placeholder="按姓名 / 学号搜索学生" /></div>
          <label class="vf-field"><span>服务名称 *</span><AppTextInput v-model="form.serviceName" placeholder="如：社区图书整理" /></label>
          <label class="vf-field"><span>时长(小时) *</span><AppNumberInput v-model="form.hours" :min="0" :step="0.5" /></label>
          <label class="vf-field"><span>服务单位</span><AppTextInput v-model="form.orgName" placeholder="如：社区服务中心" /></label>
          <label class="vf-field"><span>服务日期</span><AppDatePicker v-model="form.serviceDate" /></label>
        </div>
        <p v-if="form.error" class="vf-error">{{ form.error }}</p>
        <div class="vf-actions">
          <button type="button" class="vf-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton :allowed="canBtn('studentAffairs.activity.create')" code="studentAffairs.activity.create" :loading="saving" @click="save">提交</AppPermissionButton>
        </div>
      </AppSectionCard>

      <AppSectionCard title="志愿时长记录">
        <div class="vf-filters">
          <button v-for="f in statusFilters" :key="f.key" type="button" class="vf-chip"
                  :class="{ 'is-on': activeStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
        </div>
        <DataTable v-if="items.length" :columns="recordColumns" :rows="items" row-key="recordId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span></template>
          <template #cell-serviceName="{ row }">{{ row.serviceName }}</template>
          <template #cell-org="{ row }"><span class="vf-org">{{ row.orgName || '—' }}</span></template>
          <template #cell-hours="{ row }">{{ row.hours }} h</template>
          <template #cell-status="{ row }">
            <StatusTag :type="statusType(row.status)" :label="row.statusLabel || row.status" dot />
            <em v-if="row.status==='REJECTED' && row.rejectReason" class="vf-reason">{{ row.rejectReason }}</em>
          </template>
          <template #cell-actions="{ row }">
            <div class="vf-ops">
              <template v-if="row.status==='PENDING'">
                <AppPermissionButton :allowed="canBtn('studentAffairs.activity.confirm')" code="studentAffairs.activity.confirm" size="sm" :loading="acting===row.recordId" @click="confirm(row)">认定</AppPermissionButton>
                <AppPermissionButton :allowed="canBtn('studentAffairs.activity.confirm')" code="studentAffairs.activity.confirm" size="sm" variant="secondary" danger :loading="acting===row.recordId" @click="reject(row)">驳回</AppPermissionButton>
              </template>
              <span v-else class="vf-dash">—</span>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前范围与筛选下暂无志愿记录</p>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 驳回原因：无「志愿服务记录驳回」口径词条，不强行套其他场景的模板 -->
    <AppConfirmDialog
      v-model:visible="rejDlg.visible" title="驳回志愿服务记录" type="danger" confirm-text="确认驳回"
      require-reason :reason-min-length="5" reason-label="驳回原因（≥5 字）"
      :submitting="acting === rejDlg.recordId" @confirm="submitReject"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppDatePicker, AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell,
  AppPermissionButton, AppSectionCard, AppStatusTag, AppStudentPicker, AppTextInput
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'


const RECORD_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'serviceName', title: '服务名称' },
  { key: 'org', title: '单位' },
  { key: 'hours', title: '时长' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', align: 'right', width: '160px' }
]
const STATUS_FILTERS = [
  { key: '', label: '全部' }, { key: 'PENDING', label: '待认定' },
  { key: 'CONFIRMED', label: '已认定' }, { key: 'REJECTED', label: '已驳回' }
]

export default {
  name: 'VolunteerRecordView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppDatePicker, AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell,
    AppPermissionButton, AppSectionCard, StatusTag: AppStatusTag, AppStudentPicker, AppTextInput, DataTable
  },
  data() {
    return {
      recordColumns: RECORD_COLUMNS,
      loading: true, saving: false, acting: '', errorMessage: '', all: [], items: [],
      activeStatus: '', statusFilters: STATUS_FILTERS,
      formVisible: false, form: this.blankForm(),
      rejDlg: { visible: false, recordId: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const s = (k) => this.all.filter((x) => x.status === k).length
      const hours = this.all.filter((x) => x.status === 'CONFIRMED').reduce((a, x) => a + (Number(x.hours) || 0), 0)
      return [
        { key: 'p', label: '待认定', value: s('PENDING'), accent: 'warning' },
        { key: 'c', label: '已认定', value: s('CONFIRMED'), accent: 'success' },
        { key: 'h', label: '已认定时长合计', value: Math.round(hours * 10) / 10, accent: 'primary' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    blankForm() { return { studentId: '', serviceName: '', hours: null, orgName: '', serviceDate: '', error: '' } },
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getVolunteerRecords({ pageSize: 300 })
      if (res.code === 0 && res.data) {
        this.all = res.data.items || []
        this.applyFilter()
      } else {
        this.errorMessage = res.message || '志愿记录加载失败'
      }
      this.loading = false
    },
    applyFilter() { this.items = this.activeStatus ? this.all.filter((x) => x.status === this.activeStatus) : this.all },
    setStatus(k) { this.activeStatus = k; this.applyFilter() },
    openForm() { this.form = this.blankForm(); this.formVisible = true },
    async save() {
      const m = this.form
      const serviceName = (m.serviceName || '').trim()
      if (!m.studentId || !serviceName || !m.hours) { m.error = '学生、服务名称、时长必填'; return }
      m.error = ''; this.saving = true
      const body = { studentId: Number(m.studentId), serviceName, hours: Number(m.hours) }
      if ((m.orgName || '').trim()) body.orgName = m.orgName.trim()
      if (m.serviceDate) body.serviceDate = m.serviceDate
      const res = await studentAffairsApi.createVolunteerRecord(body)
      this.saving = false
      if (res.code === 0) { toast.success('已提交待认定'); this.formVisible = false; this.load() }
      else m.error = res.message || '提交失败'
    },
    async confirm(r) {
      this.acting = r.recordId
      const res = await studentAffairsApi.confirmVolunteerRecord(r.recordId)
      this.acting = ''
      if (res.code === 0) { toast.success('已认定，计入志愿时长'); this.load() } else toast.error(res.message || '认定失败')
    },
    reject(r) { this.rejDlg = { visible: true, recordId: r.recordId } },
    async submitReject({ reason }) {
      const d = this.rejDlg
      this.acting = d.recordId
      const res = await studentAffairsApi.rejectVolunteerRecord(d.recordId, reason.trim())
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已驳回'); this.load() } else toast.error(res.message || '驳回失败')
    },
    statusType(s) { return ({ PENDING: 'warning', CONFIRMED: 'success', REJECTED: 'danger' })[s] || 'default' }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); flex: 1; min-width: 320px; }
.vf-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: var(--space-3); margin-bottom: var(--space-3); }
.vf-field { display: flex; flex-direction: column; gap: 4px; font-size: var(--font-size-sm); }
.vf-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.vf-error { color: var(--danger-500,#dc2626); font-size: var(--font-size-sm); }
.vf-actions { display: flex; gap: var(--space-3); justify-content: flex-end; }
.vf-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
.vf-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.vf-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.vf-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.vf-org { color: var(--text-secondary); font-size: var(--font-size-sm); }
.vf-reason { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); font-style: normal; }
.vf-ops { display: flex; gap: 6px; }
.vf-dash { color: var(--text-tertiary); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } .vf-grid { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
