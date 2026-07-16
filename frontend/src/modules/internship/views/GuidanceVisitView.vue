<template>
  <ModulePageShell title="指导巡访管理" subtitle="记录指导教师联系学生、企业沟通、现场巡访和问题整改情况 · 指导记录 · 教师巡访 · 安全隐患整改跟进"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppPermissionButton code="internship.guidance.manage" :allowed="canBtn('internship.guidance.manage')" variant="primary" @click="goCreate">＋ 新增{{ tab === 'guidance' ? '指导' : '巡访' }}记录</AppPermissionButton>
      <AppButton variant="ghost" @click="$router.push('/admin/internship/guidance-plan')">指导计划</AppButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <div class="mp-stack">
      <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

      <div v-if="statsCards.length" class="stats">
        <div v-for="c in statsCards" :key="c.label" class="stats__card">
          <div class="stats__val" :class="{ 'is-warn': c.warn }">{{ c.value }}</div>
          <div class="stats__lbl">{{ c.label }}</div>
        </div>
      </div>

      <div class="tabs">
        <button v-for="t in tabs" :key="t.key" type="button" class="tabs__btn" :class="{ 'is-active': tab === t.key }" @click="switchTab(t.key)">{{ t.label }}</button>
      </div>

      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
        <AppQuickFilterChips v-if="tab === 'visit'" v-model="rectifyFilter" :options="rectifyOptions" allow-clear @change="reload" />
      </div>

      <DualPaneWorkspace :aside-title="tab === 'guidance' ? '指导记录' : '巡访记录'" :aside-count="total">
        <!-- 左栏：记录队列（紧凑列表，连续处理） -->
        <template #aside>
          <div v-if="loading" class="state">加载中…</div>
          <div v-else-if="error" class="state is-err">{{ error }} <button type="button" class="mp-link" @click="load">重试</button></div>
          <div v-else-if="!rows.length" class="state">当前筛选下暂无记录</div>
          <ul v-else class="gv-list">
            <li v-for="r in rows" :key="r.id">
              <button type="button" class="gv-item" :class="{ 'is-active': String(r.id) === selectedId }" @click="select(r.id)">
                <div class="gv-item__row">
                  <span class="gv-item__name">{{ r.studentName }}</span>
                  <template v-if="tab === 'guidance'">
                    <AppStatusTag v-if="r.toRisk" type="danger">已转风险</AppStatusTag>
                  </template>
                  <AppStatusTag v-else :type="rectifyTone(r.rectifyStatus)">{{ r.rectifyStatusLabel }}</AppStatusTag>
                </div>
                <div class="gv-item__sub">{{ [r.studentNo, tab === 'guidance' ? r.advisorName : r.enterpriseName].filter(Boolean).join(' · ') }}</div>
                <div v-if="tab === 'guidance'" class="gv-item__sub">{{ [r.methodLabel, r.topic, r.createdAt].filter(Boolean).join(' · ') }}</div>
                <div v-else class="gv-item__sub">{{ [r.methodLabel, r.visitAt].filter(Boolean).join(' · ') }}</div>
              </button>
            </li>
          </ul>
        </template>
        <template #aside-foot>
          <AppPagination v-model:page="page" :page-size="pageSize" :total="total"
                        :show-total="false" :show-size-changer="false" :disabled="loading" @change="load" />
        </template>

        <!-- 右栏：当前记录详情（原详情弹窗内容 + 附件 + 审计 + 操作） -->
        <section class="mp-card gv-main">
          <template v-if="!selectedId">
            <EmptyState title="从左侧选择一条记录查看详情"
              :description="tab === 'guidance' ? '可查看指导内容、附件与操作留痕，并对记录发起撤销' : '可查看巡访反馈、安全隐患与整改要求，并跟进整改'" />
          </template>
          <div v-else-if="detail.loading" class="state gv-main__state">详情加载中…</div>
          <div v-else-if="detail.error" class="state is-err gv-main__state">
            {{ detail.error }} <button type="button" class="mp-link" @click="loadDetail(selectedId)">重试</button>
          </div>
          <template v-else-if="detail.data">
            <div class="gv-main__body">
              <div class="gv-head">
                <span class="gv-head__name">{{ detail.data.studentName }}</span>
                <AppStatusTag v-if="tab === 'guidance' && detail.data.toRisk" type="danger">已转风险</AppStatusTag>
                <AppStatusTag v-else-if="tab === 'visit' && detail.data.rectifyStatus" :type="rectifyTone(detail.data.rectifyStatus)">{{ detail.data.rectifyStatusLabel }}</AppStatusTag>
              </div>

              <div class="sec-t">{{ tab === 'guidance' ? '指导详情' : '巡访详情' }}</div>
              <AppDescriptionList :items="detailItems" :columns="2" />

              <template v-if="detail.data.attachment">
                <div class="sec-t">附件</div>
                <AppFilePreview :files="attachmentFiles" @download="downloadAtt" />
              </template>

              <div class="sec-t">操作留痕</div>
              <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无记录" />
            </div>

            <div v-if="tab === 'guidance' || detail.data.rectifyStatus === 'PENDING'" class="gv-foot">
              <AppPermissionButton v-if="tab === 'guidance'" code="internship.guidance.manage" :allowed="canBtn('internship.guidance.manage')" variant="ghost" :danger="true"
                @click="openVoid(detail.data)">撤销</AppPermissionButton>
              <AppPermissionButton v-if="tab === 'visit' && detail.data.rectifyStatus === 'PENDING'" code="internship.visit.manage" :allowed="canBtn('internship.visit.manage')" variant="secondary"
                @click="openRectify(detail.data)">整改跟进</AppPermissionButton>
            </div>
          </template>
        </section>
      </DualPaneWorkspace>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="true"
      :reason-label="cd.reasonLabel" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/**
 * 指导巡访管理（双栏工作区）。
 * 左栏 = 指导 / 巡访记录队列（分页 + 搜索 + 整改筛选），右栏 = 选中记录详情 + 附件 + 审计 + 撤销 / 整改跟进。
 * 选中记录写入 query.id，刷新可恢复；新增记录走独立录入页 /admin/internship/guidance/new。
 */
