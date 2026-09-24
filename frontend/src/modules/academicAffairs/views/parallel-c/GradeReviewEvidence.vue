<template>
  <section class="grade-evidence">
    <header v-if="!compact">
      <div><h3>{{ task.courseName }}</h3><p>{{ task.termCode }} · 任务 {{ task.gradeTaskId }}</p></div>
      <strong>{{ statusLabel(task.status) }}</strong>
    </header>
    <ol v-if="!compact">
      <li :aria-current="task.status === 'RETURNED' ? 'step' : undefined">{{ task.status === 'RETURNED' ? '任课教师修改重提' : '提交冻结名单' }}</li>
      <li :aria-current="['SUBMITTED', 'COLLEGE_REVIEW'].includes(task.status) ? 'step' : undefined">学院审核</li>
      <li :aria-current="task.status === 'ACADEMIC_REVIEW' ? 'step' : undefined">教务发布</li>
      <li>后置扫描</li><li>更正留痕</li>
    </ol>

    <div class="grade-evidence__title">
      <div><h3>审核证据与新鲜度</h3><p>请核对正式名单、成绩完整性与审核阻断；提交时将再次核验证据。</p></div>
      <span :class="['grade-evidence__state', { 'is-ready': evidenceReady }]">{{ evidenceReady ? '证据可确认' : '证据待核验' }}</span>
    </div>
    <p v-if="loading" class="note">正在读取正式审核证据…</p>
    <p v-else-if="error" class="note note--danger">{{ error }}</p>
    <template v-else-if="evidence">
      <div class="grade-evidence__counts" aria-label="成绩完整性计数">
        <div v-for="item in countItems" :key="item.key"><small>{{ item.label }}</small><strong>{{ fact(item.value) }}</strong></div>
      </div>
      <table>
        <thead><tr><th>核验对象</th><th>当前正式事实</th><th>来源 / 核验结果</th></tr></thead>
        <tbody>
          <tr><th>课程与任务</th><td>{{ task.courseId || '未关联课程' }} · {{ evidence.gradeTaskId || '未提供任务 ID' }}</td><td>{{ statusLabel(evidence.status) }}</td></tr>
          <tr><th>正式教学班</th><td>{{ task.teachingClassId || '未提供' }}</td><td>{{ task.teacherNames?.filter(Boolean).join('、') || '任课教师姓名未提供' }}</td></tr>
          <tr><th>提交冻结名单</th><td>第 {{ fact(roster.snapshotVersion) }} 版快照</td><td>{{ businessLabel(roster.source) }} · {{ roster.current === true ? '当前有效' : roster.current === false ? '已不是当前版本' : '有效性待核验' }}</td></tr>
          <tr><th>正式名单版本</th><td>第 {{ fact(roster.rosterVersionNo) }} 版 · {{ fact(roster.memberCount) }} 人</td><td>{{ roster.rosterHash ? '已取得正式名单校验摘要' : '校验摘要未提供' }}</td></tr>
          <tr><th>异常标记</th><td colspan="2"><span v-for="item in exceptionItems" :key="item.key" class="grade-evidence__chip">{{ item.label }} {{ fact(item.value) }}</span></td></tr>
          <tr><th>计分方案</th><td>{{ schemeLabel }}<span v-if="scheme.version"> · 第 {{ scheme.version }} 版</span></td><td>{{ businessLabel(scheme.status) }}</td></tr>
          <tr><th>方案分项</th><td colspan="2"><span v-if="!schemeComponents.length">分项未提供</span><span v-for="item in schemeComponents" :key="item.code" class="grade-evidence__chip">{{ item.name || item.code || '未命名分项' }} {{ fact(item.weight) }}%</span></td></tr>
          <tr><th>成绩策略</th><td>{{ businessLabel(policy.policyCode) }} · 第 {{ fact(policy.policyVersion) }} 版</td><td>{{ businessLabel(policy.attemptStrategy) }}</td></tr>
          <tr><th>审核责任节点</th><td>{{ businessLabel(workflow.currentNode) }}</td><td>{{ workflow.assigneeId ? '已指派办理人，身份由服务端核验' : '具体办理人未提供' }}</td></tr>
          <tr><th>证据检查</th><td>{{ evidence.evidenceHash ? '已取得正式校验摘要' : '校验摘要未提供' }}</td><td>{{ evidence.checkedAt ? '检查于 ' + evidence.checkedAt.replace('T', ' ') : '检查时间未提供' }}</td></tr>
        </tbody>
      </table>
      <section class="grade-evidence__blockers" aria-label="审核阻断项">
        <h4>审核阻断</h4>
        <p v-if="!blockersProvided" class="note--danger">阻断清单未提供</p>
        <p v-else-if="!blockers.length" class="grade-evidence__pass">未发现阻断项</p>
        <ul v-else><li v-for="(item, index) in blockers" :key="`${item.code || 'BLOCKER'}-${index}`"><strong>需处理 {{ index + 1 }}</strong><span>{{ item.message || '服务端未提供具体说明' }}</span></li></ul>
      </section>
      <p class="note">当前可办理：{{ allowedActions.length ? allowedActions.map(businessLabel).join('、') : '暂无可用动作' }}。提交时再次核验正式事实。</p>
      <details class="note"><summary>实施人员使用：校验编号与摘要</summary><p>名单快照 {{ fact(roster.snapshotId) }} · 名单版本 {{ fact(roster.rosterVersionId) }}</p><p class="mono">名单摘要：{{ roster.rosterHash || '未提供' }}</p><p class="mono">证据摘要：{{ evidence.evidenceHash || '未提供' }}</p></details>
    </template>
    <p v-else class="note note--danger">正式审核证据未返回，不能执行通过；仍可按原权限退回教师修改。</p>
    <p v-if="task.returnReason" class="note">退回意见：{{ task.returnReason }}</p>
    <footer><slot /></footer>
  </section>
