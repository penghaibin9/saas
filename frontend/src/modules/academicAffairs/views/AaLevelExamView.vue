<template>
  <ModulePageShell
    title="等级考试"
    :subtitle="'四六级 / 普通话 / 职业技能等级证书：建考 → 网上报名 → 缴费确认 → 成绩录入（通过可回填证书号，供 1+X 台账取数）'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="openCreate">新建等级考试</AppButton>
    </template>

    <AaExamObjectBar
      :title="current?.examName || '等级考试批次清单'"
      :object-id="current ? `LEVEL-EXAM-${current.examId}` : `${rows.length} 个考试批次`"
      source="考务管理 / 等级考试"
      :status="current ? stLabel(current.status) : '等待选择考试'"
      :owner="levelOwner"
      :blocker="levelBlocker"
      :blocked="!!detailError"
      :next-owner="levelNextOwner"
    />
    <AaExamStageRail :steps="stageSteps" :active-index="stageIndex" aria-label="等级考试办理阶段" />

    <div class="aalv-kpis" aria-label="等级考试业务摘要">
      <div><span>考试批次</span><strong>{{ rows.length }}</strong><small>当前真实数据范围</small></div>
      <div><span>报名中</span><strong>{{ openExamCount }}</strong><small>学生可提交报名</small></div>
      <div :class="{ 'is-risk': unpaidCount }"><span>待缴费确认</span><strong>{{ current ? unpaidCount : '—' }}</strong><small>所选批次正式报名</small></div>
      <div :class="{ 'is-risk': unscoredCount }"><span>待录成绩</span><strong>{{ current ? unscoredCount : '—' }}</strong><small>已截止或完成批次</small></div>
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
      </div>

      <div class="aalv-detail">
        <EmptyState v-if="!current" title="选择一个考试" description="从左侧选择等级考试管理报名与成绩" />
        <template v-else>
          <div class="aalv-head">
            <div class="aalv-title">{{ current.examName }}</div>
            <div class="aalv-actions">
              <AppButton v-if="current.status === 'DRAFT'" size="small" variant="primary" @click="act('OPEN', '开放报名')">开放报名</AppButton>
              <AppButton v-if="current.status === 'OPEN'" size="small" variant="warning" @click="act('CLOSE', '截止报名')">截止报名</AppButton>
              <AppButton v-if="current.status === 'CLOSED'" size="small" variant="primary" @click="act('FINISH', '完成考试（须成绩全录）')">完成</AppButton>
            </div>
          </div>

          <ErrorState v-if="detailError" title="报名名单加载失败" :description="detailError" @retry="select(current)" />
          <LoadingState v-else-if="detailLoading" />
          <EmptyState v-else-if="!regs.length" title="暂无报名" description="开放报名后学生报名显示在此" />
          <DataTable v-else :columns="regColumns" :rows="regs" row-key="regId">
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
              <button v-if="row.status === 'REGISTERED' && row.feeStatus === 'UNPAID'" class="mp-link" @click="confirmFee(row)">缴费确认</button>
              <button v-if="row.status === 'REGISTERED' && ['CLOSED','FINISHED'].includes(current.status)" class="mp-link" @click="openScore(row)">录成绩</button>
            </template>
          </DataTable>
        </template>
      </div>
    </div>

    <AppDrawer :visible="createVisible" title="新建等级考试" mode="modal" size="large" @close="createVisible = false">
      <div class="aalv-form">
        <AppFormItem label="考试名称" required><AppTextInput v-model="form.examName" placeholder="如 大学英语四级(2025-06)" :disabled="saving" /></AppFormItem>
        <AppFormItem label="类别" required>
          <AppSelect v-model="form.category" :options="[{ label: '大学英语等级(CET)', value: 'CET' }, { label: '普通话水平', value: 'PUTONGHUA' }, { label: '职业技能等级证书', value: 'SKILL' }, { label: '其他', value: 'OTHER' }]" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="等级"><AppTextInput v-model="form.level" placeholder="如 四级 / 二甲 / 中级" :disabled="saving" /></AppFormItem>
        <AppFormItem label="考试日期"><AppDatePicker v-model="form.examDate" :disabled="saving" /></AppFormItem>
        <AppFormItem label="报名费（元）"><AppNumberInput v-model="form.fee" :min="0" :max="9999" :disabled="saving" /></AppFormItem>
        <AppFormItem label="合格线（分数制考试）"><AppNumberInput v-model="form.passLine" :min="0" :max="750" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="scoreVisible" :title="'录入成绩 · ' + (scoreRow ? scoreRow.studentName : '')" mode="modal" size="medium" @close="scoreVisible = false">
      <div class="aalv-form">
        <AppFormItem :label="current && current.passLine ? '分数（合格线 ' + current.passLine + '，自动判定通过）' : '分数（选填）'">
          <AppNumberInput v-model="scoreForm.score" :min="0" :max="750" :disabled="saving" />
        </AppFormItem>
        <AppFormItem v-if="!(current && current.passLine)" label="结论" required>
          <AppSelect v-model="scoreForm.result" :options="[{ label: '通过', value: 'PASS' }, { label: '未通过', value: 'FAIL' }]" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="证书编号（通过时选填）"><AppTextInput v-model="scoreForm.certNo" placeholder="如 CET4-2025-XXXX" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="scoreError" type="danger" :description="scoreError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="scoreVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitScore">保存</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** 等级考务（/admin/academic-affairs/level-exams）：建考→报名→缴费确认→成绩录入。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect, AppDatePicker } from '@/components/common'
