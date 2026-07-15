<template>
  <ModulePageShell
    title="成绩录入"
    subtitle="建录入任务（配平时/期末占比）→ 逐生录入平时/期末分（实时合成总评）→ 提交进入学院审核"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/grade-overview')">成绩总览</button>
      <button class="mp-btn" @click="loadTasks">我的录入任务</button>
    </template>

    <div class="mp-stack">
      <!-- 建任务 -->
      <AppSectionCard v-if="!task" title="新建成绩录入任务">
        <div class="aa-grid2">
          <label class="aa-field"><span class="req">课程名称</span><input v-model.trim="form.courseName" class="aa-input" /></label>
          <label class="aa-field"><span>学期码</span><input v-model.trim="form.termCode" class="aa-input" placeholder="如 2026-1" /></label>
          <label class="aa-field"><span>学分</span><input v-model.number="form.credit" type="number" min="0" step="0.5" class="aa-input" /></label>
          <label class="aa-field"><span>班级ID</span><input v-model.trim="form.classId" class="aa-input" placeholder="选填，填了可自动圈定名单" /></label>
          <label class="aa-field"><span>平时占比%</span><input v-model.number="form.usualRatio" type="number" min="0" max="100" class="aa-input" /></label>
          <label class="aa-field"><span>期末占比%</span><input v-model.number="form.finalRatio" type="number" min="0" max="100" class="aa-input" /></label>
          <label class="aa-field"><span>及格线</span><input v-model.number="form.passLine" type="number" min="0" max="100" class="aa-input" /></label>
        </div>
        <p class="mp-note">平时占比 + 期末占比必须 = 100。</p>
        <div class="aa-actions"><button class="mp-btn mp-btn--primary" :disabled="creating" @click="createTask">{{ creating ? '创建中…' : '创建任务' }}</button></div>

        <div v-if="myTasks.length" class="aa-my-tasks">
          <h4>我的录入任务</h4>
          <ul>
            <li v-for="t in myTasks" :key="t.gradeTaskId" class="aa-my-task-item">
              <span>{{ t.courseName }}</span>
              <AppStatusTag :type="statusColor(t.status)" dot>{{ statusLabel(t.status) }}</AppStatusTag>
              <button class="mp-link" @click="openTask(t)">进入</button>
            </li>
          </ul>
        </div>
      </AppSectionCard>

      <!-- 录入 -->
      <template v-else>
        <AppSectionCard :title="`录入任务：${task.courseName}`">
          <template #header-extra><button class="mp-link" @click="task = null">返回</button></template>
          <div class="aa-task-head">
            <span>平时 {{ task.usualRatio }}% · 期末 {{ task.finalRatio }}% · 及格线 {{ task.passLine }}</span>
            <AppStatusTag :type="statusColor(task.status)" dot>{{ statusLabel(task.status) }}</AppStatusTag>
          </div>
          <AppInlineAlert v-if="task.status === 'RETURNED' && task.returnReason" type="warning"
                         :message="`已被退回：${task.returnReason}，请核对后重新提交`" />
        </AppSectionCard>

        <AppSectionCard v-if="editable" title="添加学生">
          <div class="aa-reg-search">
            <input v-model.trim="kw" class="aa-input aa-input--grow" placeholder="按姓名/学号检索学生添加到录入表" @keyup.enter="searchStudents" />
            <button class="mp-btn" :disabled="searching" @click="searchStudents">检索</button>
            <button class="mp-btn" :disabled="loadingRoster" @click="loadRoster">按班级自动圈定名单</button>
            <button class="mp-btn" @click="importVisible = true">导入成绩（Excel）</button>
          </div>
          <ul v-if="candidates.length" class="aa-cand-list">
            <li v-for="s in candidates" :key="s.studentId" class="aa-cand-item">
              <span>{{ s.realName }} · 学号 {{ s.studentNo }}</span>
              <button class="mp-link" @click="addRow(s)">加入</button>
            </li>
          </ul>
        </AppSectionCard>

        <AppExcelImportDrawer
          v-if="task"
          v-model:visible="importVisible"
          title="导入成绩（学号/平时分/期末分/异常标记）"
          template-name="成绩导入模板.xlsx"
          :required-fields="['学号']"
          :preview-fields="['studentNo', 'studentName', 'usualScore', 'finalScore', 'exceptionFlag']"
          :download-template-fn="() => academicAffairsApi.downloadGradeImportTemplate(task.gradeTaskId)"
          :upload-fn="(file) => academicAffairsApi.uploadGradeImportXlsx(task.gradeTaskId, file)"
          :confirm-fn="({ rows }) => academicAffairsApi.confirmGradeImport(task.gradeTaskId, rows)"
          :download-errors-fn="({ rows, errors }) => academicAffairsApi.downloadGradeImportErrors(task.gradeTaskId, rows, errors)"
          @imported="onImported"
        />

        <AppSectionCard title="成绩录入表">
          <EmptyState v-if="!rows.length" title="录入表为空" description="从上方检索学生加入，或用「按班级自动圈定名单」" />
          <table v-else class="aa-course-table">
            <thead><tr><th>学生</th><th>异常标记</th><th>平时分</th><th>期末分</th><th>总评</th><th>结果</th><th></th></tr></thead>
            <tbody>
              <tr v-for="r in rows" :key="r.studentId">
                <td>{{ r.realName }}</td>
                <td>
                  <select v-model="r.exceptionFlag" class="aa-input aa-input--xs" :disabled="!editable">
                    <option value="NORMAL">正常</option>
                    <option value="ABSENT">缺考</option>
                    <option value="DEFERRED">缓考</option>
                    <option value="EXEMPT">免修</option>
                  </select>
                </td>
                <td><input v-model.number="r.usual" type="number" min="0" max="100" class="aa-input aa-input--xs" :disabled="!editable || r.exceptionFlag !== 'NORMAL'" /></td>
                <td><input v-model.number="r.final" type="number" min="0" max="100" class="aa-input aa-input--xs" :disabled="!editable || r.exceptionFlag !== 'NORMAL'" /></td>
                <td>{{ r.total ?? '—' }}</td>
                <td><AppStatusTag v-if="r.passStatus" :type="r.passStatus === 'PASSED' ? 'success' : 'danger'">{{ r.passStatus === 'PASSED' ? '及格' : '不及格' }}</AppStatusTag></td>
                <td><button v-if="editable" class="mp-link" @click="saveRow(r)">录入</button></td>
              </tr>
            </tbody>
          </table>
          <div v-if="editable" class="aa-actions">
            <button class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '提交进入学院审核' }}</button>
            <span class="mp-note">提交前所有学生须录全平时+期末分或有异常标记；提交后进入学院审核，不可再改（退回后可重新录入）。</span>
          </div>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 成绩录入（/admin/academic-affairs/grade-entry）：POST /grade-tasks + /scores + /submit。 */
