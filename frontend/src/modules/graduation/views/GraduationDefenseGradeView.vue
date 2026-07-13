<template>
  <ModulePageShell
    title="答辩与成绩"
    subtitle="查重 / 教师评阅 / 答辩评分 / 成绩评定 —— 按学生维度查看与处理"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="gp-mode">
      <button class="gp-mode__btn" :class="{ 'is-active': mode === 'single' }" @click="setMode('single')">按学生连续处理</button>
      <button class="gp-mode__btn" :class="{ 'is-active': mode === 'batch' }" @click="setMode('batch')">成绩台账批量核对</button>
    </div>

    <!-- 批量核对：全员成绩台账（真实 /gd-grades 列表） -->
    <div v-if="mode === 'batch'" class="mp-stack">
      <div class="mp-tabs">
        <button v-for="s in batchTabs" :key="s.value" class="mp-tab" :class="{ 'is-active': batch.status === s.value }" @click="batch.status = s.value; batch.page = 1; loadGrades()">{{ s.label }}</button>
        <label class="gp-missing-only"><input v-model="batch.missingOnly" type="checkbox" /> 只看本页缺项</label>
      </div>
      <AppSearchBox v-model="batch.keyword" placeholder="搜索学生 / 学号" @search="batch.page = 1; loadGrades()" />
      <ErrorState v-if="batch.error" :description="batch.error" @retry="loadGrades" />
      <LoadingState v-else-if="batch.loading" />
      <EmptyState v-else-if="!batchRows.length" title="暂无成绩记录" description="可调整筛选或先在「按学生连续处理」中核算" />
      <DataTable v-else :columns="batchColumns" :rows="batchRows" row-key="id" :pagination="{ page: batch.page, pageSize: batch.pageSize, total: batch.total }" @page-change="p => { batch.page = p; loadGrades() }">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName || '—' }}</div>
          <div class="mp-cell-sub">{{ row.studentNo || '' }}</div>
        </template>
        <template #cell-advisor="{ row }"><span :class="{ 'gp-miss': row.advisorScore == null }">{{ row.advisorScore ?? '缺' }}</span></template>
        <template #cell-reviewer="{ row }"><span :class="{ 'gp-miss': row.reviewerScore == null }">{{ row.reviewerScore ?? '缺' }}</span></template>
        <template #cell-defense="{ row }"><span :class="{ 'gp-miss': row.defenseScore == null }">{{ row.defenseScore ?? '缺' }}</span></template>
        <template #cell-total="{ row }">
          <b v-if="row.totalScore != null">{{ row.totalScore }}</b><span v-else class="gp-miss">未核算</span>
          <span v-if="row.gradeLevel" class="mp-cell-sub"> {{ row.gradeLevel }}</span>
        </template>
        <template #cell-status="{ row }"><StatusTag :type="row.statusTone" :label="row.statusLabel" dot /></template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openFromBatch(row)">处理 →</button>
        </template>
      </DataTable>
      <p class="mp-note">缺项以红色标出；核算 / 复核 / 发布 / 撤回在「按学生连续处理」模式或点「处理 →」完成，全部走真实状态机并留痕。</p>
    </div>

    <div v-else class="gp-layout">
      <div class="gp-side">
        <input v-model="studentKeyword" class="ie-in" placeholder="搜索学生姓名/学号" @input="searchStudents" />
        <ul class="gp-stu-list">
          <li v-for="s in studentOptions" :key="s.id" class="gp-stu-item" :class="{ 'is-active': current && current.id === s.id }" tabindex="0" @click="selectStudent(s)" @keydown.enter.prevent="selectStudent(s)" @keydown.space.prevent="selectStudent(s)">
            <div class="mp-cell-main">{{ s.name }}</div>
            <div class="mp-cell-sub">{{ s.studentNo }} · {{ s.advisorName || '未分配导师' }}</div>
          </li>
        </ul>
        <ErrorState v-if="sideError" :description="sideError" @retry="searchStudents" />
        <EmptyState v-else-if="!studentOptions.length" title="未找到学生" />
      </div>

      <div class="gp-main">
        <template v-if="!current">
          <EmptyState title="请先从左侧选择一名毕设学生" />
        </template>
        <template v-else>
          <section class="gp-context" aria-label="当前处理学生">
            <div class="gp-context__avatar">{{ (current.name || '学').slice(0, 1) }}</div>
            <div class="gp-context__identity">
              <strong>{{ current.name }}</strong>
              <span>{{ current.studentNo || '未关联学号' }} · {{ current.advisorName || '未分配指导教师' }}</span>
            </div>
            <div class="gp-context__hint">按阶段完成查重、评阅、答辩与成绩发布</div>
          </section>
          <div class="gp-tabs">
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'plagiarism' }" @click="switchTab('plagiarism')">查重记录</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'review' }" @click="switchTab('review')">教师评阅</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'defense' }" @click="switchTab('defense')">答辩评分</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'grade' }" @click="switchTab('grade')">成绩评定</button>
          </div>

          <ErrorState v-if="loadError" :description="loadError" @retry="loadAll" />

          <!-- 查重 -->
          <div v-if="tab === 'plagiarism'" class="gp-panel">
            <div class="ie-actions" style="justify-content: flex-start; margin-bottom: var(--space-3)"><button class="mp-btn mp-btn--primary" @click="doSubmitPlagiarism">发起查重</button></div>
            <ul class="gp-timeline">
              <li v-for="p in plagiarismList" :key="p.id" class="gp-timeline-item">
                <div class="mp-cell-main"><AppDateDisplay :value="p.submitAt" mode="datetime" /> · <StatusTag :type="p.overThreshold ? 'danger' : 'success'" :label="p.status === 'DONE' ? (p.rate || '—') : p.statusLabel" dot /></div>
                <div v-if="p.status === 'CHECKING'" class="mp-cell-sub"><button class="mp-link" @click="fillResult(p)">回填结果</button></div>
                <div v-if="p.overThreshold && !p.disputeStatus" class="mp-cell-sub"><button class="mp-link" @click="doDispute(p)">申请复查</button></div>
                <div v-if="p.disputeStatus === 'PENDING'" class="mp-cell-sub">复查申请：{{ p.disputeReason }}
                  <button class="mp-link" @click="doDisputeReview(p, 'APPROVE')">通过</button>
                  <button class="mp-link mp-link--danger" @click="doDisputeReview(p, 'REJECT')">驳回</button>
                </div>
              </li>
            </ul>
            <EmptyState v-if="!plagiarismList.length" title="暂无查重记录" />
          </div>

          <!-- 评阅 -->
          <div v-if="tab === 'review'" class="gp-panel">
            <div class="ie-actions" style="justify-content: flex-start; margin-bottom: var(--space-3)">
              <AppMentorPicker v-model="reviewerName" :remote-search="searchReviewers" placeholder="搜索评阅教师（自动回避该生导师）" style="width: 260px" />
              <button class="mp-btn mp-btn--primary" @click="doAssignReview">分配评阅</button>
            </div>
            <ul class="gp-timeline">
              <li v-for="r in reviewList" :key="r.id" class="gp-timeline-item">
                <div class="mp-cell-main">{{ r.reviewerName }} · <StatusTag :type="r.statusTone" :label="r.statusLabel" dot /></div>
                <div v-if="r.opinion" class="mp-cell-sub">评分 {{ r.score }} · {{ r.opinion }}</div>
                <div class="ie-actions" style="justify-content:flex-start;margin-top:4px">
                  <button v-if="['ASSIGNED', 'REVIEWING', 'RETURNED'].includes(r.status)" class="mp-link" @click="openReviewSubmit(r)">提交评阅</button>
                  <button v-if="r.status === 'COMPLETED'" class="mp-link" @click="openReviewReturn(r)">退回重评</button>
                </div>
              </li>
            </ul>
            <EmptyState v-if="!reviewList.length" title="暂无评阅任务" />
          </div>

          <!-- 答辩评分 -->
          <div v-if="tab === 'defense'" class="gp-panel">
            <div class="ie-actions" style="justify-content: flex-start; margin-bottom: var(--space-3)"><button class="mp-btn mp-btn--primary" @click="openScoreEntry">录入评委评分</button></div>
            <ul class="gp-timeline">
              <li v-for="d in scoreList" :key="d.id" class="gp-timeline-item">
                <div class="mp-cell-main">{{ d.judgeName }}（第{{ d.roundNo }}轮）· {{ d.absent ? '缺席' : d.score }} · <StatusTag :type="d.status === 'CONFIRMED' ? 'success' : 'warning'" :label="d.statusLabel" dot /></div>
              </li>
            </ul>
            <EmptyState v-if="!scoreList.length" title="暂无评分记录" />
            <div class="ie-actions">
              <button class="mp-btn" @click="doConfirmScores">确认本轮成绩</button>
              <button class="mp-btn" @click="openSecondDefense">创建二次答辩</button>
            </div>
          </div>

          <!-- 成绩 -->
          <div v-if="tab === 'grade'" class="gp-panel">
            <LoadingState v-if="gradeLoading" />
            <template v-else-if="grade">
              <div class="gp-kv"><span>状态</span><StatusTag :type="grade.statusTone" :label="grade.statusLabel" dot /></div>
              <div class="gp-kv"><span>导师分</span><span>{{ grade.advisorScore ?? '—' }}</span></div>
              <div class="gp-kv"><span>评阅分</span><span>{{ grade.reviewerScore ?? '—' }}</span></div>
              <div class="gp-kv"><span>答辩分</span><span>{{ grade.defenseScore ?? '—' }}</span></div>
              <div class="gp-kv"><span>综合分</span><span>{{ grade.totalScore ?? '—' }}（{{ grade.gradeLevel }}）</span></div>
              <div class="gp-kv"><span>发布时间</span><AppDateDisplay :value="grade.publishedAt" mode="datetime" /></div>
              <div class="ie-actions">
                <button v-if="['DRAFT', 'WITHDRAWN'].includes(grade.status)" class="mp-btn mp-btn--primary" @click="openCalculate">核算成绩</button>
                <button v-if="grade.status === 'CALCULATED' && !grade.reviewedAt" class="mp-btn" @click="doReview('APPROVE')">复核通过</button>
                <button v-if="grade.status === 'CALCULATED' && !grade.reviewedAt" class="mp-btn" @click="openReturnGrade">复核退回</button>
                <button v-if="grade.status === 'CALCULATED' && grade.reviewedAt" class="mp-btn mp-btn--primary" @click="doPublish">发布成绩</button>
                <button v-if="grade.status === 'PUBLISHED'" class="mp-btn mp-link--danger" @click="openWithdraw">撤回</button>
              </div>
            </template>
          </div>
        </template>
      </div>
    </div>

  </ModulePageShell>
