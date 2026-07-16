<template>
  <ModulePageShell
    title="选课管理 · 教务处控制台"
    :subtitle="'批次生命周期：草稿→发布→开选→截止→锁定→归档 · 共 ' + pagination.total + ' 个批次'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="ghost" @click="runTimeTick">按时间批量开选/截止</AppButton>
      <AppButton variant="primary" @click="openCreate">新建批次</AppButton>
    </template>

    <div class="aasel-layout">
      <!-- 左：批次列表 -->
      <div class="aasel-list">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无选课批次" description="点击右上角「新建批次」创建" />
        <ul v-else class="aasel-batches">
          <li
            v-for="b in rows" :key="b.batchId"
            :class="['aasel-batch', { 'is-active': current && current.batchId === b.batchId }]"
            @click="select(b)"
          >
            <div class="aasel-batch-name">{{ b.batchName }}</div>
            <StatusTag :type="statusType(b.status)" :label="statusLabel(b.status)" dot />
          </li>
        </ul>
      </div>

      <!-- 右：选中批次详情 -->
      <div class="aasel-detail">
        <EmptyState v-if="!current" title="选择一个批次" description="从左侧列表选择批次以管理可选课程与名单" />
        <template v-else>
          <div class="aasel-detail-head">
            <div>
              <div class="aasel-detail-title">{{ current.batchName }}</div>
              <StatusTag :type="statusType(current.status)" :label="statusLabel(current.status)" dot />
            </div>
            <div class="aasel-actions">
              <AppButton v-if="current.status === 'DRAFT'" variant="primary" size="small" @click="lifecycle('publishBatch', '发布')">发布</AppButton>
              <AppButton v-if="current.status === 'PUBLISHED'" variant="primary" size="small" @click="lifecycle('openBatch', '开选')">开选</AppButton>
              <AppButton v-if="current.status === 'OPEN'" variant="warning" size="small" @click="lifecycle('closeBatch', '截止')">截止</AppButton>
              <AppButton v-if="current.status === 'CLOSED'" variant="primary" size="small" @click="lifecycle('lockBatch', '锁定名单')">锁定名单</AppButton>
              <AppButton v-if="current.status === 'LOCKED'" variant="ghost" size="small" @click="lifecycle('archiveBatch', '归档')">归档</AppButton>
            </div>
          </div>

          <!-- 统计条 -->
          <div v-if="stats" class="aasel-stats">
            <span>课程 {{ stats.courseCount }}</span>
            <span>容量 {{ stats.totalCapacity }}</span>
            <span>已选 {{ stats.totalSelected }}</span>
            <span>填充率 {{ (stats.fillRate * 100).toFixed(0) }}%</span>
            <span :class="{ 'is-warn': stats.lowEnrollCount }">低人数 {{ stats.lowEnrollCount }}</span>
          </div>

          <div class="aasel-tabs">
            <button v-for="t in detailTabs" :key="t.key" class="aasel-tab" :class="{ 'is-active': detailTab === t.key }" @click="detailTab = t.key; onTabChange()">{{ t.label }}</button>
          </div>

          <!-- 课程供给 -->
          <template v-if="detailTab === 'courses'">
            <div class="aasel-courses-head">
              <span>可选课程供给</span>
              <AppButton v-if="['DRAFT','PUBLISHED'].includes(current.status)" size="small" variant="ghost" @click="openAddCourse">+ 添加课程</AppButton>
            </div>
            <EmptyState v-if="!courses.length" title="未配置课程" description="添加至少一门课程后方可发布" />
            <DataTable v-else :columns="courseColumns" :rows="courses" row-key="selectionCourseId">
              <template #cell-course="{ row }">
                <div class="mp-cell-main">{{ row.courseName }}</div>
                <div class="mp-cell-sub">{{ row.teacherName || '未派课' }} · {{ row.credit }} 学分</div>
              </template>
              <template #cell-fill="{ row }">{{ row.selectedCount }} / {{ row.capacity }}（余 {{ row.remain }}）</template>
              <template #cell-status="{ row }">
                <StatusTag :type="row.status === 'OPEN' ? 'success' : 'default'" :label="row.status === 'OPEN' ? '开放' : '已取消'" dot />
              </template>
              <template #cell-ops="{ row }">
                <button class="mp-link" @click="openRoster(row)">名单</button>
                <button v-if="current.status === 'CLOSED' && row.status === 'OPEN'" class="mp-link is-danger" @click="cancelCourse(row)">取消开课</button>
              </template>
            </DataTable>
          </template>

          <!-- 选课规则（03号卡） -->
          <template v-else-if="detailTab === 'rule'">
            <div class="aasel-rule">
              <AppFormItem label="选课学分上限（0 = 不限）">
                <AppNumberInput v-model="ruleForm.maxCredits" :min="0" :max="80" :disabled="ruleSaving || !['DRAFT','PUBLISHED'].includes(current.status)" />
              </AppFormItem>
              <AppButton v-if="['DRAFT','PUBLISHED'].includes(current.status)" size="small" variant="primary" :loading="ruleSaving" @click="saveRule">保存规则</AppButton>
              <AppInlineAlert v-else type="warning" description="选课已开始，规则不可修改（批次OPEN后规则冻结）" />
              <div class="aasel-rule-fixed">
                <div class="aasel-rule-fixed-title">以下校验始终启用，不可关闭（选课八条中的强制项）：</div>
                <ul>
                  <li>批次开选窗口内</li>
                  <li>学生所属年级/专业/班级在适用范围内</li>
                  <li>未修过该课程（同批次不可重复选）</li>
                  <li>满足先修课程要求</li>
                  <li>课表不冲突</li>
                  <li>不超课程容量</li>
                  <li>符合重修规则</li>
                </ul>
              </div>
            </div>
          </template>

          <!-- 补选指引（06号卡·教务处视角） -->
          <template v-else-if="detailTab === 'reselect'">
            <EmptyState v-if="current.status !== 'CLOSED'" title="仅 CLOSED 批次有补选指引" description="批次截止后可在此查看因人数不足取消开课的课程与可补选课程" />
            <template v-else>
              <div class="aasel-section-title">已取消开课（受影响学生需补选）</div>
              <EmptyState v-if="!reselectData.cancelledCourses.length" title="暂无取消开课的课程" description="" />
              <DataTable v-else :columns="miniCourseColumns" :rows="reselectData.cancelledCourses" row-key="selectionCourseId" />
              <div class="aasel-section-title">仍有余量课程（可供补选）</div>
              <EmptyState v-if="!reselectData.availableCourses.length" title="暂无有余量课程" description="" />
              <DataTable v-else :columns="miniCourseColumns" :rows="reselectData.availableCourses" row-key="selectionCourseId" />
            </template>
          </template>

          <!-- 冲突检测（09号卡） -->
          <template v-else-if="detailTab === 'conflict'">
            <div class="aasel-conflict-toolbar">
              <AppTextInput v-model="conflictStudentNo" placeholder="按学号查询冲突明细（选填）" />
              <AppButton size="small" variant="ghost" @click="loadConflictReport">查询</AppButton>
              <AppTextInput v-model="conflictExportPurpose" placeholder="导出用途（≥5字，导出前必填）" />
              <AppButton size="small" variant="ghost" :loading="conflictExporting" @click="exportConflict">导出Excel</AppButton>
            </div>
            <EmptyState v-if="!conflictReport.summary.length && !conflictReport.items.length" title="暂无冲突拒选记录" description="学生因课表冲突被拒选选课时会在此汇总" />
            <template v-else>
              <DataTable v-if="!conflictStudentNo" :columns="conflictSummaryColumns" :rows="conflictReport.summary" row-key="courseName" />
              <DataTable v-else :columns="conflictItemColumns" :rows="conflictReport.items" row-key="occurredAt" />
            </template>
          </template>
        </template>
      </div>
    </div>

    <!-- 建批次 -->
    <AppDrawer :visible="createVisible" title="新建选课批次" @close="createVisible = false">
      <div class="aasel-form">
        <AppFormItem label="批次名称" required>
          <AppTextInput v-model="form.batchName" placeholder="如 2024秋公共选修课选课" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="选课学分上限">
          <AppNumberInput v-model="form.maxCredits" :min="0" :max="50" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="备注">
          <AppTextarea ref="remarkInput" v-model="form.remark" placeholder="选填" :disabled="saving" />
          <AppQuickPhrases scene-key="aa.remark" @pick="onPickRemark" />
        </AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <!-- 加课程 -->
    <AppDrawer :visible="courseVisible" title="添加可选课程" @close="courseVisible = false">
      <div class="aasel-form">
        <AppFormItem label="课程 ID" required>
          <AppTextInput v-model="courseForm.courseId" placeholder="课程库中的课程 ID" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="教学任务 ID">
          <AppTextInput v-model="courseForm.teachingTaskId" placeholder="选填（关联任课教师/教学班）" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="容量上限" required>
          <AppNumberInput v-model="courseForm.capacity" :min="1" :max="1000" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="开课人数下限">
          <AppNumberInput v-model="courseForm.minCapacity" :min="0" :max="1000" :disabled="saving" />
        </AppFormItem>
        <AppInlineAlert v-if="courseError" type="danger" :description="courseError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="courseVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCourse">添加</AppButton>
      </template>
    </AppDrawer>

    <!-- 名单抽屉 -->
    <AppDrawer :visible="rosterVisible" :title="'选课名单 · ' + (rosterCourse ? rosterCourse.courseName : '')" @close="rosterVisible = false">
      <EmptyState v-if="!rosterRows.length" title="暂无学生" description="该课程尚无有效选课记录" />
      <DataTable v-else :columns="rosterColumns" :rows="rosterRows" row-key="recordId">
        <template #cell-student="{ row }">{{ row.studentName }}（{{ row.studentNo }}）</template>
      </DataTable>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** 选课管理 · 教务处控制台（/admin/academic-affairs/selection）：批次生命周期 + 课程供给 + 名单 + 统计。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppQuickPhrases } from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi, academicAffairsSelectionApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _LABEL = { DRAFT: '草稿', PUBLISHED: '已发布', OPEN: '选课中', CLOSED: '已截止', LOCKED: '已锁定', ARCHIVED: '已归档' }

