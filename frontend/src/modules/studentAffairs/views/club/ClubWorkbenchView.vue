<template>
  <AppPageShell
    title="社团管理"
    subtitle="建社→审批→成员/任职→年审→注销全流程；社团档案与成员台账供团委掌握。"
    role-name="团委 / 学工处"
    data-scope-name="按租户（团委全校）"
    watermark-purpose="学生社团管理"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载社团..." @retry="load"
                    @back="$router.push('/admin/student-affairs/activity')">
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton code="studentAffairs.club.manage" :loading="saving" @click="openForm">建社团</AppPermissionButton>
      </div>

      <AppSectionCard v-if="formVisible" title="新建社团">
        <div class="cf-grid">
          <label class="cf-field"><span>社团名称 *</span><AppTextInput v-model="form.clubName" /></label>
          <label class="cf-field"><span>类型</span>
            <AppSelect v-model="form.clubType" :options="TYPE_OPTIONS" placeholder="" /></label>
          <label class="cf-field"><span>指导教师</span><AppTextInput v-model="form.advisorName" /></label>
        </div>
        <p v-if="form.error" class="cf-error">{{ form.error }}</p>
        <div class="cf-actions">
          <button type="button" class="cf-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton code="studentAffairs.club.manage" :loading="saving" @click="save">提交</AppPermissionButton>
        </div>
      </AppSectionCard>

      <div class="cf-layout">
        <AppSectionCard title="社团列表" class="cf-list">
          <div class="cf-filters">
            <button v-for="f in statusFilters" :key="f.key" type="button" class="cf-chip"
                    :class="{ 'is-on': activeStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
          </div>
          <ul class="cf-clubs">
            <li v-for="c in items" :key="c.clubId" class="cf-club" :class="{ 'is-active': sel && sel.clubId === c.clubId }" @click="select(c)">
              <div class="cf-club__top"><span class="cf-club__name">{{ c.clubName }}</span>
                <StatusTag :type="statusType(c.status)" :label="c.statusLabel" dot /></div>
              <div class="cf-club__meta">{{ TYPES[c.clubType] || c.clubType }} · 成员 {{ c.memberCount }} · {{ c.advisorName || '无指导老师' }}</div>
              <div class="cf-club__ops" @click.stop>
                <AppPermissionButton v-if="c.status==='PENDING'" code="studentAffairs.club.manage" size="sm" :loading="acting===c.clubId" @click="review(c,'APPROVE')">通过</AppPermissionButton>
                <AppPermissionButton v-if="c.status==='PENDING'" code="studentAffairs.club.manage" size="sm" variant="secondary" danger :loading="acting===c.clubId" @click="review(c,'REJECT')">驳回</AppPermissionButton>
                <AppPermissionButton v-if="c.status==='ACTIVE'" code="studentAffairs.club.manage" size="sm" variant="secondary" danger @click="disband(c)">注销</AppPermissionButton>
              </div>
            </li>
            <li v-if="!items.length" class="cf-empty">暂无社团，点右上「建社团」</li>
          </ul>
        </AppSectionCard>

        <AppSectionCard :title="sel ? (sel.clubName + ' · 成员与年审') : '社团详情'" class="cf-detail">
          <p v-if="!sel" class="cf-hint">从左侧选择一个社团查看成员与年审。</p>
          <template v-else>
            <div class="cf-subhead">
              <h4>成员（{{ members.length }}）</h4>
              <AppPermissionButton v-if="sel.status==='ACTIVE'" code="studentAffairs.club.manage" size="sm" @click="openMember">增补成员</AppPermissionButton>
            </div>
            <div v-if="memberForm.visible" class="cf-inline">
              <AppStudentPicker v-model="memberForm.studentId" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索学生" />
              <AppSelect v-model="memberForm.role" :options="ROLE_OPTIONS" placeholder="" />
              <AppPermissionButton code="studentAffairs.club.manage" size="sm" @click="addMember">加入</AppPermissionButton>
            </div>
            <DataTable v-if="members.length" :columns="memberColumns" :rows="members" row-key="memberId">
              <template #cell-student="{ row }">{{ row.realName || ('#'+row.studentId) }}</template>
              <template #cell-role="{ row }">{{ ROLES[row.role] || row.role }}</template>
              <template #cell-actions="{ row }">
                <AppPermissionButton v-if="sel.status==='ACTIVE'" code="studentAffairs.club.manage" size="sm" variant="secondary" danger @click="removeMember(row)">退社</AppPermissionButton>
              </template>
            </DataTable>
            <p v-else class="sa-empty">暂无成员</p>

            <div class="cf-subhead">
              <h4>年审记录</h4>
              <AppPermissionButton v-if="sel.status==='ACTIVE'" code="studentAffairs.club.manage" size="sm" @click="openReview">登记年审</AppPermissionButton>
            </div>
            <div v-if="reviewForm.visible" class="cf-inline">
              <AppTextInput v-model="reviewForm.reviewYear" placeholder="学年 如 2025-2026" />
              <AppSelect v-model="reviewForm.result" :options="REVIEW_RESULT_OPTIONS" placeholder="" />
              <AppPermissionButton code="studentAffairs.club.manage" size="sm" @click="addReview">提交</AppPermissionButton>
            </div>
            <DataTable v-if="reviews.length" :columns="reviewColumns" :rows="reviews" row-key="reviewId">
              <template #cell-year="{ row }">{{ row.reviewYear }}</template>
              <template #cell-result="{ row }">{{ reviewLabel(row.result) }}</template>
              <template #cell-activityCount="{ row }">{{ row.activityCount != null ? row.activityCount : '—' }}</template>
              <template #cell-reviewer="{ row }">{{ row.reviewerName || '—' }}</template>
            </DataTable>
            <p v-else class="sa-empty">暂无年审</p>
          </template>
        </AppSectionCard>
      </div>
    </AppGlobalState>

    <!-- 社团审核驳回 / 注销：无社团口径词条，不套用其他场景模板 -->
    <AppConfirmDialog
      v-model:visible="rejDlg.visible" title="驳回社团申请" type="danger" confirm-text="确认驳回"
      require-reason :reason-min-length="5" reason-label="驳回原因（≥5 字）"
      :submitting="acting === rejDlg.clubId" @confirm="submitReject"
    />
    <AppConfirmDialog
      v-model:visible="disDlg.visible" :title="`注销社团 · ${disDlg.clubName}`" type="danger" confirm-text="确认注销"
      require-reason :reason-min-length="5" reason-label="注销原因（≥5 字）"
      description="注销后该社团停止活动，成员关系一并失效。原因记入台账。"
      :submitting="acting === disDlg.clubId" @confirm="submitDisband"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard,
  AppSelect, AppStatusTag, AppStudentPicker, AppTextInput
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const MEMBER_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'role', title: '任职' },
  { key: 'actions', title: '操作', align: 'right', width: '100px' }
]
const REVIEW_COLUMNS = [
  { key: 'year', title: '学年' },
  { key: 'result', title: '结果' },
  { key: 'activityCount', title: '活动数' },
  { key: 'reviewer', title: '审核人' }
]

