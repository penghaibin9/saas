<template>
  <ModulePageShell
    title="毕业资格审核 · 审核工作台"
    subtitle="十项跨域供数三态判定 · 学分/课程/实践达成审核 · 毕设/实习/处分状态联动 · 教务终审 · 归档"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/graduation')">返回审核批次</button>
    </template>

    <div class="mp-stack">
      <AppSectionCard title="当前批次">
        <div class="agc-batch-bar">
          <select v-model="batchId" class="aa-select" :disabled="loadingBatches" @change="onBatchChange">
            <option value="">{{ loadingBatches ? '批次加载中…' : '选择批次' }}</option>
            <option v-for="b in batches" :key="b.batchId" :value="b.batchId">
              {{ b.batchName }}（{{ b.status }}，应审 {{ b.total }}）
            </option>
          </select>
          <template v-if="currentBatch">
            <span class="agc-chip">应审 {{ currentBatch.total }}</span>
            <span class="agc-chip is-pass">系统通过 {{ currentBatch.passed }}</span>
            <span class="agc-chip is-warn">系统异常 {{ currentBatch.abnormal }}</span>
            <span class="agc-chip is-final">已终审 {{ currentBatch.concluded }}</span>
            <span class="agc-chip is-archive">已归档 {{ currentBatch.archived }}</span>
          </template>
        </div>
        <EmptyState v-if="!loadingBatches && !batches.length" title="暂无审核批次" description="请先到「审核批次」页新建批次并执行预审" />
      </AppSectionCard>

      <div class="agc-tabs">
        <button v-for="t in tabs" :key="t.key" :class="['agc-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
      </div>

      <template v-if="!batchId">
        <EmptyState title="请先选择批次" description="从上方下拉选择一个审核批次" />
      </template>

      <!-- 学分 / 实践 / 毕设联动 / 实习联动 / 处分联动 · 单项透视 -->
      <template v-else-if="['credit', 'practice', 'thesis', 'internship', 'discipline'].includes(tab)">
        <ErrorState v-if="error" :description="error" @retry="loadTab" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" :title="`暂无${currentTabLabel}数据`" description="批次尚未执行预审，或该项供数为空" />
        <DataTable v-else :columns="itemColumns" :rows="rows" row-key="resultId" :pagination="pagination" @page-change="onPageChange">
          <template #cell-result="{ row }"><AppStatusTag :type="gradItemColor(itemOf(row).result)" dot>{{ itemResultLabel(itemOf(row).result) }}</AppStatusTag></template>
          <template #cell-evidence="{ row }"><span class="agc-evidence">{{ itemOf(row).evidence || '—' }}</span></template>
          <template #cell-ops="{ row }">
            <router-link v-if="linkFor(row)" class="mp-link" :to="linkFor(row)">跳转责任模块</router-link>
            <button class="mp-link" @click="openDetail(row)">十项详情</button>
          </template>
        </DataTable>
      </template>

      <!-- 课程达成审核：必修 + 选修两项并列 -->
      <template v-else-if="tab === 'course'">
        <ErrorState v-if="error" :description="error" @retry="loadCourseTab" />
        <LoadingState v-else-if="loading" />
        <template v-else>
          <AppSectionCard title="必修全通过">
            <EmptyState v-if="!courseRequiredRows.length" title="暂无必修数据" description="批次尚未执行预审" />
            <DataTable v-else :columns="itemColumns" :rows="courseRequiredRows" row-key="resultId">
              <template #cell-result="{ row }"><AppStatusTag :type="gradItemColor(itemOf(row, 'COURSE_REQUIRED').result)" dot>{{ itemResultLabel(itemOf(row, 'COURSE_REQUIRED').result) }}</AppStatusTag></template>
              <template #cell-evidence="{ row }"><span class="agc-evidence">{{ itemOf(row, 'COURSE_REQUIRED').evidence || '—' }}</span></template>
              <template #cell-ops="{ row }"><button class="mp-link" @click="openDetail(row)">十项详情</button></template>
            </DataTable>
          </AppSectionCard>
          <AppSectionCard title="选修学分达标">
            <EmptyState v-if="!courseElectiveRows.length" title="暂无选修数据" description="批次尚未执行预审" />
            <DataTable v-else :columns="itemColumns" :rows="courseElectiveRows" row-key="resultId">
              <template #cell-result="{ row }"><AppStatusTag :type="gradItemColor(itemOf(row, 'COURSE_ELECTIVE').result)" dot>{{ itemResultLabel(itemOf(row, 'COURSE_ELECTIVE').result) }}</AppStatusTag></template>
              <template #cell-evidence="{ row }"><span class="agc-evidence">{{ itemOf(row, 'COURSE_ELECTIVE').evidence || '—' }}</span></template>
              <template #cell-ops="{ row }"><button class="mp-link" @click="openDetail(row)">十项详情</button></template>
            </DataTable>
          </AppSectionCard>
        </template>
      </template>

      <!-- 毕业资格终审：仅 ACADEMIC_REVIEW（学院初审已通过，待教务处终审） -->
      <template v-else-if="tab === 'final'">
        <ErrorState v-if="error" :description="error" @retry="loadTab" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无待终审名单" description="需学院初审通过（ACADEMIC_REVIEW）后才进入本队列" />
        <DataTable v-else :columns="finalColumns" :rows="rows" row-key="resultId" :pagination="pagination" @page-change="onPageChange">
          <template #cell-overall="{ row }"><AppStatusTag :type="overallColor(row.overall)" dot>{{ overallLabel(row.overall) }}</AppStatusTag></template>
          <template #cell-ops="{ row }"><button class="mp-btn mp-btn--primary" @click="openFinal(row)">教务终审</button></template>
        </DataTable>
      </template>

      <!-- 审核结果：全量总览 -->
      <template v-else-if="tab === 'results'">
        <ErrorState v-if="error" :description="error" @retry="loadTab" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无预审结果" description="请先在「审核批次」页执行预审" />
        <DataTable v-else :columns="resultColumns" :rows="rows" row-key="resultId" :pagination="pagination" @page-change="onPageChange">
          <template #cell-overall="{ row }"><AppStatusTag :type="overallColor(row.overall)" dot>{{ overallLabel(row.overall) }}</AppStatusTag></template>
          <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'ARCHIVED' ? 'default' : 'primary'" dot>{{ statusLabel(row.status) }}</AppStatusTag></template>
          <template #cell-conclusion="{ row }"><span v-if="row.conclusion" class="agc-conclusion">{{ conclusionLabel(row.conclusion) }}</span><span v-else>—</span></template>
          <template #cell-ops="{ row }"><button class="mp-link" @click="openDetail(row)">详情 / 处理</button></template>
        </DataTable>
      </template>

      <!-- 审核归档 -->
      <template v-else-if="tab === 'archive'">
        <AppSectionCard title="归档操作">
          <p class="mp-note">收敛该批次已终审的「毕业/结业」结果为已归档（ARCHIVED）；延毕滚入下一批次、退回待重初审的结果不在本次归档范围内，需重新走完流程后再归档。</p>
          <button class="mp-btn mp-btn--primary" :disabled="archiving || !batchId" @click="confirmArchive">执行归档</button>
        </AppSectionCard>
        <ErrorState v-if="error" :description="error" @retry="loadTab" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无已归档结果" description="执行归档后，已终审的毕业/结业名单会出现在此" />
        <DataTable v-else :columns="archiveColumns" :rows="rows" row-key="resultId" :pagination="pagination" @page-change="onPageChange">
          <template #cell-conclusion="{ row }"><span class="agc-conclusion">{{ conclusionLabel(row.conclusion) }}</span></template>
        </DataTable>
      </template>
    </div>

    <AppDrawer :visible="detail.visible" title="预审结果详情（十项）" @close="detail.visible = false">
      <template v-if="detail.row">
        <div class="agc-detail-head">
          <div class="agc-detail-name">{{ detail.row.realName || ('学生 ' + detail.row.studentId) }}</div>
          <AppStatusTag :type="overallColor(detail.row.overall)" dot>{{ overallLabel(detail.row.overall) }}</AppStatusTag>
          <AppStatusTag :type="detail.row.status === 'ARCHIVED' ? 'default' : 'primary'" dot>{{ statusLabel(detail.row.status) }}</AppStatusTag>
        </div>
        <div class="agc-items">
          <div v-for="it in detail.row.items" :key="it.item" class="agc-item">
            <span class="agc-item__label">{{ itemLabel(it.item) }}</span>
            <AppStatusTag :type="gradItemColor(it.result)" dot>{{ itemResultLabel(it.result) }}</AppStatusTag>
            <span class="agc-item__ev">{{ it.evidence }}</span>
          </div>
        </div>
        <AppInlineAlert v-if="detail.row.reviewNote" type="info" :description="`最近处理意见：${detail.row.reviewNote}`" />

        <div v-if="canCollegeReview(detail.row)" class="agc-actions">
          <div class="agc-actions__title">学院初审</div>
          <button class="mp-btn mp-btn--primary" :disabled="detailBusy" @click="doCollegeReview('APPROVE')">通过</button>
          <button class="mp-btn" :disabled="detailBusy" @click="doCollegeReview('REJECT')">退回学院（需≥5字原因）</button>
        </div>

        <div v-if="detail.row.status === 'ACADEMIC_REVIEW'" class="agc-actions">
          <div class="agc-actions__title">毕业资格终审</div>
          <label v-for="(l, v) in CONCLUSION_LABEL" :key="v" class="agc-radio">
            <input v-model="finalConclusion" type="radio" :value="v" /> {{ l }}
          </label>
          <button class="mp-btn mp-btn--primary" :disabled="detailBusy" @click="confirmFinal">确认终审并写学籍</button>
        </div>
        <p v-if="detail.row.conclusion" class="mp-note">终审结论：{{ conclusionLabel(detail.row.conclusion) }}（涉学籍终态，不可在本页撤销）</p>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="finalDlg.visible"
      title="确认毕业资格终审"
      type="danger"
      :message="`将对该生写入学籍终态「${CONCLUSION_LABEL[finalConclusion]}」，是否确认？`"
      :submitting="finalDlg.submitting"
      @confirm="doFinal"
    />
    <AppConfirmDialog
      v-model:visible="archiveDlg.visible"
      title="确认审核归档"
      type="warning"
      :message="'将该批次已终审的毕业/结业结果标记为已归档，归档后不可在本页撤销，是否确认？'"
      :submitting="archiving"
      @confirm="doArchive"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 毕业资格审核 · 审核工作台（/admin/academic-affairs/graduation/audit-console?tab=）。
 * 十项跨域供数三态判定的下游六个叶子（学分/课程/实践达成审核、毕设/实习/处分状态联动、毕业资格终审、
 * 审核结果、审核归档）共享同一批次选择与详情抽屉，避免为每个叶子各建一套重复列表页。
 * 「审核批次」（建批次/圈定/预审）仍在既有 AaGraduationBatchView.vue（/graduation），本页不重复。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import AppStatusTag from '@/components/common/AppStatusTag.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import {
  GRAD_ITEM_LABEL, GRAD_ITEM_RESULT, gradItemColor, OVERALL_LABEL, overallColor,
  CONCLUSION_LABEL, GRAD_STATUS_LABEL
} from '@/modules/academicAffairs/constants/grade-graduation'
import { toast } from '@/utils/toast'

