<template>
  <AppPageShell title="勤工助学" subtitle="部门发岗 → 学生申请 → 录用 → 上岗 → 终止。补贴金额按角色脱敏。"
    role-name="学工处 / 资助老师" data-scope-name="资助范围（辅导员限本班）" watermark-purpose="勤工助学管理">
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载中..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="ws-cols">
        <AppSectionCard title="岗位（部门发岗）" class="ws-posts">
          <div class="ws-add">
            <AppTextInput v-model="postForm.deptName" placeholder="用人部门" />
            <AppTextInput v-model="postForm.postName" placeholder="岗位名称" />
            <AppNumberInput v-model="postForm.salary" class="ws-sm" :min="0" placeholder="月薪" />
            <AppPermissionButton :allowed="canBtn('studentAffairs.funding.workstudy.manage')" code="studentAffairs.funding.workstudy.manage" size="sm" :loading="acting==='post'" @click="addPost">发岗</AppPermissionButton>
          </div>
          <ul class="ws-postlist">
            <li v-for="p in posts" :key="p.postId" class="ws-post" :class="{ 'is-on': selPost===p.postId }" @click="selectPost(p)">
              <strong>{{ p.postName }}</strong><span>{{ p.deptName }} · {{ p.salary != null ? ('¥'+p.salary) : '—' }} · {{ p.headcount || '—' }}人</span>
              <AppPermissionButton :allowed="canBtn('studentAffairs.funding.workstudy.manage')" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" @click.stop="applyTo(p)">代录申请</AppPermissionButton>
            </li>
            <li v-if="!posts.length" class="ws-empty">暂无岗位</li>
          </ul>
        </AppSectionCard>

        <AppSectionCard :title="selPost ? '上岗记录（本岗位）' : '上岗记录（全部）'" class="ws-recs">
          <DataTable v-if="records.length" :columns="recordColumns" :rows="records" row-key="recordId">
            <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('#'+row.studentId) }}</span></template>
            <template #cell-status="{ row }"><StatusTag :type="wsType(row.status)" :label="row.statusLabel || row.status" dot /></template>
            <template #cell-subsidyTotal="{ row }">{{ amountText(row.subsidyTotal) }}</template>
            <template #cell-actions="{ row }">
              <div class="ws-ops">
                <AppPermissionButton :allowed="canBtn('studentAffairs.funding.workstudy.manage')" v-if="row.status==='APPLIED'" code="studentAffairs.funding.workstudy.manage" size="sm" :loading="acting===row.recordId" @click="act(row,'APPROVE')">录用</AppPermissionButton>
                <AppPermissionButton :allowed="canBtn('studentAffairs.funding.workstudy.manage')" v-if="row.status==='APPLIED'" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" danger @click="act(row,'REJECT')">拒绝</AppPermissionButton>
                <AppPermissionButton :allowed="canBtn('studentAffairs.funding.workstudy.manage')" v-if="row.status==='APPROVED'" code="studentAffairs.funding.workstudy.manage" size="sm" @click="act(row,'ONBOARD')">上岗</AppPermissionButton>
                <AppPermissionButton :allowed="canBtn('studentAffairs.funding.workstudy.manage')" v-if="row.status==='ONBOARD'" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" @click="openMonthly(row)">月度考核</AppPermissionButton>
                <AppPermissionButton :allowed="canBtn('studentAffairs.funding.workstudy.manage')" v-if="['APPROVED','ONBOARD'].includes(row.status)" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" danger @click="act(row,'TERMINATE')">终止</AppPermissionButton>
              </div>
            </template>
          </DataTable>
          <p v-else class="sa-empty">暂无记录</p>
        </AppSectionCard>
      </div>

      <AppDrawer :visible="mm.visible" :title="mm.name + ' · 月度考核（累计补贴 ' + amountText(mm.subsidyTotal) + '）'" @update:visible="mm.visible = $event">
        <div class="ws-madd">
          <AppTextInput v-model="mm.form.monthCode" placeholder="考核月 2025-10" />
          <AppSelect v-model="mm.form.rating" :options="RATING_OPTIONS" placeholder="" />
          <AppNumberInput v-model="mm.form.workHours" class="ws-sm" :min="0" placeholder="工时" />
          <AppNumberInput v-model="mm.form.subsidyAmount" class="ws-sm" :min="0" placeholder="补贴" />
          <AppPermissionButton :allowed="canBtn('studentAffairs.funding.workstudy.manage')" code="studentAffairs.funding.workstudy.manage" size="sm" :loading="acting==='mon'" @click="addMonthly">录入</AppPermissionButton>
        </div>
        <DataTable v-if="mm.list.length" :columns="monthlyColumns" :rows="mm.list" row-key="monthlyId">
          <template #cell-month="{ row }">{{ row.monthCode }}</template>
          <template #cell-rating="{ row }">{{ row.ratingLabel || row.rating }}</template>
          <template #cell-workHours="{ row }">{{ row.workHours != null ? row.workHours : '—' }}</template>
          <template #cell-subsidy="{ row }">{{ amountText(row.subsidyAmount) }}</template>
        </DataTable>
        <p v-else class="sa-empty">暂无月度考核</p>
        <template #footer>
          <AppButton @click="mm.visible = false">关闭</AppButton>
        </template>
      </AppDrawer>
    </AppGlobalState>

    <!-- 岗位申请：原为「学生主档ID」原生弹窗，要老师手打内部 ID -->
    <AppConfirmDialog
      v-model:visible="appDlg.visible" :title="`为学生申请岗位 · ${appDlg.postName}`" type="primary"
      confirm-text="提交申请" :submitting="!!acting" @confirm="submitApply"
    >
      <AppFormItem label="申请学生" required>
        <AppStudentPicker v-model="appDlg.studentId" placeholder="按姓名 / 学号搜索" />
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
  AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppNumberInput, AppPageShell,
  AppPermissionButton, AppSectionCard, AppSelect, AppStatusTag, AppStudentPicker, AppTextInput
} from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'


