<template>
  <ModulePageShell
    class="tw-shell"
    title="我的毕设工作"
    :subtitle="subtitle"
    :role-name="ctx.currentRole?.roleName"
    :data-scope-name="ctx.dataScope?.scopeName"
  >
    <template #summary>
      <div class="tw-summary">
        <div class="tw-ids" aria-label="我的毕设身份">
          <span v-for="label in data.identityLabels" :key="label" class="tw-id">{{ label }}</span>
          <span v-if="!data.identityLabels.length && !loading" class="tw-id tw-id--muted">暂无毕设身份</span>
        </div>
        <div class="tw-kpis">
          <span class="tw-kpi" :class="{ 'is-warn': data.todoTotal > 0 }"><b>{{ data.todoTotal }}</b>件待处理</span>
          <span v-if="hasMentor" class="tw-kpi"><b>{{ data.studentTotal }}</b>名指导学生</span>
          <span v-if="data.groups.length" class="tw-kpi"><b>{{ data.groups.length }}</b>个答辩组</span>
        </div>
      </div>
    </template>
    <template #actions>
      <AppButton :disabled="loading" @click="load">刷新</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" text="正在汇总你的毕设工作…" />
    <EmptyState
      v-else-if="!hasBatch"
      title="还没有可用的毕业设计批次"
      description="学校开启毕业设计批次后，这里会自动出现你要做的事。"
    />
    <EmptyState v-else-if="!data.identities.length" title="你目前没有毕业设计工作" :description="data.message" />

    <div v-else class="mp-stack tw-page">
      <section class="tw-today" :class="{ 'is-clear': !activeTasks.length }" aria-label="今天要处理">
        <header class="tw-today__head">
          <div v-if="activeTasks.length">
            <h2>今天要处理 <strong>{{ data.todoTotal }}</strong> 件事</h2>
            <p>按毕业设计先后顺序排好了，从上往下做即可。处理完会自动回到这里。</p>
          </div>
          <div v-else>
            <h2>✓ 现在没有要你处理的事</h2>
            <p>学生提交材料、学校分配评阅或答辩后，会自动出现在这里。</p>
          </div>
        </header>

        <ol v-if="activeTasks.length" class="tw-tasks">
          <li v-for="task in activeTasks" :key="task.key" class="tw-task">
            <div class="tw-task__head">
              <span class="tw-task__no">{{ stepNo(task) }}</span>
              <div class="tw-task__title">
                <strong>{{ task.title }}</strong>
                <span class="tw-tag">{{ task.identityLabel }}</span>
                <small>{{ task.hint }}</small>
              </div>
              <b class="tw-task__count" :aria-label="`${task.count} 件`">{{ task.count }}</b>
              <AppButton
                v-if="task.action !== 'topic.choice' && task.items.length"
               
                variant="primary"
                @click="go(task, task.items[0])"
              >{{ startLabel(task) }} →</AppButton>
            </div>
            <ul class="tw-items">
              <li v-for="item in visibleItems(task)" :key="`${task.key}-${item.id || item.gdStudentId}`" class="tw-item">
                <div class="tw-item__who">
                  <strong>{{ item.studentName }}</strong>
                  <small>{{ [item.className, item.studentNo].filter(Boolean).join(' · ') }}</small>
                </div>
                <div class="tw-item__what">
                  <span>{{ item.topicTitle || '（未定题）' }}</span>
                  <small v-if="item.groupName">{{ item.groupName }} · {{ item.defenseDate ? String(item.defenseDate).replace('T', ' ') : '时间待定' }} · {{ item.location || '地点待定' }}</small>
                  <small v-else-if="item.note">理由：{{ item.note }}</small>
                </div>
                <span class="tw-item__status">{{ item.statusLabel }}</span>
                <span class="tw-item__time">{{ shortTime(item.submittedAt) }}</span>
                <div v-if="task.action === 'topic.choice'" class="tw-item__ops">
                  <template v-if="rejecting === item.id">
                    <input v-model.trim="rejectReason" class="tw-input" maxlength="200" placeholder="驳回理由（学生能看到）" aria-label="驳回理由" />
                    <button type="button" class="mp-link mp-link--danger" :disabled="busy" @click="rejectChoice(item)">确认驳回</button>
                    <button type="button" class="mp-link" :disabled="busy" @click="rejecting = ''">取消</button>
                  </template>
                  <template v-else>
                    <AppButton variant="primary" :disabled="busy" @click="confirmChoice(item)">确认</AppButton>
                    <button type="button" class="mp-link mp-link--danger" :disabled="busy" @click="startReject(item)">驳回</button>
                  </template>
                </div>
                <button v-else type="button" class="mp-link tw-item__go" @click="go(task, item)">{{ itemLabel(task, item) }} →</button>
              </li>
            </ul>
            <button
              v-if="task.items.length > PREVIEW"
              type="button"
              class="mp-link tw-more"
              @click="toggle(task.key)"
            >{{ expanded[task.key] ? '收起' : `展开全部 ${task.items.length} 条` }}</button>
            <p v-if="task.truncated" class="mp-note">只显示前 {{ task.items.length }} 条，点「{{ startLabel(task) }}」进入完整列表继续处理。</p>
          </li>
        </ol>
        <p v-if="idleTasks.length" class="tw-idle">暂时没有待办的环节：{{ idleTasks.map((t) => t.title).join('、') }}</p>
      </section>

      <section v-if="hasMentor" class="mp-card tw-students" aria-label="我指导的学生">
        <div class="mp-card__head">
          <span class="mp-card__title">我指导的学生</span>
          <small>{{ data.studentTotal }} 人</small>
          <input v-model.trim="keyword" class="tw-input tw-search" placeholder="搜姓名、学号、班级或题目" aria-label="搜索我指导的学生" />
        </div>
        <div class="mp-card__body">
          <p v-if="!data.students.length" class="mp-note">这个批次还没有分给你的学生。学校完成导师分配后会自动出现。</p>
          <div v-else class="tw-table-wrap">
            <table class="tw-table">
              <thead><tr><th>学生</th><th>题目</th><th>当前阶段</th><th>最近指导</th><th aria-label="操作" /></tr></thead>
              <tbody>
                <tr v-for="s in filteredStudents" :key="s.gdStudentId">
                  <td><strong>{{ s.studentName }}</strong><small>{{ [s.className, s.studentNo].filter(Boolean).join(' · ') }}</small></td>
                  <td>{{ s.topicTitle || '（未定题）' }}</td>
                  <td><span class="tw-stage" :class="{ 'is-risk': s.riskLevel && s.riskLevel !== 'NONE' }">{{ s.stageLabel }}</span></td>
                  <td>{{ s.lastGuidanceAt ? shortTime(s.lastGuidanceAt) : '还没有记录' }}</td>
                  <td class="tw-table__ops">
                    <button type="button" class="mp-link" @click="goGuidance(s)">记指导</button>
                    <button type="button" class="mp-link" @click="goStudent(s)">详情</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <p v-if="data.studentTotal > data.students.length" class="mp-note">只列出前 {{ data.students.length }} 人，可用上方搜索或到「过程指导台」查找。</p>
          </div>
        </div>
      </section>

      <section v-if="data.groups.length" class="mp-card" aria-label="我的答辩组">
        <div class="mp-card__head"><span class="mp-card__title">我的答辩组</span></div>
        <div class="mp-card__body tw-groups">
          <article v-for="g in data.groups" :key="g.id" class="tw-group">
            <strong>{{ g.groupName }}</strong>
            <span class="tw-tag" v-for="r in g.myRoles" :key="r">我是{{ r }}</span>
            <p>{{ g.defenseDate ? String(g.defenseDate).replace('T', ' ') : '时间待定' }} · {{ g.location || '地点待定' }} · 学生 {{ g.studentCount }} 人 · 评委 {{ g.judgeCount }} 人</p>
            <small v-if="!g.published">学校还没有发布这个答辩组，发布后才能评分。</small>
            <small v-else-if="g.myRoles.includes('秘书')">可确认成绩：{{ g.confirmable }} 人</small>
            <small v-else>我已评分：{{ g.scoredByMe }} / {{ g.studentCount }}</small>
          </article>
        </div>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { gdTopicRoundApi } from '@/modules/graduation/api/graduation-topic-round.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'

