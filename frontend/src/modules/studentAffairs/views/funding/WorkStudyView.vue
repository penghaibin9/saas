<template>
  <AppPageShell
    title="勤工助学"
    subtitle="申请、上岗与补贴台账"
    role-name="资助经办"
    data-scope-name="学工数据范围"
    watermark-purpose="勤工助学管理"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载勤工助学工作区..." @retry="loadAll">
      <div class="ws-switchbar">
        <div class="ws-view-tabs" role="tablist" aria-label="勤工助学业务视图">
          <button type="button" role="tab" :aria-selected="activeView === 'records'" :class="{ active: activeView === 'records' }" @click="activeView = 'records'">申请与在岗 <span>{{ totalRecordCount }}</span></button>
          <button type="button" role="tab" :aria-selected="activeView === 'posts'" :class="{ active: activeView === 'posts' }" @click="activeView = 'posts'">岗位目录 <span>{{ postTotal }}</span></button>
        </div>
        <AppPermissionButton
          v-if="activeView === 'posts'"
          :allowed="canBtn('studentAffairs.funding.workstudy.manage')"
          code="studentAffairs.funding.workstudy.manage"
          @click="openPostDialog"
        >发布岗位</AppPermissionButton>
        <AppPermissionButton
          v-else
          :allowed="canBtn('studentAffairs.funding.workstudy.manage')"
          code="studentAffairs.funding.workstudy.manage"
          variant="secondary"
          @click="applyDlg.visible = true"
        >线下申请代录</AppPermissionButton>
      </div>

      <section v-if="activeView === 'records'" class="ws-panel">
        <div class="ws-statusbar" aria-label="按办理状态筛选">
          <button type="button" :class="{ active: recordQuery.status === '' }" @click="setRecordStatus('')">全部 <span>{{ totalRecordCount }}</span></button>
          <button type="button" :class="{ active: recordQuery.status === 'APPLIED' }" @click="setRecordStatus('APPLIED')">待审核 <span>{{ statusCount('APPLIED') }}</span></button>
          <button type="button" :class="{ active: recordQuery.status === 'APPROVED' }" @click="setRecordStatus('APPROVED')">已录用 <span>{{ statusCount('APPROVED') }}</span></button>
          <button type="button" :class="{ active: recordQuery.status === 'ONBOARD' }" @click="setRecordStatus('ONBOARD')">在岗 <span>{{ statusCount('ONBOARD') }}</span></button>
          <button type="button" :class="{ active: recordQuery.status === 'TERMINATED' }" @click="setRecordStatus('TERMINATED')">已终止 <span>{{ statusCount('TERMINATED') }}</span></button>
        </div>
        <div class="ws-toolbar">
          <AppTextInput v-model="recordQuery.keyword" placeholder="搜索学生姓名、学号或岗位" @keydown.enter="searchRecords" />
          <AppSelect v-model="recordQuery.postId" :options="postFilterOptions" @change="searchRecords" />
          <button class="ws-search" type="button" @click="searchRecords">查询</button>
        </div>
        <DataTable v-if="records.length" :columns="recordColumns" :rows="records" row-key="recordId">
          <template #cell-student="{ row }"><span class="ws-main">{{ row.realName || ('学生#' + row.studentId) }}</span><small>{{ row.studentNo || '' }}</small></template>
          <template #cell-post="{ row }"><span class="ws-main">{{ row.post?.postName || postName(row.postId) }}</span><small>{{ row.post?.deptName || '' }} · {{ row.post?.workLocation || '地点待确认' }}</small></template>
          <template #cell-availability="{ row }"><span>{{ row.availability || '未填写' }}</span><small>{{ row.applyStatement || '' }}</small></template>
          <template #cell-subsidy="{ row }">{{ money(row.subsidyTotal) }}</template>
          <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="row.statusLabel || row.status" dot /></template>
          <template #cell-actions="{ row }">
            <div class="ws-ops">
              <AppPermissionButton v-if="allows(row, 'APPROVE')" :allowed="canManage" code="studentAffairs.funding.workstudy.manage" size="sm" :disabled="!hasVersion(row)" @click="openAction(row, 'APPROVE')">录用</AppPermissionButton>
              <AppPermissionButton v-if="allows(row, 'REJECT')" :allowed="canManage" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" danger :disabled="!hasVersion(row)" @click="openAction(row, 'REJECT')">拒绝</AppPermissionButton>
              <AppPermissionButton v-if="allows(row, 'ONBOARD')" :allowed="canManage" code="studentAffairs.funding.workstudy.manage" size="sm" :disabled="!hasVersion(row)" @click="openAction(row, 'ONBOARD')">核验协议并上岗</AppPermissionButton>
              <AppPermissionButton v-if="row.status === 'ONBOARD'" :allowed="canManage" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" @click="openMonthly(row)">月度考核</AppPermissionButton>
              <AppPermissionButton v-if="allows(row, 'TERMINATE')" :allowed="canManage" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" danger :disabled="!hasVersion(row)" @click="openAction(row, 'TERMINATE')">结束岗位</AppPermissionButton>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前没有待处理记录。</p>
        <AppPagination v-if="recordTotal > recordQuery.pageSize" v-model:page="recordQuery.page" v-model:pageSize="recordQuery.pageSize" :total="recordTotal" @change="loadRecords" />
      </section>

      <section v-else class="ws-panel">
        <div class="ws-toolbar ws-toolbar--posts">
          <AppTextInput v-model="postQuery.keyword" placeholder="搜索岗位、部门或地点" @keydown.enter="searchPosts" />
          <AppSelect v-model="postQuery.status" :options="POST_STATUS_OPTIONS" @change="searchPosts" />
          <button class="ws-search" type="button" @click="searchPosts">查询</button>
        </div>
        <DataTable v-if="posts.length" :columns="postColumns" :rows="posts" row-key="postId">
          <template #cell-post="{ row }"><span class="ws-main">{{ row.postName }}</span><small>{{ row.deptName }} · {{ row.workLocation || '地点待确认' }}</small></template>
          <template #cell-pay="{ row }"><span class="ws-main">{{ money(row.salary) }}</span><small>{{ row.employmentType === 'TEMPORARY' ? '临时岗位计酬标准' : '固定岗位月酬标准' }}</small></template>
          <template #cell-capacity="{ row }"><span>{{ row.onboardCount }} 人在岗 / {{ row.headcount ?? '不限' }}</span><small>剩余 {{ row.remainingHeadcount ?? '不限' }} · 待审 {{ row.appliedCount }}</small></template>
          <template #cell-deadline="{ row }"><span>{{ dateTime(row.applyEnd) || '长期开放' }}</span><small>月工时上限 {{ hours(row.monthlyHoursLimit) }}</small></template>
          <template #cell-status="{ row }"><StatusTag :type="row.status === 'ENABLED' && row.openForApplication ? 'success' : 'default'" :label="postStatus(row)" dot /></template>
          <template #cell-actions="{ row }">
            <AppPermissionButton :allowed="canManage" code="studentAffairs.funding.workstudy.manage" size="sm" :variant="row.status === 'ENABLED' ? 'secondary' : 'primary'" :danger="row.status === 'ENABLED'" :disabled="!hasVersion(row)" @click="togglePost(row)">{{ row.status === 'ENABLED' ? '停止申请' : '重新开放' }}</AppPermissionButton>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前条件没有勤工岗位。</p>
        <AppPagination v-if="postTotal > postQuery.pageSize" v-model:page="postQuery.page" v-model:pageSize="postQuery.pageSize" :total="postTotal" @change="loadPosts" />
      </section>
    </AppGlobalState>

    <AppConfirmDialog v-model:visible="postDlg.visible" title="发布勤工助学岗位" type="primary" message="岗位发布后学生 PC 和小程序会同步可见；停止申请不影响已经录用或在岗的学生。" confirm-text="发布岗位" :submitting="acting === 'post'" @confirm="submitPost">
      <div class="ws-form-grid">
        <AppFormItem label="用人部门" required><AppTextInput v-model="postDlg.deptName" :maxlength="200" /></AppFormItem>
        <AppFormItem label="岗位名称" required><AppTextInput v-model="postDlg.postName" :maxlength="200" /></AppFormItem>
        <AppFormItem label="岗位类型" required><AppSelect v-model="postDlg.employmentType" :options="EMPLOYMENT_OPTIONS" /></AppFormItem>
        <AppFormItem label="需求人数" required><AppNumberInput v-model="postDlg.headcount" :min="1" :max="10000" /></AppFormItem>
        <AppFormItem label="计酬标准（元）"><AppNumberInput v-model="postDlg.salary" :min="0" :max="999999999999.99" :precision="2" /></AppFormItem>
        <AppFormItem label="月工时上限" required><AppNumberInput v-model="postDlg.monthlyHoursLimit" :min="1" :max="40" :precision="2" /></AppFormItem>
        <AppFormItem label="工作地点"><AppTextInput v-model="postDlg.workLocation" :maxlength="200" /></AppFormItem>
        <AppFormItem label="申请截止"><AppDateTimePicker v-model="postDlg.applyEnd" /></AppFormItem>
      </div>
      <AppFormItem label="工作时段"><AppTextInput v-model="postDlg.scheduleText" :maxlength="500" placeholder="如：周一至周五课余时段排班" /></AppFormItem>
      <AppFormItem label="岗位要求"><AppTextarea v-model="postDlg.requirement" :maxlength="1000" :rows="3" /></AppFormItem>
      <label class="ws-check"><input v-model="postDlg.agreementRequired" type="checkbox" />上岗前必须核验勤工助学协议</label>
      <AppInlineAlert v-if="postDlg.error" type="danger" :description="postDlg.error" />
    </AppConfirmDialog>

    <AppConfirmDialog v-model:visible="applyDlg.visible" title="代录线下申请" type="primary" message="优先让学生在 PC 或小程序自行申请；代录只用于线下材料已经收齐的特殊情况。" confirm-text="提交代录" :submitting="acting === 'apply'" @confirm="submitApply">
      <AppFormItem label="岗位" required><AppSelect v-model="applyDlg.postId" :options="postOptions" /></AppFormItem>
      <AppFormItem label="学生" required><AppStudentPicker v-model="applyDlg.studentId" /></AppFormItem>
      <AppFormItem label="申请说明"><AppTextarea v-model="applyDlg.statement" :maxlength="1000" :rows="3" /></AppFormItem>
      <AppFormItem label="可工作时段"><AppTextInput v-model="applyDlg.availability" :maxlength="500" /></AppFormItem>
      <AppInlineAlert v-if="applyDlg.error" type="danger" :description="applyDlg.error" />
    </AppConfirmDialog>

    <AppConfirmDialog v-model:visible="actionDlg.visible" :title="actionTitle" :type="['TERMINATE', 'REJECT'].includes(actionDlg.action) ? 'danger' : 'primary'" :message="actionMessage" :confirm-text="actionConfirmText" :require-reason="['REJECT', 'TERMINATE'].includes(actionDlg.action)" :reason-min-length="5" :submitting="acting === actionDlg.recordId" @confirm="submitAction">
      <label v-if="actionDlg.action === 'ONBOARD'" class="ws-check"><input v-model="actionDlg.agreementConfirmed" type="checkbox" />已核对学生与学校签署的勤工助学协议</label>
    </AppConfirmDialog>

    <AppConfirmDialog v-model:visible="monthlyDlg.visible" title="登记月度考核与补贴" type="primary" message="同一学生同一月份的全部勤工记录累计不得超过岗位上限，且最高 40 小时。" confirm-text="保存考核" :submitting="acting === monthlyDlg.recordId" @confirm="submitMonthly">
      <div class="ws-form-grid">
        <AppFormItem label="考核月" required><AppTextInput v-model="monthlyDlg.monthCode" placeholder="YYYY-MM" :maxlength="7" /></AppFormItem>
        <AppFormItem label="本月工时" required><AppNumberInput v-model="monthlyDlg.workHours" :min="0" :max="40" :precision="2" /></AppFormItem>
        <AppFormItem label="考核等级" required><AppSelect v-model="monthlyDlg.rating" :options="RATING_OPTIONS" /></AppFormItem>
        <AppFormItem label="确认补贴（元）" required><AppNumberInput v-model="monthlyDlg.subsidyAmount" :min="0" :max="999999999999.99" :precision="2" :disabled="monthlyDlg.rating === 'FAIL'" /></AppFormItem>
      </div>
      <AppFormItem label="考核备注"><AppTextarea v-model="monthlyDlg.remark" :maxlength="500" :rows="3" /></AppFormItem>
      <AppInlineAlert v-if="monthlyDlg.error" type="danger" :description="monthlyDlg.error" />
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppDateTimePicker, AppFormItem, AppGlobalState, AppInlineAlert,
  AppNumberInput, AppPageShell, AppPagination, AppPermissionButton, AppSelect,
  AppStatusTag, AppStudentPicker, AppTextInput, AppTextarea
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { toast } from '@/utils/toast'