import { ModulePageShell, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppFilePreview, AppPagination } from '@/components/common'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'

/* 右栏只渲染详情接口真实返回字段（/internship/guidances/{id}、/internship/visits/{id}） */
const DETAIL = {
  guidance: [
    { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '指导教师' }, { key: 'methodLabel', label: '方式' },
    { key: 'topic', label: '主题' }, { key: 'content', label: '指导内容' }, { key: 'problemType', label: '问题类型' },
    { key: 'suggestion', label: '处理建议' }, { key: 'nextFollowDate', label: '下次跟进' }
  ],
  visit: [
    { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '巡访教师' }, { key: 'enterpriseName', label: '企业' },
    { key: 'methodLabel', label: '方式' }, { key: 'enterpriseFeedback', label: '企业反馈' }, { key: 'studentFeedback', label: '学生反馈' },
    { key: 'safetyIssue', label: '安全隐患' }, { key: 'rectifyRequire', label: '整改要求' }, { key: 'rectifyDeadline', label: '整改截止' },
    { key: 'rectifyStatusLabel', label: '整改状态' }, { key: 'monthlyReport', label: '月度小结' }
  ]
}
const RECTIFY_OPTIONS = [{ label: '整改中', value: 'PENDING' }, { label: '已整改', value: 'DONE' }, { label: '无需整改', value: 'NONE' }]
const PANEL_PRESETS = {
  plan: () => ({ redirect: '/admin/internship/guidance-plan' }),
  'insufficient-warning': () => ({ redirect: '/admin/internship/guidance-plan?insufficient=1' }),
  guidance: () => ({ tab: 'guidance', rectifyFilter: '' }),
  communication: () => ({ tab: 'guidance', rectifyFilter: '' }),
  visit: () => ({ tab: 'visit', rectifyFilter: '' }),
  'visit-plan': () => ({ tab: 'visit', rectifyFilter: '' }),
  'visit-issue': () => ({ tab: 'visit', rectifyFilter: '' }),
  rectify: () => ({ tab: 'visit', rectifyFilter: 'PENDING' })
}
const TAB_PANEL = { guidance: 'guidance', visit: 'visit' }

