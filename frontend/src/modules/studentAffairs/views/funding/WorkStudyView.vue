<template>
  <AppPageShell title="勤工助学" subtitle="部门发岗 → 学生申请 → 录用 → 上岗 → 终止。补贴金额按角色脱敏。"
    role-name="学工处 / 资助老师" data-scope-name="资助范围（辅导员限本班）" watermark-purpose="勤工助学管理">
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载中..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="ws-cols">
        <AppSectionCard title="岗位（部门发岗）" class="ws-posts">
          <div class="ws-add">
            <input v-model.trim="postForm.deptName" class="ws-input" placeholder="用人部门" />
            <input v-model.trim="postForm.postName" class="ws-input" placeholder="岗位名称" />
            <input v-model.number="postForm.salary" type="number" class="ws-input ws-sm" placeholder="月薪" />
            <AppPermissionButton code="studentAffairs.funding.workstudy.manage" size="sm" :loading="acting==='post'" @click="addPost">发岗</AppPermissionButton>
          </div>
          <ul class="ws-postlist">
            <li v-for="p in posts" :key="p.postId" class="ws-post" :class="{ 'is-on': selPost===p.postId }" @click="selectPost(p)">
              <strong>{{ p.postName }}</strong><span>{{ p.deptName }} · {{ p.salary != null ? ('¥'+p.salary) : '—' }} · {{ p.headcount || '—' }}人</span>
              <AppPermissionButton code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" @click.stop="applyTo(p)">代录申请</AppPermissionButton>
            </li>
            <li v-if="!posts.length" class="ws-empty">暂无岗位</li>
          </ul>
        </AppSectionCard>

        <AppSectionCard :title="selPost ? '上岗记录（本岗位）' : '上岗记录（全部）'" class="ws-recs">
          <table class="sa-table">
            <thead><tr><th>学生</th><th>状态</th><th>累计补贴</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="r in records" :key="r.recordId">
                <td><strong>{{ r.realName || ('#'+r.studentId) }}</strong></td>
                <td><StatusTag :type="wsType(r.status)" :label="r.statusLabel || r.status" dot /></td>
                <td>{{ amountText(r.subsidyTotal) }}</td>
                <td class="ws-ops">
                  <AppPermissionButton v-if="r.status==='APPLIED'" code="studentAffairs.funding.workstudy.manage" size="sm" :loading="acting===r.recordId" @click="act(r,'APPROVE')">录用</AppPermissionButton>
                  <AppPermissionButton v-if="r.status==='APPLIED'" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" danger @click="act(r,'REJECT')">拒绝</AppPermissionButton>
                  <AppPermissionButton v-if="r.status==='APPROVED'" code="studentAffairs.funding.workstudy.manage" size="sm" @click="act(r,'ONBOARD')">上岗</AppPermissionButton>
                  <AppPermissionButton v-if="r.status==='ONBOARD'" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" @click="openMonthly(r)">月度考核</AppPermissionButton>
                  <AppPermissionButton v-if="['APPROVED','ONBOARD'].includes(r.status)" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" danger @click="act(r,'TERMINATE')">终止</AppPermissionButton>
                </td>
              </tr>
              <tr v-if="!records.length"><td colspan="4" class="sa-empty">暂无记录</td></tr>
            </tbody>
          </table>
        </AppSectionCard>
      </div>

      <div v-if="mm.visible" class="ws-mask" @click.self="mm.visible=false">
        <div class="ws-modal">
          <h3 class="ws-modal__title">{{ mm.name }} · 月度考核（累计补贴 {{ amountText(mm.subsidyTotal) }}）</h3>
          <div class="ws-madd">
            <input v-model.trim="mm.form.monthCode" class="ws-input" placeholder="考核月 2025-10" />
            <select v-model="mm.form.rating" class="ws-input"><option value="GOOD">优</option><option value="PASS">合格</option><option value="FAIL">不合格</option></select>
            <input v-model.number="mm.form.workHours" type="number" class="ws-input ws-sm" placeholder="工时" />
            <input v-model.number="mm.form.subsidyAmount" type="number" class="ws-input ws-sm" placeholder="补贴" />
            <AppPermissionButton code="studentAffairs.funding.workstudy.manage" size="sm" :loading="acting==='mon'" @click="addMonthly">录入</AppPermissionButton>
          </div>
          <table class="sa-table">
            <thead><tr><th>月份</th><th>等级</th><th>工时</th><th>补贴</th></tr></thead>
            <tbody>
              <tr v-for="m in mm.list" :key="m.monthlyId">
                <td>{{ m.monthCode }}</td><td>{{ m.ratingLabel || m.rating }}</td>
                <td>{{ m.workHours != null ? m.workHours : '—' }}</td><td>{{ amountText(m.subsidyAmount) }}</td>
              </tr>
              <tr v-if="!mm.list.length"><td colspan="4" class="sa-empty">暂无月度考核</td></tr>
            </tbody>
          </table>
          <div class="ws-mfoot"><button type="button" class="ws-btn" @click="mm.visible=false">关闭</button></div>
        </div>
      </div>
    </AppGlobalState>

    <!-- 岗位申请：原为「学生主档ID」原生弹窗，要老师手打内部 ID -->
    <AppConfirmDialog
      v-model:visible="appDlg.visible" :title="`为学生申请岗位 · ${appDlg.postName}`" type="primary"
      confirm-text="提交申请" :submitting="!!acting" @confirm="submitApply"
    >
      <AppFormItem label="申请学生" required>
        <AppStudentPicker v-model="appDlg.studentId" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索" />
      </AppFormItem>
      <AppInlineAlert v-if="appDlg.error" type="danger" :description="appDlg.error" />
    </AppConfirmDialog>

    <!-- 终止原因：后端 act_work_study 卡 ≥5 字，前端此前只判非空，失败要重打 -->
    <AppConfirmDialog
      v-model:visible="terDlg.visible" title="终止勤工助学" type="danger" confirm-text="确认终止"
      require-reason :reason-min-length="5" reason-label="终止原因（≥5 字）"
      description="终止后该生岗位记录置为已终止，原因记入台账。"
      :submitting="acting === terDlg.recordId" @confirm="submitTerminate"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPermissionButton,
  AppSectionCard, AppStatusTag, AppStudentPicker
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'WorkStudyView',
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPermissionButton,
    AppSectionCard, AppStudentPicker, StatusTag: AppStatusTag
  },
  data() {
    return { loading: true, acting: '', errorMessage: '', posts: [], records: [], selPost: '', postForm: { deptName: '', postName: '', salary: null },
      appDlg: { visible: false, postId: '', postName: '', studentId: '', error: '' },
      terDlg: { visible: false, recordId: '' },
      mm: { visible: false, recordId: '', name: '', subsidyTotal: null, list: [], form: this.blankMonthly() } }
  },
  computed: { pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') } },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const [ps, rs] = await Promise.all([studentAffairsApi.getWorkStudyPosts(), studentAffairsApi.getWorkStudyRecords({ postId: this.selPost })])
      if (ps.code === 0 && ps.data) this.posts = ps.data.items || []
      else this.errorMessage = ps.message || '加载失败'
      this.records = (rs.code === 0 && rs.data) ? (rs.data.items || []) : []
      this.loading = false
    },
    async addPost() {
      const f = this.postForm
      if (!f.deptName || !f.postName) { toast.error('部门与岗位名称必填'); return }
      this.acting = 'post'
      const res = await studentAffairsApi.createWorkStudyPost({ deptName: f.deptName, postName: f.postName, salary: f.salary != null ? Number(f.salary) : undefined })
      this.acting = ''
      if (res.code === 0) { toast.success('已发岗'); this.postForm = { deptName: '', postName: '', salary: null }; this.load() } else toast.error(res.message || '发岗失败')
    },
    selectPost(p) { this.selPost = this.selPost === p.postId ? '' : p.postId; this.load() },
    searchStudents(keyword) { return studentAffairsApi.searchStudents(keyword) },
    applyTo(p) {
      this.appDlg = { visible: true, postId: p.postId, postName: p.postName || '该岗位', studentId: '', error: '' }
    },
    async submitApply() {
      const d = this.appDlg
      if (!d.studentId) { d.error = '请选择申请学生'; return }
      d.error = ''
      this.acting = d.postId
      const res = await studentAffairsApi.applyWorkStudy(d.postId, Number(d.studentId))
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已申请'); this.load() }
      else { d.error = res.message || '申请失败' }
    },
    async act(r, action) {
      if (action === 'TERMINATE') { this.terDlg = { visible: true, recordId: r.recordId }; return }
      this.acting = r.recordId
      const res = await studentAffairsApi.actWorkStudy(r.recordId, action, '')
      this.acting = ''
      if (res.code === 0) { toast.success('已处理'); this.load() } else toast.error(res.message || '操作失败')
    },
    async submitTerminate({ reason }) {
      const d = this.terDlg
      this.acting = d.recordId
      const res = await studentAffairsApi.actWorkStudy(d.recordId, 'TERMINATE', reason.trim())
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已处理'); this.load() } else toast.error(res.message || '操作失败')
    },
    wsType(s) { return ({ APPLIED: 'warning', APPROVED: 'processing', ONBOARD: 'success', REJECTED: 'default', TERMINATED: 'default' })[s] || 'default' },
    amountText(a) { return (a == null || a === '') ? '¥0' : (typeof a === 'number' ? ('¥' + a) : a) },
    blankMonthly() { return { monthCode: '', rating: 'PASS', workHours: null, subsidyAmount: null } },
    async openMonthly(r) {
      this.mm = { visible: true, recordId: r.recordId, name: r.realName || ('#' + r.studentId), subsidyTotal: r.subsidyTotal, list: [], form: this.blankMonthly() }
      const res = await studentAffairsApi.getWorkStudyMonthly(r.recordId)
      if (res.code === 0 && res.data) this.mm.list = res.data.items || []
    },
    async addMonthly() {
      const f = this.mm.form
      if (!f.monthCode) { toast.error('考核月必填'); return }
      this.acting = 'mon'
      const res = await studentAffairsApi.addWorkStudyMonthly(this.mm.recordId, { monthCode: f.monthCode, rating: f.rating, workHours: f.workHours != null ? Number(f.workHours) : undefined, subsidyAmount: f.subsidyAmount != null ? Number(f.subsidyAmount) : undefined })
      this.acting = ''
      if (res.code === 0) {
        toast.success('已录入'); this.mm.form = this.blankMonthly()
        const lr = await studentAffairsApi.getWorkStudyMonthly(this.mm.recordId)
        this.mm.list = (lr.code === 0 && lr.data) ? (lr.data.items || []) : this.mm.list
        this.mm.subsidyTotal = this.mm.list.reduce((a, m) => a + (Number(m.subsidyAmount) || 0), 0)
        this.load()
      } else toast.error(res.message || '录入失败')
    }
  }
}
</script>

<style scoped>
.ws-cols { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.ws-add { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.ws-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.ws-sm { width: 90px; }
.ws-postlist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.ws-post { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: var(--space-3); cursor: pointer; display: flex; flex-direction: column; gap: 2px; }
.ws-post.is-on { border-color: var(--color-primary); box-shadow: 0 0 0 2px rgba(37,99,235,0.12); }
.ws-post span { font-size: var(--font-size-sm); color: var(--text-secondary); }
.ws-empty, .sa-empty { color: var(--text-tertiary); padding: var(--space-3); text-align: center; }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-2) var(--space-3); text-align: left; }
.ws-ops { display: flex; gap: 6px; flex-wrap: wrap; }
.ws-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.ws-modal { width: 560px; max-width: calc(100vw - 32px); background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-5); max-height: 80vh; overflow: auto; }
.ws-modal__title { margin: 0 0 var(--space-3); font-size: var(--font-size-lg); }
.ws-madd { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.ws-mfoot { display: flex; justify-content: flex-end; margin-top: var(--space-3); }
.ws-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 18px; cursor: pointer; }
@media (max-width: 960px) { .ws-cols { grid-template-columns: 1fr; } }
</style>
