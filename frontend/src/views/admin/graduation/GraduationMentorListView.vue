<template>
  <ModulePageShell
    title="导师管理"
    :subtitle="'共 ' + total + ' 位导师 · 资格认证 / 容量 / 方向 / 工作量 / 分配'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="gm-tabs">
      <button class="gm-tabs__item" :class="{ 'is-active': tab === 'mentors' }" @click="switchTab('mentors')">导师名单</button>
      <button class="gm-tabs__item" :class="{ 'is-active': tab === 'assign' }" @click="switchTab('assign')">导师分配</button>
    </div>

    <!-- ═══ 导师名单 ═══ -->
    <div v-if="tab === 'mentors'" class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无导师" description="点「＋ 申报导师」新增一位导师" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-mentor="{ row }">
          <div class="mp-cell-main">{{ row.teacherName }}</div>
          <div class="mp-cell-sub">{{ row.teacherNo }} · {{ row.mentorTypeLabel }} · {{ row.title || '—' }}</div>
        </template>
        <template #cell-org="{ row }">{{ row.collegeName || '—' }} / {{ row.majorName || '—' }}</template>
        <template #cell-capacity="{ row }"><span :class="{ 'gm-full': row.capacityFull }">{{ row.capacityText }}</span></template>
        <template #cell-status="{ row }"><StatusTag :type="row.qualificationTone" :label="row.qualificationLabel" dot /></template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">详情</button>
          <button v-if="row.qualificationStatus === 'QUALIFIED'" class="mp-link" style="margin-left: var(--space-2)" @click="openEval(row)">评价</button>
          <button v-if="row.qualificationStatus !== 'ARCHIVED'" class="mp-link" style="margin-left: var(--space-2)" @click="openEdit(row)">编辑</button>
          <button v-if="row.qualificationStatus === 'PENDING_REVIEW'" class="mp-link" style="margin-left: var(--space-2)" @click="askReview(row)">审核</button>
          <button v-if="row.qualificationStatus === 'QUALIFIED'" class="mp-link" style="margin-left: var(--space-2)" @click="askDisable(row)">停用</button>
          <button v-if="row.qualificationStatus === 'DISABLED'" class="mp-link" style="margin-left: var(--space-2)" @click="doEnable(row)">启用</button>
          <button v-if="['DISABLED', 'REJECTED'].includes(row.qualificationStatus)" class="mp-link" style="margin-left: var(--space-2)" @click="doArchive(row)">归档</button>
        </template>
      </DataTable>
    </div>

    <!-- ═══ 导师分配 ═══ -->
    <div v-else class="mp-stack">
      <div class="gm-assign-hint">未分配导师学生共 <b>{{ unassignedTotal }}</b> 人；分配须导师「已认证」且未满员，调导师原因≥5字。</div>
      <AdvancedFilter v-model="uFilters" :fields="uFilterFields" @search="searchUnassigned" @reset="resetUnassigned" />
      <ErrorState v-if="uError" :description="uError" @retry="loadUnassigned" />
      <LoadingState v-else-if="uLoading" />
      <EmptyState v-else-if="!uRows.length" title="暂无未分配导师学生" />
      <DataTable v-else :columns="uColumns" :rows="uRows" row-key="id" :pagination="{ page: uPage, pageSize: uPageSize, total: uTotal }" @page-change="turnUnassignedPage">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }} · {{ row.className || '—' }}</div>
        </template>
        <template #cell-actions="{ row }"><button class="mp-link" @click="openAssign(row)">分配导师</button></template>
      </DataTable>

      <div class="gm-section-title" style="margin-top: var(--space-4)" >分配记录</div>
      <DataTable :columns="aColumns" :rows="aRows" row-key="id" :pagination="{ page: aPage, pageSize: aPageSize, total: aTotal }" @page-change="turnAssignPage">
        <template #cell-pair="{ row }">
          <div class="mp-cell-main">{{ row.studentName }} ← {{ row.mentorName }}</div>
          <div class="mp-cell-sub">{{ row.assignReason || '—' }}</div>
        </template>
        <template #cell-status="{ row }"><StatusTag :type="row.status === 'ACTIVE' ? 'success' : 'default'" :label="row.statusLabel" dot /></template>
        <template #cell-actions="{ row }">
          <button v-if="row.status === 'ACTIVE'" class="mp-link" @click="openChange(row)">调导师</button>
          <button v-if="row.status === 'ACTIVE'" class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askCancel(row)">取消</button>
        </template>
      </DataTable>
    </div>

    <!-- 新建 / 编辑导师 -->
    <AppDrawer v-model:visible="editVisible" :title="editing ? '编辑导师' : '申报导师'">
      <form class="ie-form" @submit.prevent="submitEdit">
        <label class="ie-fld"><span class="ie-lbl">教师工号 <i>*</i></span><input v-model.trim="form.teacherNo" class="ie-in" :disabled="!!editing" /></label>
        <label class="ie-fld"><span class="ie-lbl">教师姓名 <i>*</i></span><input v-model.trim="form.teacherName" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">导师类型</span>
          <select v-model="form.mentorType" class="ie-in">
            <option v-for="o in MENTOR_TYPE" :key="o.value" :value="o.value">{{ o.label }}</option>
          </select>
        </label>
        <label class="ie-fld"><span class="ie-lbl">职称</span><input v-model.trim="form.title" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">所属学院</span><input v-model.trim="form.collegeName" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">所属专业</span><input v-model.trim="form.majorName" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">最大指导人数</span><input v-model.number="form.maxCapacity" type="number" min="1" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">联系电话</span><input v-model.trim="form.phone" class="ie-in" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">指导方向</span><input v-model.trim="form.researchDirection" class="ie-in" placeholder="如 Web 开发 / 嵌入式系统" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><textarea v-model.trim="form.remark" class="ie-in" rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="editVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">保存</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 详情 -->
    <AppDrawer v-model:visible="detailVisible" :title="detail ? detail.teacherName : '导师详情'">
      <template v-if="detail">
        <div class="gm-detail-kv"><span>资格状态</span><StatusTag :type="detail.qualificationTone" :label="detail.qualificationLabel" dot /></div>
        <div class="gm-detail-kv"><span>工作量</span><span>{{ detail.capacityText }}</span></div>
        <div class="gm-detail-kv"><span>指导方向</span><span>{{ detail.researchDirection || '—' }}</span></div>
        <div class="gm-detail-kv"><span>联系电话</span><span>{{ detail.phone || '—' }}</span></div>
        <div v-if="detail.reviewComment" class="gm-detail-kv"><span>审核意见</span><span>{{ detail.reviewComment }}</span></div>
        <div v-if="detail.latestEval" class="gm-detail-kv"><span>最新评价</span><span>{{ detail.latestEval.level }} · {{ detail.latestEval.score }}分（{{ detail.latestEval.evaluatedBy }}）</span></div>
        <div class="gm-section-title" style="margin-top: var(--space-3)" >在指导学生</div>
        <EmptyState v-if="!detail.students.length" title="暂无在指导学生" />
        <ul v-else class="gm-stu-list">
          <li v-for="s in detail.students" :key="s.id">{{ s.name }}（{{ s.studentNo }}）· {{ s.topicTitle || '未确认选题' }}</li>
        </ul>
        <div class="gm-section-title" style="margin-top: var(--space-3)" >操作记录</div>
        <EmptyState v-if="!detail.auditTrail.length" title="暂无操作记录" />
        <ul v-else class="gm-trail">
          <li v-for="(a, i) in detail.auditTrail" :key="i" class="gm-trail__item"><span>{{ a.action }}</span><span class="gm-trail__meta">{{ a.operator }} · {{ a.occurredAt }}</span></li>
        </ul>
      </template>
    </AppDrawer>

    <!-- 分配 / 调导师 -->
    <AppDrawer v-model:visible="assignVisible" :title="assignForm.mode === 'change' ? '调导师' : '分配导师'">
      <form class="ie-form" @submit.prevent="submitAssign">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">学生</span><input class="ie-in" :value="assignForm.studentLabel" disabled /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">导师 <i>*</i></span>
          <select v-model="assignForm.mentorId" class="ie-in">
            <option value="">请选择已认证且未满员的导师</option>
            <option v-for="m in availableMentors" :key="m.id" :value="m.id">{{ m.teacherName }}（{{ m.capacityText }}）</option>
          </select>
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">{{ assignForm.mode === 'change' ? '调导师原因（≥5字）' : '分配原因' }}<i v-if="assignForm.mode === 'change'">*</i></span><textarea v-model.trim="assignForm.reason" class="ie-in" rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="assignVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">确认</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 导师评价 -->
    <AppDrawer v-model:visible="evalVisible" :title="evalMentor ? evalMentor.teacherName + ' · 导师评价' : '导师评价'">
      <form class="ie-form" @submit.prevent="submitEval">
        <label class="ie-fld"><span class="ie-lbl">评价周期</span><input v-model.trim="evalForm.period" class="ie-in" placeholder="如 2026春" /></label>
        <label class="ie-fld"><span class="ie-lbl">评分（0-100）<i>*</i></span><input v-model.number="evalForm.score" type="number" min="0" max="100" class="ie-in" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">评价等级 <i>*</i></span>
          <select v-model="evalForm.level" class="ie-in">
            <option v-for="l in ['优秀','良好','合格','不合格']" :key="l" :value="l">{{ l }}</option>
          </select>
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">评价意见</span><textarea v-model.trim="evalForm.note" class="ie-in" rows="3" /></label>
        <p v-if="evalError" class="ie-err">{{ evalError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="evalVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">提交评价</button>
        </div>
      </form>
      <div class="gm-section-title" style="margin-top: var(--space-3)">评价历史</div>
      <EmptyState v-if="!evalHistory.length" title="暂无评价记录" />
      <ul v-else class="gm-trail">
        <li v-for="e in evalHistory" :key="e.id" class="gm-trail__item">
          <span>{{ e.level }} · {{ e.score }}分 {{ e.period ? '（' + e.period + '）' : '' }}{{ e.note ? ' · ' + e.note : '' }}</span>
          <span class="gm-trail__meta">{{ e.evaluatedBy }} · {{ e.evaluatedAt }}</span>
        </li>
      </ul>
    </AppDrawer>

    <!-- 分配冲突检测 -->
    <AppDrawer v-model:visible="conflictsVisible" title="分配冲突自动检测">
      <template v-if="conflicts">
        <div class="gm-assign-hint">共检出 <b>{{ conflicts.total }}</b> 项分配冲突，请及时处理。</div>
        <div class="gm-section-title" style="margin-top: var(--space-3)">导师超容量（{{ conflicts.overCapacity.length }}）</div>
        <EmptyState v-if="!conflicts.overCapacity.length" title="无超容量导师" />
        <ul v-else class="gm-stu-list"><li v-for="m in conflicts.overCapacity" :key="m.mentorId">{{ m.teacherName }}：{{ m.current }}/{{ m.capacity }}</li></ul>
        <div class="gm-section-title" style="margin-top: var(--space-3)">进入指导阶段却无导师（{{ conflicts.advancedNoMentor.length }}）</div>
        <EmptyState v-if="!conflicts.advancedNoMentor.length" title="无此类学生" />
        <ul v-else class="gm-stu-list"><li v-for="s in conflicts.advancedNoMentor" :key="s.gdStudentId">{{ s.name }}（{{ s.className }}）· {{ s.stage }}</li></ul>
        <div class="gm-section-title" style="margin-top: var(--space-3)">学生导师非「已认证」（{{ conflicts.unqualifiedMentor.length }}）</div>
        <EmptyState v-if="!conflicts.unqualifiedMentor.length" title="无此类学生" />
        <ul v-else class="gm-stu-list"><li v-for="s in conflicts.unqualifiedMentor" :key="s.gdStudentId">{{ s.name }} → {{ s.mentorName }}（{{ s.mentorStatus }}）</li></ul>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />

    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入导师名单"
      template-name="导师名单导入模板.xlsx"
      :required-fields="['教师工号', '教师姓名']"
      :preview-fields="['teacherNo', 'teacherName', 'mentorType', 'title', 'collegeName', 'maxCapacity']"
      :download-template-fn="() => graduationMentorApi.downloadImportTemplate()"
      :upload-fn="(file) => graduationMentorApi.uploadImportXlsx(file)"
      :confirm-fn="({ rows }) => graduationMentorApi.importConfirm(rows)"
      :download-errors-fn="({ rows, errors }) => graduationMentorApi.downloadImportErrors(rows, errors)"
      @imported="onImported"
    />
  </ModulePageShell>
</template>

<script>
/** 导师管理 + 导师分配（/admin/graduation/mentors）：生产级只走真实后端；申报/审核/停用/启用/归档 + 分配/调导师/取消 + Excel。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { graduationMentorApi } from '@/modules/graduation/api/graduation-mentor.api'
import { MENTOR_QUALIFICATION_STATUS, MENTOR_TYPE } from '@/modules/graduation/constants/graduation-mentor.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', qualificationStatus: '', mentorType: '', dateStart: '', dateEnd: '' })
const EMPTY_U_FILTERS = () => ({ keyword: '', dateStart: '', dateEnd: '' })
const EMPTY_FORM = () => ({ teacherNo: '', teacherName: '', mentorType: 'INTERNAL', title: '', collegeName: '', majorName: '', researchDirection: '', maxCapacity: 8, phone: '', remark: '' })

export default {
  name: 'GraduationMentorListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDrawer, AppConfirmDialog, AppExcelImportDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      MENTOR_TYPE,
      tab: 'mentors',
      loading: true, error: '', submitting: false,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      editVisible: false, editing: null, form: EMPTY_FORM(), formError: '',
      detailVisible: false, detail: null,
      importVisible: false,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      columns: [
        { key: 'mentor', title: '导师 / 工号' },
        { key: 'org', title: '学院 / 专业' },
        { key: 'capacity', title: '工作量' },
        { key: 'status', title: '资格状态' },
        { key: 'actions', title: '操作', width: '260px' }
      ],
      // 分配
      uFilters: EMPTY_U_FILTERS(), uRows: [], uTotal: 0, uPage: 1, uPageSize: 10, uLoading: true, uError: '',
      unassignedTotal: 0,
      aRows: [], aTotal: 0, aPage: 1, aPageSize: 10,
      uColumns: [{ key: 'student', title: '学生' }, { key: 'actions', title: '操作', width: '120px' }],
      aColumns: [{ key: 'pair', title: '学生 ← 导师' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '160px' }],
      assignVisible: false, assignForm: { mode: 'assign', studentId: '', studentLabel: '', mentorId: '', reason: '', assignmentId: '' },
      availableMentors: [],
      // Batch 4：评价 / 冲突
      evalVisible: false, evalMentor: null, evalForm: { period: '', score: 90, level: '良好', note: '' }, evalError: '', evalHistory: [],
      conflictsVisible: false, conflicts: null
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 工号 / 方向' },
        { key: 'qualificationStatus', label: '资格状态', type: 'select', options: MENTOR_QUALIFICATION_STATUS },
        { key: 'mentorType', label: '导师类型', type: 'select', options: MENTOR_TYPE },
        {
          key: 'date', label: '申报/变更时间', type: 'daterange',
          startKey: 'dateStart', endKey: 'dateEnd',
          memoryKey: 'graduation.mentors.dateRange', emptyLabel: '全部时间'
        }
      ]
    },
    uFilterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 学号' },
        {
          key: 'date', label: '分配时间', type: 'daterange',
          startKey: 'dateStart', endKey: 'dateEnd',
          memoryKey: 'graduation.mentors.assignDateRange', emptyLabel: '全部时间'
        }
      ]
    },
    toolbarActions() {
      if (this.tab === 'assign') return [{ key: 'batchAssign', label: '一键批量分配', variant: 'primary' }]
      return [{ key: 'create', label: '＋ 申报导师', variant: 'primary' }, { key: 'conflicts', label: '分配冲突检测' }, { key: 'batchArchive', label: '批量归档' }, { key: 'import', label: '导入 Excel' }, { key: 'export', label: '导出台账' }]
    }
  },
  created() { this.applyPanel(this.$route.query.panel, true) },
  watch: { '$route.query.panel'(p) { this.applyPanel(p, false) } },
  methods: {
    applyPanel(panel, initial) {
      panel = panel || 'list'
      this.tab = panel === 'assign' ? 'assign' : 'mentors'
      if (panel === 'create') { this.tab = 'mentors'; this.load(); this.onToolbar('create'); return }
      if (this.tab === 'mentors') this.load(); else { this.loadUnassigned(); this.loadAssignments() }
      if (!initial) { /* 切换 panel 已在上面处理 */ }
    },
    switchTab(t) {
      this.tab = t
      this.$router.replace({ query: { ...this.$route.query, panel: t === 'assign' ? 'assign' : 'list' } })
      if (t === 'mentors') this.load(); else { this.loadUnassigned(); this.loadAssignments() }
    },
    async load() {
      this.loading = true; this.error = ''
      const res = await graduationMentorApi.getMentors({ ...this.filters, page: this.page, pageSize: this.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(key) {
      if (key === 'create') { this.editing = null; this.form = EMPTY_FORM(); this.formError = ''; this.editVisible = true }
      if (key === 'import') this.importVisible = true
      if (key === 'export') this.doExport()
      if (key === 'conflicts') this.openConflicts()
      if (key === 'batchArchive') this.doBatchArchive()
      if (key === 'batchAssign') this.doBatchAssign()
    },
    async openEval(row) {
      this.evalMentor = row
      this.evalForm = { period: '', score: 90, level: '良好', note: '' }
      this.evalError = ''
      this.evalHistory = []
      this.evalVisible = true
      const res = await graduationMentorApi.getEvals(row.id)
      if (res.code === 0) this.evalHistory = res.data.list
    },
    async submitEval() {
      this.evalError = ''
      if (this.evalForm.score === '' || this.evalForm.score < 0 || this.evalForm.score > 100) { this.evalError = '评分须 0-100'; return }
      this.submitting = true
      const res = await graduationMentorApi.createEval(this.evalMentor.id, this.evalForm)
      this.submitting = false
      if (res.code === 0) {
        toast.success('已评价')
        const h = await graduationMentorApi.getEvals(this.evalMentor.id)
        if (h.code === 0) this.evalHistory = h.data.list
        this.evalForm.note = ''
      } else this.evalError = res.message
    },
    async openConflicts() {
      this.conflicts = null
      this.conflictsVisible = true
      const res = await graduationMentorApi.getConflicts()
      if (res.code === 0) this.conflicts = res.data
      else toast.error(res.message)
    },
    async doBatchArchive() {
      const ids = this.rows.filter((m) => ['DISABLED', 'REJECTED'].includes(m.qualificationStatus)).map((m) => m.id)
      if (!ids.length) { toast.info('当前页无「已停用/已驳回」的可归档导师'); return }
      const res = await graduationMentorApi.batchArchive(ids)
      if (res.code === 0) { toast.success(res.message || '已批量归档'); this.load() }
      else toast.error(res.message)
    },
    async doBatchAssign() {
      // 一键批量分配：把未分配学生按顺序分给「已认证且未满员」导师
      const [us, ms] = await Promise.all([
        graduationMentorApi.getUnassignedStudents({ page: 1, pageSize: 200 }),
        graduationMentorApi.getMentors({ qualificationStatus: 'QUALIFIED', page: 1, pageSize: 200 })
      ])
      if (us.code !== 0 || ms.code !== 0) { toast.error('加载数据失败'); return }
      const students = us.data.list
      const caps = ms.data.list.filter((m) => !m.capacityFull).map((m) => ({ id: m.id, free: m.maxCapacity - m.currentCount }))
      if (!students.length) { toast.info('暂无未分配学生'); return }
      if (!caps.length) { toast.info('暂无可用容量的已认证导师'); return }
      const assignments = []
      let mi = 0
      for (const s of students) {
        while (mi < caps.length && caps[mi].free <= 0) mi += 1
        if (mi >= caps.length) break
        assignments.push({ gdStudentId: s.id, mentorId: caps[mi].id })
        caps[mi].free -= 1
      }
      const res = await graduationMentorApi.batchAssign(assignments)
      if (res.code === 0) { toast.success(res.message || '批量分配完成'); this.loadUnassigned(); this.loadAssignments() }
      else toast.error(res.message)
    },
    onImported() { this.importVisible = false; this.load(); toast.success('导入完成') },
    openEdit(row) {
      this.editing = row
      this.form = { teacherNo: row.teacherNo, teacherName: row.teacherName, mentorType: row.mentorType, title: row.title, collegeName: row.collegeName, majorName: row.majorName, researchDirection: row.researchDirection, maxCapacity: row.maxCapacity, phone: '', remark: '' }
      this.formError = ''; this.editVisible = true
    },
    async submitEdit() {
      this.formError = ''
      if (!this.form.teacherNo || !this.form.teacherName) { this.formError = '教师工号与姓名必填'; return }
      this.submitting = true
      try {
        const res = this.editing ? await graduationMentorApi.updateMentor(this.editing.id, this.form) : await graduationMentorApi.createMentor(this.form)
        if (res.code === 0) { toast.success('已保存'); this.editVisible = false; this.load() } else this.formError = res.message
      } finally { this.submitting = false }
    },
    async openDetail(row) {
      const res = await graduationMentorApi.getMentorDetail(row.id)
      if (res.code !== 0) return toast.error(res.message)
      this.detail = res.data; this.detailVisible = true
    },
    askReview(row) {
      this.confirm = { visible: true, title: '审核导师资格', message: `确认「${row.teacherName}」资格审核通过？`, type: 'primary', confirmText: '通过', requireReason: false, action: 'review-approve', row }
    },
    askDisable(row) {
      this.confirm = { visible: true, title: '停用导师', message: `确认停用「${row.teacherName}」？停用后不可被分配新学生。`, type: 'danger', confirmText: '确认停用', requireReason: true, reasonLabel: '停用原因', action: 'disable', row }
    },
    async doEnable(row) {
      const res = await graduationMentorApi.enableMentor(row.id)
      if (res.code === 0) { toast.success('已启用'); this.load() } else toast.error(res.message)
    },
    async doArchive(row) {
      const res = await graduationMentorApi.archiveMentor(row.id)
      if (res.code === 0) { toast.success('已归档'); this.load() } else toast.error(res.message)
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      this.submitting = true
      try {
        let res
        if (action === 'review-approve') res = await graduationMentorApi.reviewMentor(row.id, 'APPROVE')
        else if (action === 'disable') res = await graduationMentorApi.disableMentor(row.id, reason || '')
        else if (action === 'cancel-assign') res = await graduationMentorApi.cancelAssignment(row.id, reason || '')
        if (res && res.code === 0) { toast.success('已更新'); this.confirm.visible = false; this.load(); this.loadUnassigned(); this.loadAssignments() } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    },
    async doExport() {
      const res = await graduationMentorApi.downloadMentorExport({ ...this.filters })
      if (res.code === 0) toast.success(`已导出 ${res.data.rowCount} 位导师台账`)
      else toast.error(res.message)
    },
    // ═══ 分配 ═══
    async loadUnassigned() {
      this.uLoading = true; this.uError = ''
      const res = await graduationMentorApi.getUnassignedStudents({ ...this.uFilters, page: this.uPage, pageSize: this.uPageSize })
      if (res.code === 0) { this.uRows = res.data.list; this.uTotal = res.data.total; this.unassignedTotal = res.data.total } else this.uError = res.message
      this.uLoading = false
    },
    searchUnassigned() { this.uPage = 1; this.loadUnassigned() },
    resetUnassigned() { this.uFilters = EMPTY_U_FILTERS(); this.uPage = 1; this.loadUnassigned() },
    turnUnassignedPage(p) { this.uPage = p; this.loadUnassigned() },
    async loadAssignments() {
      const res = await graduationMentorApi.getAssignments({ page: this.aPage, pageSize: this.aPageSize })
      if (res.code === 0) { this.aRows = res.data.list; this.aTotal = res.data.total }
    },
    turnAssignPage(p) { this.aPage = p; this.loadAssignments() },
    async loadAvailableMentors() {
      const res = await graduationMentorApi.getMentors({ qualificationStatus: 'QUALIFIED', hasCapacity: 'true', pageSize: 200 })
      this.availableMentors = res.code === 0 ? res.data.list : []
    },
    async openAssign(row) {
      await this.loadAvailableMentors()
      this.assignForm = { mode: 'assign', studentId: row.id, studentLabel: `${row.name}（${row.studentNo}）`, mentorId: '', reason: '', assignmentId: '' }
      this.formError = ''; this.assignVisible = true
    },
    async openChange(row) {
      await this.loadAvailableMentors()
      this.assignForm = { mode: 'change', studentId: row.gdStudentId, studentLabel: row.studentName, mentorId: '', reason: '', assignmentId: row.id }
      this.formError = ''; this.assignVisible = true
    },
    askCancel(row) {
      this.confirm = { visible: true, title: '取消分配', message: `确认取消「${row.studentName}」与「${row.mentorName}」的分配关系？`, type: 'danger', confirmText: '确认取消', requireReason: true, reasonLabel: '取消原因', action: 'cancel-assign', row }
    },
    async submitAssign() {
      this.formError = ''
      if (!this.assignForm.mentorId) { this.formError = '请选择导师'; return }
      if (this.assignForm.mode === 'change' && (!this.assignForm.reason || this.assignForm.reason.length < 5)) { this.formError = '调导师原因至少 5 字'; return }
      this.submitting = true
      try {
        const res = this.assignForm.mode === 'change'
          ? await graduationMentorApi.changeMentor(this.assignForm.studentId, this.assignForm.mentorId, this.assignForm.reason)
          : await graduationMentorApi.assignMentor(this.assignForm.studentId, this.assignForm.mentorId, this.assignForm.reason)
        if (res.code === 0) { toast.success('已保存'); this.assignVisible = false; this.loadUnassigned(); this.loadAssignments() } else this.formError = res.message
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-link--danger { color: var(--danger, #dc2626); }
.gm-full { color: var(--danger, #dc2626); font-weight: 600; }
.gm-tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--line, #e2e8f0); margin-bottom: var(--space-3); }
.gm-tabs__item { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--t2, #475569); border-bottom: 2px solid transparent; }
.gm-tabs__item.is-active { color: var(--pri, #2563eb); border-bottom-color: var(--pri, #2563eb); font-weight: 600; }
.gm-assign-hint { font-size: 12px; color: var(--t3, #64748b); }
.gm-section-title { font-size: 13px; font-weight: 600; color: var(--t1, #1e293b); margin-bottom: var(--space-2); }
.gm-detail-kv { display: flex; justify-content: space-between; gap: var(--space-3); padding: 6px 0; border-bottom: 1px dashed var(--line, #eef1f6); font-size: 13px; }
.gm-stu-list { margin: 0; padding-left: 18px; font-size: 13px; }
.gm-stu-list li { padding: 4px 0; }
.gm-trail__item { display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px dashed var(--line, #eef1f6); font-size: 13px; }
.gm-trail__meta { color: var(--t3, #64748b); font-size: 12px; }
.ie-form { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); padding: var(--space-1) 0; }
.ie-fld { display: flex; flex-direction: column; gap: 4px; }
.ie-fld--full { grid-column: 1 / -1; }
.ie-lbl { font-size: 12px; color: var(--t2, #475569); }
.ie-lbl i { color: var(--danger, #dc2626); font-style: normal; }
.ie-in { width: 100%; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.ie-err { grid-column: 1 / -1; color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.ie-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