</template>

<script>
import { gradeStatusLabel } from './grade-review.js'

const COUNT_LABELS = [
  ['expected', '应录'], ['entered', '已录'], ['missing', '缺失'],
  ['outside', '名单外'], ['incomplete', '未完整'], ['duplicates', '重复']
]
const EXCEPTION_LABELS = [
  ['NORMAL', '正常'], ['ABSENT', '缺考'], ['EXEMPT', '免修'], ['CHEAT', '作弊'], ['DEFERRED', '缓考']
]

export default {
  name: 'GradeReviewEvidence',
  props: {
    task: { type: Object, required: true },
    compact: { type: Boolean, default: false },
    evidence: { type: Object, default: null },
    loading: { type: Boolean, default: false },
    error: { type: String, default: '' }
  },
  computed: {
    roster() { return this.evidence?.roster || {} },
    scheme() { return this.evidence?.scheme || {} },
    policy() { return this.evidence?.policy || {} },
    workflow() { return this.evidence?.workflow || {} },
    blockersProvided() { return Array.isArray(this.evidence?.blockers) },
    blockers() { return Array.isArray(this.evidence?.blockers) ? this.evidence.blockers : [] },
    allowedActions() { return Array.isArray(this.evidence?.allowedActions) ? this.evidence.allowedActions : [] },
    schemeComponents() { return Array.isArray(this.scheme.components) ? this.scheme.components : [] },
    schemeLabel() { return this.scheme.mode === 'DYNAMIC' ? '动态分项' : this.scheme.mode === 'FIXED' ? '固定分项' : '方案类型未提供' },
    countItems() { const counts = this.evidence?.counts || {}; return COUNT_LABELS.map(([key, label]) => ({ key, label, value: counts[key] })) },
    exceptionItems() { const values = this.evidence?.exceptions || {}; return EXCEPTION_LABELS.map(([key, label]) => ({ key, label, value: values[key] })) },
    evidenceReady() {
      return !!this.evidence?.evidenceHash && this.blockersProvided && this.blockers.length === 0 && this.allowedActions.includes('APPROVE')
    }
  },
  methods: {
    statusLabel: gradeStatusLabel,
    businessLabel(value) {
      return ({ ADMIN_CLASS: '行政班正式名单', TEACHING_CLASS: '教学班正式名单', SELECTION: '选课正式名单', TASK_RATIOS: '按任务固定比例计分', DEFAULT: '默认方案', DRAFT: '草稿', LOCKED: '已锁定', ACTIVE: '已启用', LATEST_FORMAL_SOURCE_V1: '最新正式成绩来源', LEGACY_LATEST_ATTEMPT_V1: '历史最近修读规则', LATEST_ATTEMPT: '采用最近一次修读', HIGHEST_SCORE: '采用最高成绩', HIGHEST_PASSED: '采用最高及格成绩', LATEST_PASSED: '采用最近一次及格成绩', COLLEGE_REVIEW: '学院成绩审核', ACADEMIC_REVIEW: '教务成绩审核', RETURN: '退回教师修改', APPROVE: '审核通过', PUBLISH: '正式发布' })[value] || '具体规则待核对'
    },
    fact(value) { return value === null || value === undefined || value === '' ? '未提供' : value }
  }
}
</script>