export default {
  name: 'AaSelectionConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppQuickPhrases
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', rows: [],
      pagination: { page: 1, pageSize: 50, total: 0 },
      current: null, courses: [], stats: null,
      createVisible: false, form: { batchName: '', maxCredits: 0, remark: '' }, formError: '',
      courseVisible: false, courseForm: { courseId: '', teachingTaskId: '', capacity: 30, minCapacity: 1 }, courseError: '',
      rosterVisible: false, rosterCourse: null, rosterRows: [],
      saving: false,
      confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      courseColumns: [
        { key: 'course', title: '课程' }, { key: 'fill', title: '选课情况' },
        { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }
      ],
      rosterColumns: [{ key: 'student', title: '学生' }, { key: 'status', title: '状态' }],
      // ── 选课规则 / 补选指引 / 冲突检测（03/06/09号卡） ──
      detailTab: 'courses',
      detailTabs: [
        { key: 'courses', label: '课程供给' }, { key: 'rule', label: '选课规则' },
        { key: 'reselect', label: '补选指引' }, { key: 'conflict', label: '冲突检测' }
      ],
      ruleForm: { maxCredits: 0 }, ruleSaving: false,
      reselectData: { cancelledCourses: [], availableCourses: [] },
      miniCourseColumns: [
        { key: 'courseName', title: '课程' }, { key: 'credit', title: '学分' },
        { key: 'selectedCount', title: '已选' }, { key: 'capacity', title: '容量' }
      ],
      conflictStudentNo: '', conflictReport: { summary: [], items: [] },
      conflictExportPurpose: '', conflictExporting: false,
      conflictSummaryColumns: [{ key: 'courseName', title: '课程' }, { key: 'conflictRejectCount', title: '冲突拒选次数' }],
      conflictItemColumns: [{ key: 'occurredAt', title: '时间' }, { key: 'courseName', title: '课程' }, { key: 'detail', title: '详情' }]
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.detailTabs.some((t) => t.key === q)) this.detailTab = q
    this.load()
  },
  methods: {
    onPickRemark(text) {
      const el = this.$refs.remarkInput && this.$refs.remarkInput.$refs.el
      const { value, selStart, selEnd } = insertAtCursor(el, this.form.remark, text)
      this.form.remark = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    async runTimeTick() {
      const res = await api.timeTick()
      if (res.code === 0) {
        const d = res.data || {}
        toast.success(`已按时间处理：开选 ${d.opened != null ? d.opened : 0} / 截止 ${d.closed != null ? d.closed : 0}`)
        await this.load()
        if (this.current) await this.select(this.current)
      } else toast.error(res.message)
    },
    statusLabel(s) { return _LABEL[s] || s },
    statusType(s) {
      if (s === 'OPEN') return 'success'
      if (s === 'CLOSED') return 'warning'
      if (['LOCKED', 'ARCHIVED'].includes(s)) return 'default'
      return 'primary'
    },
    async load() {
      this.loading = true; this.error = ''
      const res = await api.listBatches({ page: 1, pageSize: 50 })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else this.error = res.message
      this.loading = false
    },
    async select(b) {
      this.current = b
      this.detailTab = 'courses'
      this.ruleForm = { maxCredits: (b.rule && b.rule.maxCredits) || 0 }
      this.reselectData = { cancelledCourses: [], availableCourses: [] }
      this.conflictReport = { summary: [], items: [] }
      this.conflictStudentNo = ''
      await this.refreshDetail()
    },
    async onTabChange() {
      if (!this.current) return
      if (this.detailTab === 'reselect' && this.current.status === 'CLOSED') await this.loadReselectGuide()
      else if (this.detailTab === 'conflict') await this.loadConflictReport()
    },
    async saveRule() {
      this.ruleSaving = true
      const rule = { ...(this.current.rule || {}), maxCredits: Number(this.ruleForm.maxCredits) || 0 }
      const res = await api.saveRule(this.current.batchId, rule)
      this.ruleSaving = false
      if (res.code === 0) { toast.success('规则已保存'); this.current = res.data; await this.load() }
      else toast.error(res.message)
    },
    async loadReselectGuide() {
      const res = await api.reselectGuide(this.current.batchId)
      if (res.code === 0) this.reselectData = res.data
      else toast.error(res.message)
    },
    async loadConflictReport() {
      const res = await api.conflictReport(this.current.batchId, this.conflictStudentNo || undefined)
      if (res.code === 0) this.conflictReport = res.data
      else toast.error(res.message)
    },
    async exportConflict() {
      if (!this.conflictExportPurpose || this.conflictExportPurpose.trim().length < 5) {
        toast.error('导出用途必填且不少于 5 个字'); return
      }
      this.conflictExporting = true
      const res = await api.exportConflictReport(this.current.batchId, this.conflictExportPurpose.trim())
      this.conflictExporting = false
      if (res.code !== 0) { toast.error(res.message || '导出失败'); return }
      const href = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = href; a.download = `选课冲突报表-${Date.now()}.xlsx`
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(href)
    },
    async refreshDetail() {
      if (!this.current) return
      const [cs, st] = await Promise.all([
        api.listCourses(this.current.batchId, { pageSize: 200 }),
        api.batchStats(this.current.batchId)
      ])
      this.courses = cs.code === 0 ? cs.data.list : []
      this.stats = st.code === 0 ? st.data : null
    },
    openCreate() { this.form = { batchName: '', maxCredits: 0, remark: '' }; this.formError = ''; this.createVisible = true },
    async submitCreate() {
      if (!this.form.batchName) { this.formError = '批次名称必填'; return }
      this.saving = true
      const body = { batchName: this.form.batchName, remark: this.form.remark }
      if (this.form.maxCredits > 0) body.rule = { maxCredits: this.form.maxCredits }
      const res = await api.createBatch(body)
      this.saving = false
      if (res.code === 0) { toast.success('已创建'); this.createVisible = false; await this.load() }
      else this.formError = res.message
    },
    lifecycle(fn, label) {
      this.confirmTitle = label
      this.confirmMessage = `确认对批次「${this.current.batchName}」执行「${label}」？`
      this.pendingAction = async () => {
        const res = await api[fn](this.current.batchId)
        if (res.code === 0) { toast.success(label + '成功'); this.current = res.data; await this.load(); await this.refreshDetail() }
        else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    openAddCourse() { this.courseForm = { courseId: '', teachingTaskId: '', capacity: 30, minCapacity: 1 }; this.courseError = ''; this.courseVisible = true },
    async submitCourse() {
      if (!this.courseForm.courseId) { this.courseError = '课程 ID 必填'; return }
      this.saving = true
      const res = await api.addCourse(this.current.batchId, {
        courseId: this.courseForm.courseId,
        teachingTaskId: this.courseForm.teachingTaskId || undefined,
        capacity: this.courseForm.capacity, minCapacity: this.courseForm.minCapacity
      })
      this.saving = false
      if (res.code === 0) { toast.success('已添加'); this.courseVisible = false; await this.refreshDetail() }
      else this.courseError = res.message
    },
    cancelCourse(row) {
      this.confirmTitle = '取消开课'
      this.confirmMessage = `确认取消「${row.courseName}」开课？已选学生将置为课程取消状态。`
      this.pendingAction = async () => {
        const res = await api.cancelCourse(row.selectionCourseId)
        if (res.code === 0) { toast.success('已取消开课'); await this.refreshDetail() }
        else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    async openRoster(row) {
      this.rosterCourse = row; this.rosterRows = []; this.rosterVisible = true
      const res = await api.courseRoster(row.selectionCourseId, { pageSize: 500 })
      if (res.code === 0) this.rosterRows = res.data.list
      else toast.error(res.message)
    },
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() }
  }
}
</script>

<style scoped>
.aasel-layout { display: grid; grid-template-columns: 300px 1fr; gap: 16px; }
.aasel-batches { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aasel-batch { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aasel-batch.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aasel-batch-name { font-weight: 500; }
.aasel-detail-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.aasel-detail-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
.aasel-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.aasel-stats { display: flex; gap: 16px; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
.aasel-stats .is-warn { color: var(--warning-color, #d97706); font-weight: 600; }
.aasel-courses-head { display: flex; justify-content: space-between; align-items: center; margin: 8px 0; font-weight: 500; }
.aasel-form { display: flex; flex-direction: column; gap: 12px; }
.aasel-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 12px; }
.aasel-tab { padding: 6px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--text-500, #646a73); border-bottom: 2px solid transparent; }
.aasel-tab.is-active { color: var(--primary-600, #2563eb); border-bottom-color: var(--primary-500, #3b82f6); font-weight: 500; }
.aasel-rule { display: flex; flex-direction: column; gap: 12px; max-width: 420px; }
.aasel-rule-fixed { background: var(--fill-light, #f8fafc); border-radius: 8px; padding: 10px 14px; font-size: 13px; color: var(--text-600, #566073); }
.aasel-rule-fixed-title { font-weight: 500; margin-bottom: 6px; }
.aasel-rule-fixed ul { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; }
.aasel-section-title { font-weight: 500; margin: 12px 0 8px; }
.aasel-conflict-toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
</style>
