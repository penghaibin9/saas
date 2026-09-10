<template>
  <ModulePageShell
    title="学籍信息更正"
    subtitle="学号 / 姓名 / 性别 / 证件号 / 年级录入错误据实更正 · 单步审核后同步主档（不产生学籍状态迁移）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton variant="primary" @click="openCreate">＋ 发起更正</AppButton>
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="resetFilters" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无学籍信息更正申请" description="点击右上角「＋ 发起更正」创建，或从「学籍名册」学生详情发起" />
      <div v-else class="aa-correction-workspace">
        <section class="aa-object-summary">
          <div>
            <h2>{{ selectedRow.realName || '姓名待核实' }}</h2>
            <p>学籍信息更正 · {{ selectedRow.correctionId }} · {{ selectedRow.studentNo || '学号待核实' }}</p>
            <small>来源：当前对象已由其来源岗位建立；本入口只办理所列动作，不重复创建上游对象</small>
          </div>
          <dl>
            <div><dt>当前责任</dt><dd>学籍专员</dd></div>
            <div><dt>下一责任</dt><dd>{{ selectedRow.status === 'PENDING' ? '学籍核验岗' : '返回原队列' }}</dd></div>
          </dl>
        </section>

        <ol class="aa-stage-rail" aria-label="学籍信息更正办理阶段">
          <li class="is-complete"><span>✓</span><div><strong>权威学生主档</strong><small>上游事实可回查</small></div></li>
          <li class="is-complete"><span>✓</span><div><strong>注册与异动</strong><small>历史事实可回查</small></div></li>
          <li class="is-current"><span>3</span><div><strong>正式身份</strong><small>当前设计视角</small></div></li>
          <li><span>4</span><div><strong>历史档案</strong><small>按真实状态解锁</small></div></li>
        </ol>

        <AppInlineAlert type="info" description="申请只记录拟更正内容，不先改正式事实；按当前审核节点处理，已归档场景进入受控纠错。" />

        <div class="aa-correction-layout">
          <aside class="aa-responsibility-queue" aria-label="学籍信息更正责任队列">
            <h3>责任队列</h3>
            <button v-for="row in rows" :key="row.correctionId" type="button"
                    :class="['aa-queue-item', { 'is-active': row.correctionId === selectedCorrectionId }]"
                    @click="selectedCorrectionId = row.correctionId">
              <strong>{{ row.realName || '姓名待核实' }}</strong>
              <small>{{ row.fieldLabel }} · {{ row.correctionId }}</small>
              <span><AppStatusTag :type="statusColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag></span>
            </button>
            <div class="aa-queue-pager">
              <button class="mp-link" :disabled="pagination.page <= 1" @click="onPageChange(pagination.page - 1)">上一页</button>
              <span>第 {{ pagination.page }} 页 · 共 {{ pagination.total }} 条</span>
              <button class="mp-link" :disabled="pagination.page * pagination.pageSize >= pagination.total" @click="onPageChange(pagination.page + 1)">下一页</button>
            </div>
          </aside>

          <main class="aa-correction-detail">
            <section class="aa-detail-card">
              <h3>原值与申请新值</h3>
              <div class="aa-value-grid">
                <div class="aa-value-column">
                  <small>{{ selectedRow.fieldLabel }} · 当前正式值</small>
                  <strong class="aa-diff-old">{{ selectedRow.oldValue || '—' }}</strong>
                </div>
                <div class="aa-value-column is-new">
                  <small>{{ selectedRow.fieldLabel }} · 拟更正值</small>
                  <strong class="aa-diff-new">{{ selectedRow.newValue || '—' }}</strong>
                </div>
              </div>
              <p class="mp-note">{{ selectedRow.sensitive ? '敏感字段按授权脱敏展示；审核时仍须核对证明材料。' : '动态字段从当前正式主档与本次申请读取，不使用固定演示值。' }}</p>
            </section>

            <section class="aa-detail-card">
              <h3>本岗位办理</h3>
              <dl class="aa-review-facts">
                <div><dt>申请原因</dt><dd>{{ selectedRow.reason || '未填写' }}</dd></div>
                <div><dt>当前状态</dt><dd><AppStatusTag :type="statusColor(selectedRow.status)" dot>{{ statusLabel(selectedRow.status) }}</AppStatusTag></dd></div>
                <div v-if="selectedRow.reviewNote"><dt>审核意见</dt><dd>{{ selectedRow.reviewNote }}</dd></div>
              </dl>
              <div class="aa-detail-actions">
                <template v-if="selectedRow.status === 'PENDING'">
                  <AppButton variant="primary" :disabled="acting" @click="approve(selectedRow)">通过并同步主档</AppButton>
                  <AppButton variant="ghost" :disabled="acting" @click="reject(selectedRow)">驳回申请</AppButton>
                </template>
                <AppButton variant="ghost" @click="goRoster(selectedRow)">查看学籍档案</AppButton>
              </div>
              <p class="mp-note">审核命令返回后重新读取正式更正记录；最终事实以学生主档为准。</p>
            </section>
          </main>
        </div>
      </div>
      <p class="mp-note">仅支持学号/姓名/性别/证件号/年级四类身份数据纠错；学籍状态、院系专业班级变更须走「学籍异动」。</p>
    </div>

    <AppDrawer :visible="createVisible" title="发起学籍信息更正" mode="modal" size="large" @close="createVisible = false">
      <div class="aa-form">
        <AppFormItem label="学生" required>
          <AppStudentPicker v-model="form.studentId" placeholder="按姓名/学号检索学生" @change="onStudentChange" />
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
import { ModulePageShell, LoadingState, ErrorState, EmptyState, AdvancedFilter } from '@/components/business'
import { AppStatusTag, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppInlineAlert, AppConfirmDialog, AppDescriptionList, AppStudentPicker } from '@/components/common'
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
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AdvancedFilter, AppStatusTag,
               AppFormItem, AppTextInput, AppTextarea, AppSelect, AppInlineAlert, AppButton, AppDrawer,
               AppConfirmDialog, AppDescriptionList, AppStudentPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      FIELD_LABEL,
      approveDialog: { visible: false, row: null },
      rejectDialog: { visible: false, row: null },
      loading: true,
      error: '',
      rows: [],
      selectedCorrectionId: '',
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
    },
    selectedRow() {
      return this.rows.find((row) => row.correctionId === this.selectedCorrectionId) || this.rows[0] || {}
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
    statusLabel(s) { return STATUS_LABEL[s] || (s ? '状态待确认' : '') },
    statusText(s) { return STUDENT_STATUS_TEXT[s] || (s ? '状态待确认' : '') },
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
      this.formError = ''
      this.createVisible = true
    },
    onStudentChange(value, items) {
      const item = items?.[0]
      const student = item?.raw || item || {}
      this.form.studentName = student.realName || student.studentName || item?.label || ''
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
        if (!this.rows.some((row) => row.correctionId === this.selectedCorrectionId)) {
          this.selectedCorrectionId = this.rows[0]?.correctionId || ''
        }
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
.aa-correction-workspace { display: grid; gap: 16px; }
.aa-object-summary { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 16px 18px; border: 1px solid var(--border-200, #e5eaf3); border-left: 3px solid var(--primary-600, #2f65c8); border-radius: 10px; background: #fff; }
.aa-object-summary h2 { margin: 0 0 4px; font-size: 17px; }
.aa-object-summary p, .aa-object-summary small { margin: 0; color: var(--text-500, #667085); }
.aa-object-summary dl { display: grid; grid-template-columns: repeat(2, minmax(120px, auto)); gap: 24px; margin: 0; }
.aa-object-summary dl div { display: grid; gap: 4px; }
.aa-object-summary dt { color: var(--text-500, #667085); font-size: 12px; }
.aa-object-summary dd { margin: 0; font-weight: 700; color: var(--text-900, #172b4d); }
.aa-stage-rail { display: grid; grid-template-columns: repeat(4, 1fr); margin: 0; padding: 14px 16px; list-style: none; border: 1px solid var(--border-200, #e5eaf3); border-radius: 10px; background: #fff; }
.aa-stage-rail li { display: flex; align-items: center; gap: 10px; color: var(--text-500, #667085); }
.aa-stage-rail li > span { display: grid; width: 24px; height: 24px; place-items: center; border: 1px solid #dbe3ef; border-radius: 50%; background: #fff; font-size: 12px; }
.aa-stage-rail li div { display: grid; gap: 2px; }
.aa-stage-rail li small { font-size: 11px; }
.aa-stage-rail li.is-complete > span { border-color: #b9dfcc; background: #eef9f3; color: #22865b; }
.aa-stage-rail li.is-current { color: var(--primary-700, #2458b8); }
.aa-stage-rail li.is-current > span { border-color: var(--primary-600, #2f65c8); background: var(--primary-600, #2f65c8); color: #fff; }
.aa-correction-layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 16px; align-items: start; }
.aa-responsibility-queue, .aa-detail-card { overflow: hidden; border: 1px solid var(--border-200, #e5eaf3); border-radius: 10px; background: #fff; }
.aa-responsibility-queue h3, .aa-detail-card h3 { margin: 0; padding: 14px 16px; border-bottom: 1px solid var(--border-200, #e5eaf3); font-size: 15px; }
.aa-queue-item { display: grid; width: 100%; gap: 5px; padding: 13px 14px; border: 0; border-bottom: 1px solid var(--border-100, #eef1f5); background: #fff; color: inherit; text-align: left; cursor: pointer; }
.aa-queue-item small { color: var(--text-500, #667085); }
.aa-queue-item.is-active { background: #edf4ff; box-shadow: inset 3px 0 var(--primary-600, #2f65c8); }
.aa-queue-pager { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 12px; font-size: 12px; color: var(--text-500, #667085); }
.aa-correction-detail { display: grid; gap: 16px; }
.aa-value-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; padding: 16px; }
.aa-value-column { display: grid; gap: 8px; padding: 14px; border: 1px solid #dfe6f0; border-radius: 8px; background: #f7f9fc; }
.aa-value-column.is-new { background: #fff; }
.aa-value-column small { color: var(--text-500, #667085); }
.aa-detail-card > .mp-note { margin: 0; padding: 0 16px 16px; }
.aa-review-facts { display: grid; gap: 12px; margin: 0; padding: 16px; }
.aa-review-facts div { display: grid; grid-template-columns: 92px minmax(0, 1fr); gap: 12px; }
.aa-review-facts dt { color: var(--text-500, #667085); }
.aa-review-facts dd { margin: 0; color: var(--text-900, #172b4d); }
.aa-detail-actions { display: flex; flex-wrap: wrap; gap: 10px; padding: 0 16px 16px; }
@media (max-width: 980px) {
  .aa-object-summary { align-items: flex-start; flex-direction: column; }
  .aa-correction-layout { grid-template-columns: 1fr; }
  .aa-stage-rail { grid-template-columns: repeat(2, 1fr); gap: 12px; }
}
</style>