import { ModulePageShell, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag, AppInlineAlert } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const TASK_STATUS = {
  NOT_STARTED: '未开始', INPUTTING: '录入中', SUBMITTED: '已提交',
  COLLEGE_REVIEW: '学院审核中', ACADEMIC_REVIEW: '教务终审中', PUBLISHED: '已发布',
  RETURNED: '已退回', ARCHIVED: '已归档'
}
const EDITABLE_STATUS = new Set(['NOT_STARTED', 'INPUTTING', 'RETURNED'])

export default {
  name: 'AaGradeEntryView',
  components: { ModulePageShell, EmptyState, AppSectionCard, AppStatusTag, AppInlineAlert, AppExcelImportDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      form: { courseName: '', termCode: '', credit: null, classId: '', usualRatio: 30, finalRatio: 70, passLine: 60 },
      creating: false, task: null, myTasks: [],
      kw: '', searching: false, loadingRoster: false, candidates: [], rows: [], submitting: false,
      importVisible: false
    }
  },
  computed: {
    editable() { return this.task && EDITABLE_STATUS.has(this.task.status) }
  },
  created() {
    this.loadTasks()
  },
  methods: {
    statusLabel(s) { return TASK_STATUS[s] || s || '' },
    statusColor(s) {
      if (s === 'PUBLISHED') return 'success'
      if (s === 'RETURNED') return 'danger'
      if (['SUBMITTED', 'COLLEGE_REVIEW', 'ACADEMIC_REVIEW'].includes(s)) return 'primary'
      return 'default'
    },
    async loadTasks() {
      const res = await academicAffairsApi.getGradeTasks({ page: 1, pageSize: 50 })
      if (res.code === 0) this.myTasks = res.data.list
    },
    async openTask(t) {
      this.task = { ...t }
      this.rows = []
      this.candidates = []
      await this.refreshRecords()
      if (this.$route.query.action === 'import') this.importVisible = true
    },
    async refreshRecords() {
      if (!this.task) return
      const res = await academicAffairsApi.getGradeRecords(this.task.gradeTaskId)
      if (res.code === 0) {
        this.rows = (res.data.items || []).map((it) => ({
          studentId: it.studentId, realName: it.realName, usual: it.usualScore, final: it.finalScore,
          total: it.totalScore, passStatus: it.passStatus, exceptionFlag: it.exceptionFlag || 'NORMAL'
        }))
      }
    },
    async onImported(result) {
      toast.success(`已导入 ${result?.imported ?? result?.created ?? 0} 条成绩`)
      if (this.task && this.task.status === 'NOT_STARTED' && (result?.imported || result?.created)) {
        this.task.status = 'INPUTTING'
      }
      await this.refreshRecords()
    },
    async createTask() {
      if (this.creating) return
      if (!this.form.courseName) { toast.error('请填写课程名称'); return }
      if (Number(this.form.usualRatio) + Number(this.form.finalRatio) !== 100) { toast.error('平时+期末占比须=100'); return }
      this.creating = true
      const res = await academicAffairsApi.createGradeTask({
        courseName: this.form.courseName, termCode: this.form.termCode || undefined,
        credit: this.form.credit || undefined, classId: this.form.classId || undefined,
        usualRatio: this.form.usualRatio, finalRatio: this.form.finalRatio, passLine: this.form.passLine
      })
      this.creating = false
      if (res.code === 0) { this.task = res.data; toast.success('任务已创建，开始录入'); this.loadTasks() }
      else toast.error(res.message || '创建失败')
    },
    async loadRoster() {
      if (this.loadingRoster) return
      this.loadingRoster = true
      const res = await academicAffairsApi.getGradeRoster(this.task.gradeTaskId)
      this.loadingRoster = false
      if (res.code === 0) {
        const items = res.data.items || []
        if (!items.length) { toast.error(res.data.note || '未圈定到名单'); return }
        items.forEach((s) => this.addRow(s))
        toast.success(`已加入 ${items.length} 人`)
      } else {
        toast.error(res.message || '加载名单失败')
      }
    },
    async searchStudents() {
      if (this.searching) return
      this.searching = true
      const res = await academicAffairsApi.getRoster({ keyword: this.kw || undefined, page: 1, pageSize: 20 })
      this.candidates = res.code === 0 ? res.data.list : []
      this.searching = false
    },
    addRow(s) {
      if (this.rows.some((r) => r.studentId === s.studentId)) return
      this.rows.push({ studentId: s.studentId, realName: s.realName, usual: null, final: null, total: null, passStatus: null, exceptionFlag: 'NORMAL' })
      this.candidates = this.candidates.filter((c) => c.studentId !== s.studentId)
    },
    async saveRow(r) {
      const res = await academicAffairsApi.enterScore(this.task.gradeTaskId, {
        studentId: r.studentId,
        usualScore: r.exceptionFlag === 'NORMAL' && r.usual != null ? r.usual : undefined,
        finalScore: r.exceptionFlag === 'NORMAL' && r.final != null ? r.final : undefined,
        exceptionFlag: r.exceptionFlag
      })
      if (res.code === 0) {
        r.total = res.data.totalScore; r.passStatus = res.data.passStatus
        toast.success(`${r.realName} 已录入`)
        if (this.task.status === 'NOT_STARTED') this.task.status = 'INPUTTING'
      } else toast.error(res.message || '录入失败')
    },
    async submit() {
      if (this.submitting) return
      this.submitting = true
      const res = await academicAffairsApi.submitGradeTask(this.task.gradeTaskId)
      this.submitting = false
      if (res.code === 0) {
        this.task.status = res.data.status
        toast.success('已提交，进入学院审核')
        this.loadTasks()
      } else toast.error(res.message || '提交失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-grid2 { display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 14px 24px; }
.aa-field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-field .req::before { content: '*'; color: var(--danger-600, #f53f3f); margin-right: 4px; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-input--grow { flex: 1; }
.aa-input--xs { width: 90px; height: 30px; padding: 0 8px; }
.aa-actions { margin-top: 16px; display: flex; gap: 12px; align-items: center; }
.aa-reg-search { display: flex; gap: 12px; }
.aa-cand-list { list-style: none; margin: 10px 0 0; padding: 0; border: 1px solid var(--border-100, #f0f1f2); border-radius: 6px; }
.aa-cand-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 13px; }
.aa-cand-item:last-child { border-bottom: none; }
.aa-task-head { display: flex; align-items: center; gap: 16px; font-size: 14px; color: var(--text-700, #4e5969); margin-bottom: 8px; }
.aa-course-table { width: 100%; border-collapse: collapse; }
.aa-course-table th, .aa-course-table td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 14px; }
.aa-course-table th { color: var(--text-500, #646a73); font-weight: 500; font-size: 13px; }
.aa-my-tasks { margin-top: 20px; border-top: 1px solid var(--border-100, #f0f1f2); padding-top: 16px; }
.aa-my-tasks h4 { margin: 0 0 10px; font-size: 14px; color: var(--text-700, #4e5969); }
.aa-my-tasks ul { list-style: none; margin: 0; padding: 0; }
.aa-my-task-item { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 14px; }
</style>
