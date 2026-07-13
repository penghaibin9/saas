<template>
  <ModulePageShell
    title="问题预警 · 毕设归档 · 毕设统计"
    subtitle="风险扫描与处置闭环 / 材料归档核验 / 跨模块统计看板"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <GraduationBatchStrip />
    <div class="gp-tabs">
      <button class="gp-tabs__item" :class="{ 'is-active': tab === 'risk' }" @click="switchTab('risk')">问题预警</button>
      <button class="gp-tabs__item" :class="{ 'is-active': tab === 'archive' }" @click="switchTab('archive')">毕设归档</button>
      <button class="gp-tabs__item" :class="{ 'is-active': tab === 'stats' }" @click="switchTab('stats')">毕设统计</button>
    </div>

    <!-- 问题预警：连续双栏处置 -->
    <div v-if="tab === 'risk'" class="mp-stack">
      <div class="ie-actions" style="justify-content: flex-start"><button class="mp-btn mp-btn--primary" @click="doScan">扫描生成风险项</button></div>
      <AdvancedFilter v-model="riskFilters" :fields="riskFilterFields" @search="loadRisks" @reset="resetRiskFilters" />
      <ErrorState v-if="riskError" :description="riskError" @retry="loadRisks" />
      <LoadingState v-else-if="riskLoading" />
      <EmptyState v-else-if="!riskRows.length" title="暂无风险记录" description="点「扫描生成风险项」按当前数据生成" />
      <div v-else class="rk-split">
        <aside class="rk-list">
          <ul class="rk-rows">
            <li v-for="(row, i) in riskRows" :key="row.id" class="rk-row" :class="{ 'is-active': String(row.id) === riskSelKey }" tabindex="0" role="button" @click="selectRisk(row)" @keydown.enter.prevent="selectRisk(row)" @keydown.space.prevent="selectRisk(row)">
              <div class="rk-row__main">
                <span class="rk-row__name">{{ row.riskName }}</span>
                <StatusTag :type="row.level === 'CRITICAL' || row.level === 'HIGH' ? 'danger' : 'warning'" :label="levelLabel(row.level)" dot />
              </div>
              <div class="rk-row__sub">{{ row.studentName }} · {{ row.studentNo }}</div>
              <div class="rk-row__meta"><StatusTag :type="row.statusTone" :label="row.statusLabel" dot /><span class="rk-row__idx">{{ (riskPage - 1) * riskPageSize + i + 1 }}</span></div>
            </li>
          </ul>
          <div style="display: flex; justify-content: center"><AppPagination :total="riskTotal" :page="riskPage" :page-size="riskPageSize" :show-size-changer="false" @update:page="p => { riskPage = p; loadRisks() }" /></div>
        </aside>
        <section class="rk-pane">
          <div class="rk-pane__bar">
            <span>本页第 {{ riskSelIndex + 1 }} / {{ riskRows.length }} 条 · 共 {{ riskTotal }} 条</span>
            <label class="rk-pane__auto"><input v-model="riskAutoNext" type="checkbox" /> 处置后自动进入下一条</label>
            <span class="rk-pane__nav">
              <button class="mp-link" :disabled="riskSelIndex <= 0" @click="stepRisk(-1)">← 上一条</button>
              <button class="mp-link" :disabled="riskSelIndex >= riskRows.length - 1" @click="stepRisk(1)">下一条 →</button>
            </span>
          </div>
          <EmptyState v-if="!selectedRisk" title="从左侧选择一条风险" description="处置后可自动进入下一条待办风险" />
          <section v-else class="mp-card">
            <div class="mp-card__head">
              <span class="mp-card__title">{{ selectedRisk.riskName }}</span>
              <button v-if="selectedRisk.gdStudentId" class="mp-link" @click="$router.push('/admin/graduation/students/' + selectedRisk.gdStudentId)">查看学生档案 →</button>
            </div>
            <div class="mp-card__body">
              <div class="mp-kv"><span class="mp-kv__k">等级</span><span class="mp-kv__v"><StatusTag :type="selectedRisk.level === 'CRITICAL' || selectedRisk.level === 'HIGH' ? 'danger' : 'warning'" :label="levelLabel(selectedRisk.level)" dot /></span></div>
              <div class="mp-kv"><span class="mp-kv__k">状态</span><span class="mp-kv__v"><StatusTag :type="selectedRisk.statusTone" :label="selectedRisk.statusLabel" dot /></span></div>
              <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ selectedRisk.studentName }} · {{ selectedRisk.studentNo }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">指导教师</span><span class="mp-kv__v">{{ selectedRisk.advisorName || '未分配导师' }}</span></div>
              <div v-if="selectedRisk.detail" class="mp-kv"><span class="mp-kv__k">风险详情</span><span class="mp-kv__v">{{ selectedRisk.detail }}</span></div>
              <div v-if="selectedRisk.createdAt" class="mp-kv"><span class="mp-kv__k">首次触发</span><span class="mp-kv__v">{{ (selectedRisk.createdAt || '').replace('T', ' ').slice(0, 16) }}</span></div>
              <div v-if="selectedRisk.handleNote" class="mp-kv"><span class="mp-kv__k">处理记录</span><span class="mp-kv__v">{{ selectedRisk.handleNote }}</span></div>
              <div class="ie-actions" style="justify-content: flex-start; margin-top: var(--space-3)">
                <button v-if="selectedRisk.status === 'OPEN'" class="mp-btn mp-btn--primary" @click="doAccept(selectedRisk)">受理</button>
                <button v-if="selectedRisk.status === 'PROCESSING'" class="mp-btn mp-btn--primary" @click="doProcess(selectedRisk)">记录处理</button>
                <button v-if="selectedRisk.status === 'PROCESSING'" class="mp-btn" @click="doClose(selectedRisk)">关闭风险</button>
                <span v-if="selectedRisk.status === 'CLOSED'" class="mp-note">该风险已关闭</span>
              </div>
              <p class="mp-note" style="margin-top: var(--space-2)">受理 / 处理 / 关闭均写入审计留痕；关闭需填写原因。</p>
            </div>
          </section>
        </section>
      </div>
    </div>
    <!-- 毕设归档：连续双栏核验（左队列 + 右缺件清单与状态机动作） -->
    <div v-if="tab === 'archive'" class="mp-stack">
      <div class="ie-actions" style="justify-content: flex-start">
        <button class="mp-btn mp-btn--primary" @click="doBatchGenerate">批量生成提交</button>
        <button class="mp-btn" @click="doBatchFile">一键核验备案</button>
        <AppExportButton :export-fn="exportArchivesFn">导出台账</AppExportButton>
      </div>
      <AdvancedFilter v-model="archiveFilters" :fields="archiveFilterFields" @search="loadArchives" @reset="resetArchiveFilters" />
      <ErrorState v-if="archiveError" :description="archiveError" @retry="loadArchives" />
      <LoadingState v-else-if="archiveLoading" />
      <EmptyState v-else-if="!archiveRows.length" title="暂无归档记录" />
      <div v-else class="rk-split">
        <aside class="rk-list">
          <ul class="rk-rows">
            <li v-for="(row, i) in archiveRows" :key="row.id" class="rk-row" :class="{ 'is-active': String(row.id) === archiveSelKey }" tabindex="0" role="button" @click="selectArchive(row)" @keydown.enter.prevent="selectArchive(row)" @keydown.space.prevent="selectArchive(row)">
              <div class="rk-row__main">
                <span class="rk-row__name">{{ row.studentName }}</span>
                <StatusTag :type="row.statusTone" :label="row.statusLabel" dot />
              </div>
              <div class="rk-row__sub">{{ row.studentNo }}</div>
              <div class="rk-row__meta">
                <span :style="row.missingItems.length ? 'color: var(--danger, #dc2626)' : 'color: var(--success-600, #16a34a)'">{{ row.missingItems.length ? '缺 ' + row.missingItems.length + ' 项' : '材料齐全' }}</span>
                <span class="rk-row__idx">{{ (archivePage - 1) * archivePageSize + i + 1 }}</span>
              </div>
            </li>
          </ul>
          <div style="display: flex; justify-content: center"><AppPagination :total="archiveTotal" :page="archivePage" :page-size="archivePageSize" :show-size-changer="false" @update:page="p => { archivePage = p; loadArchives() }" /></div>
        </aside>
        <section class="rk-pane">
          <div class="rk-pane__bar">
            <span>本页第 {{ archiveSelIndex + 1 }} / {{ archiveRows.length }} 条 · 共 {{ archiveTotal }} 条</span>
            <span class="rk-pane__nav">
              <button class="mp-link" :disabled="archiveSelIndex <= 0" @click="stepArchive(-1)">← 上一条</button>
              <button class="mp-link" :disabled="archiveSelIndex >= archiveRows.length - 1" @click="stepArchive(1)">下一条 →</button>
            </span>
          </div>
          <EmptyState v-if="!selectedArchive" title="从左侧选择一名学生" description="逐个核验材料完整性并办理归档" />
          <section v-else class="mp-card">
            <div class="mp-card__head">
              <span class="mp-card__title">{{ selectedArchive.studentName }} · 归档核验</span>
              <button v-if="selectedArchive.gdStudentId" class="mp-link" @click="$router.push('/admin/graduation/students/' + selectedArchive.gdStudentId)">查看学生档案 →</button>
            </div>
            <div class="mp-card__body">
              <div class="mp-kv"><span class="mp-kv__k">学号</span><span class="mp-kv__v">{{ selectedArchive.studentNo }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">归档状态</span><span class="mp-kv__v"><StatusTag :type="selectedArchive.statusTone" :label="selectedArchive.statusLabel" dot /></span></div>
              <div class="mp-kv"><span class="mp-kv__k">材料完整性</span>
                <span class="mp-kv__v" :style="selectedArchive.missingItems.length ? 'color: var(--danger, #dc2626)' : 'color: var(--success-600, #16a34a)'">
                  {{ selectedArchive.missingItems.length ? '缺失 ' + selectedArchive.missingItems.length + ' 项' : '必备材料齐全' }}
                </span>
              </div>
              <template v-if="selectedArchive.missingItems.length">
                <p class="mp-note" style="margin-top: var(--space-2); font-weight: 600; color: var(--text-primary)">缺件明细（点击直达补齐入口）</p>
                <ul class="ar-missing">
                  <li v-for="m in selectedArchive.missingItems" :key="m" class="ar-missing__item">
                    <span class="ar-missing__name">✕ {{ m }}</span>
                    <button class="mp-link" @click="goFix(m, selectedArchive)">去补齐 →</button>
                  </li>
                </ul>
              </template>
              <div class="ie-actions" style="justify-content: flex-start; margin-top: var(--space-3)">
                <button v-if="['NOT_GENERATED', 'REJECTED'].includes(selectedArchive.status)" class="mp-btn mp-btn--primary" @click="doGenerate(selectedArchive)">生成清单</button>
                <button v-if="selectedArchive.status === 'PENDING_SUBMIT' && !selectedArchive.missingItems.length" class="mp-btn mp-btn--primary" @click="doSubmit(selectedArchive)">提交归档</button>
                <span v-if="selectedArchive.status === 'PENDING_SUBMIT' && selectedArchive.missingItems.length" class="mp-note">缺件补齐后方可提交归档</span>
                <button v-if="selectedArchive.status === 'SUBMITTED'" class="mp-btn mp-btn--primary" @click="doFile(selectedArchive)">核验归档</button>
                <button v-if="selectedArchive.status === 'SUBMITTED'" class="mp-btn" @click="doReject(selectedArchive)">驳回</button>
                <span v-if="selectedArchive.status === 'FILED'" class="mp-note">已正式归档备案，记录只读</span>
              </div>
              <p class="mp-note" style="margin-top: var(--space-2)">生成 / 提交 / 核验 / 驳回均写入审计留痕；完整性以后端清单核验为准。</p>
            </div>
          </section>
        </section>
      </div>
    </div>
    <!-- 毕设统计 -->
    <div v-if="tab === 'stats'" class="mp-stack">
      <AppDateRangePicker
        v-model="statsRange"
        label="统计时间范围"
        mode="filter"
        empty-label="全部时间"
        memory-key="graduation.riskArchive.statsRange"
        @change="onStatsRangeChange"
      />
      <ErrorState v-if="statsError" :description="statsError" @retry="loadStats" />
      <LoadingState v-else-if="statsLoading" />
      <template v-else-if="overview">
        <div class="gs-cards">
          <div class="gs-card"><div class="gs-card__label">毕设学生</div><div class="gs-card__value">{{ overview.studentTotal }}</div></div>
          <div class="gs-card"><div class="gs-card__label">导师已认证</div><div class="gs-card__value">{{ overview.mentor.qualifiedCount }}</div></div>
          <div class="gs-card"><div class="gs-card__label">未分配导师</div><div class="gs-card__value">{{ overview.mentor.unassignedStudents }}</div></div>
          <div class="gs-card"><div class="gs-card__label">开放风险</div><div class="gs-card__value">{{ overview.risk.openCount }}</div></div>
          <div class="gs-card"><div class="gs-card__label">归档率</div><div class="gs-card__value">{{ overview.archive.archiveRate }}%</div></div>
          <div class="gs-card"><div class="gs-card__label">成绩已发布均分</div><div class="gs-card__value">{{ overview.grade.publishedAvg }}</div></div>
        </div>
        <div class="gm-section-title" style="margin-top: var(--space-4)">阶段分布</div>
        <AppStackedBarChart
          v-if="stageChartData.length >= 2"
          title="各阶段学生数"
          :data="stageChartData"
          horizontal
          :height="Math.max(150, stageChartData.length * 38)"
          x-field="label"
          y-field="count"
          series-field="cat"
          value-label="人数"
        />
        <ul v-else class="gs-stage-list">
          <li v-for="s in overview.byStage" :key="s.stage">{{ s.label }}：{{ s.count }}</li>
        </ul>
        <div class="gm-section-title" style="margin-top: var(--space-4)">学院/专业对比</div>
        <DataTable :columns="collegeColumns" :rows="collegeRows" row-key="name" />
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 问题预警+毕设归档+毕设统计（/admin/graduation/risk-archive）：扫描处置闭环 + 材料核验归档 + 跨模块统计看板。 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import GraduationBatchStrip from './_shared/GraduationBatchStrip.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppExportButton, AppPagination, AppStackedBarChart } from '@/components/common'
import { AppDateRangePicker } from '@/components/common/date'
import { graduationRiskArchiveApi } from '@/modules/graduation/api/graduation-risk-archive.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationRiskArchiveView',
  components: { GraduationBatchStrip, ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppDateRangePicker, AppExportButton, AppPagination, AppStackedBarChart },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'risk',
      riskSelKey: '', riskAutoNext: true,
      archiveSelKey: '',
      riskFilters: { status: '', level: '', dateStart: '', dateEnd: '' }, riskRows: [], riskTotal: 0, riskPage: 1, riskPageSize: 10, riskLoading: true, riskError: '',
      archiveFilters: { keyword: '', status: '', dateStart: '', dateEnd: '' }, archiveRows: [], archiveTotal: 0, archivePage: 1, archivePageSize: 10, archiveLoading: true, archiveError: '',
      statsError: '',
      statsRange: { start: '', end: '' },
      overview: null, collegeRows: [], statsLoading: true,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      riskColumns: [{ key: 'risk', title: '风险 / 学生' }, { key: 'level', title: '等级' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '160px' }],
      archiveColumns: [{ key: 'student', title: '学生' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '200px' }],
      collegeColumns: [{ key: 'name', title: '学院/专业' }, { key: 'total', title: '学生数' }, { key: 'archived', title: '已归档' }, { key: 'highRisk', title: '高风险' }]
    }
  },
  computed: {
    selectedRisk() {
      return this.riskRows.find((r) => String(r.id) === this.riskSelKey) || null
    },
    riskSelIndex() {
      return this.riskRows.findIndex((r) => String(r.id) === this.riskSelKey)
    },
    stageChartData() {
      return ((this.overview && this.overview.byStage) || []).filter((s) => (s.count || 0) > 0).map((s) => ({ label: s.label, count: s.count, cat: '人数' }))
    },
    selectedArchive() {
      return this.archiveRows.find((r) => String(r.id) === this.archiveSelKey) || null
    },
    archiveSelIndex() {
      return this.archiveRows.findIndex((r) => String(r.id) === this.archiveSelKey)
    },
    riskFilterFields() {
      return [
        { key: 'status', label: '状态', type: 'select', options: [{ value: 'OPEN', label: '待受理' }, { value: 'PROCESSING', label: '处理中' }, { value: 'CLOSED', label: '已关闭' }] },
        { key: 'level', label: '等级', type: 'select', options: [{ value: 'LOW', label: '低' }, { value: 'MEDIUM', label: '中' }, { value: 'HIGH', label: '高' }, { value: 'CRITICAL', label: '紧急' }] },
        {
          key: 'date', label: '预警时间', type: 'daterange',
          startKey: 'dateStart', endKey: 'dateEnd',
          memoryKey: 'graduation.risk.dateRange', emptyLabel: '全部时间'
        }
      ]
    },
    archiveFilterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生姓名' },
        { key: 'status', label: '状态', type: 'select', options: [{ value: 'NOT_GENERATED', label: '待生成' }, { value: 'PENDING_SUBMIT', label: '待提交' }, { value: 'SUBMITTED', label: '已提交' }, { value: 'FILED', label: '已备案' }, { value: 'REJECTED', label: '已驳回' }] },
        {
          key: 'date', label: '归档时间', type: 'daterange',
          startKey: 'dateStart', endKey: 'dateEnd',
          memoryKey: 'graduation.archive.dateRange', emptyLabel: '全部时间'
        }
      ]
    }
  },
  created() {
    const p = this.$route.query.panel
    if (['risk', 'archive', 'stats'].includes(p)) this.tab = p
    this.riskSelKey = (this.$route.query.rsel || '').toString()
    this.archiveSelKey = (this.$route.query.asel || '').toString()
    this.loadRisks(); this.loadArchives(); this.loadStats()
  },
  watch: {
    // 应用内点左侧三级菜单（同路由不同 ?panel=）时组件被复用，必须监听 query 才能切页签
    '$route.query.panel'(p) {
      if (['risk', 'archive', 'stats'].includes(p) && p !== this.tab) this.tab = p
    }
  },
  methods: {
    /** 页签切换同步到 URL，保证刷新/分享/左侧菜单高亮一致 */
    switchTab(t) {
      this.tab = t
      if (this.$route.query.panel !== t) this.$router.replace({ query: { ...this.$route.query, panel: t } })
    },
    async doScan() {
      const res = await graduationRiskArchiveApi.scanRisks()
      if (res.code === 0) { toast.success(res.message || '扫描完成'); this.loadRisks() } else toast.error(res.message)
    },
    /** 风险等级展示映射（不向老师透出内部英文枚举） */
    levelLabel(level) {
      return { LOW: '低', MEDIUM: '中', HIGH: '高', CRITICAL: '紧急' }[level] || level
    },
    selectRisk(row) {
      this.riskSelKey = String(row.id)
      this.$router.replace({ query: { ...this.$route.query, rsel: this.riskSelKey } })
    },
    stepRisk(d) {
      const i = this.riskSelIndex + d
      if (i >= 0 && i < this.riskRows.length) this.selectRisk(this.riskRows[i])
    },
    /** 保持/推进选中：处置后若开启自动下一条且当前已关闭，则跳到下一条待办风险 */
    ensureRiskSelection() {
      if (!this.riskRows.length) { this.riskSelKey = ''; return }
      const cur = this.selectedRisk
      const actionable = (r) => r.status === 'OPEN' || r.status === 'PROCESSING'
      if (cur && this.riskAutoNext && cur.status === 'CLOSED') {
        const from = this.riskSelIndex
        for (let i = from + 1; i < this.riskRows.length; i++) if (actionable(this.riskRows[i])) { this.selectRisk(this.riskRows[i]); return }
        for (let i = 0; i < from; i++) if (actionable(this.riskRows[i])) { this.selectRisk(this.riskRows[i]); return }
        return
      }
      if (!cur) {
        const target = this.riskRows.find(actionable) || this.riskRows[0]
        if (target) this.selectRisk(target)
      }
    },
    async loadRisks() {
      this.riskLoading = true
      this.riskError = ''
      const res = await graduationRiskArchiveApi.getRiskList({ ...this.riskFilters, page: this.riskPage, pageSize: this.riskPageSize })
      if (res.code === 0) { this.riskRows = res.data.list; this.riskTotal = res.data.total; this.ensureRiskSelection() } else { this.riskRows = []; this.riskError = res.message || '加载失败' }
      this.riskLoading = false
    },
    resetRiskFilters() { this.riskFilters = { status: '', level: '', dateStart: '', dateEnd: '' }; this.riskPage = 1; this.loadRisks() },
    doAccept(row) {
      this.confirm = { visible: true, title: '受理风险', message: `确认受理「${row.riskName}」（${row.studentName}）？`, type: 'primary', confirmText: '受理', requireReason: false, action: 'accept', row }
    },
    doProcess(row) {
      this.confirm = { visible: true, title: '记录处理', message: '', type: 'primary', confirmText: '提交', requireReason: true, reasonLabel: '处理说明', action: 'process', row }
    },
    doClose(row) {
      this.confirm = { visible: true, title: '关闭风险', message: '', type: 'danger', confirmText: '确认关闭', requireReason: true, reasonLabel: '关闭原因', action: 'close', row }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      let res
      if (action === 'accept') res = await graduationRiskArchiveApi.acceptRisk(row.id)
      else if (action === 'process') res = await graduationRiskArchiveApi.processRisk(row.id, reason || '')
      else if (action === 'close') res = await graduationRiskArchiveApi.closeRisk(row.id, reason || '')
      else if (action === 'reject-archive') res = await graduationRiskArchiveApi.rejectArchive(row.gdStudentId, reason || '')
      else if (action === 'batch-file') res = await graduationRiskArchiveApi.batchFileArchive()
      if (res && res.code === 0) {
        toast.success(action === 'batch-file' ? `已批量备案 ${res.data.filed} 份` : '已更新'); this.confirm.visible = false
        if (action === 'reject-archive' || action === 'batch-file') this.loadArchives(); else this.loadRisks()
      } else if (res) toast.error(res.message)
    },
    selectArchive(row) {
      this.archiveSelKey = String(row.id)
      this.$router.replace({ query: { ...this.$route.query, asel: this.archiveSelKey } })
    },
    stepArchive(d) {
      const i = this.archiveSelIndex + d
      if (i >= 0 && i < this.archiveRows.length) this.selectArchive(this.archiveRows[i])
    },
    ensureArchiveSelection() {
      if (!this.archiveRows.length) { this.archiveSelKey = ''; return }
      if (!this.selectedArchive) {
        const target = this.archiveRows.find((r) => r.status !== 'FILED') || this.archiveRows[0]
        if (target) this.selectArchive(target)
      }
    },
    /** 缺件补齐入口：按材料名称映射到真实业务工作区（带学生上下文） */
    goFix(item, row) {
      const sid = row.gdStudentId
      const name = (item || '').toString()
      if (name.includes('任务书')) return this.$router.push('/admin/graduation/process?panel=taskbook')
      if (name.includes('开题')) return this.$router.push('/admin/graduation/proposals')
      if (name.includes('中期')) return this.$router.push('/admin/graduation/process?panel=midterm')
      if (name.includes('指导')) return this.$router.push('/admin/graduation/process?panel=guidance')
      if (name.includes('查重')) return this.$router.push('/admin/graduation/defense-grade?panel=plagiarism')
      if (name.includes('评阅')) return this.$router.push('/admin/graduation/defense-grade?panel=review')
      if (name.includes('答辩')) return this.$router.push('/admin/graduation/defense')
      if (name.includes('成绩')) return this.$router.push('/admin/graduation/defense-grade?panel=grade')
      if (name.includes('成果') || name.includes('论文')) return this.$router.push('/admin/graduation/finals')
      if (sid) return this.$router.push('/admin/graduation/students/' + sid)
      this.$router.push('/admin/graduation/students')
    },
    async loadArchives() {
      this.archiveLoading = true
      this.archiveError = ''
      const res = await graduationRiskArchiveApi.getArchiveList({ ...this.archiveFilters, page: this.archivePage, pageSize: this.archivePageSize })
      if (res.code === 0) { this.archiveRows = res.data.list; this.archiveTotal = res.data.total; this.ensureArchiveSelection() } else { this.archiveRows = []; this.archiveError = res.message || '加载失败' }
      this.archiveLoading = false
    },
    resetArchiveFilters() { this.archiveFilters = { keyword: '', status: '', dateStart: '', dateEnd: '' }; this.archivePage = 1; this.loadArchives() },
    onStatsRangeChange() { this.loadStats() },
    async doGenerate(row) {
      const res = await graduationRiskArchiveApi.generateArchive(row.gdStudentId)
      if (res.code === 0) { toast.success('已生成'); this.loadArchives() } else toast.error(res.message)
    },
    async doSubmit(row) {
      const res = await graduationRiskArchiveApi.submitArchive(row.gdStudentId)
      if (res.code === 0) { toast.success('已提交'); this.loadArchives() } else toast.error(res.message)
    },
    async doFile(row) {
      const res = await graduationRiskArchiveApi.fileArchive(row.gdStudentId)
      if (res.code === 0) { toast.success('已归档'); this.loadArchives() } else toast.error(res.message)
    },
    doReject(row) {
      this.confirm = { visible: true, title: '驳回归档', message: '', type: 'danger', confirmText: '确认驳回', requireReason: true, reasonLabel: '驳回原因', action: 'reject-archive', row }
    },
    exportArchivesFn() {
      return graduationRiskArchiveApi.exportArchives({ ...this.archiveFilters })
    },
    async doBatchGenerate() {
      const res = await graduationRiskArchiveApi.batchGenerateArchive()
      if (res.code === 0) { toast.success(`已提交 ${res.data.submitted}，缺材料跳过 ${res.data.skipped}`); this.loadArchives() }
      else toast.error(res.message)
    },
    doBatchFile() {
      this.confirm = {
        visible: true, title: '一键核验备案',
        message: '系统将再次核验所有已提交归档记录，并将材料齐全的记录正式备案。备案后学生毕设阶段变为只读，是否继续？',
        type: 'warning', confirmText: '确认核验备案', requireReason: false, reasonLabel: '说明', action: 'batch-file', row: null
      }
    },
    async loadStats() {
      this.statsLoading = true
      this.statsError = ''
      const [o, c] = await Promise.all([graduationRiskArchiveApi.getOverviewStats(), graduationRiskArchiveApi.getCollegeComparison()])
      this.overview = o.code === 0 ? o.data : null
      this.collegeRows = c.code === 0 ? c.data : []
      if (o.code !== 0) this.statsError = o.message || '统计加载失败'
      this.statsLoading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.rk-split { display: flex; gap: var(--space-4); align-items: flex-start; }
.rk-list { width: 340px; flex: none; display: flex; flex-direction: column; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--card, #fff); box-shadow: 0 1px 2px rgba(15, 23, 42, .03); }
.rk-pane { flex: 1; min-width: 0; padding: var(--space-4); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--card, #fff); box-shadow: 0 1px 2px rgba(15, 23, 42, .03); }
.rk-rows { list-style: none; margin: 0; padding: 0; max-height: 600px; overflow-y: auto; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); }
.rk-row { padding: 10px 12px; border-bottom: 1px solid var(--border-light, #eef1f6); cursor: pointer; transition: background .12s ease, box-shadow .12s ease; }
.rk-row:last-child { border-bottom: none; }
.rk-row:hover { background: var(--gray-50, #f8fafc); }
.rk-row.is-active { background: var(--primary-50, #eff6ff); box-shadow: inset 2px 0 0 var(--brand-primary, #2563eb); }
.rk-row:focus-visible { position: relative; z-index: 1; outline: 2px solid var(--primary-400, #60a5fa); outline-offset: -2px; }
.rk-row__main { display: flex; align-items: center; gap: var(--space-2); }
.rk-row__name { font-weight: var(--font-weight-medium, 500); color: var(--text-primary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rk-row__sub { margin-top: 2px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.rk-row__meta { margin-top: 2px; display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-xs); color: var(--text-tertiary); }
.rk-row__idx { margin-left: auto; }
.rk-pane__bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-2) var(--space-3); margin-bottom: var(--space-3); background: var(--gray-50, #f8fafc); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); font-size: var(--font-size-sm); color: var(--text-secondary); }
.rk-pane__auto { display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.rk-pane__nav { margin-left: auto; display: inline-flex; gap: var(--space-3); }
.rk-pane__nav .mp-link:disabled { opacity: 0.4; cursor: not-allowed; }
.ar-missing { list-style: none; margin: var(--space-1) 0 0; padding: 0; }
.ar-missing__item { display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; border: 1px dashed var(--danger, #fca5a5); border-radius: var(--radius-md, 8px); margin-bottom: 6px; background: var(--danger-50, #fef2f2); font-size: var(--font-size-sm, 13px); }
.ar-missing__name { color: var(--danger, #dc2626); }
.mp-link--danger { color: var(--danger, #dc2626); }
.gp-tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--line, #e2e8f0); margin-bottom: var(--space-3); }
.gp-tabs__item { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--t2, #475569); border-bottom: 2px solid transparent; }
.gp-tabs__item.is-active { color: var(--pri, #2563eb); border-bottom-color: var(--pri, #2563eb); font-weight: 600; }
.gs-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-3); }
.gs-card { border: 1px solid var(--line, #e2e8f0); border-radius: 10px; padding: 12px; background: linear-gradient(145deg, var(--color-bg-subtle, #f8fafc), var(--card, #fff)); box-shadow: 0 1px 1px rgba(15, 23, 42, .02); }
.gs-card__label { font-size: 12px; color: var(--t3, #64748b); }
.gs-card__value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.gm-section-title { font-size: 13px; font-weight: 600; }
.gs-stage-list { list-style: none; margin: 8px 0; padding: 0; display: flex; gap: var(--space-4); flex-wrap: wrap; font-size: 13px; }
.ie-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-bottom: var(--space-3); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
@media (max-width: 1100px) { .rk-split { flex-direction: column; } .rk-list, .rk-pane { width: 100%; box-sizing: border-box; } .rk-pane { padding: var(--space-3); } }
</style>