import { academicAffairsApi, academicAffairsLevelExamApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import AaExamObjectBar from '@/modules/academicAffairs/components/exam/AaExamObjectBar.vue'
import AaExamStageRail from '@/modules/academicAffairs/components/exam/AaExamStageRail.vue'
import { toast } from '@/utils/toast'

const _L = { DRAFT: '草稿', OPEN: '报名中', CLOSED: '已截止', FINISHED: '已完成' }
const _CAT = { CET: '大学英语', PUTONGHUA: '普通话', SKILL: '技能证书', OTHER: '其他' }

export default {
  name: 'AaLevelExamView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect, AppDatePicker,
    AaExamObjectBar, AaExamStageRail
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', rows: [], current: null, regs: [], detailLoading: false, detailError: '', loadSeq: 0, detailSeq: 0,
      stageSteps: ['创建批次', '圈课冻结', '编排预检', '考试发布', '异常收口'],
      regColumns: [{ key: 'student', title: '学生' }, { key: 'fee', title: '缴费' },
                   { key: 'result', title: '成绩' }, { key: 'ops', title: '操作' }],
      createVisible: false, formError: '',
      form: { examName: '', category: 'SKILL', level: '', examDate: '', fee: null, passLine: null },
      scoreVisible: false, scoreRow: null, scoreForm: { score: null, result: '', certNo: '' }, scoreError: '',
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
  },
  beforeUnmount() { this.loadSeq++; this.detailSeq++ },
  computed: {
    stageIndex() { return ({ DRAFT: 0, OPEN: 1, CLOSED: 2, FINISHED: 4 })[this.current?.status] ?? 0 },
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
      if (this.current?.status === 'OPEN' && this.unpaidCount) return `${this.unpaidCount} 条报名待缴费确认`
      if (this.current?.status === 'CLOSED' && this.unscoredCount) return `${this.unscoredCount} 条报名待录成绩`
      return '无已知阻断'
    }
  },
  methods: {
    stLabel(s) { return _L[s] || '状态待确认' },
    stType(s) { return s === 'OPEN' ? 'success' : s === 'FINISHED' ? 'default' : s === 'CLOSED' ? 'warning' : 'primary' },
    catLabel(c) { return _CAT[c] || c },
    async load() {
      const seq = ++this.loadSeq
      this.loading = true; this.error = ''
      try {
        const res = await api.listExams({ pageSize: 50 })
        if (seq !== this.loadSeq) return
        if (res.code === 0) {
          this.rows = Array.isArray(res.data?.list) ? res.data.list : []
          if (this.current) {
            const selected = this.rows.find(row => row.examId === this.current.examId)
            if (selected) this.current = selected
          }
        } else this.error = res.message
      } catch (error) { if (seq === this.loadSeq) this.error = error?.message || '等级考试加载失败' }
      finally { if (seq === this.loadSeq) this.loading = false }
    },
    async select(e) {
      const exam = { ...e }, seq = ++this.detailSeq
      this.current = exam; this.regs = []; this.detailError = ''; this.detailLoading = true
      try {
        const res = await api.listRegs(exam.examId, { pageSize: 200 })
        if (seq !== this.detailSeq || exam.examId !== this.current?.examId) return
        if (res.code === 0) this.regs = Array.isArray(res.data?.list) ? res.data.list : []
        else this.detailError = res.message || '报名名单加载失败'
      } catch (error) { if (seq === this.detailSeq) this.detailError = error?.message || '报名名单加载失败' }
      finally { if (seq === this.detailSeq) this.detailLoading = false }
    },
    openCreate() {
      this.form = { examName: '', category: 'SKILL', level: '', examDate: '', fee: null, passLine: null }
      this.formError = ''; this.createVisible = true
    },
    async submitCreate() {
      if (!this.form.examName) { this.formError = '考试名称必填'; return }
      this.saving = true
      const res = await api.createExam({ ...this.form, fee: this.form.fee ?? undefined, passLine: this.form.passLine ?? undefined })
      this.saving = false
      if (res.code === 0) { toast.success('已创建'); this.createVisible = false; this.load() } else this.formError = res.message
    },
    act(action, label) {
      const exam = { ...this.current }
      this.confirmTitle = label
      this.confirmMessage = `确认对「${exam.examName}」执行「${label}」？`
      this.pendingAction = async () => {
        if (exam.examId !== this.current?.examId) { toast.error('当前考试对象已变化，请重新确认'); return }
        const res = await api.transition(exam.examId, action)
        if (res.code === 0) { toast.success(label + '成功'); await this.load(); const cur = this.rows.find((r) => r.examId === exam.examId); if (cur) await this.select(cur) }
        else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    confirmFee(row) {
      const examId = this.current?.examId
      const registration = { ...row }
      this.confirmTitle = '缴费确认'
      this.confirmMessage = `确认「${registration.studentName}」已缴纳报名费${this.current.fee != null ? '（¥' + this.current.fee + '）' : ''}？`
      this.pendingAction = async () => {
        if (examId !== this.current?.examId) { toast.error('当前考试对象已变化，请重新确认'); return }
        const res = await api.confirmFee(registration.regId)
        if (res.code === 0) { toast.success('已确认'); await this.select(this.current) } else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    openScore(row) { this.scoreRow = row; this.scoreForm = { score: null, result: '', certNo: '' }; this.scoreError = ''; this.scoreVisible = true },
    async submitScore() {
      const hasLine = this.current && this.current.passLine
      if (hasLine && this.scoreForm.score == null) { this.scoreError = '分数必填（按合格线自动判定）'; return }
      if (!hasLine && !this.scoreForm.result) { this.scoreError = '结论必选'; return }
      this.saving = true
      const res = await api.enterResult(this.scoreRow.regId, {
        score: this.scoreForm.score ?? undefined,
        result: this.scoreForm.result || undefined,
        certNo: this.scoreForm.certNo || undefined
      })
      this.saving = false
      if (res.code === 0) { toast.success('已录入'); this.scoreVisible = false; await this.select(this.current) } else this.scoreError = res.message
    },
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() }
  }
}
</script>

<style scoped>
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
.aalv-actions { display: flex; gap: 8px; }
.aalv-form { display: flex; flex-direction: column; gap: 12px; }
@media (max-width: 900px) { .aalv-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } .aalv-layout { grid-template-columns: 1fr; } }
@media (max-width: 560px) { .aalv-kpis { grid-template-columns: 1fr; } }
</style>
