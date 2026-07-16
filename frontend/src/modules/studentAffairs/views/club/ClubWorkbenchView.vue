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
          <label class="cf-field"><span>社团名称 *</span><input v-model.trim="form.clubName" class="cf-input" /></label>
          <label class="cf-field"><span>类型</span>
            <select v-model="form.clubType" class="cf-input">
              <option v-for="(l,k) in TYPES" :key="k" :value="k">{{ l }}</option>
            </select></label>
          <label class="cf-field"><span>指导教师</span><input v-model.trim="form.advisorName" class="cf-input" /></label>
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
                <AppPermissionButton v-if="c.status==='PENDING'" code="studentAffairs.club.manage" size="sm" variant="secondary" danger :loading="acting===c.clubId" @click="openReject(c)">驳回</AppPermissionButton>
                <AppPermissionButton v-if="c.status==='ACTIVE'" code="studentAffairs.club.manage" size="sm" variant="secondary" danger @click="openDisband(c)">注销</AppPermissionButton>
              </div>
            </li>
            <li v-if="!items.length" class="cf-empty">暂无社团，点右上「建社团」</li>
          </ul>
          <AppPagination v-model:page="pagination.page" v-model:pageSize="pagination.pageSize"
                         :total="pagination.total" @change="load" />
        </AppSectionCard>

        <AppSectionCard :title="sel ? (sel.clubName + ' · 成员与年审') : '社团详情'" class="cf-detail">
          <p v-if="!sel" class="cf-hint">从左侧选择一个社团查看成员与年审。</p>
          <template v-else>
            <div class="cf-subhead">
              <h4>成员（{{ members.length }}）</h4>
              <AppPermissionButton v-if="sel.status==='ACTIVE'" code="studentAffairs.club.manage" size="sm" @click="openMember">增补成员</AppPermissionButton>
            </div>
            <div v-if="memberForm.visible" class="cf-inline">
              <input v-model.number="memberForm.studentId" type="number" class="cf-input" placeholder="学生主档ID" />
              <select v-model="memberForm.role" class="cf-input">
                <option v-for="(l,k) in ROLES" :key="k" :value="k">{{ l }}</option>
              </select>
              <button type="button" class="cf-btn" @click="addMember">加入</button>
            </div>
            <table class="sa-table">
              <thead><tr><th>学生</th><th>任职</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="m in members" :key="m.memberId">
                  <td>{{ m.realName || ('#'+m.studentId) }}</td><td>{{ ROLES[m.role] || m.role }}</td>
                  <td><AppPermissionButton v-if="sel.status==='ACTIVE'" code="studentAffairs.club.manage" size="sm" variant="secondary" danger @click="removeMember(m)">退社</AppPermissionButton></td>
                </tr>
                <tr v-if="!members.length"><td colspan="3" class="sa-empty">暂无成员</td></tr>
              </tbody>
            </table>

            <div class="cf-subhead">
              <h4>年审记录</h4>
              <AppPermissionButton v-if="sel.status==='ACTIVE'" code="studentAffairs.club.manage" size="sm" @click="openReview">登记年审</AppPermissionButton>
            </div>
            <div v-if="reviewForm.visible" class="cf-inline">
              <input v-model.trim="reviewForm.reviewYear" class="cf-input" placeholder="学年 如 2025-2026" />
              <select v-model="reviewForm.result" class="cf-input">
                <option value="PASS">通过</option><option value="CONDITIONAL">限期整改</option><option value="FAIL">不通过</option>
              </select>
              <button type="button" class="cf-btn" @click="addReview">提交</button>
            </div>
            <table class="sa-table">
              <thead><tr><th>学年</th><th>结果</th><th>活动数</th><th>审核人</th></tr></thead>
              <tbody>
                <tr v-for="r in reviews" :key="r.reviewId">
                  <td>{{ r.reviewYear }}</td><td>{{ reviewLabel(r.result) }}</td>
                  <td>{{ r.activityCount != null ? r.activityCount : '—' }}</td><td>{{ r.reviewerName || '—' }}</td>
                </tr>
                <tr v-if="!reviews.length"><td colspan="4" class="sa-empty">暂无年审</td></tr>
              </tbody>
            </table>
          </template>
        </AppSectionCard>
      </div>
    </AppGlobalState>

    <!-- 驳回社团申请 -->
    <AppConfirmDialog
      v-model:visible="rejectDialog.visible"
      title="驳回社团申请"
      type="danger"
      :message="rejectDialog.club ? `确认驳回「${rejectDialog.club.clubName}」的建社申请？` : ''"
      require-reason
      reason-label="驳回原因"
      confirm-text="确认驳回"
      :submitting="acting === (rejectDialog.club && rejectDialog.club.clubId)"
      phrase-scene-key="common.reject"
      @confirm="confirmReject"
    />

    <!-- 注销社团 -->
    <AppConfirmDialog
      v-model:visible="disbandDialog.visible"
      title="注销社团"
      type="danger"
      :message="disbandDialog.club ? `确认注销「${disbandDialog.club.clubName}」？注销后不可恢复。` : ''"
      require-reason
      reason-label="注销原因"
      confirm-text="确认注销"
      @confirm="confirmDisband"
    />
  </AppPageShell>