export default {
  name: 'GuidanceVisitView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, EmptyState, DualPaneWorkspace, ModuleSummaryStrip, AppButton,
    AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
    AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppFilePreview, AppPagination },
  data() {
    return {
      tab: 'guidance',
      tabs: [{ key: 'guidance', label: '指导记录' }, { key: 'visit', label: '教师巡访' }],
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', rectifyFilter: '', rectifyOptions: RECTIFY_OPTIONS,
      selectedId: '',
      detail: { loading: false, error: '', data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', reasonLabel: '说明', submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校',
      guidanceStats: null,
      visitStats: null
    }
  },
  computed: {
    statsCards() {
      if (this.tab === 'guidance' && this.guidanceStats) {
        const g = this.guidanceStats
        return [
          { label: '在岗学生', value: g.studentCount },
          { label: '人均指导次数', value: g.avgCount },
          { label: `不足 ${g.threshold} 次`, value: g.insufficientCount, warn: g.insufficientCount > 0 }
        ]
      }
      if (this.tab === 'visit' && this.visitStats) {
        const v = this.visitStats
        return [
          { label: '巡访记录', value: v.totalVisits },
          { label: '整改中', value: v.pendingRectify, warn: v.pendingRectify > 0 },
          { label: '已整改', value: v.doneRectify }
        ]
      }
      return []
    },
    summaryMetrics() {
      return this.statsCards.slice(0, 5).map((c) => ({ label: c.label, value: c.value }))
    },
    detailFields() { return DETAIL[this.tab] },
    detailItems() { const d = this.detail.data || {}; return this.detailFields.map((f) => ({ label: f.label, value: d[f.key] })) },
    attachmentFiles() { const a = this.detail.data?.attachment; return a ? [{ id: a.fileId, name: a.fileName, sensitive: true }] : [] },
    auditRecords() {
      return (this.detail.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.note || t.detail.reason || ''), at: t.occurredAt
      }))
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'guidance').toString())
      }
    },
    '$route.query.keyword': {
      immediate: true,
      handler(kw) {
        if (kw && String(kw) !== this.keyword) {
          this.keyword = String(kw)
          this.page = 1
          this.load()
        }
      }
    },
    '$route.query.id': {
      immediate: true,
      handler(id) {
        const sid = (id || '').toString()
        if (sid === this.selectedId) return
        this.selectedId = sid
        if (sid) this.loadDetail(sid)
        else this.detail = { loading: false, error: '', data: null }
      }
    }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.guidance
      const cfg = preset()
      if (cfg.redirect) {
        this.$router.replace(cfg.redirect)
        return
      }
      const { tab, rectifyFilter } = cfg
      this.tab = tab
      if (!this.$route.query.keyword) this.keyword = ''
      this.rectifyFilter = rectifyFilter
      this.page = 1
      this.loadStats()
      this.load()
    },
    async loadStats() {
      if (this.tab === 'guidance') {
        const res = await guidanceVisitApi.getGuidanceStats(2)
        if (res.code === 0) this.guidanceStats = res.data
      } else {
        const res = await guidanceVisitApi.getVisitStats()
        if (res.code === 0) this.visitStats = res.data
      }
    },
    rectifyTone(s) { return s === 'PENDING' ? 'warning' : s === 'DONE' ? 'success' : 'default' },
    exportFn() {
      return this.tab === 'guidance'
        ? guidanceVisitApi.exportGuidances({ keyword: this.keyword })
        : guidanceVisitApi.exportVisits({ keyword: this.keyword })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    goCreate() { this.$router.push('/admin/internship/guidance/new?type=' + this.tab) },
    switchTab(k) {
      const panel = TAB_PANEL[k] || k
      // 切换 tab 时清掉选中：指导 / 巡访详情走不同接口，选中不跨 tab 复用
      const query = { ...this.$route.query, panel }
      delete query.id
      if (this.$route.query.panel !== panel) {
        this.$router.replace({ path: this.$route.path, query })
      } else if (this.$route.query.id) {
        this.$router.replace({ path: this.$route.path, query })
      } else {
        this.applyPanel(panel)
      }
    },
    reload() { this.page = 1; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
      let res
      if (this.tab === 'guidance') res = await guidanceVisitApi.getGuidances(params)
      else { if (this.rectifyFilter) params.rectify = this.rectifyFilter; res = await guidanceVisitApi.getVisits(params) }
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
      // 撤销 / 筛选后翻页越界：自动回到最后一个有效页
      const pc = Math.max(1, Math.ceil(this.total / this.pageSize))
      if (!this.rows.length && this.total > 0 && this.page > pc) { this.page = pc; return this.load() }
    },
    select(id) {
      const sid = String(id)
      if (String(this.$route.query.id || '') === sid) {
        if (this.selectedId !== sid) { this.selectedId = sid; this.loadDetail(sid) }
        return
      }
      this.$router.replace({ query: { ...this.$route.query, id: sid } })
    },
    clearSelection() {
      const query = { ...this.$route.query }
      delete query.id
      this.$router.replace({ query })
    },
    async loadDetail(id) {
      this.detail = { loading: true, error: '', data: null }
      const res = this.tab === 'guidance'
        ? await guidanceVisitApi.getGuidanceDetail(id)
        : await guidanceVisitApi.getVisitDetail(id)
      if (String(this.selectedId) !== String(id)) return
      this.detail.loading = false
      if (res.code !== 0) { this.detail.error = res.message || '详情加载失败'; return }
      this.detail.data = res.data
    },
    async downloadAtt() {
      const a = this.detail.data?.attachment
      if (!a) return
      try { await guidanceVisitApi.downloadAttachment(a.fileId, a.fileName) } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    openVoid(d) {
      this.pending = { kind: 'void', id: this.selectedId }
      this.cd = { visible: true, title: '撤销指导记录', content: `撤销「${d.studentName}」的指导记录，撤销原因将写入审计。`,
        danger: true, confirmText: '撤销', reasonLabel: '撤销原因', submitting: false }
    },
    openRectify(d) {
      this.pending = { kind: 'rectify', id: this.selectedId }
      this.cd = { visible: true, title: '巡访整改跟进', content: `将「${d.studentName}」的安全隐患整改标记为「已整改」，跟进说明将写入审计。`,
        danger: false, confirmText: '标记已整改', reasonLabel: '整改跟进说明', submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      this.cd.submitting = true
      const res = p.kind === 'void'
        ? await guidanceVisitApi.voidGuidance(p.id, { reason })
        : await guidanceVisitApi.rectifyVisit(p.id, { status: 'DONE', note: reason })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('操作成功，已写审计')
      this.loadStats(); this.load()
      if (p.kind === 'void') this.clearSelection()
      else this.loadDetail(p.id)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.stats { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.stats__card { min-width: 120px; padding: var(--space-3); background: var(--bg-card); border: 1px solid var(--border-light); border-radius: 8px; }
.stats__val { font-size: var(--font-size-xl); font-weight: 600; }
.stats__val.is-warn { color: var(--danger-600); }
.stats__lbl { font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: var(--space-1); }
.tabs { display: flex; gap: var(--space-2); border-bottom: 1px solid var(--border-light); }
.tabs__btn { border: none; background: none; padding: var(--space-2) var(--space-3); cursor: pointer; color: var(--text-secondary); font-size: var(--font-size-sm); border-bottom: 2px solid transparent; }
.tabs__btn.is-active { color: var(--primary-700); border-bottom-color: var(--primary-600); font-weight: var(--font-weight-medium); }
.bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); margin: var(--space-3); }
.state.is-err { color: var(--danger-600); }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-4) 0 var(--space-2); }

/* 左栏紧凑列表 */
.gv-list { list-style: none; margin: 0; padding: var(--space-2); display: flex; flex-direction: column; gap: var(--space-1); }
.gv-item { display: block; width: 100%; text-align: left; font: inherit; cursor: pointer; background: transparent; border: 1px solid transparent; border-radius: var(--radius-md, 8px); padding: var(--space-2) var(--space-3); transition: background 0.12s ease, border-color 0.12s ease; }
.gv-item:hover { background: var(--primary-50, #eff6ff); }
.gv-item.is-active { background: var(--primary-50, #eff6ff); border-color: var(--primary-600, #2563eb); }
.gv-item__row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.gv-item__name { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.gv-item__sub { margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }

/* 右栏详情与固定操作区 */
.gv-main { display: flex; flex-direction: column; min-height: 320px; }
.gv-main__body { flex: 1; padding: var(--space-4); min-width: 0; }
.gv-main__state { margin: var(--space-4); }
.gv-head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.gv-head__name { font-size: var(--font-size-md, 15px); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.gv-foot { position: sticky; bottom: 0; display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); background: var(--bg-card, #fff); border-radius: 0 0 var(--r, 12px) var(--r, 12px); }
</style>