const RATING_OPTIONS = [{ value: 'GOOD', label: '优' }, { value: 'PASS', label: '合格' }, { value: 'FAIL', label: '不合格' }]
const RECORD_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'status', title: '状态' },
  { key: 'subsidyTotal', title: '累计补贴' },
  { key: 'actions', title: '操作', align: 'right', width: '260px' }
]
const MONTHLY_COLUMNS = [
  { key: 'month', title: '月份' },
  { key: 'rating', title: '等级' },
  { key: 'workHours', title: '工时' },
  { key: 'subsidy', title: '补贴' }
]

export default {
  name: 'WorkStudyView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppNumberInput, AppPageShell,
    AppPermissionButton, AppSectionCard, AppSelect, AppStudentPicker, StatusTag: AppStatusTag, AppTextInput, DataTable,
    AppButton, AppDrawer
  },
  data() {
    return { recordColumns: RECORD_COLUMNS, monthlyColumns: MONTHLY_COLUMNS, loading: true, acting: '', errorMessage: '', posts: [], records: [], selPost: '', postForm: { deptName: '', postName: '', salary: null },
      appDlg: { visible: false, postId: '', postName: '', studentId: '', error: '' },
      terDlg: { visible: false, recordId: '' },
      mm: { visible: false, recordId: '', name: '', subsidyTotal: null, list: [], form: this.blankMonthly() } }
  },
  computed: {
    RATING_OPTIONS: () => RATING_OPTIONS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
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
      const deptName = (f.deptName || '').trim()
      const postName = (f.postName || '').trim()
      if (!deptName || !postName) { toast.error('部门与岗位名称必填'); return }
      this.acting = 'post'
      const res = await studentAffairsApi.createWorkStudyPost({ deptName, postName, salary: f.salary != null ? Number(f.salary) : undefined })
      this.acting = ''
      if (res.code === 0) { toast.success('已发岗'); this.postForm = { deptName: '', postName: '', salary: null }; this.load() } else toast.error(res.message || '发岗失败')
    },
    selectPost(p) { this.selPost = this.selPost === p.postId ? '' : p.postId; this.load() },
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
      if (action === 'TERMINATE') { this.terDlg = { visible: true, recordId: r.recordId, version: r.version }; return }
      this.acting = r.recordId
      const res = await studentAffairsApi.actWorkStudy(r.recordId, action, '', r.version)
      this.acting = ''
      if (res.code === 0) { toast.success('已处理'); this.load() } else toast.error(res.message || '操作失败')
    },
    async submitTerminate({ reason }) {
      const d = this.terDlg
      this.acting = d.recordId
      const res = await studentAffairsApi.actWorkStudy(d.recordId, 'TERMINATE', reason.trim(), d.version)
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
      const monthCode = (f.monthCode || '').trim()
      if (!monthCode) { toast.error('考核月必填'); return }
      this.acting = 'mon'
      const res = await studentAffairsApi.addWorkStudyMonthly(this.mm.recordId, { monthCode, rating: f.rating, workHours: f.workHours != null ? Number(f.workHours) : undefined, subsidyAmount: f.subsidyAmount != null ? Number(f.subsidyAmount) : undefined })
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
.ws-add { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; align-items: center; }
.ws-add > *, .ws-madd > * { flex: 1 1 130px; min-width: 110px; }
.ws-add > .app-perm-btn, .ws-madd > .app-perm-btn { flex: 0 0 auto; min-width: 0; }
.ws-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.ws-sm { flex: 0 0 100px; min-width: 90px; }
.ws-postlist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.ws-post { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: var(--space-3); cursor: pointer; display: flex; flex-direction: column; gap: 2px; }
.ws-post.is-on { border-color: var(--color-primary); box-shadow: 0 0 0 2px rgba(37,99,235,0.12); }
.ws-post span { font-size: var(--font-size-sm); color: var(--text-secondary); }
.ws-empty, .sa-empty { color: var(--text-tertiary); padding: var(--space-3); text-align: center; }
.ws-ops { display: flex; gap: 6px; flex-wrap: wrap; }
.ws-madd { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; align-items: center; }
@media (max-width: 960px) { .ws-cols { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
