<template>
  <AppPageShell
    title="学生活动管理"
    subtitle="活动发布→报名→签到→确认名单→生成第二课堂学时/积分（进学生画像·供综测评优引用）。"
    role-name="团委 / 学工处 / 学院"
    data-scope-name="发布方范围（团委全校/学院本院）"
    watermark-purpose="学生活动管理"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载活动..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <section class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">当前活动运营</span>
          <h2 class="sa-summary-strip__title">报名中 {{ statusCount('PUBLISHED') }} 场，待确认名单 {{ statusCount('FINISHED') }} 场</h2>
          <p class="sa-summary-strip__text">活动必须按顺序完成发布、报名截止、开始、结束和名单确认。只有确认名单后才生成正式第二课堂学时、积分或志愿时长。</p>
        </div>
        <div class="sa-summary-strip__actions">
          <AppPermissionButton :allowed="canBtn('studentAffairs.activity.create')" code="studentAffairs.activity.create" :loading="saving" @click="openForm">新建活动</AppPermissionButton>
        </div>
      </section>

      <div class="sa-workflow-strip" aria-label="学生活动流程">
        <div class="sa-workflow-step" data-step="1"><strong>创建草稿</strong><br>配置活动、名额、时间和积分规则</div>
        <div class="sa-workflow-step" data-step="2"><strong>发布报名</strong><br>学生报名，必要时进入候补队列</div>
        <div class="sa-workflow-step" data-step="3"><strong>开始签到</strong><br>活动开始后使用可信签到方式</div>
        <div class="sa-workflow-step" data-step="4"><strong>结束确认</strong><br>结束后核对名单与签到记录</div>
        <div class="sa-workflow-step" data-step="5"><strong>积分入账</strong><br>确认名单后生成正式积分并归档</div>
      </div>

      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton :allowed="canBtn('studentAffairs.activity.create')" code="studentAffairs.activity.create" :loading="saving" @click="openForm">建活动</AppPermissionButton>
      </div>

      <AppSectionCard v-if="formVisible" title="新建活动草稿">
        <div class="af-form-note">先填写活动基本信息，再配置第二课堂规则、名额和时间地点。保存后仅生成草稿，不会立即开放报名。</div>
        <div class="af-form-section">
          <h3>基本信息</h3>
          <div class="af-grid">
            <label class="af-field af-field--wide"><span>活动名称 *</span><AppTextInput v-model="form.activityName" placeholder="如：2026 迎新晚会" /></label>
            <label class="af-field"><span>活动类型</span><AppSelect v-model="form.activityType" :options="TYPE_OPTIONS" placeholder="" /></label>
            <label class="af-field"><span>地点</span><AppTextInput v-model="form.location" placeholder="如：学校大礼堂" /></label>
            <label class="af-field"><span>名额</span><AppNumberInput v-model="form.quota" :min="0" placeholder="空=不限" /></label>
          </div>
        </div>
        <div class="af-form-section">
          <h3>第二课堂规则</h3>
          <div class="af-grid">
            <label class="af-field"><span>学分类型</span><AppSelect v-model="form.creditType" :options="CREDIT_TYPE_OPTIONS" placeholder="" /></label>
            <label class="af-field"><span>学时 / 积分 / 时长</span><AppNumberInput v-model="form.creditValue" :min="0" :step="0.5" placeholder="如：2" /></label>
            <label class="af-field"><span>二课类目</span><AppSelect v-model="form.categoryCode" :options="categoryOptions" placeholder="" /></label>
          </div>
        </div>
        <div class="af-form-section">
          <h3>时间安排</h3>
          <div class="af-grid af-grid--two">
            <label class="af-field"><span>开始时间</span><AppDateTimePicker v-model="form.startAt" role="start" :end-value="form.endAt" /></label>
            <label class="af-field"><span>结束时间</span><AppDateTimePicker v-model="form.endAt" role="end" :start-value="form.startAt" /></label>
          </div>
        </div>
        <p v-if="form.error" class="af-error">{{ form.error }}</p>
        <div class="af-actions">
          <button type="button" class="af-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton :allowed="canBtn('studentAffairs.activity.create')" code="studentAffairs.activity.create" :loading="saving" @click="save">保存草稿</AppPermissionButton>
        </div>
      </AppSectionCard>

      <AppSectionCard title="活动列表与阶段推进">
        <p class="af-section-hint">优先处理“待确认”活动。操作按钮按当前状态显示，必须按发布、截止、开始、结束、确认名单、归档的顺序推进。</p>
        <div class="af-filters sa-filter-bar">
          <AppSelect v-model="activeType" :options="activityTypeFilters" placeholder="全部类型"
                     @change="setType" />
          <button v-for="f in statusFilters" :key="f.key" type="button" class="af-chip"
                  :class="{ 'is-on': activeStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}<em>{{ statusCount(f.key) }}</em></button>
        </div>
        <DataTable v-if="items.length" :columns="activityColumns" :rows="items" row-key="activityId">
          <template #cell-name="{ row }">
            <span class="mp-cell-main">{{ row.activityName }}</span>
            <em v-if="row.startAt" class="af-time">{{ (row.startAt||'').slice(0,16).replace('T',' ') }}</em>
          </template>
          <template #cell-type="{ row }">{{ typeLabel(row.activityType) }}</template>
          <template #cell-credit="{ row }"><span class="af-credit">{{ row.creditValue != null ? (row.creditValue + creditUnit(row.creditType)) : '—' }}</span></template>
          <template #cell-signups="{ row }"><span class="af-signups">{{ row.signupCount != null ? row.signupCount : 0 }}</span></template>
          <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="row.statusLabel || row.status" dot /></template>
          <template #cell-actions="{ row }">
            <div class="af-ops">
              <AppPermissionButton :allowed="canBtn('studentAffairs.activity.publish')" v-if="row.status==='DRAFT'" code="studentAffairs.activity.publish" size="sm" variant="secondary" :loading="acting===row.activityId" @click="act(row,'publish','PUBLISH')">发布</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.activity.publish')" v-if="row.status==='PUBLISHED'" code="studentAffairs.activity.publish" size="sm" variant="secondary" :loading="acting===row.activityId" @click="act(row,'transition','ENROLL_CLOSE')">报名截止</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.activity.publish')" v-if="row.status==='ENROLL_CLOSED'" code="studentAffairs.activity.publish" size="sm" variant="secondary" :loading="acting===row.activityId" @click="act(row,'transition','START')">开始</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.activity.publish')" v-if="row.status==='ONGOING'" code="studentAffairs.activity.publish" size="sm" variant="secondary" :loading="acting===row.activityId" @click="act(row,'transition','FINISH')">结束</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.activity.confirm')" v-if="row.status==='FINISHED'" code="studentAffairs.activity.confirm" size="sm" :loading="acting===row.activityId" @click="act(row,'confirm')">确认名单</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.activity.confirm')" v-if="row.status==='CONFIRMED'" code="studentAffairs.activity.confirm" size="sm" variant="secondary" @click="act(row,'archive')">归档</AppPermissionButton>
              <button type="button" class="af-link" @click="openParticipants(row)">查看名单</button>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前筛选下暂无活动。可清除筛选，或点击“新建活动”创建草稿。</p>
        <AppPagination v-model:page="pagination.page" v-model:pageSize="pagination.pageSize"
                       :total="pagination.total" @change="load" />
      </AppSectionCard>

      <AppDrawer :visible="pv.visible" :title="pv.name + ' · 名单（' + pv.list.length + '）'" mode="modal" size="xlarge" @update:visible="pv.visible = $event">
        <div class="participant-note">确认名单前请核对报名状态与签到时间；名单确认后会生成正式第二课堂记录。</div>
        <DataTable v-if="pv.list.length" :columns="participantColumns" :rows="pv.list" row-key="signupId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('#'+row.studentId) }}</span></template>
          <template #cell-studentNo="{ row }">{{ row.studentNo||'—' }}</template>
          <template #cell-status="{ row }">{{ signupLabel(row.signupStatus) }}</template>
          <template #cell-checkin="{ row }">{{ (row.checkinAt||'').slice(0,16).replace('T',' ')||'—' }}</template>
        </DataTable>
        <p v-else class="sa-empty">暂无报名记录。</p>
        <template #footer>
          <AppButton @click="pv.visible = false">关闭</AppButton>
        </template>
      </AppDrawer>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppDateTimePicker, AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell, AppPermissionButton,
  AppPagination, AppSectionCard, AppSelect, AppStatusTag, AppTextInput
} from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const ACTIVITY_COLUMNS = [
  { key: 'name', title: '活动' },
  { key: 'type', title: '类型' },
  { key: 'credit', title: '学分' },
  { key: 'signups', title: '报名' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', align: 'right', width: '320px' }
]
const PARTICIPANT_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'studentNo', title: '学号' },
  { key: 'status', title: '状态' },
  { key: 'checkin', title: '签到' }
]
const TYPE = { ACTIVITY: '活动', VOLUNTEER: '志愿服务', LECTURE: '讲座报告', COMPETITION: '竞赛', PRACTICE: '社会实践' }
const TYPE_OPTIONS = Object.entries(TYPE).map(([value, label]) => ({ value, label }))
const CREDIT_TYPE_OPTIONS = [
  { value: 'SECOND_CLASS', label: '第二课堂学时' }, { value: 'MORAL', label: '德育积分' }, { value: 'VOLUNTEER_HOUR', label: '志愿时长' }
]
const STATUS_FILTERS = [
  { key: '', label: '全部' }, { key: 'DRAFT', label: '草稿' }, { key: 'PUBLISHED', label: '报名中' },
  { key: 'ONGOING', label: '进行中' }, { key: 'FINISHED', label: '待确认' }, { key: 'CONFIRMED', label: '已确认' }
]