const POST_STATUS_OPTIONS = [{ value: '', label: '全部岗位' }, { value: 'ENABLED', label: '开放中' }, { value: 'DISABLED', label: '已停止' }]
const EMPLOYMENT_OPTIONS = [{ value: 'FIXED', label: '固定岗位' }, { value: 'TEMPORARY', label: '临时岗位' }]
const RATING_OPTIONS = [{ value: 'GOOD', label: '优秀' }, { value: 'PASS', label: '合格' }, { value: 'FAIL', label: '不合格' }]
const createEmptyPost = () => ({
  visible: false,
  deptName: '',
  postName: '',
  salary: null,
  headcount: 1,
  employmentType: 'FIXED',
  workLocation: '',
  scheduleText: '',
  requirement: '',
  applyEnd: '',
  monthlyHoursLimit: 40,
  agreementRequired: true,
  error: ''
})

export default {
  name: 'WorkStudyView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppDateTimePicker, AppFormItem, AppGlobalState, AppInlineAlert,
    AppNumberInput, AppPageShell, AppPagination, AppPermissionButton, AppSelect,
    StatusTag: AppStatusTag, AppStudentPicker, AppTextInput, AppTextarea, DataTable
  },
  data() {
    return {
      POST_STATUS_OPTIONS, EMPLOYMENT_OPTIONS, RATING_OPTIONS,
      activeView: 'records', loading: true, acting: '', errorMessage: '', posts: [], records: [], statusCounts: {},
      postTotal: 0, recordTotal: 0,
      postQuery: { status: '', keyword: '', page: 1, pageSize: 20 },
      recordQuery: { postId: '', status: 'APPLIED', keyword: '', page: 1, pageSize: 20 },
      postColumns: [
        { key: 'post', title: '岗位与地点' }, { key: 'pay', title: '计酬标准' },
        { key: 'capacity', title: '名额' }, { key: 'deadline', title: '申请与工时' },
        { key: 'status', title: '状态' }, { key: 'actions', title: '操作', align: 'right', width: '120px' }
      ],
      recordColumns: [
        { key: 'student', title: '学生' }, { key: 'post', title: '岗位' },
        { key: 'availability', title: '申请说明' }, { key: 'subsidy', title: '累计补贴' },
        { key: 'status', title: '状态' }, { key: 'actions', title: '下一步', align: 'right', width: '310px' }
      ],
      postDlg: createEmptyPost(),
      applyDlg: { visible: false, postId: '', studentId: '', statement: '', availability: '', error: '' },
      actionDlg: { visible: false, recordId: '', version: null, action: '', agreementConfirmed: false },
      monthlyDlg: { visible: false, recordId: '', monthCode: '', workHours: null, rating: 'PASS', subsidyAmount: null, remark: '', error: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    canManage() { return canCode(this.ctx, 'studentAffairs.funding.workstudy.manage') },
    totalRecordCount() { return Number(this.statusCounts?.ALL || 0) },
    postOptions() { return this.posts.filter((post) => post.openForApplication).map((post) => ({ value: post.postId, label: `${post.postName} · ${post.deptName}` })) },
    postFilterOptions() { return [{ value: '', label: '全部岗位' }, ...this.posts.map((post) => ({ value: post.postId, label: post.postName }))] },
    actionTitle() { return ({ APPROVE: '确认录用', REJECT: '拒绝申请', ONBOARD: '核验协议并确认上岗', TERMINATE: '结束岗位' })[this.actionDlg.action] || '处理勤工申请' },
    actionConfirmText() { return ({ APPROVE: '确认录用', REJECT: '确认拒绝', ONBOARD: '确认上岗', TERMINATE: '确认结束' })[this.actionDlg.action] || '确认' },
    actionMessage() { return ({ APPROVE: '录用时会锁定岗位并校验剩余人数。', REJECT: '拒绝后本次申请结束，请填写清楚原因。', ONBOARD: '上岗前必须完成协议核验；确认后才能登记月度考核。', TERMINATE: '结束后不能继续登记月度考核，原台账仍保留。' })[this.actionDlg.action] || '' }
  },
  mounted() { this.loadAll() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    hasVersion(row) { return row?.version !== undefined && row?.version !== null && row?.version !== '' },
    allows(row, action) { return Array.isArray(row?.allowedActions) && row.allowedActions.includes(action) },
    statusCount(status) { return Number(this.statusCounts?.[status] || 0) },
    postName(id) { return this.posts.find((post) => String(post.postId) === String(id))?.postName || `岗位#${id}` },
    money(value) { return value == null || value === '' ? '待确认' : `¥${Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` },
    hours(value) { return value == null || value === '' ? '40 小时' : `${Number(value)} 小时` },
    dateTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '' },
    statusType(status) { return ({ APPLIED: 'warning', APPROVED: 'processing', ONBOARD: 'success', REJECTED: 'default', WITHDRAWN: 'default', TERMINATED: 'danger' })[status] || 'default' },
    postStatus(row) { if (row.status !== 'ENABLED') return '已停止'; return row.openForApplication ? '申请中' : '已截止' },
    async loadAll() {
      this.loading = true; this.errorMessage = ''
      const [posts, records] = await Promise.all([this.loadPosts(), this.loadRecords()])
      if (!posts && !records) this.errorMessage = '勤工助学数据加载失败，请重试。'
      this.loading = false
    },
    async loadPosts() {
      const response = await studentAffairsApi.getWorkStudyPosts(this.postQuery)
      if (response.code !== 0) return null
      this.posts = response.data?.items || []; this.postTotal = Number(response.data?.total || 0); return this.posts
    },
    async loadRecords() {
      const response = await studentAffairsApi.getWorkStudyRecords(this.recordQuery)
      if (response.code !== 0) return null
      this.records = response.data?.items || []; this.recordTotal = Number(response.data?.total || 0); this.statusCounts = response.data?.statusCounts || {}; return this.records
    },
    searchPosts() { this.postQuery.page = 1; return this.loadPosts() },
    searchRecords() { this.recordQuery.page = 1; return this.loadRecords() },
    setRecordStatus(status) { this.recordQuery.status = status; return this.searchRecords() },
    openPostDialog() { this.postDlg = createEmptyPost(); this.postDlg.visible = true },
    async submitPost() {
      const form = this.postDlg
      if (!form.deptName.trim() || !form.postName.trim()) { form.error = '用人部门和岗位名称必填'; return }
      if (!Number.isFinite(Number(form.headcount)) || Number(form.headcount) < 1) { form.error = '需求人数至少为1'; return }
      if (!Number.isFinite(Number(form.monthlyHoursLimit)) || Number(form.monthlyHoursLimit) <= 0 || Number(form.monthlyHoursLimit) > 40) { form.error = '月工时上限应大于0且不超过40小时'; return }
      this.acting = 'post'; form.error = ''
      const response = await studentAffairsApi.createWorkStudyPost({ ...form, visible: undefined, error: undefined })
      this.acting = ''
      if (response.code === 0) { form.visible = false; toast.success('岗位已发布，学生端已同步开放'); await this.loadPosts() }
      else form.error = response.message || '岗位发布失败'
    },
    async togglePost(row) {
      const action = row.status === 'ENABLED' ? 'DISABLE' : 'ENABLE'
      const response = await studentAffairsApi.setWorkStudyPostStatus(row.postId, action, row.version)
      if (response.code === 0) { toast.success(action === 'DISABLE' ? '已停止新申请' : '岗位已重新开放'); await this.loadPosts() }
      else toast.error(response.message || '岗位状态更新失败')
    },
    async submitApply() {
      const form = this.applyDlg
      if (!form.postId || !form.studentId) { form.error = '请选择岗位和学生'; return }
      this.acting = 'apply'; form.error = ''
      const response = await studentAffairsApi.applyWorkStudy(form.postId, form.studentId, form.statement, form.availability)
      this.acting = ''
      if (response.code === 0) { form.visible = false; toast.success('线下申请已代录'); await this.loadRecords() }
      else form.error = response.message || '代录失败'
    },
    openAction(row, action) { this.actionDlg = { visible: true, recordId: row.recordId, version: row.version, action, agreementConfirmed: false } },
    async submitAction(reason) {
      const form = this.actionDlg
      if (form.action === 'ONBOARD' && !form.agreementConfirmed) { toast.error('请先确认协议已经核验'); return }
      const text = String(reason || '').trim()
      if (['REJECT', 'TERMINATE'].includes(form.action) && (text.length < 5 || text.length > 500)) { toast.error('处理原因需5-500字'); return }
      this.acting = form.recordId
      const response = await studentAffairsApi.actWorkStudy(form.recordId, form.action, text, form.version, form.agreementConfirmed)
      this.acting = ''
      if (response.code === 0) { form.visible = false; toast.success('状态已更新'); await Promise.all([this.loadRecords(), this.loadPosts()]) }
      else { toast.error(response.message || '操作失败'); if (response.bizCode === 'APPROVAL_VERSION_CONFLICT') await this.loadRecords() }
    },
    openMonthly(row) { this.monthlyDlg = { visible: true, recordId: row.recordId, monthCode: new Date().toISOString().slice(0, 7), workHours: null, rating: 'PASS', subsidyAmount: null, remark: '', error: '' } },
    async submitMonthly() {
      const form = this.monthlyDlg
      if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(form.monthCode.trim())) { form.error = '考核月格式应为YYYY-MM'; return }
      if (form.workHours == null || Number(form.workHours) < 0 || Number(form.workHours) > 40) { form.error = '本月工时应为0-40小时'; return }
      if (form.rating !== 'FAIL' && (form.subsidyAmount == null || Number(form.subsidyAmount) < 0)) { form.error = '请填写确认后的补贴金额'; return }
      this.acting = form.recordId; form.error = ''
      const response = await studentAffairsApi.addWorkStudyMonthly(form.recordId, { monthCode: form.monthCode.trim(), workHours: String(form.workHours), rating: form.rating, subsidyAmount: form.rating === 'FAIL' ? '0' : String(form.subsidyAmount), remark: form.remark.trim() })
      this.acting = ''
      if (response.code === 0) { form.visible = false; toast.success('月度考核已登记'); await this.loadRecords() }
      else form.error = response.message || '登记失败'
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ws-switchbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }.ws-view-tabs,.ws-statusbar { display: flex; align-items: center; gap: 4px; }.ws-view-tabs { padding: 3px; border-radius: 10px; background: var(--bg-secondary); }.ws-view-tabs button,.ws-statusbar button { border: 0; color: var(--text-secondary); background: transparent; cursor: pointer; }.ws-view-tabs button { padding: 7px 12px; border-radius: 8px; font-weight: 600; }.ws-view-tabs button.active { color: var(--brand-primary); background: var(--bg-card); box-shadow: var(--shadow-xs); }.ws-view-tabs span,.ws-statusbar span { margin-left: 4px; font-variant-numeric: tabular-nums; }
.ws-panel { padding: 12px; border: 1px solid var(--border-light); border-radius: var(--radius-lg); background: var(--bg-card); }.ws-statusbar { gap: 6px; margin-bottom: 8px; overflow-x: auto; }.ws-statusbar button { flex: 0 0 auto; padding: 5px 10px; border-radius: 7px; font-size: 12px; }.ws-statusbar button:hover { color: var(--text-primary); background: var(--bg-secondary); }.ws-statusbar button.active { color: var(--color-primary); background: var(--color-primary-light); font-weight: 600; }.ws-toolbar { display: grid; grid-template-columns: minmax(220px, 1fr) 180px auto; gap: 8px; align-items: center; margin-bottom: 8px; }.ws-toolbar--posts { grid-template-columns: minmax(240px, 1fr) 150px auto; }.ws-search { height: 36px; padding: 0 16px; border: 0; border-radius: var(--radius-md); color: #fff; background: var(--brand-primary); cursor: pointer; }.ws-main { display: block; color: var(--text-primary); font-weight: 600; }.ws-main + small,.ws-panel small { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: 11px; line-height: 1.4; }.ws-ops { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }.ws-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }.ws-check { display: flex; align-items: center; gap: 8px; margin: 8px 0; color: var(--text-secondary); font-size: 13px; }
@media (max-width: 1050px) { .ws-toolbar { grid-template-columns: 1fr 1fr; }.ws-search { width: max-content; }.ws-ops { justify-content: flex-start; } }
@media (max-width: 720px) { .ws-switchbar { align-items: stretch; flex-direction: column; }.ws-view-tabs,.ws-switchbar > button { width: 100%; }.ws-view-tabs button { flex: 1; }.ws-toolbar,.ws-toolbar--posts,.ws-form-grid { grid-template-columns: 1fr; } }
</style>