const TAB_CONFIG = {
  credit: { label: '学分达成审核', item: 'CREDIT' },
  course: { label: '课程达成审核' },
  practice: { label: '实践环节审核', item: 'PRACTICE' },
  thesis: { label: '毕设状态联动', item: 'GRADUATION_DESIGN' },
  internship: { label: '实习状态联动', item: 'INTERNSHIP' },
  discipline: { label: '处分状态联动', item: 'DISCIPLINE' },
  final: { label: '毕业资格终审', status: 'ACADEMIC_REVIEW' },
  results: { label: '审核结果' },
  archive: { label: '审核归档', status: 'ARCHIVED' }
}
// 仅 GRADUATION_DESIGN / INTERNSHIP 的 refId 语义已核实（对应目标模块详情页路径参数），处分域暂无可核实的
// 详情路由（学工中心处分导航正在从 campusService 迁移至 studentAffairs，未提供稳定 :id 详情页），故不建跳转，
// 只展示证据文本，避免死链接/假按钮。
const LINK_ITEM = {
  GRADUATION_DESIGN: (refId) => `/admin/graduation/students/${refId}`,
  INTERNSHIP: (refId) => `/admin/internship/students/${refId}`
}

export default {
  name: 'AaGraduationAuditConsoleView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppSectionCard, AppConfirmDialog, AppInlineAlert, AppDrawer, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      CONCLUSION_LABEL,
      tabs: Object.keys(TAB_CONFIG).map((key) => ({ key, label: TAB_CONFIG[key].label })),
      tab: 'credit',
      batches: [], loadingBatches: true, batchId: '',
      rows: [], courseRequiredRows: [], courseElectiveRows: [],
      loading: false, error: '',
      pagination: { page: 1, pageSize: 20, total: 0 },
      detail: { visible: false, row: null }, detailBusy: false,
      finalConclusion: 'GRADUATED',
      finalDlg: { visible: false, submitting: false },
      archiveDlg: { visible: false },
      archiving: false,
      itemColumns: [
        { key: 'studentId', title: '学号' }, { key: 'realName', title: '姓名' },
        { key: 'result', title: '结果' }, { key: 'evidence', title: '证据' }, { key: 'ops', title: '操作', width: '160px' }
      ],
      finalColumns: [
        { key: 'studentId', title: '学号' }, { key: 'realName', title: '姓名' },
        { key: 'overall', title: '系统预审' }, { key: 'ops', title: '操作', width: '120px' }
      ],
      resultColumns: [
        { key: 'studentId', title: '学号' }, { key: 'realName', title: '姓名' },
        { key: 'overall', title: '系统预审' }, { key: 'status', title: '当前状态' },
        { key: 'conclusion', title: '终审结论' }, { key: 'ops', title: '操作', width: '120px' }
      ],
      archiveColumns: [
        { key: 'studentId', title: '学号' }, { key: 'realName', title: '姓名' }, { key: 'conclusion', title: '终审结论' }
      ]
    }
  },
  computed: {
    currentTabLabel() { return TAB_CONFIG[this.tab] ? TAB_CONFIG[this.tab].label : '' },
    currentBatch() { return this.batches.find((b) => b.batchId === this.batchId) || null }
  },
  async created() {
    const q = this.$route && this.$route.query
    if (q && q.tab && TAB_CONFIG[q.tab]) this.tab = q.tab
    await this.loadBatches()
    if (q && q.batchId && this.batches.some((b) => b.batchId === q.batchId)) this.batchId = q.batchId
    else if (this.batches.length) this.batchId = (this.batches.find((b) => b.status !== 'ARCHIVED') || this.batches[0]).batchId
    this.loadTab()
  },
  methods: {
    gradItemColor, overallColor,
    itemLabel(i) { return GRAD_ITEM_LABEL[i] || i },
    itemResultLabel(r) { return GRAD_ITEM_RESULT[r] || r },
    overallLabel(o) { return OVERALL_LABEL[o] || o || '—' },
    statusLabel(s) { return GRAD_STATUS_LABEL[s] || s || '' },
    conclusionLabel(c) { return CONCLUSION_LABEL[c] || c },
    itemOf(row, key) {
      const target = key || (TAB_CONFIG[this.tab] && TAB_CONFIG[this.tab].item)
      return (row.items || []).find((it) => it.item === target) || row.itemDetail || {}
    },
    linkFor(row) {
      const cfg = TAB_CONFIG[this.tab]
      if (!cfg || !cfg.item || !LINK_ITEM[cfg.item]) return null
      const it = this.itemOf(row)
      if (!it.refId) return null
      return LINK_ITEM[cfg.item](it.refId)
    },
    canCollegeReview(r) { return ['SYSTEM_PASSED', 'SYSTEM_ABNORMAL', 'COLLEGE_REVIEW'].includes(r.status) },
    switchTab(k) {
      this.tab = k
      this.$router.replace({ query: { ...this.$route.query, tab: k } }).catch(() => {})
      this.pagination.page = 1
      this.loadTab()
    },
    onBatchChange() {
      this.$router.replace({ query: { ...this.$route.query, batchId: this.batchId } }).catch(() => {})
      this.pagination.page = 1
      this.loadTab()
    },
    onPageChange(p) { this.pagination.page = p; this.loadTab() },
    async loadBatches() {
      this.loadingBatches = true
      const res = await academicAffairsApi.listGradBatches({ pageSize: 100 })
      this.batches = res.code === 0 ? res.data.list : []
      this.loadingBatches = false
    },
    async loadTab() {
      if (this.tab === 'course') { this.loadCourseTab(); return }
      if (!this.batchId) { this.rows = []; this.pagination.total = 0; return }
      this.loading = true; this.error = ''
      const cfg = TAB_CONFIG[this.tab] || {}
      const params = { page: this.pagination.page, pageSize: this.pagination.pageSize }
      if (cfg.item) params.item = cfg.item
      if (cfg.status) params.status = cfg.status
      const res = await academicAffairsApi.getGradResults(this.batchId, params)
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total } else { this.error = res.message }
      this.loading = false
    },
    async loadCourseTab() {
      if (!this.batchId) { this.courseRequiredRows = []; this.courseElectiveRows = []; return }
      this.loading = true; this.error = ''
      const [req, ele] = await Promise.all([
        academicAffairsApi.getGradResults(this.batchId, { item: 'COURSE_REQUIRED', pageSize: 100 }),
        academicAffairsApi.getGradResults(this.batchId, { item: 'COURSE_ELECTIVE', pageSize: 100 })
      ])
      if (req.code === 0) this.courseRequiredRows = req.data.list; else this.error = req.message
      if (ele.code === 0) this.courseElectiveRows = ele.data.list; else this.error = this.error || ele.message
      this.loading = false
    },
    openDetail(row) {
      this.detail = { visible: true, row }
      this.finalConclusion = 'GRADUATED'
    },
    openFinal(row) { this.openDetail(row) },
    async doCollegeReview(action) {
      let note = ''
      if (action === 'REJECT') {
        note = window.prompt('退回原因（≥5字）') || ''
        if (note.trim().length < 5) { toast.error('原因至少 5 字'); return }
      }
      this.detailBusy = true
      const res = await academicAffairsApi.collegeReviewGrad(this.detail.row.resultId, action, note)
      this.detailBusy = false
      if (res.code === 0) {
        toast.success('已处理')
        this.detail.visible = false
        this.loadTab()
      } else toast.error(res.message || '处理失败')
    },
    confirmFinal() { this.finalDlg.visible = true },
    async doFinal() {
      this.finalDlg.submitting = true
      const res = await academicAffairsApi.finalGrad(this.detail.row.resultId, this.finalConclusion, true)
      this.finalDlg.submitting = false
      if (res.code === 0) {
        toast.success('终审完成，已写学籍')
        this.finalDlg.visible = false
        this.detail.visible = false
        this.loadBatches()
        this.loadTab()
      } else toast.error(res.message || '终审失败')
    },
    confirmArchive() { this.archiveDlg.visible = true },
    async doArchive() {
      this.archiving = true
      const res = await academicAffairsApi.archiveGradBatch(this.batchId)
      this.archiving = false
      this.archiveDlg.visible = false
      if (res.code === 0) {
        toast.success(`已归档 ${res.data.archived} 条`)
        this.loadBatches()
        this.loadTab()
      } else toast.error(res.message || '归档失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.agc-batch-bar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; min-width: 260px; }
.agc-chip { padding: 4px 10px; border-radius: 12px; font-size: 12px; background: var(--fill-100, #f2f3f5); color: var(--text-700, #4e5969); }
.agc-chip.is-pass { background: var(--success-50, #eafff3); color: var(--success-600, #16a34a); }
.agc-chip.is-warn { background: var(--warning-50, #fffbeb); color: var(--warning-600, #d97706); }
.agc-chip.is-final { background: var(--primary-50, #eff6ff); color: var(--primary-600, #2563eb); }
.agc-chip.is-archive { background: var(--fill-200, #e5e6eb); color: var(--text-500, #86909c); }
.agc-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); flex-wrap: wrap; }
.agc-tab { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; white-space: nowrap; }
.agc-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.agc-evidence { color: var(--text-500, #86909c); font-size: 12px; }
.agc-conclusion { color: var(--success-600, #16a34a); font-weight: 500; }
.agc-detail-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.agc-detail-name { font-size: 16px; font-weight: 600; }
.agc-items { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.agc-item { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.agc-item__label { min-width: 76px; color: var(--text-700, #4e5969); }
.agc-item__ev { color: var(--text-400, #8a9099); font-size: 12px; }
.agc-actions { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border-color, #e5e7eb); display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.agc-actions__title { width: 100%; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.agc-radio { display: flex; align-items: center; gap: 6px; font-size: 13px; }
</style>