</template>

<script>
/** 答辩与成绩（/admin/graduation/defense-grade）：查重/评阅/答辩评分/成绩评定，按学生维度处理。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSearchBox } from '@/components/common'
import { AppDateDisplay } from '@/components/common/date'
import { graduationDefenseGradeApi } from '@/modules/graduation/api/graduation-defense-grade.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { graduationMentorApi } from '@/modules/graduation/api/graduation-mentor.api'
import { AppMentorPicker } from '@/components/common'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationDefenseGradeView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDateDisplay, AppMentorPicker, AppSearchBox },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      studentKeyword: '', studentOptions: [], current: null, tab: 'plagiarism',
      mode: 'single',
      batch: { loading: false, error: '', rows: [], total: 0, page: 1, pageSize: 20, keyword: '', status: '', missingOnly: false, loaded: false },
      batchTabs: [
        { value: '', label: '全部' },
        { value: 'DRAFT', label: '待核算' },
        { value: 'CALCULATED', label: '已核算' },
        { value: 'PUBLISHED', label: '已发布' },
        { value: 'WITHDRAWN', label: '已撤回' }
      ],
      batchColumns: [
        { key: 'student', title: '学生' },
        { key: 'advisor', title: '导师分' },
        { key: 'reviewer', title: '评阅分' },
        { key: 'defense', title: '答辩分' },
        { key: 'total', title: '综合分' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '90px' }
      ],
      sideError: '', loadError: '',
      plagiarismList: [], reviewList: [], scoreList: [], grade: null, gradeLoading: false,
      reviewerName: '',
      submitting: false
    }
  },
  computed: {
    batchRows() {
      if (!this.batch.missingOnly) return this.batch.rows
      return this.batch.rows.filter((r) => r.advisorScore == null || r.reviewerScore == null || r.defenseScore == null || r.totalScore == null)
    },
    ...({}
    )
  },
  created() {
    const p = this.$route.query.panel
    if (['plagiarism', 'review', 'defense', 'grade'].includes(p)) this.tab = p
    if ((this.$route.query.view || '') === 'batch') { this.mode = 'batch'; this.loadGrades() }
    this.searchStudents()
  },
  watch: {
    // 应用内点左侧三级菜单（同路由不同 ?panel=）时组件被复用，必须监听 query 才能切页签
    '$route.query.panel'(p) {
      if (['plagiarism', 'review', 'defense', 'grade'].includes(p) && p !== this.tab) this.tab = p
    }
  },
  methods: {
    setMode(m) {
      this.mode = m
      const q = { ...this.$route.query, view: m === 'batch' ? 'batch' : undefined }
      this.$router.replace({ query: q })
      if (m === 'batch' && !this.batch.loaded) this.loadGrades()
    },
    async loadGrades() {
      const B = this.batch
      B.loading = true; B.error = ''
      const res = await graduationDefenseGradeApi.getGrades({ keyword: B.keyword, status: B.status || undefined, page: B.page, pageSize: B.pageSize })
      if (res.code === 0) { B.rows = res.data.list; B.total = res.data.total; B.loaded = true } else { B.rows = []; B.error = res.message || '加载失败' }
      B.loading = false
    },
    /** 台账行 → 切回按学生模式并定位该生成绩页签 */
    openFromBatch(row) {
      this.mode = 'single'
      this.$router.replace({ query: { ...this.$route.query, view: undefined, panel: 'grade' } })
      this.tab = 'grade'
      this.current = { id: row.gdStudentId, name: row.studentName, studentNo: row.studentNo, advisorName: row.advisorName }
      this.loadAll()
    },
    /** 页签切换同步到 URL，保证刷新/分享/左侧菜单高亮一致 */
    switchTab(t) {
      this.tab = t
      if (this.$route.query.panel !== t) this.$router.replace({ query: { ...this.$route.query, panel: t } })
    },
    /** 评阅教师远程搜索：排除该生指导教师（SoD），最终由后端再次校验 */
    async searchReviewers(keyword) {
      const res = await graduationMentorApi.getMentors({ keyword, qualificationStatus: 'QUALIFIED', pageSize: 20 })
      if (res.code !== 0) throw new Error(res.message || '搜索失败')
      const advisor = this.current && this.current.advisorName
      return res.data.list.map((m) => ({
        label: m.teacherName === advisor ? `${m.teacherName}（该生导师 · 回避）` : `${m.teacherName}（${m.capacityText || m.collegeName || '教师'}）`,
        value: m.teacherName,
        disabled: m.teacherName === advisor
      }))
    },
    async searchStudents() {
      this.sideError = ''
      const res = await gdStudentApi.getStudents({ keyword: this.studentKeyword, pageSize: 20 })
      if (res.code === 0) { this.studentOptions = res.data.list } else { this.studentOptions = []; this.sideError = res.message || '学生列表加载失败' }
    },
    selectStudent(s) { this.current = s; this.loadAll() },
    async loadAll() {
      this.loadError = ''
      await Promise.all([this.loadPlagiarism(), this.loadReview(), this.loadScores(), this.loadGrade()])
    },
    async loadPlagiarism() {
      const res = await graduationDefenseGradeApi.getPlagiarismList({ gdStudentId: this.current.id, pageSize: 50 })
      if (res.code === 0) { this.plagiarismList = res.data.list } else { this.plagiarismList = []; this.loadError = res.message || '查重记录加载失败' }
    },
    async loadReview() {
      const res = await graduationDefenseGradeApi.getReviewList({ gdStudentId: this.current.id, pageSize: 50 })
      if (res.code === 0) { this.reviewList = res.data.list } else { this.reviewList = []; this.loadError = res.message || '评阅记录加载失败' }
    },
    async loadScores() {
      const res = await graduationDefenseGradeApi.getScoreList({ gdStudentId: this.current.id, pageSize: 50 })
      if (res.code === 0) { this.scoreList = res.data.list } else { this.scoreList = []; this.loadError = res.message || '评分记录加载失败' }
    },
    async loadGrade() {
      this.gradeLoading = true
      const res = await graduationDefenseGradeApi.getGrade(this.current.id)
      if (res.code === 0) { this.grade = res.data } else { this.grade = null; this.loadError = res.message || '成绩加载失败' }
      this.gradeLoading = false
    },
    async doSubmitPlagiarism() {
      const res = await graduationDefenseGradeApi.submitPlagiarism(this.current.id)
      if (res.code === 0) { toast.success('已提交检测'); this.loadPlagiarism() } else toast.error(res.message)
    },
    openForm(formKey, recordId = '') {
      if (!this.current) return
      this.$router.push({
        path: '/admin/graduation/defense-grade/form',
        query: {
          formKey,
          recordId: recordId || undefined,
          studentId: this.current.id,
          panel: this.tab
        }
      })
    },
    fillResult(p) {
      this.openForm('plagiarismResult', p.id)
    },
    doDispute(p) {
      this.openForm('dispute', p.id)
    },
    async doDisputeReview(p, action) {
      const res = await graduationDefenseGradeApi.reviewDispute(p.id, action, action === 'REJECT' ? '维持原查重结果' : '核实无误')
      if (res.code === 0) { toast.success('已审核'); this.loadPlagiarism() } else toast.error(res.message)
    },
    async doAssignReview() {
      if (!this.reviewerName) return toast.error('请填写评阅人姓名')
      const res = await graduationDefenseGradeApi.assignReview(this.current.id, this.reviewerName)
      if (res.code === 0) { toast.success('已分配'); this.reviewerName = ''; this.loadReview() } else toast.error(res.message)
    },
    openReviewSubmit(r) {
      this.openForm('reviewSubmit', r.id)
    },
    openReviewReturn(r) {
      this.openForm('reviewReturn', r.id)
    },
    openScoreEntry() {
      this.openForm('scoreEntry')
    },
    async doConfirmScores() {
      const res = await graduationDefenseGradeApi.confirmScores(this.current.id)
      if (res.code === 0) { toast.success('已确认'); this.loadScores() } else toast.error(res.message)
    },
    openSecondDefense() {
      this.openForm('secondDefense')
    },
    openCalculate() {
      this.openForm('calculate')
    },
    async doReview(action) {
      const res = await graduationDefenseGradeApi.reviewGrade(this.current.id, { action })
      if (res.code === 0) { toast.success('已复核'); this.loadGrade() } else toast.error(res.message)
    },
    openReturnGrade() {
      this.openForm('returnGrade')
    },
    async doPublish() {
      const res = await graduationDefenseGradeApi.publishGrade(this.current.id)
      if (res.code === 0) { toast.success('已发布'); this.loadGrade() } else toast.error(res.message)
    },
    openWithdraw() {
      this.openForm('withdraw')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gp-mode { display: inline-flex; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); overflow: hidden; margin-bottom: var(--space-3); box-shadow: 0 1px 2px rgba(15, 23, 42, .04); }
