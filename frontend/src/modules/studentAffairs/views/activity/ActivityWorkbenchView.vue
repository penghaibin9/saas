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
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton code="studentAffairs.activity.create" :loading="saving" @click="openForm">建活动</AppPermissionButton>
      </div>

      <AppSectionCard v-if="formVisible" title="新建活动">
        <div class="af-grid">
          <label class="af-field"><span>活动名称 *</span><AppTextInput v-model="form.activityName" placeholder="如：2026 迎新晚会" /></label>
          <label class="af-field"><span>类型</span>
            <AppSelect v-model="form.activityType" :options="TYPE_OPTIONS" placeholder="" /></label>
          <label class="af-field"><span>学分类型</span>
            <AppSelect v-model="form.creditType" :options="CREDIT_TYPE_OPTIONS" placeholder="" /></label>
          <label class="af-field"><span>学时/积分/时长</span><AppNumberInput v-model="form.creditValue" :min="0" :step="0.5" placeholder="如：2" /></label>
          <label class="af-field"><span>二课类目</span>
            <AppSelect v-model="form.categoryCode" :options="categoryOptions" placeholder="" /></label>
          <label class="af-field"><span>名额</span><AppNumberInput v-model="form.quota" :min="0" placeholder="空=不限" /></label>
          <label class="af-field"><span>开始时间</span><AppDateTimePicker v-model="form.startAt" role="start" :end-value="form.endAt" /></label>
          <label class="af-field"><span>结束时间</span><AppDateTimePicker v-model="form.endAt" role="end" :start-value="form.startAt" /></label>
          <label class="af-field af-field--wide"><span>地点</span><AppTextInput v-model="form.location" /></label>
        </div>
        <p v-if="form.error" class="af-error">{{ form.error }}</p>
        <div class="af-actions">
          <button type="button" class="af-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton code="studentAffairs.activity.create" :loading="saving" @click="save">保存草稿</AppPermissionButton>
        </div>
      </AppSectionCard>

      <AppSectionCard title="活动列表">
        <div class="af-filters">
          <button v-for="f in statusFilters" :key="f.key" type="button" class="af-chip"
                  :class="{ 'is-on': activeStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
        </div>
        <table class="sa-table">
          <thead><tr><th>活动</th><th>类型</th><th>学分</th><th>报名</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="a in items" :key="a.activityId">
              <td><strong>{{ a.activityName }}</strong><em v-if="a.startAt" class="af-time">{{ (a.startAt||'').slice(0,16).replace('T',' ') }}</em></td>
              <td>{{ typeLabel(a.activityType) }}</td>
              <td>{{ a.creditValue != null ? (a.creditValue + creditUnit(a.creditType)) : '—' }}</td>
              <td>{{ a.signupCount != null ? a.signupCount : 0 }}</td>
              <td><StatusTag :type="statusType(a.status)" :label="a.statusLabel || a.status" dot /></td>
              <td class="af-ops">
                <AppPermissionButton v-if="a.status==='DRAFT'" code="studentAffairs.activity.publish" size="sm" variant="secondary" :loading="acting===a.activityId" @click="act(a,'publish','PUBLISH')">发布</AppPermissionButton>
                <AppPermissionButton v-if="a.status==='PUBLISHED'" code="studentAffairs.activity.publish" size="sm" variant="secondary" :loading="acting===a.activityId" @click="act(a,'transition','ENROLL_CLOSE')">报名截止</AppPermissionButton>
                <AppPermissionButton v-if="a.status==='ENROLL_CLOSED'" code="studentAffairs.activity.publish" size="sm" variant="secondary" :loading="acting===a.activityId" @click="act(a,'transition','START')">开始</AppPermissionButton>
                <AppPermissionButton v-if="a.status==='ONGOING'" code="studentAffairs.activity.publish" size="sm" variant="secondary" :loading="acting===a.activityId" @click="act(a,'transition','FINISH')">结束</AppPermissionButton>
                <AppPermissionButton v-if="a.status==='FINISHED'" code="studentAffairs.activity.confirm" size="sm" :loading="acting===a.activityId" @click="act(a,'confirm')">确认名单</AppPermissionButton>
                <AppPermissionButton v-if="a.status==='CONFIRMED'" code="studentAffairs.activity.confirm" size="sm" variant="secondary" @click="act(a,'archive')">归档</AppPermissionButton>
                <button type="button" class="af-link" @click="openParticipants(a)">名单</button>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="sa-empty">暂无活动，点右上「建活动」</td></tr>
          </tbody>
        </table>
      </AppSectionCard>

      <div v-if="pv.visible" class="af-mask" @click.self="pv.visible=false">
        <div class="af-modal">
          <h3 class="af-modal__title">{{ pv.name }} · 名单（{{ pv.list.length }}）</h3>
          <table class="sa-table"><thead><tr><th>学生</th><th>学号</th><th>状态</th><th>签到</th></tr></thead>
            <tbody>
              <tr v-for="p in pv.list" :key="p.signupId">
                <td>{{ p.realName || ('#'+p.studentId) }}</td><td>{{ p.studentNo||'—' }}</td>
                <td>{{ signupLabel(p.signupStatus) }}</td><td>{{ (p.checkinAt||'').slice(0,16).replace('T',' ')||'—' }}</td>
              </tr>
              <tr v-if="!pv.list.length"><td colspan="4" class="sa-empty">暂无报名</td></tr>
            </tbody></table>
          <div class="af-actions"><button type="button" class="af-btn" @click="pv.visible=false">关闭</button></div>
        </div>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppDateTimePicker, AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell, AppPermissionButton,
  AppSectionCard, AppSelect, AppStatusTag, AppTextInput
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

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
  components: {
    AppDateTimePicker, AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell, AppPermissionButton,
    AppSectionCard, AppSelect, StatusTag: AppStatusTag, AppTextInput
  },
  data() {
    return {
      loading: true, saving: false, acting: '', errorMessage: '', all: [], items: [], categories: [],
      activeStatus: '', statusFilters: STATUS_FILTERS,
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
      const s = (k) => this.all.filter((a) => a.status === k).length
      return [
        { key: 't', label: '活动总数', value: this.all.length, accent: 'primary' },
        { key: 'p', label: '报名中', value: s('PUBLISHED'), accent: 'success' },
        { key: 'f', label: '待确认', value: s('FINISHED'), accent: 'warning' },
        { key: 'c', label: '已确认', value: s('CONFIRMED'), accent: 'info' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    blankForm() { return { activityName: '', activityType: 'ACTIVITY', creditType: 'SECOND_CLASS', creditValue: null, categoryCode: '', quota: null, startAt: '', endAt: '', location: '', error: '' } },
    async load() {
      this.loading = true; this.errorMessage = ''
      const [res, cat] = await Promise.all([
        studentAffairsApi.getActivities({ status: this.activeStatus, pageSize: 200 }),
        studentAffairsApi.getCreditCategories()
      ])
      if (res.code === 0 && res.data) {
        this.all = res.data.items || []
        this.items = this.all
        this.categories = (cat.code === 0 && cat.data) ? (cat.data.items || []) : []
      } else {
        this.errorMessage = res.message || '活动加载失败'
      }
      this.loading = false
    },
    setStatus(k) { if (this.activeStatus === k) return; this.activeStatus = k; this.load() },
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
      let res
      if (kind === 'publish') res = await studentAffairsApi.publishActivity(a.activityId, arg)
      else if (kind === 'transition') res = await studentAffairsApi.transitionActivity(a.activityId, arg)
      else if (kind === 'confirm') res = await studentAffairsApi.confirmActivity(a.activityId)
      else if (kind === 'archive') res = await studentAffairsApi.archiveActivity(a.activityId)
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
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: var(--space-4); flex: 1; min-width: 320px; }
.af-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: var(--space-3); margin-bottom: var(--space-3); }
.af-field { display: flex; flex-direction: column; gap: 4px; font-size: var(--font-size-sm); }
.af-field--wide { grid-column: span 3; }
.af-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.af-error { color: var(--danger-500,#dc2626); font-size: var(--font-size-sm); }
.af-actions { display: flex; gap: var(--space-3); justify-content: flex-end; margin-top: var(--space-2); }
.af-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
.af-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.af-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.af-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.af-time { color: var(--text-tertiary); font-size: var(--font-size-xs); font-style: normal; margin-left: 8px; }
.af-ops { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.af-link { border: none; background: none; color: var(--color-primary); cursor: pointer; font-size: var(--font-size-sm); }
.af-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.af-modal { width: 560px; max-width: calc(100vw - 32px); background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-5); max-height: 80vh; overflow: auto; }
.af-modal__title { margin: 0 0 var(--space-3); font-size: var(--font-size-lg); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } .af-grid { grid-template-columns: 1fr; } .af-field--wide { grid-column: span 1; } }
</style>
