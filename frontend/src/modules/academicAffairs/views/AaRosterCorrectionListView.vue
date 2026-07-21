<template>
  <ModulePageShell
    title="学籍信息更正"
    subtitle="学号 / 姓名 / 性别 / 证件号 / 年级录入错误据实更正 · 单步审核后同步主档（不产生学籍状态迁移）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="openCreate">＋ 发起更正</AppButton>
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="resetFilters" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无学籍信息更正申请" description="点击右上角「＋ 发起更正」创建，或从「学籍名册」学生详情发起" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="correctionId"
                 :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.realName }}</div>
          <div class="mp-cell-sub">学号 {{ row.studentNo || '—' }} · {{ row.fieldLabel }}</div>
        </template>
        <template #cell-diff="{ row }">
          <span class="aa-diff-old">{{ row.oldValue || '—' }}</span>
          <span class="aa-diff-arrow">→</span>
          <span class="aa-diff-new">{{ row.newValue }}</span>
          <span v-if="row.sensitive" class="aa-sensitive">敏感</span>
        </template>
        <template #cell-reason="{ row }">{{ row.reason }}</template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="statusColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
          <div v-if="row.reviewNote" class="mp-cell-sub">{{ row.reviewNote }}</div>
        </template>
        <template #cell-actions="{ row }">
          <template v-if="row.status === 'PENDING'">
            <button class="mp-link" :disabled="acting" @click="approve(row)">通过</button>
            <button class="mp-link" :disabled="acting" @click="reject(row)">驳回</button>
          </template>
          <button class="mp-link" @click="goRoster(row)">学籍档案</button>
        </template>
      </DataTable>
      <p class="mp-note">仅支持学号/姓名/性别/证件号/年级四类身份数据纠错；学籍状态、院系专业班级变更须走「学籍异动」。</p>
    </div>

    <AppDrawer :visible="createVisible" title="发起学籍信息更正" @close="createVisible = false">
      <div class="aa-form">
        <AppFormItem label="学生" required>
          <div v-if="form.studentId" class="aa-picked">
            {{ form.studentName || '学生' }} · ID {{ form.studentId }}
            <button class="mp-link" @click="clearStudent">重选</button>
          </div>
          <div v-else class="aa-reg-search">
            <AppTextInput v-model="kw" placeholder="按姓名/学号检索学生" @keyup.enter="searchStudents" />
            <AppButton variant="ghost" :loading="searching" @click="searchStudents">检索</AppButton>
          </div>
          <ul v-if="!form.studentId && candidates.length" class="aa-cand-list">
            <li v-for="s in candidates" :key="s.studentId" class="aa-cand-item">
              <span>{{ s.realName }} · 学号 {{ s.studentNo }} · {{ statusText(s.studentStatus) }}</span>
              <button class="mp-link" @click="pickStudent(s)">选择</button>
            </li>
          </ul>
        </AppFormItem>

        <AppFormItem label="更正字段" required>
          <AppSelect v-model="form.fieldKey" :options="fieldOptions" placeholder="选择更正字段" @change="onFieldChange" />
        </AppFormItem>

        <AppFormItem v-if="form.fieldKey" :label="`更正为（${FIELD_LABEL[form.fieldKey]}）`" required>
          <AppSelect v-if="form.fieldKey === 'GENDER'" v-model="form.newValue" :options="[{label:'男',value:'男'},{label:'女',value:'女'}]" placeholder="选择性别" />
          <AppTextInput v-else v-model="form.newValue" :placeholder="fieldPlaceholder" />
        </AppFormItem>

        <AppFormItem label="更正原因" required hint="≥5 字，写入审计留痕">
          <AppTextarea v-model="form.reason" :rows="3" :maxlength="500" show-count placeholder="如：迎新录入笔误，据学生身份证原件核实更正" />
        </AppFormItem>

        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="submitting" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="submitting" @click="submitCreate">提交</AppButton>
      </template>
    </AppDrawer>

    <!-- 通过：无原因动作，但会立即写学籍主档，故仍给正规弹窗把新旧值摆出来核对 -->
    <AppConfirmDialog
      v-model:visible="approveDialog.visible" title="通过学籍更正申请" type="warning"
      confirm-text="确认通过并同步主档"
      description="通过后立即写入学籍主档，该动作不可撤销。请先核对下方新旧值。"
      :submitting="acting" @confirm="doApprove"
    >
      <AppDescriptionList v-if="approveDialog.row" :items="approveItems" :columns="1" bordered />
      <p v-if="approveDialog.row && approveDialog.row.sensitive" class="rc-mask-note">
        证件号按敏感字段脱敏显示，与列表页一致；如需核对完整号码请查阅申请人上传的证明材料。
      </p>
    </AppConfirmDialog>

    <!-- 驳回原因未挂快捷用语：配置方案未给「学籍更正驳回」场景词条，不硬套其它场景（会串味） -->
    <AppConfirmDialog
      v-model:visible="rejectDialog.visible" title="驳回学籍更正申请" type="danger"
      confirm-text="确认驳回" require-reason reason-label="驳回原因（≥5字，将回传申请人）"
      :submitting="acting" @confirm="doReject"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 学籍信息更正（/admin/academic-affairs/roster/corrections）：
 * GET/POST /academic-affairs/roster/corrections、POST /roster/corrections/{id}/review。
 * 区别于「学籍异动」：只纠正学号/姓名/性别/证件号/年级录入错误，不产生学籍状态迁移，
 * 字段范围明确排除学籍状态/院系专业班级（那些变更走 change_student_status 单一入口）。
 * 通过与驳回均走 AppConfirmDialog：通过虽无原因入参，但会立即写学籍主档且不可撤销，
 * 故仍需正规弹窗把新旧值摆出来核对（原为 window.confirm，与学工中心同类动作不一致）。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AdvancedFilter } from '@/components/business'
