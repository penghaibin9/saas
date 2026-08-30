<template>
  <ModulePageShell
    :title="titleMap[tab] || '毕业设计扩展事项'"
    :subtitle="subtitleMap[tab] || '仅展示当前角色有权处理的事项'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbar" @action="onToolbar" />
    </template>

    <div class="gm-tabs">
      <button
        v-for="t in visibleTabs"
        :key="t.key"
        class="gm-tabs__item"
        :class="{ 'is-active': tab === t.key }"
        @click="switchTab(t.key)"
      >{{ t.label }}</button>
    </div>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />

    <!-- 成果互查整改 -->
    <div v-else-if="tab === 'peer'" class="mp-stack">
      <EmptyState
        v-if="!rows.length"
        title="还没有互查记录"
        description="成果互查是让学生之间互相查论文、再据此整改。这一步不是必做的——学校要求做才做。"
      >
        <template v-if="canPeerAssign" #actions>
          <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/graduation/more/peer-assign')">分配互查</button>
        </template>
      </EmptyState>
      <DataTable v-else :columns="peerCols" :rows="rows" row-key="id">
        <template #cell-pair="{ row }"><div class="mp-cell-main">{{ row.reviewerName }} 查 {{ row.studentName }}</div><div class="mp-cell-sub">{{ row.opinion || '（待互查）' }}{{ row.rectifyNote ? ' · 整改：' + row.rectifyNote : '' }}</div></template>
        <template #cell-status="{ row }"><StatusTag :type="row.status === 'RECTIFIED' ? 'success' : row.status === 'REVIEWED' ? 'warning' : 'default'" :label="row.statusLabel" dot /></template>
      </DataTable>
    </div>

    <!-- 答辩专家库 -->
    <div v-else-if="tab === 'experts'" class="mp-stack">
      <EmptyState
        v-if="!rows.length"
        title="还没有答辩专家"
        description="把评委先录进专家库，之后每次排答辩直接从库里挑，不用重复录入。校外专家可以标记，需要回避的也能在这里记上。"
      >
        <template v-if="canManageExperts" #actions>
          <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/graduation/more/expert/create')">＋ 新增专家</button>
        </template>
      </EmptyState>
      <DataTable v-else :columns="expertCols" :rows="rows" row-key="id">
        <template #cell-expert="{ row }"><div class="mp-cell-main">{{ row.expertName }} <StatusTag v-if="row.isExternal" type="info" label="校外" /></div><div class="mp-cell-sub">{{ row.title || '—' }} · {{ row.collegeName || '—' }}{{ row.avoidNote ? ' · 回避：' + row.avoidNote : '' }}</div></template>
        <template #cell-status="{ row }"><StatusTag :type="row.status === 'ACTIVE' ? 'success' : 'default'" :label="row.statusLabel" dot /></template>
        <template #cell-actions="{ row }"><button v-if="canManageExperts" class="mp-link" @click="toggleExpert(row)">{{ row.status === 'ACTIVE' ? '停用' : '启用' }}</button></template>
      </DataTable>
    </div>

    <!-- 成绩更正申诉 -->
    <div v-else-if="tab === 'appeals'" class="mp-stack">
      <div class="mp-tabs">
        <button v-for="s in appealTabs" :key="s.value" class="mp-tab" :class="{ 'is-active': appealStatus === s.value }" @click="appealStatus = s.value; load()">{{ s.label }}</button>
      </div>
      <EmptyState v-if="!rows.length" title="暂无成绩申诉" description="学生对已发布成绩发起申诉后在此复核" />
      <DataTable v-else :columns="appealCols" :rows="rows" row-key="id">
        <template #cell-student="{ row }">
          <article class="ga-card">
            <header><strong>{{ row.studentName }}</strong><span>{{ row.studentNo }}</span></header>
            <div v-if="row.appealedGrade" class="ga-score">
              <b>申诉对象：{{ formatPublishedAt(row.appealedGrade.publishedAt) }}发布的第 {{ row.appealedGrade.gradeVersion }} 版成绩</b>
              <span>综合 {{ score(row.appealedGrade.totalScore) }} · 导师 {{ score(row.appealedGrade.advisorScore) }} / 评阅 {{ score(row.appealedGrade.reviewerScore) }} / 答辩 {{ score(row.appealedGrade.defenseScore) }}</span>
            </div>
            <div v-else class="ga-warning">该历史申诉缺少成绩版本快照，不能继续处理。</div>
            <p><b>学生理由：</b>{{ row.reason }}</p>
            <div :class="row.versionMatches ? 'ga-match' : 'ga-warning'">{{ row.versionMessage }}</div>
            <button v-if="!row.versionMatches" class="mp-link" @click="openCurrentGrade(row)">查看当前成绩 →</button>
            <details v-if="row.appealedGrade"><summary>版本校验证据</summary>申诉版本 {{ row.appealedGrade.gradeVersion }} · 当前版本 {{ row.currentGrade?.gradeVersion || '—' }}</details>
          </article>
        </template>
        <template #cell-status="{ row }"><StatusTag :type="row.status === 'APPROVED' ? 'success' : row.status === 'REJECTED' ? 'danger' : 'warning'" :label="row.statusLabel" dot /></template>
        <template #cell-actions="{ row }">
          <template v-if="row.status === 'PENDING'">
            <AppPermissionButton
              :allowed="canReviewAppeal && row.versionMatches"
              :reason="row.versionMatches ? reviewAppealReason : row.versionMessage"
              variant="ghost"
              @click="askAppeal(row, 'APPROVE')"
            >受理</AppPermissionButton>
            <AppPermissionButton
              :allowed="canReviewAppeal && row.versionMatches"
              :reason="row.versionMatches ? reviewAppealReason : row.versionMessage"
              variant="ghost"
              danger
              style="margin-left:var(--space-2)"
              @click="askAppeal(row, 'REJECT')"
            >驳回</AppPermissionButton>
          </template>
          <span v-else class="mp-cell-sub">{{ row.reviewComment || '—' }}</span>
        </template>
      </DataTable>
    </div>

    <EmptyState
      v-else
      title="当前角色没有可处理的扩展事项"
      description="请从毕业设计中心选择当前角色已授权的工作区。"
    />

    <AppConfirmDialog v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message" :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason" reason-label="驳回理由" :reason-chips="confirm.reasonChips || []" :submitting="submitting" @confirm="onConfirmAppeal" />
  </ModulePageShell>