.gp-mode__btn { padding: 8px 16px; border: none; background: #fff; cursor: pointer; font-size: 13px; color: var(--text-secondary, #475569); transition: background .15s ease, color .15s ease; }
.gp-mode__btn:hover:not(.is-active) { background: var(--gray-50, #f8fafc); }
.gp-mode__btn:focus-visible, .gp-tabs__item:focus-visible, .gp-stu-item:focus-visible { outline: 2px solid var(--primary-400, #60a5fa); outline-offset: -2px; }
.gp-mode__btn.is-active { background: var(--brand-primary, #2563eb); color: #fff; }
.gp-miss { color: var(--danger, #dc2626); font-weight: 600; }
.gp-missing-only { margin-left: auto; font-size: var(--font-size-sm, 13px); color: var(--text-secondary, #475569); display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.mp-tabs { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-1); }
.gp-layout { display: flex; gap: var(--space-4); align-items: flex-start; }
.gp-side { width: 280px; flex: none; padding: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--card, #fff); box-shadow: 0 1px 2px rgba(15, 23, 42, .03); }
.gp-main { flex: 1; min-width: 0; padding: var(--space-4); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--card, #fff); box-shadow: 0 1px 2px rgba(15, 23, 42, .03); }
.gp-stu-list { list-style: none; margin: var(--space-2) 0 0; padding: 0; max-height: 560px; overflow-y: auto; }
.gp-stu-item { padding: 9px 10px; border-radius: 8px; cursor: pointer; border: 1px solid transparent; transition: background .12s ease, border-color .12s ease; }
.gp-stu-item:hover { background: var(--bg2, #f8fafc); }
.gp-stu-item.is-active { background: var(--pri-bg, #eff6ff); border-color: var(--pri, #2563eb); }
.gp-context { display: flex; align-items: center; gap: var(--space-3); padding: 0 0 var(--space-3); margin-bottom: var(--space-1); border-bottom: 1px solid var(--border-light, #e2e8f0); }
.gp-context__avatar { display: grid; place-items: center; width: 36px; height: 36px; flex: 0 0 auto; border-radius: var(--radius-full); background: var(--primary-50, #eff6ff); color: var(--primary-700, #1d4ed8); font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); }
.gp-context__identity { display: grid; gap: 2px; min-width: 0; }
.gp-context__identity strong { color: var(--text-primary); font-size: var(--font-size-md); }
.gp-context__identity span { overflow: hidden; color: var(--text-tertiary); font-size: var(--font-size-xs); text-overflow: ellipsis; white-space: nowrap; }
.gp-context__hint { margin-left: auto; max-width: 235px; color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: 1.5; text-align: right; }
.gp-tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--line, #e2e8f0); margin-bottom: var(--space-3); flex-wrap: wrap; }
.gp-tabs__item { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--t2, #475569); border-bottom: 2px solid transparent; }
.gp-tabs__item.is-active { color: var(--pri, #2563eb); border-bottom-color: var(--pri, #2563eb); font-weight: 600; }
.gp-panel { font-size: 13px; }
.gp-kv { display: flex; gap: var(--space-3); padding: 6px 0; border-bottom: 1px dashed var(--line, #eef1f6); }
.gp-kv > span:first-child { width: 90px; flex: none; color: var(--t3, #64748b); }
.gp-timeline { list-style: none; margin: 0; padding: 0; }
.gp-timeline-item { padding: 10px 0; border-bottom: 1px dashed var(--line, #eef1f6); }
.mp-link--danger { color: var(--danger, #dc2626); }
.ie-form { display: grid; grid-template-columns: 1fr; gap: var(--space-3); padding: var(--space-1) 0; }
.ie-fld { display: flex; flex-direction: column; gap: 4px; }
.ie-fld--full { grid-column: 1 / -1; }
.ie-lbl { font-size: 12px; color: var(--t2, #475569); }
.ie-lbl i { color: var(--danger, #dc2626); font-style: normal; }
.ie-in { width: 100%; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.ie-err { color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.ie-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
@media (max-width: 960px) {
  .gp-layout { flex-direction: column; }
  .gp-side, .gp-main { width: 100%; box-sizing: border-box; }
  .gp-stu-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(185px, 1fr)); max-height: 260px; gap: var(--space-1); }
}
@media (max-width: 640px) {
  .gp-context__hint { display: none; }
  .gp-main { padding: var(--space-3); }
}
</style>
