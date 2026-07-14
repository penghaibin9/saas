<template>
  <ModulePageShell
    title="成绩录入"
    subtitle="建录入任务（配平时/期末占比）→ 逐生录入平时/期末分（实时合成总评）→ 发布回写成绩台账"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/grade-overview')">成绩总览</button>
    </template>

    <div class="mp-stack">
      <!-- 建任务 -->
      <AppSectionCard v-if="!task" title="新建成绩录入任务">
        <div class="aa-grid2">
          <label class="aa-field"><span class="req">课程名称</span><input v-model.trim="form.courseName" class="aa-input" /></label>
          <label class="aa-field"><span>学期码</span><input v-model.trim="form.termCode" class="aa-input" placeholder="如 2026-1" /></label>
          <label class="aa-field"><span>学分</span><input v-model.number="form.credit" type="number" min="0" step="0.5" class="aa-input" /></label>
          <label class="aa-field"><span>班级ID</span><input v-model.trim="form.classId" class="aa-input" placeholder="选填" /></label>
          <label class="aa-field"><span>平时占比%</span><input v-model.number="form.usualRatio" type="number" min="0" max="100" class="aa-input" /></label>
          <label class="aa-field"><span>期末占比%</span><input v-model.number="form.finalRatio" type="number" min="0" max="100" class="aa-input" /></label>
          <label class="aa-field"><span>及格线</span><input v-model.number="form.passLine" type="number" min="0" max="100" class="aa-input" /></label>
        </div>
        <p class="mp-note">平时占比 + 期末占比必须 = 100。</p>
        <div class="aa-actions"><button class="mp-btn mp-btn--primary" :disabled="creating" @click="createTask">{{ creating ? '创建中…' : '创建任务' }}</button></div>
      </AppSectionCard>

      <!-- 录入 -->
      <template v-else>
        <AppSectionCard :title="`录入任务：${task.courseName}`">
          <div class="aa-task-head">
            <span>平时 {{ task.usualRatio }}% · 期末 {{ task.finalRatio }}%</span>
            <AppStatusTag :type="task.status === 'PUBLISHED' ? 'success' : 'primary'">{{ statusLabel(task.status) }}</AppStatusTag>
          </div>
        </AppSectionCard>

        <AppSectionCard v-if="task.status !== 'PUBLISHED'" title="添加学生">
          <div class="aa-reg-search">
            <input v-model.trim="kw" class="aa-input aa-input--grow" placeholder="按姓名/学号检索学生添加到录入表" @keyup.enter="searchStudents" />
            <button class="mp-btn" :disabled="searching" @click="searchStudents">检索</button>
          </div>
          <ul v-if="candidates.length" class="aa-cand-list">
            <li v-for="s in candidates" :key="s.studentId" class="aa-cand-item">
              <span>{{ s.realName }} · 学号 {{ s.studentNo }}</span>
              <button class="mp-link" @click="addRow(s)">加入</button>
            </li>
          </ul>
        </AppSectionCard>

        <AppSectionCard title="成绩录入表">
          <EmptyState v-if="!rows.length" title="录入表为空" description="从上方检索学生加入，或核对是否已发布" />
          <table v-else class="aa-course-table">
            <thead><tr><th>学生</th><th>平时分</th><th>期末分</th><th>总评</th><th>结果</th><th></th></tr></thead>
            <tbody>
              <tr v-for="r in rows" :key="r.studentId">
                <td>{{ r.realName }}</td>
                <td><input v-model.number="r.usual" type="number" min="0" max="100" class="aa-input aa-input--xs" :disabled="published" /></td>
                <td><input v-model.number="r.final" type="number" min="0" max="100" class="aa-input aa-input--xs" :disabled="published" /></td>
                <td>{{ r.total ?? '—' }}</td>
                <td><AppStatusTag v-if="r.passStatus" :type="r.passStatus === 'PASSED' ? 'success' : 'danger'">{{ r.passStatus === 'PASSED' ? '及格' : '不及格' }}</AppStatusTag></td>
                <td><button v-if="!published" class="mp-link" @click="saveRow(r)">录入</button></td>
              </tr>
            </tbody>
          </table>
          <div v-if="!published" class="aa-actions">
            <button class="mp-btn mp-btn--primary" :disabled="publishing" @click="publish">发布成绩</button>
            <span class="mp-note">发布前所有学生须录全平时+期末分；发布后原子回写成绩台账，不可再改（更正走教务）。</span>
          </div>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 成绩录入（/admin/academic-affairs/grade-entry）：POST /grade-tasks + /scores + /publish。 */
import { ModulePageShell, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const TASK_STATUS = { DRAFT: '草稿', ENTERING: '录入中', PUBLISHED: '已发布' }

export default {
  name: 'AaGradeEntryView',
  components: { ModulePageShell, AppSectionCard, EmptyState, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      form: { courseName: '', termCode: '', credit: null, classId: '', usualRatio: 30, finalRatio: 70, passLine: 60 },
      creating: false, task: null,
      kw: '', searching: false, candidates: [], rows: [], publishing: false
    }
  },
  computed: {
    published() { return this.task && this.task.status === 'PUBLISHED' }
  },
  methods: {
    statusLabel(s) { return TASK_STATUS[s] || s || '' },
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
      if (res.code === 0) { this.task = res.data; toast.success('任务已创建，开始录入') }
      else toast.error(res.message || '创建失败')
    },
    async searchStudents() {
      if (this.searching) return
      this.searching = true
      const res = await academicAffairsApi.getRoster({ keyword: this.kw || undefined, page: 1, pageSize: 20 })
      this.candidates = res.code === 0 ? res.data.list : []
      this.searching = false
    },
    addRow(s) {
      if (this.rows.some((r) => r.studentId === s.studentId)) { toast.info('该生已在录入表'); return }
      this.rows.push({ studentId: s.studentId, realName: s.realName, usual: null, final: null, total: null, passStatus: null })
      this.candidates = this.candidates.filter((c) => c.studentId !== s.studentId)
    },
    async saveRow(r) {
      const res = await academicAffairsApi.enterScore(this.task.gradeTaskId, {
        studentId: r.studentId,
        usualScore: r.usual != null ? r.usual : undefined,
        finalScore: r.final != null ? r.final : undefined
      })
      if (res.code === 0) { r.total = res.data.totalScore; r.passStatus = res.data.passStatus; toast.success(`${r.realName} 已录入`) }
      else toast.error(res.message || '录入失败')
    },
    async publish() {
      if (this.publishing) return
      this.publishing = true
      const res = await academicAffairsApi.publishGrades(this.task.gradeTaskId)
      this.publishing = false
      if (res.code === 0) { this.task.status = 'PUBLISHED'; toast.success(`已发布，回写 ${res.data.projected} 条成绩`) }
      else toast.error(res.message || '发布失败')
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
.aa-input--xs { width: 80px; height: 30px; padding: 0 8px; }
.aa-actions { margin-top: 16px; display: flex; gap: 12px; align-items: center; }
.aa-reg-search { display: flex; gap: 12px; }
.aa-cand-list { list-style: none; margin: 10px 0 0; padding: 0; border: 1px solid var(--border-100, #f0f1f2); border-radius: 6px; }
.aa-cand-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 13px; }
.aa-cand-item:last-child { border-bottom: none; }
.aa-task-head { display: flex; align-items: center; gap: 16px; font-size: 14px; color: var(--text-700, #4e5969); }
.aa-course-table { width: 100%; border-collapse: collapse; }
.aa-course-table th, .aa-course-table td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 14px; }
.aa-course-table th { color: var(--text-500, #646a73); font-weight: 500; font-size: 13px; }
</style>
