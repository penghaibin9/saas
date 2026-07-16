<template>
  <ModulePageShell
    :title="detail ? detail.name + ' · 毕设详情' : '毕设详情'"
    :subtitle="detail ? (detail.className + (detail.batchName ? ' · ' + detail.batchName : '')) : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" @back="$router.back()" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack gsd-page">
      <section class="gsd-summary" aria-label="毕设学生摘要">
        <div class="gsd-summary__identity">
          <div class="gsd-summary__avatar">{{ (detail.name || '学').slice(0, 1) }}</div>
          <div>
            <strong>{{ detail.name }}</strong>
            <span><AppSensitiveText :value="detail.studentNo" type="generic" /> · {{ detail.className || '未关联班级' }}</span>
          </div>
        </div>
        <div class="gsd-summary__item"><span>当前节点</span><StatusTag :type="detail.stageTone || 'processing'" :label="detail.stageLabel" dot /></div>
        <div class="gsd-summary__item"><span>指导教师</span><b>{{ detail.advisorName || '待分配' }}</b></div>
        <div class="gsd-summary__item"><span>风险状态</span><b :class="{ 'is-danger': detail.riskLevel === 'HIGH' || detail.riskLevel === 'CRITICAL' }">{{ detail.riskLabel || '无风险' }}</b></div>
      </section>

    <div class="mp-grid-2">
      <div class="mp-stack">
        <AppSectionCard title="课题信息">
          <template #header-extra>
            <StatusTag :type="detail.stageTone || 'processing'" :label="detail.stageLabel" dot />
          </template>
          <AppDescriptionList :items="topicInfoItems" :columns="1">
            <template #studentNo>
              <AppSensitiveText :value="detail.studentNo" type="generic" />
            </template>
            <template #phone>
              <AppSensitiveText :value="detail.phone" type="phone" />
            </template>
          </AppDescriptionList>
        </AppSectionCard>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">主状态进度</span></div>
          <div class="mp-card__body">
            <ul class="mp-timeline">
              <li v-for="s in detail.stateFlow" :key="s.title" class="mp-timeline__item" :class="'is-' + (s.tone === 'processing' ? 'warning' : s.tone)">
                <div class="mp-timeline__title">{{ s.title }}</div>
                <div class="mp-timeline__time">{{ s.time }}</div>
              </li>
            </ul>
          </div>
        </section>
      </div>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-tabs gsd-tabs" style="padding: 0 var(--space-4)">
            <button v-for="t in tabs" :key="t.key" class="mp-tab" :class="{ 'is-active': tab === t.key }" @click="switchTab(t.key)">
              {{ t.label }}
            </button>
          </div>
          <div class="mp-card__body">
            <table v-if="tab === 'proposals'" class="mp-audit">
              <thead><tr><th>材料</th><th>版本</th><th>提交时间</th><th>状态</th><th>批阅人</th></tr></thead>
              <tbody>
                <tr v-if="!detail.proposals.length"><td colspan="5" class="mp-note">暂无开题记录</td></tr>
                <tr v-for="p in detail.proposals" :key="p.id">
                  <td class="is-who">{{ p.type }}</td>
                  <td>{{ p.version }}</td>
                  <td>{{ p.submitAt }}</td>
                  <td><StatusTag :status="p.status" dot /></td>
                  <td>{{ p.reviewer }}</td>
                </tr>
              </tbody>
            </table>
            <table v-else-if="tab === 'finals'" class="mp-audit">
              <thead><tr><th>成果</th><th>版本</th><th>提交时间</th><th>状态</th><th>查重</th></tr></thead>
              <tbody>
                <tr v-if="!detail.finals.length"><td colspan="5" class="mp-note">暂无成果提交</td></tr>
                <tr v-for="f in detail.finals" :key="f.id">
                  <td class="is-who">{{ f.type }}</td>
                  <td>{{ f.version }}</td>
                  <td>{{ f.submitAt }}</td>
                  <td><StatusTag :status="f.status" dot /></td>
                  <td>{{ f.plagiarism }}</td>
                </tr>
              </tbody>
            </table>
            <table v-else-if="tab === 'plagiarisms'" class="mp-audit">
              <thead><tr><th>检测对象</th><th>查重率</th><th>状态</th><th>时间</th></tr></thead>
              <tbody>
                <tr v-if="!detail.plagiarisms.length"><td colspan="4" class="mp-note">暂无查重记录</td></tr>
                <tr v-for="p in detail.plagiarisms" :key="p.id">
                  <td class="is-who">{{ p.version }}</td>
                  <td>{{ p.rate }}</td>
                  <td>{{ p.status }}</td>
                  <td>{{ p.time }}</td>
                </tr>
              </tbody>
            </table>

            <!-- 任务书（真实 taskbook API，懒加载） -->
            <div v-else-if="tab === 'taskbook'">
              <ErrorState v-if="lazy.taskbook.error" :description="lazy.taskbook.error" @retry="loadTaskbook" />
              <LoadingState v-else-if="lazy.taskbook.loading" />
              <template v-else-if="lazy.taskbook.data && lazy.taskbook.data.exists">
                <div class="mp-kv"><span class="mp-kv__k">状态</span><span class="mp-kv__v"><StatusTag :type="lazy.taskbook.data.statusTone" :label="lazy.taskbook.data.statusLabel" dot /></span></div>
                <div class="mp-kv"><span class="mp-kv__k">版本</span><span class="mp-kv__v">v{{ lazy.taskbook.data.taskbookVersion }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">任务目标</span><span class="mp-kv__v">{{ lazy.taskbook.data.objective || '—' }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">任务内容</span><span class="mp-kv__v">{{ lazy.taskbook.data.content || '—' }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">截止时间</span><span class="mp-kv__v">{{ fmtTime(lazy.taskbook.data.deadline) || '未设置' }}</span></div>
                <p class="mp-note" style="margin-top: var(--space-2)">任务书下达 / 确认 / 变更在「过程指导」工作区办理</p>
              </template>
              <p v-else class="mp-note">尚未下达任务书，可在「过程指导」为该生下达</p>
            </div>

            <!-- 指导记录 -->
            <div v-else-if="tab === 'guidance'">
              <ErrorState v-if="lazy.guidance.error" :description="lazy.guidance.error" @retry="loadGuidance" />
              <LoadingState v-else-if="lazy.guidance.loading" />
              <p v-else-if="!lazy.guidance.list.length" class="mp-note">暂无指导记录</p>
              <ul v-else class="mp-timeline">
                <li v-for="g in lazy.guidance.list" :key="g.id" class="mp-timeline__item is-success">
                  <div class="mp-timeline__title">{{ fmtTime(g.guidanceDate) }} · {{ g.methodLabel }}</div>
                  <div class="mp-timeline__desc">{{ g.content }}</div>
                  <div v-if="g.issues" class="mp-timeline__desc" style="color: var(--danger, #dc2626)">问题：{{ g.issues }}</div>
                </li>
              </ul>
            </div>

            <!-- 中期检查 -->
            <div v-else-if="tab === 'midterm'">
              <ErrorState v-if="lazy.midterm.error" :description="lazy.midterm.error" @retry="loadMidterm" />
              <LoadingState v-else-if="lazy.midterm.loading" />
              <template v-else-if="lazy.midterm.data">
                <div class="mp-kv"><span class="mp-kv__k">状态</span><span class="mp-kv__v"><StatusTag :type="lazy.midterm.data.statusTone" :label="lazy.midterm.data.statusLabel" dot /></span></div>
                <div v-if="lazy.midterm.data.conclusionLabel" class="mp-kv"><span class="mp-kv__k">结论</span><span class="mp-kv__v">{{ lazy.midterm.data.conclusionLabel }}</span></div>
                <div v-if="lazy.midterm.data.checkComment" class="mp-kv"><span class="mp-kv__k">检查意见</span><span class="mp-kv__v">{{ lazy.midterm.data.checkComment }}</span></div>
                <div v-if="lazy.midterm.data.rectifyContent" class="mp-kv"><span class="mp-kv__k">整改内容</span><span class="mp-kv__v">{{ lazy.midterm.data.rectifyContent }}</span></div>
                <p class="mp-note" style="margin-top: var(--space-2)">中期检查与整改在「过程指导」工作区办理</p>
              </template>
              <p v-else class="mp-note">暂无中期检查记录</p>
            </div>

            <!-- 评阅与成绩 -->
            <div v-else-if="tab === 'review'">
              <ErrorState v-if="lazy.review.error" :description="lazy.review.error" @retry="loadReview" />
              <LoadingState v-else-if="lazy.review.loading" />
              <template v-else>
                <p v-if="!lazy.review.list.length" class="mp-note">暂无评阅任务</p>
                <ul v-else class="mp-timeline">
                  <li v-for="r in lazy.review.list" :key="r.id" class="mp-timeline__item is-warning">
                    <div class="mp-timeline__title">{{ r.reviewerName }} · {{ r.statusLabel }}</div>
                    <div v-if="r.opinion" class="mp-timeline__desc">评分 {{ r.score }} · {{ r.opinion }}</div>
                  </li>
                </ul>
                <template v-if="lazy.review.grade">
                  <div class="mp-kv" style="margin-top: var(--space-2)"><span class="mp-kv__k">成绩状态</span><span class="mp-kv__v"><StatusTag :type="lazy.review.grade.statusTone" :label="lazy.review.grade.statusLabel" dot /></span></div>
                  <div class="mp-kv"><span class="mp-kv__k">综合分</span><span class="mp-kv__v">{{ lazy.review.grade.totalScore ?? '—' }}{{ lazy.review.grade.gradeLevel ? '（' + lazy.review.grade.gradeLevel + '）' : '' }}</span></div>
                </template>
                <p class="mp-note" style="margin-top: var(--space-2)">评阅分配与成绩核算在「答辩成绩」工作区办理</p>
              </template>
            </div>

            <!-- 风险（真实按学生过滤） -->
            <div v-else-if="tab === 'risk'">
              <ErrorState v-if="lazy.risk.error" :description="lazy.risk.error" @retry="loadRiskTab" />
              <LoadingState v-else-if="lazy.risk.loading" />
              <p v-else-if="!lazy.risk.list.length" class="mp-note">该生暂无风险记录</p>
              <template v-else>
                <ul class="mp-timeline">
                  <li v-for="r in lazy.risk.list" :key="r.id" class="mp-timeline__item" :class="r.status === 'CLOSED' ? 'is-success' : 'is-danger'">
                    <div class="mp-timeline__title">{{ r.riskName }} · {{ levelLabel(r.level) }} · {{ r.statusLabel }}</div>
                    <div v-if="r.handleNote" class="mp-timeline__desc">{{ r.handleNote }}</div>
                  </li>
                </ul>
                <p class="mp-note" style="margin-top: var(--space-2)">
                  <button class="mp-link" @click="$router.push('/admin/graduation/risk-archive?panel=risk')">去风险处置工作区 →</button>
                </p>
              </template>
            </div>

            <!-- 归档（按学生真实核验记录） -->
            <div v-else-if="tab === 'archive'">
              <ErrorState v-if="lazy.archive.error" :description="lazy.archive.error" @retry="loadArchiveTab" />
              <LoadingState v-else-if="lazy.archive.loading" />
              <template v-else-if="lazy.archive.data">
                <div class="mp-kv"><span class="mp-kv__k">归档状态</span><span class="mp-kv__v"><StatusTag :type="lazy.archive.data.statusTone" :label="lazy.archive.data.statusLabel" dot /></span></div>
                <div class="mp-kv"><span class="mp-kv__k">材料完整性</span>
                  <span class="mp-kv__v" :style="(lazy.archive.data.missingItems || []).length ? 'color: var(--danger, #dc2626)' : 'color: var(--success-600, #16a34a)'">
                    {{ (lazy.archive.data.missingItems || []).length ? '缺失 ' + lazy.archive.data.missingItems.length + ' 项' : '必备材料齐全' }}
                  </span>
                </div>
                <ul v-if="(lazy.archive.data.missingItems || []).length" class="mp-timeline" style="margin-top: var(--space-1)">
                  <li v-for="m in lazy.archive.data.missingItems" :key="m" class="mp-timeline__item is-danger">
                    <div class="mp-timeline__title">缺：{{ m }}</div>
                  </li>
                </ul>
                <p class="mp-note" style="margin-top: var(--space-2)">
                  <button class="mp-link" @click="$router.push('/admin/graduation/risk-archive?panel=archive')">去归档核验工作区 →</button>
                </p>
              </template>
              <p v-else class="mp-note">暂无归档记录</p>
            </div>
          </div>
        </section>

        <AppSectionCard title="审计日志（本学生毕设档案）">
          <AppAuditTrail :records="auditRecords" empty-text="暂无审计记录" compact :show-ip="false" />
        </AppSectionCard>
      </div>
    </div>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 毕设学生详情（/admin/graduation/students/:id）：批次/选题/节点 + 材料/成果/查重 + 状态机操作 + 审计。 */
import { ModulePageShell, ModuleToolbar, StatusTag, LoadingState, ErrorState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppSensitiveText, AppAuditTrail, AppSectionCard, AppDescriptionList } from '@/components/common'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { graduationTaskbookApi } from '@/modules/graduation/api/graduation-taskbook.api'
import { graduationDefenseGradeApi } from '@/modules/graduation/api/graduation-defense-grade.api'
import { graduationRiskArchiveApi } from '@/modules/graduation/api/graduation-risk-archive.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationStudentDetailView',
  components: { ModulePageShell, ModuleToolbar, StatusTag, LoadingState, ErrorState, AppConfirmDialog, AppSensitiveText, AppAuditTrail, AppSectionCard, AppDescriptionList },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false, detail: null,
      tab: 'proposals',
      tabs: [
        { key: 'proposals', label: '开题' },
        { key: 'taskbook', label: '任务书' },
        { key: 'guidance', label: '指导记录' },
        { key: 'midterm', label: '中期' },
        { key: 'finals', label: '成果' },
        { key: 'plagiarisms', label: '查重' },
        { key: 'review', label: '评阅与成绩' },
        { key: 'risk', label: '风险' },
        { key: 'archive', label: '归档' }
      ],
      lazy: {
        taskbook: { loading: false, error: '', data: null, loaded: false },
        guidance: { loading: false, error: '', list: [], loaded: false },
        midterm: { loading: false, error: '', data: null, loaded: false },
        review: { loading: false, error: '', list: [], grade: null, loaded: false },
        risk: { loading: false, error: '', list: [], loaded: false },
        archive: { loading: false, error: '', data: null, loaded: false }
      },
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null }
    }
  },
  computed: {
    topicInfoItems() {
      if (!this.detail) return []
      const d = this.detail
      return [
        { key: 'studentNo', label: '学号', value: d.studentNo },
        { key: 'batchName', label: '毕设批次', value: d.batchName || '未关联' },
        { key: 'topicTitle', label: '课题名称', value: d.topicTitle },
        { key: 'topicSource', label: '课题来源', value: d.topicSource || '—' },
        { key: 'advisorName', label: '指导教师', value: d.advisorName || '未分配' },
        { key: 'taskbook', label: '任务书', value: d.taskbook },
        { key: 'phone', label: '联系电话', value: d.phone },
        { key: 'midterm', label: '中期检查', value: d.midterm?.conclusion },
        { key: 'defense', label: '答辩安排', value: d.defense?.group },
        { key: 'risk', label: '风险等级', value: d.riskLabel }
      ]
    },
    auditRecords() {
      return (this.detail?.auditTrail || []).map((a, i) => ({
        id: i,
        action: a.action,
        actor: a.who,
        at: a.time,
        target: a.affected
      }))
    },
    toolbarActions() {
      if (!this.detail || this.detail.stage === 'ARCHIVED') {
        return [{ key: 'back', label: '返回列表' }]
      }
      const actions = []
      if (!this.detail.topicId) actions.push({ key: 'assignTopic', label: '分配选题' })
      if (!this.detail.advisorName) actions.push({ key: 'assignAdvisor', label: '分配导师' })
      if (this.detail.stage !== 'DEFENSE' && this.detail.stage !== 'ARCHIVED') {
        actions.push({ key: 'advance', label: '推进节点', variant: 'primary' })
      }
      if (this.detail.stage === 'DEFENSE') actions.push({ key: 'archive', label: '归档' })
      actions.push({ key: 'risk', label: '标记风险' })
      return actions
    }
  },
  created() {
    const qTab = (this.$route.query.tab || '').toString()
    if (this.tabs.some((x) => x.key === qTab)) this.tab = qTab
    this.load()
    this.ensureTabData(this.tab)
  },
  methods: {
    fmtTime(s) { return (s || '').toString().replace('T', ' ').slice(0, 16) },
    switchTab(k) {
      this.tab = k
      this.$router.replace({ query: { ...this.$route.query, tab: k } })
      this.ensureTabData(k)
    },
    ensureTabData(k) {
      if (k === 'taskbook' && !this.lazy.taskbook.loaded) this.loadTaskbook()
      if (k === 'guidance' && !this.lazy.guidance.loaded) this.loadGuidance()
      if (k === 'midterm' && !this.lazy.midterm.loaded) this.loadMidterm()
      if (k === 'review' && !this.lazy.review.loaded) this.loadReview()
      if (k === 'risk' && !this.lazy.risk.loaded) this.loadRiskTab()
      if (k === 'archive' && !this.lazy.archive.loaded) this.loadArchiveTab()
    },
    async loadTaskbook() {
      const L = this.lazy.taskbook
      L.loading = true; L.error = ''
      const res = await graduationTaskbookApi.getTaskbook(this.$route.params.id)
      if (res.code === 0) { L.data = res.data; L.loaded = true } else L.error = res.message || '加载失败'
      L.loading = false
    },
    async loadGuidance() {
      const L = this.lazy.guidance
      L.loading = true; L.error = ''
      const res = await graduationTaskbookApi.getGuidanceList({ gdStudentId: this.$route.params.id, pageSize: 50 })
      if (res.code === 0) { L.list = res.data.list; L.loaded = true } else L.error = res.message || '加载失败'
      L.loading = false
    },
    async loadMidterm() {
      const L = this.lazy.midterm
      L.loading = true; L.error = ''
      const res = await graduationTaskbookApi.getMidterm(this.$route.params.id)
      if (res.code === 0) { L.data = res.data; L.loaded = true } else L.error = res.message || '加载失败'
      L.loading = false
    },
    async loadReview() {
      const L = this.lazy.review
      L.loading = true; L.error = ''
      const [r, g] = await Promise.all([
        graduationDefenseGradeApi.getReviewList({ gdStudentId: this.$route.params.id, pageSize: 50 }),
        graduationDefenseGradeApi.getGrade(this.$route.params.id)
      ])
      if (r.code === 0) { L.list = r.data.list; L.loaded = true } else L.error = r.message || '加载失败'
      L.grade = g.code === 0 ? g.data : null
      L.loading = false
    },
    async loadRiskTab() {
      const L = this.lazy.risk
      L.loading = true; L.error = ''
      const res = await graduationRiskArchiveApi.getRiskList({ gdStudentId: this.$route.params.id, pageSize: 50 })
      if (res.code === 0) { L.list = res.data.list; L.loaded = true } else L.error = res.message || '加载失败'
      L.loading = false
    },
    async loadArchiveTab() {
      const L = this.lazy.archive
      L.loading = true; L.error = ''
      const res = await graduationRiskArchiveApi.getArchiveByStudent(this.$route.params.id)
      if (res.code === 0) { L.data = res.data; L.loaded = true } else L.error = res.message || '加载失败'
      L.loading = false
    },
    levelLabel(level) {
      return { LOW: '低', MEDIUM: '中', HIGH: '高', CRITICAL: '紧急' }[level] || level
    },
    async load() {
      this.loading = true; this.error = ''
      const res = await gdStudentApi.getStudentDetail(this.$route.params.id)
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
    },
    async onToolbar(key) {
      if (key === 'back') { this.$router.push('/admin/graduation/students'); return }
      if (key === 'assignTopic') {
        this.$router.push(`/admin/graduation/students/${this.detail.id}/assign-topic`)
      }
      if (key === 'assignAdvisor') {
        this.confirm = { visible: true, title: '分配指导教师', message: '填写指导教师姓名', type: 'primary', confirmText: '确认', requireReason: true, reasonLabel: '指导教师', action: 'ADVISOR' }
      }
      if (key === 'advance') {
        this.confirm = { visible: true, title: '推进节点', message: `确认将「${this.detail.name}」推进到下一节点？`, type: 'primary', confirmText: '推进', requireReason: false, reasonLabel: '备注', action: 'ADVANCE' }
      }
      if (key === 'archive') {
        this.confirm = { visible: true, title: '归档毕设档案', message: '归档后记录只读', type: 'warning', confirmText: '确认归档', requireReason: true, reasonLabel: '归档原因', action: 'ARCHIVE' }
      }
      if (key === 'risk') {
        this.confirm = { visible: true, title: '标记高风险', message: '将学生标记为高风险并留痕', type: 'warning', confirmText: '标记', requireReason: true, reasonLabel: '风险原因', action: 'RISK_HIGH' }
      }
    },
    async onConfirm({ reason } = {}) {
      this.submitting = true
      try {
        let res
        const id = this.detail.id
        if (this.confirm.action === 'ADVISOR') res = await gdStudentApi.assignAdvisor(id, { advisorName: (reason || '').trim() })
        if (this.confirm.action === 'ADVANCE') res = await gdStudentApi.setStage(id, { action: 'ADVANCE', reason: reason || '' })
        if (this.confirm.action === 'ARCHIVE') res = await gdStudentApi.setStage(id, { action: 'ARCHIVE', reason: reason || '' })
        if (this.confirm.action === 'RISK_HIGH') res = await gdStudentApi.setRisk(id, { riskLevel: 'HIGH', reason: reason || '' })
        if (res && res.code === 0) { toast.success('已更新'); this.confirm.visible = false; this.load() } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gsd-page { gap: var(--space-4); }
.gsd-summary { display: grid; grid-template-columns: minmax(220px, 1.5fr) repeat(3, minmax(130px, 1fr)); align-items: center; gap: var(--space-3); padding: var(--space-3) var(--space-4); border: 1px solid var(--primary-100, #dbeafe); border-radius: var(--radius-md, 8px); background: linear-gradient(100deg, var(--primary-50, #eff6ff), var(--card, #fff) 68%); }
.gsd-summary__identity { display: flex; align-items: center; gap: var(--space-3); min-width: 0; }
.gsd-summary__avatar { display: grid; place-items: center; width: 38px; height: 38px; flex: 0 0 auto; border-radius: var(--radius-full); background: var(--primary-100, #dbeafe); color: var(--primary-700, #1d4ed8); font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); }
.gsd-summary__identity strong, .gsd-summary__identity span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gsd-summary__identity strong { color: var(--text-primary); font-size: var(--font-size-md); }
.gsd-summary__identity span { margin-top: 2px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.gsd-summary__item { display: grid; gap: 4px; min-width: 0; }
.gsd-summary__item > span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.gsd-summary__item b { overflow: hidden; color: var(--text-primary); font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); text-overflow: ellipsis; white-space: nowrap; }
.gsd-summary__item b.is-danger { color: var(--danger, #dc2626); }
.gsd-tabs { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: thin; }
.gsd-tabs .mp-tab { flex: 0 0 auto; white-space: nowrap; }
@media (max-width: 1050px) { .gsd-summary { grid-template-columns: minmax(220px, 1.5fr) repeat(2, minmax(130px, 1fr)); } }
@media (max-width: 680px) { .gsd-summary { grid-template-columns: 1fr 1fr; } .gsd-summary__identity { grid-column: 1 / -1; } }
</style>