const EMPTY = () => ({
  identities: [], identityLabels: [], tasks: [], todoTotal: 0,
  students: [], studentTotal: 0, groups: [], message: ''
})
const START_LABELS = {
  'topic.change': '去审核', 'taskbook.issue': '去下达', 'proposal.review': '开始批阅',
  'midterm.check': '开始检查', 'final.review': '开始批阅', 'advisor.score': '开始打分', 'review.submit': '开始评阅',
  'defense.score': '开始评分', 'defense.confirm': '去确认'
}
const PREVIEW = 5

export default {
  name: 'TeacherWorkbenchView',
  components: { AppButton, ModulePageShell, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(), loading: true, error: '', data: EMPTY(),
      expanded: {}, keyword: '', busy: false, rejecting: '', rejectReason: '', loadToken: 0, PREVIEW
    }
  },
  computed: {
    hasBatch() { return !!this.batchStore.selectedBatchId },
    hasMentor() { return this.data.identities.includes('GD_MENTOR') },
    subtitle() {
      const name = this.batchStore.selectedBatchName || '当前批次'
      return this.data.identityLabels.length ? `${name} · 你是${this.data.identityLabels.join('、')}` : name
    },
    activeTasks() { return this.data.tasks.filter((task) => task.count > 0) },
    idleTasks() { return this.data.tasks.filter((task) => !task.count) },
    filteredStudents() {
      const kw = this.keyword.toLowerCase()
      if (!kw) return this.data.students
      return this.data.students.filter((s) => [s.studentName, s.studentNo, s.className, s.topicTitle]
        .some((v) => String(v || '').toLowerCase().includes(kw)))
    }
  },
  watch: { 'batchStore.selectedBatchId'() { this.load() } },
  created() { this.load() },
  methods: {
    async load() {
      const token = ++this.loadToken
      this.error = ''
      if (!this.hasBatch) { this.loading = false; this.data = EMPTY(); return }
      this.loading = true
      try {
        const res = await graduationApi.getTeacherWorkbench({ batchId: this.batchStore.selectedBatchId })
        if (token !== this.loadToken) return
        if (res.code === 0) this.data = { ...EMPTY(), ...(res.data || {}) }
        else if (res.code === 403 || /权限|NO_PERMISSION/.test(String(res.message || ''))) {
          this.data = { ...EMPTY(), message: '你的账号还没有对应的毕业设计导师台账。学校把你加入导师名单（工号与登录账号一致）后，这里会自动出现你的毕设工作。' }
        } else this.error = res.message || '我的毕设工作加载失败，请稍后重试。'
      } catch (error) {
        if (token === this.loadToken) this.error = error?.message || '我的毕设工作加载失败，请检查网络后重试。'
      } finally {
        if (token === this.loadToken) this.loading = false
      }
    },
    stepNo(task) { return this.data.tasks.findIndex((t) => t.key === task.key) + 1 },
    startLabel(task) { return START_LABELS[task.action] || '去处理' },
    itemLabel(task, item) {
      if (task.action === 'midterm.check') return item.status === 'RECTIFY_SUBMITTED' ? '复核整改' : '检查'
      if (task.action === 'proposal.review' || task.action === 'final.review') return '批阅'
      if (task.action === 'defense.score') return '评分'
    if (task.action === 'advisor.score') return '打分'
      if (task.action === 'defense.confirm') return '确认'
      if (task.action === 'taskbook.issue') return '下达'
      if (task.action === 'review.submit') return '评阅'
      return '处理'
    },
    visibleItems(task) { return this.expanded[task.key] ? task.items : task.items.slice(0, PREVIEW) },
    toggle(key) { this.expanded = { ...this.expanded, [key]: !this.expanded[key] } },
    shortTime(value) {
      if (!value) return ''
      const text = String(value).replace('T', ' ')
      return text.length > 16 ? text.slice(0, 16) : text
    },
    batchQuery(extra = {}) {
      const batchId = this.batchStore.selectedBatchId
      return { ...(batchId ? { batchId: String(batchId) } : {}), ...extra }
    },
    returnTo() { return this.$route?.fullPath || '/admin/graduation/my-work' },
    targetOf(task, item) {
      const sid = String(item?.gdStudentId || '')
      const back = { returnTo: this.returnTo(), source: 'workbench' }
      switch (task.action) {
        case 'topic.change': return { path: `/admin/graduation/topic-changes/${item.id}`, query: this.batchQuery() }
        case 'taskbook.issue': return { path: `/admin/graduation/process/${sid}/taskbook`, query: this.batchQuery({ panel: 'taskbook', studentId: sid, ...back }) }
        case 'proposal.review': return { path: '/admin/graduation/proposals', query: this.batchQuery({ tab: 'PENDING_REVIEW', sel: item.id }) }
        case 'advisor.score': return { path: '/admin/graduation/advisor-score', query: this.batchQuery({ studentId: item.gdStudentId }) }
    case 'final.review': return { path: '/admin/graduation/finals', query: this.batchQuery({ tab: 'PENDING_REVIEW', sel: item.id }) }
        case 'midterm.check':
          if (item.status === 'RECTIFY_SUBMITTED') return { path: '/admin/graduation/process', query: this.batchQuery({ panel: 'midterm', studentId: sid, source: 'workbench' }) }
          return { path: `/admin/graduation/process/${sid}/midterm`, query: this.batchQuery({ panel: 'midterm', studentId: sid, ...back }) }
        case 'review.submit': return { path: '/admin/graduation/review-tasks', query: this.batchQuery({ caseType: 'FORMAL_REVIEW', reviewerOnly: '1' }) }
        case 'defense.score': return { path: '/admin/graduation/defense-scoring', query: this.batchQuery({ studentId: sid, ...back }) }
        case 'defense.confirm': return { path: '/admin/graduation/defense-confirmation', query: this.batchQuery({ studentId: sid, ...back }) }
        default: return null
      }
    },
    go(task, item) {
      const target = this.targetOf(task, item)
      if (target) this.$router.push(target).catch(() => {})
    },
    goGuidance(s) {
      this.$router.push({ path: `/admin/graduation/process/${s.gdStudentId}/guidance`, query: this.batchQuery({ panel: 'guidance', studentId: s.gdStudentId, returnTo: this.returnTo() }) }).catch(() => {})
    },
    goStudent(s) { this.$router.push({ path: `/admin/graduation/students/${s.gdStudentId}`, query: this.batchQuery() }).catch(() => {}) },
    startReject(item) { this.rejecting = item.id; this.rejectReason = '' },
    async confirmChoice(item) {
      if (this.busy) return
      this.busy = true
      try {
        const res = await gdTopicRoundApi.confirmChoice(item.id)
        if (res.code !== 0) { toast.error(res.message || '确认失败，请刷新后重试'); return }
        toast.success(`已确认 ${item.studentName} 的选题`)
        await this.load()
      } finally { this.busy = false }
    },
    async rejectChoice(item) {
      if (this.busy) return
      if (!this.rejectReason) { toast.error('请填写驳回理由，学生会看到'); return }
      this.busy = true
      try {
        const res = await gdTopicRoundApi.rejectChoice(item.id, this.rejectReason)
        if (res.code !== 0) { toast.error(res.message || '驳回失败，请刷新后重试'); return }
        toast.success(`已驳回 ${item.studentName} 的志愿`)
        this.rejecting = ''
        await this.load()
      } finally { this.busy = false }
    }
  }
}
</script>

