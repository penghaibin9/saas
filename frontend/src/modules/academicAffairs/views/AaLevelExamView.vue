<template>
  <ModulePageShell
    title="等级考务"
    :subtitle="'四六级 / 普通话 / 职业技能等级证书：建考 → 网上报名 → 缴费确认 → 成绩录入（通过可回填证书号，供 1+X 台账取数）'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="openCreate">新建等级考试</AppButton>
    </template>

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

          <EmptyState v-if="!regs.length" title="暂无报名" description="开放报名后学生报名显示在此" />
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

    <AppDrawer :visible="createVisible" title="新建等级考试" @close="createVisible = false">
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

    <AppDrawer :visible="scoreVisible" :title="'录入成绩 · ' + (scoreRow ? scoreRow.studentName : '')" @close="scoreVisible = false">
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
import { toast } from '@/utils/toast'

const _L = { DRAFT: '草稿', OPEN: '报名中', CLOSED: '已截止', FINISHED: '已完成' }
const _CAT = { CET: '大学英语', PUTONGHUA: '普通话', SKILL: '技能证书', OTHER: '其他' }

export default {
  name: 'AaLevelExamView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect, AppDatePicker
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', rows: [], current: null, regs: [],
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
  methods: {
    stLabel(s) { return _L[s] || s },
    stType(s) { return s === 'OPEN' ? 'success' : s === 'FINISHED' ? 'default' : s === 'CLOSED' ? 'warning' : 'primary' },
    catLabel(c) { return _CAT[c] || c },
    async load() {
      this.loading = true; this.error = ''
      const res = await api.listExams({ pageSize: 50 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    async select(e) {
      this.current = e
      const res = await api.listRegs(e.examId, { pageSize: 200 })
      this.regs = res.code === 0 ? res.data.list : []
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
      this.confirmTitle = label
      this.confirmMessage = `确认对「${this.current.examName}」执行「${label}」？`
      this.pendingAction = async () => {
        const res = await api.transition(this.current.examId, action)
        if (res.code === 0) { toast.success(label + '成功'); await this.load(); const cur = this.rows.find((r) => r.examId === this.current.examId); if (cur) await this.select(cur) }
        else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    confirmFee(row) {
      this.confirmTitle = '缴费确认'
      this.confirmMessage = `确认「${row.studentName}」已缴纳报名费${this.current.fee != null ? '（¥' + this.current.fee + '）' : ''}？`
      this.pendingAction = async () => {
        const res = await api.confirmFee(row.regId)
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
.aalv-exams { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aalv-exam { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aalv-exam.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-light, #eff6ff); }
.aalv-exam-name { font-weight: 500; font-size: 14px; }
.aalv-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.aalv-title { font-size: 16px; font-weight: 600; }
.aalv-actions { display: flex; gap: 8px; }
.aalv-form { display: flex; flex-direction: column; gap: 12px; }
</style>