export default {
  name: 'ActivityWorkbenchView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppDateTimePicker, AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell, AppPermissionButton,
    AppPagination, AppSectionCard, AppSelect, StatusTag: AppStatusTag, AppTextInput, DataTable, AppButton, AppDrawer
  },
  data() {
    return {
      activityColumns: ACTIVITY_COLUMNS,
      participantColumns: PARTICIPANT_COLUMNS,
      loading: true, saving: false, acting: '', errorMessage: '', all: [], items: [], statusCounts: null, categories: [],
      activeStatus: '', statusFilters: STATUS_FILTERS,
      activeType: '', activityTypeFilters: [{ value: '', label: '全部类型' }, ...TYPE_OPTIONS],
      pagination: { page: 1, pageSize: 20, total: 0 },
      formVisible: false, form: this.blankForm(),
      pv: { visible: false, name: '', list: [] }
    }
  },
  computed: {
    TYPE_OPTIONS: () => TYPE_OPTIONS,
    CREDIT_TYPE_OPTIONS: () => CREDIT_TYPE_OPTIONS,
    categoryOptions() {
      return [{ value: '', label: '（不限）' }].concat(
        this.categories.map((c) => ({ value: c.categoryCode, label: c.categoryName }))
      )
    },
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const s = (k) => this.statusCount(k)
      return [
        { key: 't', label: '活动总数', value: this.statusCount(''), accent: 'primary' },
        { key: 'p', label: '报名中', value: s('PUBLISHED'), accent: 'success' },
        { key: 'f', label: '待确认', value: s('FINISHED'), accent: 'warning' },
        { key: 'c', label: '已确认', value: s('CONFIRMED'), accent: 'info' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    blankForm() { return { activityName: '', activityType: 'ACTIVITY', creditType: 'SECOND_CLASS', creditValue: null, categoryCode: '', quota: null, startAt: '', endAt: '', location: '', error: '' } },
    async load() {
      this.loading = true; this.errorMessage = ''
      this.statusCounts = null
      const [res, cat] = await Promise.all([
        studentAffairsApi.getActivities({
          status: this.activeStatus, activityType: this.activeType,
          page: this.pagination.page, pageSize: this.pagination.pageSize
        }),
        studentAffairsApi.getCreditCategories()
      ])
      if (res.code === 0 && res.data) {
        this.all = res.data.items || []
        this.items = this.all
        this.pagination.total = Number(res.data.total || 0)
        this.statusCounts = res.data.statusCounts || null
        this.categories = (cat.code === 0 && cat.data) ? (cat.data.items || []) : []
      } else {
        this.errorMessage = res.message || '活动加载失败'
      }
      this.loading = false
    },
    setStatus(k) { if (this.activeStatus === k) return; this.activeStatus = k; this.pagination.page = 1; this.load() },
    setType() { this.pagination.page = 1; this.load() },
    statusCount(key) {
      if (this.statusCounts === null) return '—'
      return this.statusCounts[key || 'ALL'] || 0
    },
    openForm() { this.form = this.blankForm(); this.formVisible = true },
    async save() {
      const m = this.form
      const activityName = (m.activityName || '').trim()
      if (!activityName) { m.error = '活动名称必填'; return }
      m.error = ''; this.saving = true
      const body = { activityName, activityType: m.activityType, creditType: m.creditType }
      if (m.creditValue != null && m.creditValue !== '') body.creditValue = Number(m.creditValue)
      if (m.categoryCode) body.categoryCode = m.categoryCode
      if (m.quota != null && m.quota !== '') body.quota = Number(m.quota)
      if (m.startAt) body.startAt = m.startAt
      if (m.endAt) body.endAt = m.endAt
      if ((m.location || '').trim()) body.location = m.location.trim()
      const res = await studentAffairsApi.createActivity(body)
      this.saving = false
      if (res.code === 0) { toast.success('活动草稿已创建'); this.formVisible = false; this.load() }
      else m.error = res.message || '创建失败'
    },
    async act(a, kind, arg) {
      this.acting = a.activityId
      const ver = a.version
      let res
      if (kind === 'publish') res = await studentAffairsApi.publishActivity(a.activityId, arg, '', ver)
      else if (kind === 'transition') res = await studentAffairsApi.transitionActivity(a.activityId, arg, ver)
      else if (kind === 'confirm') res = await studentAffairsApi.confirmActivity(a.activityId, ver)
      else if (kind === 'archive') res = await studentAffairsApi.archiveActivity(a.activityId, ver)
      this.acting = ''
      if (res && res.code === 0) {
        toast.success(kind === 'confirm' ? `已确认，生成 ${res.data.creditsGranted || 0} 条学分` : '操作成功')
        this.load()
      } else {
        toast.error((res && res.message) || '操作失败')
      }
    },
    async openParticipants(a) {
      this.pv = { visible: true, name: a.activityName, list: [] }
      const res = await studentAffairsApi.getActivityParticipants(a.activityId)
      if (res.code === 0 && res.data) this.pv.list = res.data.items || []
    },
    typeLabel(t) { return TYPE[t] || t },
    creditUnit(t) { return t === 'VOLUNTEER_HOUR' ? ' 时长' : (t === 'MORAL' ? ' 积分' : ' 学时') },
    statusType(s) {
      if (s === 'CONFIRMED' || s === 'ARCHIVED') return 'success'
      if (s === 'CANCELLED') return 'default'
      if (s === 'FINISHED') return 'warning'
      if (s === 'DRAFT') return 'default'
      return 'processing'
    },
    signupLabel(s) { return ({ ENROLLED: '已报名', WAITLIST: '候补', CANCELLED: '已取消', CHECKED_IN: '已签到', CONFIRMED: '已确认' })[s] || s }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: var(--space-3); flex: 1; min-width: 320px; }
.af-form-note, .participant-note { margin-bottom: var(--space-4); padding: 10px 12px; border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.af-form-section { margin-bottom: var(--space-4); padding-bottom: var(--space-4); border-bottom: 1px solid var(--border-light); }
.af-form-section:last-of-type { border-bottom: 0; }
.af-form-section h3 { margin: 0 0 var(--space-3); color: var(--text-primary); font-size: var(--font-size-sm); }
.af-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); }
.af-grid--two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.af-field { display: flex; flex-direction: column; gap: 5px; min-width: 0; font-size: var(--font-size-sm); }
.af-field--wide { grid-column: span 3; }
.af-error { margin: 0; padding: 9px 11px; border-radius: var(--radius-md); background: var(--danger-50); color: var(--danger-700, #b91c1c); font-size: var(--font-size-sm); }
.af-actions { display: flex; gap: var(--space-3); justify-content: flex-end; margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--border-light); }
.af-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
.af-section-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.af-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.af-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 5px 13px; font-size: var(--font-size-sm); cursor: pointer; }
.af-chip em { margin-left: 5px; font-style: normal; opacity: .72; }
.af-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.af-time { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); font-style: normal; }
.af-credit { color: var(--primary-700); font-weight: 600; }
.af-signups { display: inline-grid; place-items: center; min-width: 30px; height: 26px; border-radius: var(--radius-full); background: var(--bg-section); color: var(--text-primary); font-weight: 600; font-variant-numeric: tabular-nums; }
.af-ops { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
.af-link { border: none; background: none; color: var(--color-primary); cursor: pointer; font-size: var(--font-size-sm); font-weight: 600; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } .af-grid, .af-grid--two { grid-template-columns: 1fr; } .af-field--wide { grid-column: span 1; } }
@media (max-width: 640px) { .sa-grid--metrics { grid-template-columns: 1fr; } .af-actions { align-items: stretch; flex-direction: column-reverse; } .af-actions > * { width: 100%; } }
@import '@/styles/module-page.css';
</style>