<style scoped>
.tw-summary { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2, 8px) var(--space-4, 16px); }
.tw-ids, .tw-kpis { display: flex; flex-wrap: wrap; gap: 6px; }
.tw-id { padding: 3px 10px; border-radius: 999px; background: var(--primary-50, #eff6ff); color: var(--primary-700, #1d4ed8); font-size: 12px; font-weight: 600; }
.tw-id--muted { background: var(--gray-100, #f1f5f9); color: var(--text-tertiary, #64748b); }
.tw-kpi { display: inline-flex; align-items: baseline; gap: 4px; padding: 4px 10px; border: 1px solid var(--border-light, #e2e8f0); border-radius: 8px; background: var(--card, #fff); color: var(--text-tertiary, #64748b); font-size: 12px; }
.tw-kpi b { color: var(--text-primary, #0f172a); font-size: 16px; font-variant-numeric: tabular-nums; }
.tw-kpi.is-warn b { color: var(--warning-600, #d97706); }

.tw-today { padding: var(--space-4, 16px); border: 1px solid var(--primary-100, #dbeafe); border-radius: 12px; background: var(--primary-50, #eff6ff); }
.tw-today.is-clear { background: var(--card, #fff); border-color: var(--border-light, #e2e8f0); }
.tw-today__head h2 { margin: 0; font-size: 18px; font-weight: 600; }
.tw-today__head h2 strong { color: var(--primary-700, #1d4ed8); font-size: 24px; margin: 0 2px; font-variant-numeric: tabular-nums; }
.tw-today__head p { margin: 4px 0 0; color: var(--text-tertiary, #64748b); }
.tw-tasks { list-style: none; margin: var(--space-3, 12px) 0 0; padding: 0; display: grid; gap: var(--space-3, 12px); }
.tw-task { padding: var(--space-3, 12px) var(--space-4, 16px); border: 1px solid var(--border-light, #e2e8f0); border-radius: 10px; background: var(--card, #fff); }
.tw-task__head { display: grid; grid-template-columns: 28px minmax(0, 1fr) auto auto; gap: var(--space-3, 12px); align-items: center; }
.tw-task__no { width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; background: var(--primary-600, #2563eb); color: #fff; font-weight: 700; font-size: 13px; }
.tw-task__title { min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
.tw-task__title strong { font-size: 15px; }
.tw-task__title small { flex-basis: 100%; color: var(--text-tertiary, #64748b); }
.tw-task__count { min-width: 34px; text-align: center; font-size: 20px; color: var(--primary-700, #1d4ed8); font-variant-numeric: tabular-nums; }
.tw-tag { padding: 1px 8px; border-radius: 4px; background: var(--gray-100, #f1f5f9); color: var(--text-secondary, #475569); font-size: 12px; }
.tw-items { list-style: none; margin: var(--space-2, 8px) 0 0; padding: 0; }
.tw-item { display: grid; grid-template-columns: minmax(120px, 1fr) minmax(0, 2fr) auto auto auto; gap: var(--space-3, 12px); align-items: center; padding: 8px 0; border-top: 1px solid var(--border-light, #e2e8f0); }
.tw-item__who strong, .tw-item__what span { display: block; overflow-wrap: anywhere; }
.tw-item__who small, .tw-item__what small { display: block; color: var(--text-tertiary, #64748b); font-size: 12px; }
.tw-item__status { font-size: 12px; color: var(--warning-700, #b45309); white-space: nowrap; }
.tw-item__time { font-size: 12px; color: var(--text-tertiary, #64748b); white-space: nowrap; font-variant-numeric: tabular-nums; }
.tw-item__ops { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; justify-content: flex-end; }
.tw-item__go { white-space: nowrap; }
.tw-more { margin-top: 6px; }
.tw-idle { margin: var(--space-3, 12px) 0 0; color: var(--text-tertiary, #64748b); font-size: 12px; }
.tw-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-light, #e2e8f0); border-radius: 6px; background: var(--card, #fff); color: inherit; font: inherit; min-width: 0; }
.tw-students .mp-card__head { display: flex; align-items: center; gap: var(--space-2, 8px); flex-wrap: wrap; }
.tw-search { margin-left: auto; width: 240px; max-width: 100%; }
.tw-table-wrap { overflow-x: auto; }
.tw-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.tw-table th, .tw-table td { padding: 9px 10px; border-bottom: 1px solid var(--border-light, #e2e8f0); text-align: left; vertical-align: middle; }
.tw-table th { color: var(--text-tertiary, #64748b); font-weight: 600; background: var(--gray-50, #f8fafc); white-space: nowrap; }
.tw-table td small { display: block; color: var(--text-tertiary, #64748b); font-size: 12px; }
.tw-table__ops { white-space: nowrap; text-align: right; }
.tw-table__ops .mp-link + .mp-link { margin-left: 10px; }
.tw-stage { padding: 2px 8px; border-radius: 4px; background: var(--primary-50, #eff6ff); color: var(--primary-700, #1d4ed8); font-size: 12px; white-space: nowrap; }
.tw-stage.is-risk { background: var(--warning-50, #fffbeb); color: var(--warning-700, #b45309); }
.tw-groups { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: var(--space-3, 12px); }
.tw-group { padding: var(--space-3, 12px); border: 1px solid var(--border-light, #e2e8f0); border-radius: 10px; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.tw-group p { flex-basis: 100%; margin: 2px 0 0; color: var(--text-secondary, #475569); }
.tw-group small { flex-basis: 100%; color: var(--text-tertiary, #64748b); }
@media (max-width: 760px) {
  .tw-task__head { grid-template-columns: 28px minmax(0, 1fr) auto; }
  .tw-task__head .mp-btn { grid-column: 1 / -1; justify-self: start; }
  .tw-item { grid-template-columns: minmax(0, 1fr) auto; }
  .tw-item__what, .tw-item__time { grid-column: 1 / -1; }
  .tw-search { width: 100%; margin-left: 0; }
}
</style>