const TYPES = { INTEREST: '兴趣', ACADEMIC: '学术', SPORTS: '体育', ARTS: '文艺', VOLUNTEER: '公益', PRACTICE: '实践' }
const ROLES = { MEMBER: '成员', DEPT_HEAD: '部长', VICE_PRESIDENT: '副社长', PRESIDENT: '社长' }
const TYPE_OPTIONS = Object.entries(TYPES).map(([value, label]) => ({ value, label }))
const ROLE_OPTIONS = Object.entries(ROLES).map(([value, label]) => ({ value, label }))
const REVIEW_RESULT_OPTIONS = [
  { value: 'PASS', label: '通过' }, { value: 'CONDITIONAL', label: '限期整改' }, { value: 'FAIL', label: '不通过' }
]
const STATUS_FILTERS = [
  { key: '', label: '全部' }, { key: 'PENDING', label: '待审批' }, { key: 'ACTIVE', label: '运营中' },
  { key: 'SUSPENDED', label: '暂停' }, { key: 'DISBANDED', label: '已注销' }
]

export default {
  name: 'ClubWorkbenchView',
  components: {
    AppConfirmDialog, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard,
    AppSelect, StatusTag: AppStatusTag, AppStudentPicker, AppTextInput, DataTable
  },
  data() {
    return {
      memberColumns: MEMBER_COLUMNS,
      reviewColumns: REVIEW_COLUMNS,
      loading: true, saving: false, acting: '', errorMessage: '', all: [], items: [],
      activeStatus: '', statusFilters: STATUS_FILTERS, TYPES, ROLES,
      rejDlg: { visible: false, clubId: '' },
      disDlg: { visible: false, clubId: '', clubName: '' },
      formVisible: false, form: { clubName: '', clubType: 'INTEREST', advisorName: '', error: '' },
      sel: null, members: [], reviews: [],
      memberForm: { visible: false, studentId: null, role: 'MEMBER' },
      reviewForm: { visible: false, reviewYear: '', result: 'PASS' }
    }
  },
  computed: {
    TYPE_OPTIONS: () => TYPE_OPTIONS,
    ROLE_OPTIONS: () => ROLE_OPTIONS,
    REVIEW_RESULT_OPTIONS: () => REVIEW_RESULT_OPTIONS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const s = (k) => this.all.filter((c) => c.status === k).length
      return [
        { key: 't', label: '社团总数', value: this.all.length, accent: 'primary' },
        { key: 'p', label: '待审批', value: s('PENDING'), accent: 'warning' },
        { key: 'a', label: '运营中', value: s('ACTIVE'), accent: 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getClubs({ pageSize: 300 })
      if (res.code === 0 && res.data) { this.all = res.data.items || []; this.applyFilter() }
      else this.errorMessage = res.message || '社团加载失败'
      this.loading = false
    },
    applyFilter() { this.items = this.activeStatus ? this.all.filter((c) => c.status === this.activeStatus) : this.all },
    setStatus(k) { this.activeStatus = k; this.applyFilter() },
    openForm() { this.form = { clubName: '', clubType: 'INTEREST', advisorName: '', error: '' }; this.formVisible = true },
    searchStudents(keyword) { return studentAffairsApi.searchStudents(keyword) },
    async save() {
      const m = this.form
      const clubName = (m.clubName || '').trim()
      if (!clubName) { m.error = '社团名称必填'; return }
      m.error = ''; this.saving = true
      const res = await studentAffairsApi.createClub({ clubName, clubType: m.clubType, advisorName: (m.advisorName || '').trim() || undefined })
      this.saving = false
      if (res.code === 0) { toast.success('已提交待审批'); this.formVisible = false; this.load() } else m.error = res.message || '创建失败'
    },
    async review(c, action) {
      if (action === 'REJECT') { this.rejDlg = { visible: true, clubId: c.clubId }; return }
      this.acting = c.clubId
      const res = await studentAffairsApi.reviewClub(c.clubId, action, '')
      this.acting = ''
      if (res.code === 0) { toast.success('已处理'); this.load() } else toast.error(res.message || '处理失败')
    },
    async submitReject({ reason }) {
      const d = this.rejDlg
      this.acting = d.clubId
      const res = await studentAffairsApi.reviewClub(d.clubId, 'REJECT', reason.trim())
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已处理'); this.load() } else toast.error(res.message || '处理失败')
    },
    disband(c) { this.disDlg = { visible: true, clubId: c.clubId, clubName: c.clubName || '该社团' } },
    async submitDisband({ reason }) {
      const d = this.disDlg
      this.acting = d.clubId
      const res = await studentAffairsApi.disbandClub(d.clubId, reason.trim())
      this.acting = ''
      if (res.code === 0) {
        d.visible = false
        toast.success('已注销')
        this.load()
        if (this.sel && this.sel.clubId === d.clubId) this.sel = null
      } else toast.error(res.message || '注销失败')
    },
    async select(c) {
      this.sel = c; this.members = []; this.reviews = []
      this.memberForm.visible = false; this.reviewForm.visible = false
      const [mm, rr] = await Promise.all([studentAffairsApi.getClubMembers(c.clubId), studentAffairsApi.getClubAnnualReviews(c.clubId)])
      if (mm.code === 0 && mm.data) this.members = mm.data.items || []
      if (rr.code === 0 && rr.data) this.reviews = rr.data.items || []
    },
    openMember() { this.memberForm = { visible: true, studentId: '', role: 'MEMBER' } },
    async addMember() {
      if (!this.memberForm.studentId) { toast.error('请选择学生'); return }
      const res = await studentAffairsApi.addClubMember(this.sel.clubId, { studentId: Number(this.memberForm.studentId), role: this.memberForm.role })
      if (res.code === 0) { toast.success('已加入'); this.memberForm.visible = false; this.select(this.sel); this.load() } else toast.error(res.message || '加入失败')
    },
    async removeMember(m) {
      const res = await studentAffairsApi.removeClubMember(m.memberId)
      if (res.code === 0) { toast.success('已退社'); this.select(this.sel); this.load() } else toast.error(res.message || '退社失败')
    },
    openReview() { this.reviewForm = { visible: true, reviewYear: '', result: 'PASS' } },
    async addReview() {
      const reviewYear = (this.reviewForm.reviewYear || '').trim()
      if (!reviewYear) { toast.error('请输入学年'); return }
      const res = await studentAffairsApi.createClubAnnualReview(this.sel.clubId, { reviewYear, result: this.reviewForm.result })
      if (res.code === 0) { toast.success('年审已记录'); this.reviewForm.visible = false; this.select(this.sel) } else toast.error(res.message || '年审失败')
    },
    statusType(s) { return ({ PENDING: 'warning', ACTIVE: 'success', SUSPENDED: 'processing', DISBANDED: 'default' })[s] || 'default' },
    reviewLabel(r) { return ({ PASS: '通过', CONDITIONAL: '限期整改', FAIL: '不通过' })[r] || r }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); flex: 1; min-width: 300px; }
.cf-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: var(--space-3); margin-bottom: var(--space-3); }
.cf-field { display: flex; flex-direction: column; gap: 4px; font-size: var(--font-size-sm); }
.cf-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.cf-error { color: var(--danger-500,#dc2626); font-size: var(--font-size-sm); }
.cf-actions { display: flex; gap: var(--space-3); justify-content: flex-end; }
.cf-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
.cf-layout { display: grid; grid-template-columns: 380px 1fr; gap: var(--space-4); }
.cf-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.cf-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 3px 12px; font-size: var(--font-size-xs); cursor: pointer; }
.cf-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.cf-clubs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.cf-club { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: var(--space-3); cursor: pointer; }
.cf-club.is-active { border-color: var(--color-primary); box-shadow: 0 0 0 2px rgba(37,99,235,0.12); }
.cf-club__top { display: flex; justify-content: space-between; align-items: center; }
.cf-club__name { font-weight: 600; }
.cf-club__meta { font-size: var(--font-size-sm); color: var(--text-secondary); margin: 4px 0; }
.cf-club__ops { display: flex; gap: 6px; }
.cf-empty, .cf-hint { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.cf-subhead { display: flex; justify-content: space-between; align-items: center; margin: var(--space-3) 0 var(--space-2); }
.cf-subhead h4 { margin: 0; font-size: var(--font-size-md); }
.cf-inline { display: flex; gap: var(--space-2); margin-bottom: var(--space-2); flex-wrap: wrap; }
.cf-inline > * { flex: 1 1 180px; min-width: 180px; }
.cf-inline > .app-perm-btn { flex: 0 0 auto; min-width: 0; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-3); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } .cf-grid, .cf-layout { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