import { AppStatusTag, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppInlineAlert, AppConfirmDialog, AppDescriptionList } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const FIELD_LABEL = { STUDENT_NO: '学号', REAL_NAME: '姓名', GENDER: '性别', ID_CARD: '证件号', GRADE: '年级' }
const STATUS_LABEL = { PENDING: '待审核', APPROVED: '已通过', REJECTED: '已驳回' }
const FIELD_PLACEHOLDER = { STUDENT_NO: '正确学号', REAL_NAME: '正确姓名', ID_CARD: '正确证件号（15或18位）', GRADE: '正确年级，如 2026' }
const STUDENT_STATUS_TEXT = { REGISTERED: '在籍注册', PENDING_REGISTER: '待注册', SUSPENDED: '休学', WITHDRAWN: '退学', RETAINED: '留级', GRADUATED: '毕业' }

function emptyForm() {
  return { studentId: '', studentName: '', fieldKey: '', newValue: '', reason: '' }
}

export default {
  name: 'AaRosterCorrectionListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AdvancedFilter, AppStatusTag,
               AppFormItem, AppTextInput, AppTextarea, AppSelect, AppInlineAlert, AppButton, AppDrawer,
               AppConfirmDialog, AppDescriptionList },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      FIELD_LABEL,
      approveDialog: { visible: false, row: null },
      rejectDialog: { visible: false, row: null },
      loading: true,
      error: '',
      rows: [],
      filters: { status: this.$route.query.status || '', fieldKey: '' },
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'student', title: '学生 / 字段' },
        { key: 'diff', title: '更正前 → 更正后' },
        { key: 'reason', title: '原因' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '170px' }
      ],
      acting: false,
      createVisible: false,
      submitting: false,
      formError: '',
      kw: '',
      searching: false,
      candidates: [],
      form: emptyForm()
    }
  },
  computed: {
    fieldOptions() {
      return Object.keys(FIELD_LABEL).map((k) => ({ label: FIELD_LABEL[k], value: k }))
    },
    filterFields() {
      return [
        {
          key: 'status',
          label: '审核状态',
          type: 'select',
          placeholder: '全部',
          options: [
            { value: 'PENDING', label: '待审核' },
            { value: 'APPROVED', label: '已通过' },
            { value: 'REJECTED', label: '已驳回' }
          ]
        },
        {
          key: 'fieldKey',
          label: '更正字段',
          type: 'select',
          placeholder: '全部',
          options: Object.keys(FIELD_LABEL).map((k) => ({ value: k, label: FIELD_LABEL[k] }))
        }
      ]
    },
    fieldPlaceholder() {
      return FIELD_PLACEHOLDER[this.form.fieldKey] || ''
    },
    /**
     * 通过确认弹窗里的新旧值对比——写主档前让人看清到底改的是谁的哪一项。
     * 证件号的新旧值由后端 _correction_row 默认脱敏（reveal=false 时走 _mask_id_card），
     * 此处如实展示脱敏值：与列表页、与改造前的原生确认框口径一致，不在此处放开明文。
     */
    approveItems() {
      const r = this.approveDialog.row
      if (!r) return []
      return [
        { label: '学生', value: `${r.realName || ''} ${r.studentNo || ''}`.trim() || '—' },
        { label: '更正字段', value: r.fieldLabel || FIELD_LABEL[r.fieldKey] || r.fieldKey },
        { label: '原值', value: r.oldValue || '—' },
        { label: '新值', value: r.newValue || '—' }
      ]
    }
  },
  created() {
    this.load()
    // 从「学籍档案」详情页「发起学籍信息更正」快捷入口带 studentId/name 跳转时，直接预填打开新建抽屉
    // （与 AaStatusChangeFormView 对「发起学籍异动」的预填方式一致）。
    if (this.$route.query.studentId) {
      this.openCreate()
      this.form.studentId = this.$route.query.studentId
      this.form.studentName = this.$route.query.name || ''
    }
  },
  methods: {
    // 本模块 getContext().permissionActions 恒为 {}（真实权限边界始终以后端为准，见 API 文件头注释）；
    // 不做客户端按钮级权限遮蔽，越权由后端 403 + toast 提示（与本模块其余真实页面口径一致）。
    statusLabel(s) { return STATUS_LABEL[s] || s || '' },
    statusText(s) { return STUDENT_STATUS_TEXT[s] || s || '' },
    statusColor(s) {
      if (s === 'APPROVED') return 'success'
      if (s === 'REJECTED') return 'danger'
      return 'warning'
    },
    goRoster(row) { this.$router.push(`/admin/academic-affairs/roster/${row.studentId}`) },
    onPageChange(page) { this.pagination.page = page; this.load() },
    search() { this.pagination.page = 1; this.load() },
    resetFilters() { this.filters.status = ''; this.filters.fieldKey = ''; this.search() },
    onFieldChange() { this.form.newValue = '' },
    openCreate() {
      this.form = emptyForm()
      this.kw = ''
      this.candidates = []
      this.formError = ''
      this.createVisible = true
    },
    clearStudent() { this.form.studentId = ''; this.form.studentName = '' },
    pickStudent(s) {
      this.form.studentId = s.studentId
      this.form.studentName = s.realName
      this.candidates = []
    },
    async searchStudents() {
      if (this.searching || !this.kw.trim()) return
      this.searching = true
      const res = await academicAffairsApi.getRoster({ keyword: this.kw.trim(), page: 1, pageSize: 20 })
      this.candidates = res.code === 0 ? res.data.list : []
      this.searching = false
    },
    async submitCreate() {
      this.formError = ''
      if (!this.form.studentId) { this.formError = '请先选择学生'; return }
      if (!this.form.fieldKey) { this.formError = '请选择更正字段'; return }
      if (!this.form.newValue || !this.form.newValue.trim()) { this.formError = '更正后的值不能为空'; return }
      if (!this.form.reason || this.form.reason.trim().length < 5) { this.formError = '更正原因必填且不少于5字'; return }
      this.submitting = true
      const res = await academicAffairsApi.createRosterCorrection({
        studentId: this.form.studentId, fieldKey: this.form.fieldKey,
        newValue: this.form.newValue.trim(), reason: this.form.reason.trim()
      })
      this.submitting = false
      if (res.code === 0) {
        toast.success('更正申请已提交，待审核')
        this.createVisible = false
        this.load()
      } else {
        this.formError = res.message
      }
    },
    approve(row) {
      if (this.acting) return
      this.approveDialog = { visible: true, row }
    },
    async doApprove() {
      const row = this.approveDialog.row
      if (!row) return
      this.acting = true
      const res = await academicAffairsApi.reviewRosterCorrection(row.correctionId, 'APPROVE', '')
      this.acting = false
      if (res.code === 0) {
        this.approveDialog.visible = false
        toast.success('已通过，主档已同步')
        this.load()
      } else toast.error(res.message)
    },
    reject(row) {
      if (this.acting) return
      this.rejectDialog = { visible: true, row }
    },
    async doReject({ reason }) {
      const row = this.rejectDialog.row
      if (!row) return
      this.acting = true
      const res = await academicAffairsApi.reviewRosterCorrection(row.correctionId, 'REJECT', reason)
      this.acting = false
      if (res.code === 0) {
        this.rejectDialog.visible = false
        toast.success('已驳回')
        this.load()
      } else toast.error(res.message)
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getRosterCorrections({
        status: this.filters.status || undefined,
        fieldKey: this.filters.fieldKey || undefined,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-select { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-diff-old { color: var(--text-400, #8a9099); text-decoration: line-through; }
.aa-diff-arrow { margin: 0 6px; color: var(--text-400, #8a9099); }
.aa-diff-new { color: var(--text-900, #1f2329); font-weight: 600; }
.aa-sensitive { display: inline-block; margin-left: 6px; padding: 0 6px; border-radius: 4px; background: var(--warning-50, #fff7e6); color: var(--warning-600, #d48806); border: 1px solid var(--warning-100, #ffe7ba); font-size: 12px; }
.aa-form { display: flex; flex-direction: column; gap: 16px; }
.aa-reg-search { display: flex; gap: 10px; align-items: center; }
.aa-picked { display: flex; align-items: center; gap: 12px; font-size: 14px; }
.aa-cand-list { list-style: none; margin: 10px 0 0; padding: 0; border: 1px solid var(--border-100, #f0f1f2); border-radius: 6px; }
.aa-cand-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 13px; }
.aa-cand-item:last-child { border-bottom: none; }
.rc-mask-note { margin: 12px 0 0; color: var(--text-tertiary); font-size: 13px; }
</style>