</template>

<script>
import { AppConfirmDialog, AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const TYPES = { INTEREST: '兴趣', ACADEMIC: '学术', SPORTS: '体育', ARTS: '文艺', VOLUNTEER: '公益', PRACTICE: '实践' }
const ROLES = { MEMBER: '成员', DEPT_HEAD: '部长', VICE_PRESIDENT: '副社长', PRESIDENT: '社长' }
const STATUS_FILTERS = [
  { key: '', label: '全部' }, { key: 'PENDING', label: '待审批' }, { key: 'ACTIVE', label: '运营中' },
  { key: 'SUSPENDED', label: '暂停' }, { key: 'DISBANDED', label: '已注销' }
]

export default {
  name: 'ClubWorkbenchView',
  components: { AppConfirmDialog, AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, StatusTag: AppStatusTag },
  data() {
    return {
      loading: true, saving: false, acting: '', errorMessage: '', total: 0, byStatus: {}, items: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      activeStatus: '', statusFilters: STATUS_FILTERS, TYPES, ROLES,
      formVisible: false, form: { clubName: '', clubType: 'INTEREST', advisorName: '', error: '' },
      sel: null, members: [], reviews: [],
      memberForm: { visible: false, studentId: null, role: 'MEMBER' },
      reviewForm: { visible: false, reviewYear: '', result: 'PASS' },
      rejectDialog: { visible: false, club: null }, disbandDialog: { visible: false, club: null }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      return [
        { key: 't', label: '社团总数', value: this.total, accent: 'primary' },
        { key: 'p', label: '待审批', value: this.byStatus.PENDING || 0, accent: 'warning' },
        { key: 'a', label: '运营中', value: this.byStatus.ACTIVE || 0, accent: 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      // 指标基于全量聚合（不分页）；列表按当前筛选 + 真实分页取（后端 /student-affairs/clubs 已支持 page/pageSize）
      const [all, filtered] = await Promise.all([
        studentAffairsApi.getClubs({ pageSize: 500 }),
        studentAffairsApi.getClubs({ status: this.activeStatus, page: this.pagination.page, pageSize: this.pagination.pageSize })
      ])
      if (all.code === 0 && all.data) {
        const allItems = all.data.items || []
        this.total = all.data.total != null ? all.data.total : allItems.length
        this.byStatus = allItems.reduce((m, x) => { m[x.status] = (m[x.status] || 0) + 1; return m }, {})
      } else {
        this.errorMessage = all.message || '社团加载失败'
      }
      if (filtered.code === 0 && filtered.data) {
        this.items = filtered.data.items || []
        this.pagination.total = filtered.data.total != null ? filtered.data.total : this.items.length
      } else if (!this.errorMessage) {
        this.errorMessage = filtered.message || '社团加载失败'
      }
      this.loading = false
    },
    setStatus(k) {
      if (this.activeStatus === k) return
      this.activeStatus = k
      this.pagination.page = 1
      this.load()
    },
    openForm() { this.form = { clubName: '', clubType: 'INTEREST', advisorName: '', error: '' }; this.formVisible = true },
    async save() {
      const m = this.form
      if (!m.clubName) { m.error = '社团名称必填'; return }
      m.error = ''; this.saving = true
      const res = await studentAffairsApi.createClub({ clubName: m.clubName, clubType: m.clubType, advisorName: m.advisorName || undefined })
      this.saving = false
      if (res.code === 0) { toast.success('已提交待审批'); this.formVisible = false; this.load() } else m.error = res.message || '创建失败'
    },
    async review(c, action, reason = '') {
      this.acting = c.clubId
      const res = await studentAffairsApi.reviewClub(c.clubId, action, reason)
      this.acting = ''
      if (res.code === 0) { toast.success('已处理'); this.load() } else toast.error(res.message || '处理失败')
    },
    openReject(c) { this.rejectDialog = { visible: true, club: c } },
    async confirmReject({ reason }) {
      const c = this.rejectDialog.club
      this.rejectDialog.visible = false
      if (c) await this.review(c, 'REJECT', reason)
    },
    openDisband(c) { this.disbandDialog = { visible: true, club: c } },
    async confirmDisband({ reason }) {
      const c = this.disbandDialog.club
      this.disbandDialog.visible = false
      if (!c) return
      this.acting = c.clubId
      const res = await studentAffairsApi.disbandClub(c.clubId, reason)
      this.acting = ''
      if (res.code === 0) { toast.success('已注销'); this.load(); if (this.sel && this.sel.clubId === c.clubId) this.sel = null } else toast.error(res.message || '注销失败')
    },
    async select(c) {
      this.sel = c; this.members = []; this.reviews = []
      this.memberForm.visible = false; this.reviewForm.visible = false
      const [mm, rr] = await Promise.all([studentAffairsApi.getClubMembers(c.clubId), studentAffairsApi.getClubAnnualReviews(c.clubId)])
      if (mm.code === 0 && mm.data) this.members = mm.data.items || []
      if (rr.code === 0 && rr.data) this.reviews = rr.data.items || []
    },
    openMember() { this.memberForm = { visible: true, studentId: null, role: 'MEMBER' } },
    async addMember() {
      if (!this.memberForm.studentId) { toast.error('请输入学生ID'); return }
      const res = await studentAffairsApi.addClubMember(this.sel.clubId, { studentId: Number(this.memberForm.studentId), role: this.memberForm.role })
      if (res.code === 0) { toast.success('已加入'); this.memberForm.visible = false; this.select(this.sel); this.load() } else toast.error(res.message || '加入失败')
    },
    async removeMember(m) {
      const res = await studentAffairsApi.removeClubMember(m.memberId)
      if (res.code === 0) { toast.success('已退社'); this.select(this.sel); this.load() } else toast.error(res.message || '退社失败')
    },
    openReview() { this.reviewForm = { visible: true, reviewYear: '', result: 'PASS' } },
    async addReview() {
      if (!this.reviewForm.reviewYear) { toast.error('请输入学年'); return }
      const res = await studentAffairsApi.createClubAnnualReview(this.sel.clubId, { reviewYear: this.reviewForm.reviewYear, result: this.reviewForm.result })
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
.cf-inline { display: flex; gap: var(--space-2); margin-bottom: var(--space-2); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-2) var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-3); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } .cf-grid, .cf-layout { grid-template-columns: 1fr; } }
</style>