<style scoped>
.grade-evidence { background: var(--bg-card); border: 1px solid var(--border-base); border-radius: 10px; overflow: hidden; }
header, .grade-evidence__title { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; padding: 18px; }
header { border-left: 3px solid var(--pri); } h3, h4 { font-size: 15px; margin: 0; }
header p, .grade-evidence__title p, .note { font-size: 12px; color: var(--text-secondary); line-height: 1.7; }
header p, .grade-evidence__title p { margin: 4px 0 0; } .note { margin: 14px 16px; } header strong { font-size: 12px; color: var(--pri); }
ol { list-style: decimal inside; display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; font-size: 12px; padding: 16px; margin: 0; background: var(--pri-bg); } li[aria-current] { color: var(--pri); font-weight: 600; }
.grade-evidence__title { border-bottom: 1px solid var(--border-base); }
.grade-evidence__state { padding: 4px 9px; border-radius: 999px; color: var(--text-secondary); background: var(--bg-muted, #f2f4f7); font-size: 12px; white-space: nowrap; }.grade-evidence__state.is-ready { color: #087443; background: #ecfdf3; }
.grade-evidence__counts { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 1px; background: var(--border-base); border-bottom: 1px solid var(--border-base); }.grade-evidence__counts div { padding: 12px; background: var(--bg-card); }.grade-evidence__counts small, .grade-evidence__counts strong { display: block; }.grade-evidence__counts small { color: var(--text-secondary); font-size: 11px; }.grade-evidence__counts strong { margin-top: 5px; font-size: 16px; }
table { width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 12px; } th, td { text-align: left; padding: 13px; border-top: 1px solid var(--border-base); overflow-wrap: anywhere; } thead { background: var(--pri-bg); }.mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 11px; }
.grade-evidence__chip { display: inline-block; margin: 2px 8px 2px 0; padding: 3px 7px; border-radius: 999px; background: var(--pri-bg); }
.grade-evidence__blockers { margin: 14px 16px; padding: 13px; border: 1px solid var(--border-base); border-radius: 8px; }.grade-evidence__blockers ul { margin: 10px 0 0; padding-left: 18px; }.grade-evidence__blockers li { margin-top: 7px; }.grade-evidence__blockers li strong { margin-right: 8px; }.grade-evidence__pass { margin: 8px 0 0; color: #087443; }.note--danger { color: var(--danger, #b42318); }
footer { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; padding: 16px; border-top: 1px solid var(--border-base); }
@media (max-width: 900px) { .grade-evidence__counts { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
</style>
