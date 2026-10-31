<template>
  <ModulePageShell
    title="等级考试"
    :subtitle="'四六级 / 普通话 / 职业技能等级证书：建考 → 网上报名 → 缴费确认 → 成绩录入（通过可回填证书号，供 1+X 台账取数）'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="canManage" variant="primary" :disabled="saving || !!levelPending" @click="openCreate">新建等级考试</AppButton>
    </template>

    <AppInlineAlert v-if="levelPending" type="warning" title="上次操作结果待核实" :description="levelPending.label + '尚未完成正式回读，当前页已阻止重复提交。'" />
    <AppButton v-if="levelPending" :disabled="saving" @click="verifyLevelCommand()">只刷新核对上次结果</AppButton>
    <AaExamObjectBar
      :title="current?.examName || '等级考试批次清单'"
      :object-id="current ? `LEVEL-EXAM-${current.examId}` : `${pagination.total} 个考试批次`"
      source="考务管理 / 等级考试"
      :status="current ? stLabel(current.status) : '等待选择考试'"
      :owner="levelOwner"
      :blocker="levelBlocker"
      :blocked="!!detailError"
      :next-owner="levelNextOwner"
    />
    <AaExamStageRail :steps="stageSteps" :active-index="stageIndex" aria-label="等级考试办理阶段" />

    <div class="aalv-kpis" aria-label="等级考试业务摘要">
      <div><span>考试批次</span><strong>{{ pagination.total }}</strong><small>当前权限范围总数</small></div>
      <div><span>本页报名中</span><strong>{{ openExamCount }}</strong><small>本页可报名批次</small></div>
      <div :class="{ 'is-risk': unpaidCount }"><span>本页待缴费确认</span><strong>{{ current ? unpaidCount : '—' }}</strong><small>所选批次当前页</small></div>
      <div :class="{ 'is-risk': unscoredCount }"><span>本页待录成绩</span><strong>{{ current ? unscoredCount : '—' }}</strong><small>所选批次当前页</small></div>
    </div>

    <div class="aalv-layout">
      <div class="aalv-list">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无等级考试" description="新建四六级/技能证书等考试" />
        <ul v-else class="aalv-exams">
          <li v-for="e in rows" :key="e.examId"
              :class="['aalv-exam', { 'is-active': current && current.examId === e.examId }]"
              @click="select(e)">
            <div>
              <div class="aalv-exam-name">{{ e.examName }}</div>
              <div class="mp-cell-sub">{{ catLabel(e.category) }}{{ e.level ? ' · ' + e.level : '' }}{{ e.fee != null ? ' · ¥' + e.fee : '' }}</div>
            </div>
            <StatusTag :type="stType(e.status)" :label="stLabel(e.status)" dot />
          </li>
        </ul>
        <div class="aalv-paging">
          <AppButton size="small" :disabled="pagination.page <= 1 || loading || saving" @click="changePage(pagination.page - 1)">上一页</AppButton>
          <span>第 {{ pagination.page }} 页 · 共 {{ pagination.total }} 项</span>
          <AppButton size="small" :disabled="pagination.page * pagination.pageSize >= pagination.total || loading || saving" @click="changePage(pagination.page + 1)">下一页</AppButton>
        </div>
      </div>

      <div class="aalv-detail">
        <EmptyState v-if="!current" title="选择一个考试" description="从左侧选择等级考试管理报名与成绩" />
        <template v-else>
          <div class="aalv-head">
            <div class="aalv-title">{{ current.examName }}</div>
            <div class="aalv-actions">
              <AppButton v-if="canManage && current.status === 'DRAFT'" :disabled="saving || detailLoading || !!detailError" size="small" variant="primary" @click="act('OPEN', '开放报名')">开放报名</AppButton>
              <AppButton v-if="canManage && current.status === 'OPEN'" :disabled="saving || detailLoading || !!detailError" size="small" variant="warning" @click="act('CLOSE', '截止报名')">截止报名</AppButton>
              <AppButton v-if="canManage && current.status === 'CLOSED'" :disabled="saving || detailLoading || !!detailError" size="small" variant="primary" @click="act('FINISH', '完成考试（须成绩全录）')">完成</AppButton>
            </div>
          </div>

          <ErrorState v-if="detailError" title="报名名单加载失败" :description="detailError" @retry="select(current)" />
          <LoadingState v-else-if="detailLoading" />
          <EmptyState v-else-if="!regs.length" title="暂无报名" description="开放报名后学生报名显示在此" />
          <DataTable v-else :columns="regColumns" :rows="regs" row-key="regId" :pagination="regPagination" @page-change="changeRegPage">
            <template #cell-student="{ row }">{{ row.studentName }}（{{ row.studentNo }}）</template>
            <template #cell-fee="{ row }">
              <StatusTag :type="row.feeStatus === 'PAID' ? 'success' : 'warning'"
                         :label="row.feeStatus === 'PAID' ? '已缴费' : '未缴费'" dot />
            </template>
            <template #cell-result="{ row }">
              <template v-if="row.status === 'SCORED'">
                <StatusTag :type="row.result === 'PASS' ? 'success' : 'danger'" :label="row.result === 'PASS' ? '通过' : '未通过'" dot />
                <span class="mp-cell-sub">{{ row.score != null ? row.score + ' 分' : '' }}{{ row.certNo ? ' · ' + row.certNo : '' }}</span>
              </template>
              <span v-else-if="row.status === 'CANCELLED'" class="mp-cell-sub">已取消</span>
              <span v-else class="mp-cell-sub">待录入</span>
            </template>
            <template #cell-ops="{ row }">
              <button v-if="canManage && row.status === 'REGISTERED' && row.feeStatus === 'UNPAID'" :disabled="saving || !!levelPending" class="mp-link" @click="confirmFee(row)">缴费确认</button>
              <button v-if="canManage && row.status === 'REGISTERED' && ['CLOSED','FINISHED'].includes(current.status)" :disabled="saving || !!levelPending" class="mp-link" @click="openScore(row)">录成绩</button>
            </template>
          </DataTable>
        </template>
      </div>
    </div>

    <AppDrawer :visible="createVisible" title="新建等级考试" mode="modal" size="large" @close="createVisible = false">
      <div class="aalv-form">
        <AppFormItem label="考试名称" required><AppTextInput v-model="form.examName" placeholder="如 大学英语四级(2025-06)" :disabled="saving || !!levelPending" /></AppFormItem>
        <AppFormItem label="类别" required>
          <AppSelect v-model="form.category" :options="[{ label: '大学英语等级考试', value: 'CET' }, { label: '普通话水平', value: 'PUTONGHUA' }, { label: '职业技能等级证书', value: 'SKILL' }, { label: '其他', value: 'OTHER' }]" :disabled="saving || !!levelPending" />
        </AppFormItem>
        <AppFormItem label="等级"><AppTextInput v-model="form.level" placeholder="如 四级 / 二甲 / 中级" :disabled="saving || !!levelPending" /></AppFormItem>
        <AppFormItem label="考试日期"><AppDatePicker v-model="form.examDate" :disabled="saving || !!levelPending" /></AppFormItem>
        <AppFormItem label="报名费（元）"><AppNumberInput v-model="form.fee" :min="0" :max="9999" :disabled="saving || !!levelPending" /></AppFormItem>
        <AppFormItem label="合格线（分数制考试）"><AppNumberInput v-model="form.passLine" :min="0" :max="750" :disabled="saving || !!levelPending" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton v-if="levelPending" :disabled="saving" @click="verifyLevelCommand()">只刷新核对上次结果</AppButton>
        <AppButton variant="ghost" :disabled="saving || !!levelPending" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="scoreVisible" :title="'录入成绩 · ' + (scoreRow ? scoreRow.studentName : '')" mode="modal" size="medium" @close="scoreVisible = false">
      <div class="aalv-form">
        <AppFormItem :label="current && current.passLine != null ? '分数（合格线 ' + current.passLine + '，自动判定通过）' : '分数（选填）'">
          <AppNumberInput v-model="scoreForm.score" :min="0" :max="750" :disabled="saving || !!levelPending" />
        </AppFormItem>
        <AppFormItem v-if="!(current && current.passLine != null)" label="结论" required>
          <AppSelect v-model="scoreForm.result" :options="[{ label: '通过', value: 'PASS' }, { label: '未通过', value: 'FAIL' }]" :disabled="saving || !!levelPending" />
        </AppFormItem>
        <AppFormItem label="证书编号（通过时选填）"><AppTextInput v-model="scoreForm.certNo" placeholder="如 CET4-2025-XXXX" :disabled="saving || !!levelPending" /></AppFormItem>
        <AppInlineAlert v-if="scoreError" type="danger" :description="scoreError" />
      </div>
      <template #footer>
        <AppButton v-if="levelPending" :disabled="saving" @click="verifyLevelCommand()">只刷新核对上次结果</AppButton>
        <AppButton variant="ghost" :disabled="saving || !!levelPending" @click="scoreVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitScore">保存</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" :submitting="saving" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** 等级考务（/admin/academic-affairs/level-exams）：建考→报名→缴费确认→成绩录入。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect, AppDatePicker } from '@/components/common'
import { academicAffairsLevelExamApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import AaExamObjectBar from '@/modules/academicAffairs/components/exam/AaExamObjectBar.vue'
import AaExamStageRail from '@/modules/academicAffairs/components/exam/AaExamStageRail.vue'
import { matchPermission } from '@/config/navPlan'
import { toRaw } from 'vue'
import { isDefiniteWriteRejection } from '../components/parallel-b/unconfirmedWrite'
import { currentUserFromToken } from '@/services/http/client'
import { toast } from '@/utils/toast'

const _L = { DRAFT: '草稿', OPEN: '报名中', CLOSED: '已截止', FINISHED: '已完成' }
const _CAT = { CET: '大学英语', PUTONGHUA: '普通话', SKILL: '技能证书', OTHER: '其他' }

export default {
  name: 'AaLevelExamView',
  props: { ctx: { type: Object, required: true } },
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect, AppDatePicker,
    AaExamObjectBar, AaExamStageRail
  },
  data() {
    return {
      alive: true, levelPending: null,
      loading: true, error: '', rows: [], current: null, regs: [], detailLoading: false, detailError: '', loadSeq: 0, detailSeq: 0,
      stageSteps: ['创建考试', '学生报名与缴费确认', '截止报名与录入成绩', '完成考试'],
      pagination: { page: 1, pageSize: 20, total: 0 }, regPagination: { page: 1, pageSize: 20, total: 0 },
      scoreExamId: '',
      regColumns: [{ key: 'student', title: '学生' }, { key: 'fee', title: '缴费' },
                   { key: 'result', title: '成绩' }, { key: 'ops', title: '操作' }],
      createVisible: false, formError: '',
      form: { examName: '', category: 'SKILL', level: '', examDate: '', fee: null, passLine: null },
      scoreVisible: false, scoreRow: null, scoreForm: { score: null, result: '', certNo: '' }, scoreError: '',
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null
    }
  },
  created() { this.load() },
  beforeUnmount() { this.alive = false; this.loadSeq++; this.detailSeq++ },
  watch: { identityKey() { this.resetIdentity(); this.load() } },
  computed: {
    identityKey() { return JSON.stringify([currentUserFromToken(), this.ctx]) },
    canWriteLevel() { return this.canManage && !this.levelPending },
    canManage() { return ['SCHOOL','TENANT_ALL'].includes(this.ctx.dataScope?.scope) && matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.levelExam.manage') },
    stageIndex() { return ({ DRAFT: 0, OPEN: 1, CLOSED: 2, FINISHED: 3 })[this.current?.status] ?? 0 },
    openExamCount() { return this.rows.filter(row => row.status === 'OPEN').length },
    unpaidCount() { return this.regs.filter(row => row.status === 'REGISTERED' && row.feeStatus === 'UNPAID').length },
    unscoredCount() { return this.regs.filter(row => row.status === 'REGISTERED').length },
    levelOwner() {
      return ({ DRAFT: '等级考试批次岗', OPEN: '报名与缴费确认岗', CLOSED: '成绩录入岗', FINISHED: '证书归档岗' })[this.current?.status] || (this.ctx.currentRole.roleName || '等级考试管理岗')
    },
    levelNextOwner() {
      return ({ DRAFT: '学生报名与缴费', OPEN: '报名截止与名单确认岗', CLOSED: '成绩录入岗', FINISHED: '证书台账与学生档案' })[this.current?.status] || '学生报名与缴费'
    },
    levelBlocker() {
      if (this.detailError) return this.detailError
      if (this.current?.status === 'OPEN' && this.unpaidCount) return `本页 ${this.unpaidCount} 条报名待缴费确认`
      if (this.current?.status === 'CLOSED' && this.unscoredCount) return `本页 ${this.unscoredCount} 条报名待录成绩`
      return '无已知阻断'
    }
  },
  methods: {
    resetIdentity() {
      this.loadSeq++; this.detailSeq++; this.levelPending = null
      this.rows = []; this.regs = []; this.current = null; this.detailError = ''; this.error = ''; this.detailLoading = false
      this.pagination = { page: 1, pageSize: 20, total: 0 }; this.regPagination = { page: 1, pageSize: 20, total: 0 }
      this.createVisible = false; this.scoreVisible = false; this.confirmVisible = false; this.pendingAction = null; this.saving = false
      this.scoreRow = null; this.scoreExamId = ''; this.formError = ''; this.scoreError = ''
      this.form = { examName: '', category: 'SKILL', level: '', examDate: '', fee: null, passLine: null }
      this.scoreForm = { score: null, result: '', certNo: '' }
    },
    stLabel(s) { return _L[s] || '状态待确认' },
    stType(s) { return s === 'OPEN' ? 'success' : s === 'FINISHED' ? 'default' : s === 'CLOSED' ? 'warning' : 'primary' },
    catLabel(c) { return _CAT[c] || '类别待核对' },
    async load() {
      const seq = ++this.loadSeq, identity = this.identityKey
      this.loading = true; this.error = ''
      try {
        const res = await api.listExams({ page: this.pagination.page, pageSize: this.pagination.pageSize })
        if (seq !== this.loadSeq || identity !== this.identityKey || !this.alive) return
        if (res.code === 0) {
          if (!Array.isArray(res.data?.list) || !Number.isSafeInteger(res.data.total)) throw new Error('考试列表回执不完整')
          this.rows = res.data.list; this.pagination.total = res.data.total
          if (this.current) {
            const selected = this.rows.find(row => row.examId === this.current.examId)
            if (selected) this.current = selected
            else { this.detailSeq++; this.current = null; this.regs = []; this.regPagination.total = 0 }
          }
        } else { this.rows = []; this.current = null; this.regs = []; this.error = res.message || '考试列表加载失败' }
      } catch (error) { if ((seq === this.loadSeq && identity === this.identityKey && this.alive)) { this.rows = []; this.current = null; this.regs = []; this.error = error?.message || '等级考试加载失败' } }
      finally { if ((seq === this.loadSeq && identity === this.identityKey && this.alive)) this.loading = false }
    },
    async changePage(page) {
      if (this.saving || this.levelPending) return
      this.pagination.page = page; this.detailSeq++; this.current = null; this.regs = []
      this.scoreVisible = false; this.confirmVisible = false; this.pendingAction = null
      await this.load()
    },
    async changeRegPage(page) { if (!this.saving && !this.levelPending && this.current) await this.select(this.current, page) },
    async select(e, page = 1) {
      if (!e) return
      if ((this.saving || this.levelPending) && this.current?.examId !== e.examId) return
      this.regPagination.page = page; this.regPagination.total = 0
      if (!this.levelPending) { this.scoreVisible = false; this.confirmVisible = false; this.pendingAction = null }
      const exam = { ...e }, seq = ++this.detailSeq, identity = this.identityKey
      this.current = exam; this.regs = []; this.detailError = ''; this.detailLoading = true
      try {
        const res = await api.listRegs(exam.examId, { page, pageSize: this.regPagination.pageSize })
        if (seq !== this.detailSeq || identity !== this.identityKey || !this.alive || exam.examId !== this.current?.examId) return
        if (res.code === 0) {
          if (!Array.isArray(res.data?.list) || !Number.isSafeInteger(res.data.total)) throw new Error('报名名单回执不完整')
          this.regs = res.data.list; this.regPagination.total = res.data.total
        }
        else this.detailError = res.message || '报名名单加载失败'
      } catch (error) { if ((seq === this.detailSeq && identity === this.identityKey && this.alive)) this.detailError = error?.message || '报名名单加载失败' }
      finally { if ((seq === this.detailSeq && identity === this.identityKey && this.alive)) this.detailLoading = false }
    },
    async runLevelCommand(label, write, read, accept, done) {
      if (!this.canWriteLevel || this.saving) return
      const p = { identity: this.identityKey, label, read, accept, done, reply: null, acknowledged: false }
      this.levelPending = p; this.saving = true
      try {
        const res = await write()
        if (!this.alive || this.identityKey !== p.identity) return
        if (res.code !== 0) {
          if (isDefiniteWriteRejection(res)) this.levelPending = null
          throw res
        }
        p.reply = res.data; p.acknowledged = true
        await this.verifyLevelCommand(true)
      } catch (error) {
        if (this.alive && this.identityKey === p.identity && isDefiniteWriteRejection(error)) this.levelPending = null
        if (this.alive && this.identityKey === p.identity) this.formError = this.scoreError = this.detailError = error?.message || '结果待核实，请只刷新核对，勿重复提交'
      } finally { if (this.alive && this.identityKey === p.identity) this.saving = false }
    },
    async verifyLevelCommand(fromWrite = false) {
      const p = this.levelPending
      if (!p || (!fromWrite && this.saving)) return
      this.saving = true
      const current = () => this.alive && this.identityKey === p.identity && toRaw(this.levelPending) === toRaw(p)
      try {
        const formal = await p.read(p.reply)
        if (!current()) return
        if (!p.acknowledged || !p.accept(formal, p.reply)) { this.detailError = this.formError = this.scoreError = '原操作回执与正式记录尚未核对一致，请勿重复提交'; return }
        this.levelPending = null; this.detailError = ''; this.formError = ''; this.scoreError = ''
        p.done?.(formal); toast.success(p.label + '已核对')
      } catch (error) { if (current()) this.detailError = this.formError = this.scoreError = error?.message || '正式记录暂时无法读取，请稍后只刷新核对' }
      finally { if (this.alive && this.identityKey === p.identity) this.saving = false }
    },
    openCreate() {
      if (!this.canWriteLevel || this.saving) return
      this.form = { examName: '', category: 'SKILL', level: '', examDate: '', fee: null, passLine: null }
      this.formError = ''; this.createVisible = true
    },
    async submitCreate() {
      if (!this.form.examName.trim()) { this.formError = '考试名称必填'; return }
      const body = { ...this.form, fee: this.form.fee ?? undefined, passLine: this.form.passLine ?? undefined }
      return this.runLevelCommand('创建考试', () => api.createExam(body), async reply => {
        this.pagination.page = 1; await this.load()
        return this.rows.find(row => row.examId === reply?.examId)
      }, (formal, reply) => !!formal && formal.examId === reply.examId && formal.examName === body.examName,
      () => { this.createVisible = false })
    },
    act(action, label) {
      if (!this.canWriteLevel || this.saving || !this.current) return
      const exam = { ...this.current }, identity = this.identityKey
      this.confirmTitle = label; this.confirmMessage = `确认对「${exam.examName}」执行「${label}」？`
      this.pendingAction = () => {
        if (identity !== this.identityKey || exam.examId !== this.current?.examId) return
        return this.runLevelCommand(label, () => api.transition(exam.examId, action), async () => {
          await this.load(); return this.rows.find(row => row.examId === exam.examId)
        }, (row, reply) => row?.status === ({ OPEN:'OPEN', CLOSE:'CLOSED', FINISH:'FINISHED' })[action] && row.examId === reply?.examId && row.status === reply.status,
        () => { this.confirmVisible = false; this.pendingAction = null })
      }
      this.confirmVisible = true
    },
    confirmFee(row) {
      if (!this.canWriteLevel || this.saving || !this.current) return
      const exam = { ...this.current }, identity = this.identityKey
      const registration = { ...row }
      this.confirmTitle = '缴费确认'; this.confirmMessage = `确认「${registration.studentName}」已缴纳报名费？`
      this.pendingAction = () => {
        if (identity !== this.identityKey || exam.examId !== this.current?.examId) return
        return this.runLevelCommand('缴费确认', () => api.confirmFee(registration.regId), async () => {
          await this.select(exam, this.regPagination.page); return this.regs.find(r => r.regId === registration.regId)
        }, (formal, reply) => formal?.regId === reply?.regId && formal?.feeStatus === 'PAID' && reply?.feeStatus === 'PAID')
      }; this.confirmVisible = true
    },
    openScore(row) {
      if (!this.canWriteLevel || this.saving || !this.current) return
      this.scoreRow = { ...row }; this.scoreExamId = this.current.examId
      this.scoreForm = { score: null, result: '', certNo: '' }; this.scoreError = ''; this.scoreVisible = true
    },
    async submitScore() {
      if (!this.canWriteLevel || this.saving) return
      if (!this.scoreRow || this.scoreExamId !== this.current?.examId) { this.scoreError = '考试对象已变化，请重新选择报名记录'; return }
      const hasLine = this.current.passLine != null
      if (hasLine && this.scoreForm.score == null) { this.scoreError = '分数必填（按合格线自动判定）'; return }
      if (!hasLine && !this.scoreForm.result) { this.scoreError = '结论必选'; return }
      const exam = { ...this.current }, regId = this.scoreRow.regId, body = { score: this.scoreForm.score ?? undefined, result: this.scoreForm.result || undefined, certNo: this.scoreForm.certNo || undefined }
      return this.runLevelCommand('录入成绩', () => api.enterResult(regId, body), async () => {
        await this.select(exam, this.regPagination.page); return this.regs.find(r => r.regId === regId)
      }, (row, reply) => row?.regId === regId && reply?.regId === regId && row.status === 'SCORED' && row.result === reply.result && row.score === reply.score && row.certNo === reply.certNo,
      () => { this.scoreVisible = false })
    },
    async onConfirm() { if (!this.canWriteLevel || this.saving) return; await this.pendingAction?.() }

  }
}
</script>

<style scoped>
.aalv-paging { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.aalv-list, .aalv-detail { min-width: 0; }
.aalv-layout { display: grid; grid-template-columns: 320px 1fr; gap: 16px; }
.aalv-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.aalv-kpis > div { padding: 14px 16px; border: 1px solid #dce5f2; border-radius: 12px; background: #fff; }
.aalv-kpis > div.is-risk { border-color: #efcf9a; background: #fff9ee; }
.aalv-kpis span, .aalv-kpis small { display: block; color: #71839f; font-size: 12px; }
.aalv-kpis strong { display: block; margin: 5px 0; color: #17365f; font-size: 24px; }
.aalv-exams { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aalv-exam { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aalv-exam.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-light, #eff6ff); }
.aalv-exam-name { font-weight: 500; font-size: 14px; }
.aalv-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.aalv-title { font-size: 16px; font-weight: 600; }
.aalv-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.aalv-form { display: flex; flex-direction: column; gap: 12px; }
@media (max-width: 900px) { .aalv-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } .aalv-layout { grid-template-columns: 1fr; } }
@media (max-width: 560px) { .aalv-kpis { grid-template-columns: 1fr; } }
</style>