</template>

<script>
/** 互查整改 / 答辩专家库 / 成绩更正申诉（/admin/graduation/more?panel=peer|experts|appeals）。 */
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppPermissionButton } from '@/components/common'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'

const APPEAL_REJECT_REASON_CHIPS = [
  '经复核，原评分依据充分，予以维持',
  '复核未发现评分错误或遗漏依据',
  '申诉材料不足以证明评分存在错误'
]

const MORE_TABS = [
  { key: 'peer', label: '成果互查整改', permissionKey: 'graduationDesign.review.view' },
  { key: 'experts', label: '答辩专家库', permissionKey: 'graduationDesign.defense.groupManage' },
  { key: 'appeals', label: '成绩更正申诉', permissionKey: 'graduationDesign.grade.appealReview' }
]

export default {
  name: 'GraduationMoreView',
  components: { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppPermissionButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: '', loading: true, error: '', submitting: false, rows: [],
      appealStatus: '',
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确定', requireReason: false, action: '', row: null },
      titleMap: { peer: '成果互查整改', experts: '答辩专家库', appeals: '成绩更正申诉' },
      subtitleMap: { peer: '学生互评+被评整改闭环', experts: '评委库与回避规则维护', appeals: '学生对已发布成绩申诉→复核（受理即撤回成绩重核）' },
      appealTabs: [{ value: '', label: '全部' }, { value: 'PENDING', label: '待复核' }, { value: 'APPROVED', label: '已受理' }, { value: 'REJECTED', label: '已驳回' }],
      peerCols: [{ key: 'pair', title: '互查关系 / 意见' }, { key: 'status', title: '状态' }],
      expertCols: [{ key: 'expert', title: '专家' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '100px' }],
      appealCols: [{ key: 'student', title: '申诉版本与理由' }, { key: 'status', title: '状态', width: '110px' }, { key: 'actions', title: '操作', width: '200px' }]
    }
  },
  computed: {
    permissionPatterns() {
      return Array.isArray(this.ctx?.permissionPatterns) ? this.ctx.permissionPatterns : []
    },
    visibleTabs() {
      return MORE_TABS.filter((item) => matchPermission(this.permissionPatterns, item.permissionKey))
    },
    canPeerAssign() {
      return matchPermission(this.permissionPatterns, 'graduationDesign.review.assign')
    },
    canManageExperts() {
      return matchPermission(this.permissionPatterns, 'graduationDesign.defense.groupManage')
    },
    canAppealReview() {
      return matchPermission(this.permissionPatterns, 'graduationDesign.grade.appealReview')
    },
    toolbar() {
      if (this.tab === 'peer' && this.canPeerAssign) return [{ key: 'assignPeer', label: '＋ 分配互查', variant: 'primary' }]
      if (this.tab === 'experts' && this.canManageExperts) return [{ key: 'addExpert', label: '＋ 新增专家', variant: 'primary' }]
      return []
    },
    canReviewAppeal() {
      const pa = this.ctx.permissionActions.reviewGradeAppeal || {}
      return this.canAppealReview && pa.allowed !== false && pa.visible !== false
    },
    reviewAppealReason() {
      const pa = this.ctx.permissionActions.reviewGradeAppeal || {}
      return pa.reason || '无成绩申诉复核权限'
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(p) {
        const requested = ['peer', 'experts', 'appeals'].includes(p) ? p : ''
        const fallback = this.visibleTabs[0]?.key || ''
        this.tab = this.isTabAllowed(requested) ? requested : fallback
        this.load()
      }
    }
  },
  methods: {
    isTabAllowed(t) {
      return !!t && this.visibleTabs.some((item) => item.key === t)
    },
    switchTab(t) {
      if (!this.isTabAllowed(t)) return
      this.tab = t
      this.$router.replace({ query: { ...this.$route.query, panel: t } })
    },
    onToolbar(k) {
      if (k === 'assignPeer' && this.canPeerAssign) this.$router.push('/admin/graduation/more/peer-assign')
      if (k === 'addExpert' && this.canManageExperts) this.$router.push('/admin/graduation/more/expert/create')
    },
    async load() {
      if (!this.isTabAllowed(this.tab)) {
        this.loading = false
        this.error = ''
        this.rows = []
        return
      }
      this.loading = true
      this.error = ''
      let res
      if (this.tab === 'peer') res = await graduationMoreApi.getPeerReviews()
      else if (this.tab === 'experts') res = await graduationMoreApi.getExperts()
      else res = await graduationMoreApi.getAppeals(this.appealStatus ? { status: this.appealStatus } : {})
      if (res.code === 0) {
        this.rows = res.data.list
      } else {
        this.rows = []
        this.error = res.message || '加载失败，请重试'
      }
      this.loading = false
    },
    async toggleExpert(row) {
      if (!this.canManageExperts) return toast.error('无答辩专家库维护权限')
      const res = await graduationMoreApi.setExpertStatus(row.id, row.status === 'ACTIVE' ? 'DISABLE' : 'ENABLE')
      if (res.code === 0) this.load(); else toast.error(res.message)
    },
    async askAppeal(row, action) {
      if (!this.canReviewAppeal) return toast.error(this.reviewAppealReason)
      if (!row.versionMatches) return toast.error(row.versionMessage || '成绩版本已变化，请查看当前成绩')
      this.confirm = action === 'APPROVE'
        ? { visible: true, title: '受理申诉', message: `受理「${row.studentName}」的成绩申诉？受理后将撤回其成绩，走重新核算。`, type: 'primary', confirmText: '受理', requireReason: false, action: 'APPROVE', row }
        : {
          visible: true, title: '驳回申诉', message: `驳回「${row.studentName}」的申诉，请填写理由（≥5字）。`,
          type: 'danger', confirmText: '驳回', requireReason: true, reasonChips: APPEAL_REJECT_REASON_CHIPS,
          action: 'REJECT', row
        }
    },
    async onConfirmAppeal({ reason } = {}) {
      if (!this.canReviewAppeal) return toast.error(this.reviewAppealReason)
      this.submitting = true
      const res = await graduationMoreApi.reviewAppeal(this.confirm.row.id, this.confirm.action, reason || '')
      this.submitting = false
      if (res.code === 0) { toast.success(this.confirm.action === 'APPROVE' ? '申诉已受理，原成绩已撤回并进入重新核算' : '申诉已驳回，学生端将看到复核理由'); this.confirm.visible = false; this.load() } else toast.error(res.message)
    },
    formatPublishedAt(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '原成绩发布时' },
    score(value) { return value == null ? '—' : Number(value).toFixed(1).replace(/\.0$/, '') },
    openCurrentGrade(row) {
      this.$router.push({ path: '/admin/graduation/grade-ledger', query: { studentId: row.gdStudentId, source: 'grade-appeal' } })
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gm-tabs { display: flex; gap: var(--space-1); margin-bottom: var(--space-3); border-bottom: 1px solid var(--border-base); }
.gm-tabs__item { padding: 8px 16px; font-size: var(--font-size-sm); color: var(--text-secondary); background: none; border: none; border-bottom: 2px solid transparent; cursor: pointer; }
.gm-tabs__item.is-active { color: var(--brand-primary); border-bottom-color: var(--brand-primary); font-weight: var(--font-weight-medium); }
.ga-card{display:grid;gap:7px;min-width:360px}.ga-card header{display:flex;align-items:baseline;gap:8px}.ga-card header span,.ga-card details{color:var(--text-tertiary);font-size:12px}.ga-card p{margin:0;line-height:1.55}.ga-score{display:grid;gap:3px;padding:8px 10px;border-radius:8px;background:var(--gray-50,#f8fafc)}.ga-score span{color:var(--text-secondary);font-size:12px}.ga-match,.ga-warning{padding:6px 8px;border-radius:7px;font-size:12px}.ga-match{color:var(--success-700,#15803d);background:var(--success-50,#f0fdf4)}.ga-warning{color:var(--danger-700,#b91c1c);background:var(--danger-50,#fef2f2)}
</style>
