<template>
  <ModulePageShell
    title="学业预警 · 教务处控制台"
    subtitle="多维度分类（学分/挂科/绩点/补考重修/毕业风险）· 预警规则 · 跟进闭环 · 统计"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aawc-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aawc-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <!-- 预警看板 -->
    <div v-if="tab === 'dashboard'" class="mp-stack">
      <AppInlineAlert v-if="scanResult" type="success" :message="scanResultText" />
      <div class="aawc-bar">
        <AppButton variant="primary" size="small" :loading="scanning" @click="scanOne('all')">一键扫描 5 类规则</AppButton>
      </div>
      <LoadingState v-if="summaryLoading" />
      <ErrorState v-else-if="summaryError" :description="summaryError" @retry="loadSummary" />
      <template v-else>
        <div class="aawc-metric-grid">
          <div class="aawc-metric aawc-metric--total">
            <div class="aawc-metric__value">{{ summary.total }}</div>
            <div class="aawc-metric__label">在办预警总数（非已关闭）</div>
          </div>
          <div v-for="s in dashboardSources" :key="s.code" class="aawc-metric">
            <div class="aawc-metric__value">{{ s.count }}</div>
            <div class="aawc-metric__label">{{ s.label }}</div>
            <button class="mp-link" @click="jumpToCategory(s.code)">查看 →</button>
          </div>
        </div>
        <div class="aawc-section-title">按等级分布</div>
        <div class="aawc-bars">
          <div v-for="l in summary.byLevel" :key="l.level" class="aawc-bar-row">
            <span class="aawc-bar-label"><RiskTag :level="l.level" /></span>
            <span class="aawc-bar-track"><span class="aawc-bar-fill" :style="{ width: barWidth(l.count, summary.byLevel) }" /></span>
            <span class="aawc-bar-count">{{ l.count }}</span>
          </div>
          <p v-if="!summary.byLevel.length" class="mp-note">暂无在办预警</p>
        </div>
        <div class="aawc-section-title">按处理状态分布</div>
        <div class="aawc-bars">
          <div v-for="s in summary.byStatus" :key="s.status" class="aawc-bar-row">
            <span class="aawc-bar-label"><StatusTag :type="warningStatusColor(s.status)" :label="s.label" dot /></span>
            <span class="aawc-bar-track"><span class="aawc-bar-fill" :style="{ width: barWidth(s.count, summary.byStatus) }" /></span>
            <span class="aawc-bar-count">{{ s.count }}</span>
          </div>
        </div>
      </template>
    </div>

    <!-- 5 类分维度列表（学分/挂科/绩点/补考重修/毕业风险） -->
    <div v-else-if="category" class="mp-stack">
      <div class="aawc-bar">
        <AppButton variant="primary" size="small" :loading="scanning" @click="scanOne(category.scanKey)">扫描本类预警</AppButton>
        <AppInlineAlert v-if="scanResult" type="success" :message="scanResultText" />
      </div>
      <div class="aa-filter">
        <select v-model="catFilters.level" class="aa-select" @change="loadList">
          <option value="">全部级别</option>
          <option v-for="(l, v) in WARNING_LEVEL" :key="v" :value="v">{{ l }}</option>
        </select>
        <select v-model="catFilters.status" class="aa-select" @change="loadList">
          <option value="">全部状态</option>
          <option v-for="(l, v) in WARNING_STATUS" :key="v" :value="v">{{ l }}</option>
        </select>
      </div>
      <ErrorState v-if="listError" :description="listError" @retry="loadList" />
      <LoadingState v-else-if="listLoading" />
      <EmptyState v-else-if="!rows.length" :title="`暂无${category.label}`" :description="`点击「扫描本类预警」按规则生成，或前往「预警规则」调整阈值`" />
      <DataTable v-else :columns="listColumns" :rows="rows" row-key="warningId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-level="{ row }"><RiskTag :level="row.level" /></template>
        <template #cell-status="{ row }"><StatusTag :type="warningStatusColor(row.status)" :label="WARNING_STATUS[row.status] || row.status" dot /></template>
        <template #cell-ops="{ row }"><button class="mp-link" @click="openFollowup(row.warningId)">跟进 →</button></template>
      </DataTable>
    </div>

    <!-- 预警规则 -->
    <div v-else-if="tab === 'rules'" class="mp-stack">
      <ErrorState v-if="rulesError" :description="rulesError" @retry="loadRules" />
      <LoadingState v-else-if="rulesLoading" />
      <template v-else>
        <AppInlineAlert type="info" description="调整后立即生效于下次扫描；仅教务处可配置（academicAffairs.warning.rule.manage）。" />
        <div v-for="r in rules" :key="r.key" class="aawc-rule-row">
          <div class="aawc-rule-info">
            <div class="aawc-rule-label">{{ r.label }}</div>
            <div class="mp-cell-sub">当前值：{{ r.value }}（默认 {{ r.default }}，范围 {{ r.min }}~{{ r.max }}）</div>
          </div>
          <div class="aawc-rule-edit">
            <AppNumberInput v-model="ruleEdits[r.key]" :step="r.type === 'int' ? 1 : 0.05" :min="r.min" :max="r.max" />
            <AppButton size="small" variant="primary" :loading="ruleSaving === r.key" @click="saveRuleValue(r)">保存</AppButton>
          </div>
        </div>
      </template>
    </div>

    <!-- 预警跟进 -->
    <div v-else-if="tab === 'followup'" class="mp-stack">
      <div class="aa-filter">
        <select v-model="followFilters.status" class="aa-select" @change="loadFollowList">
          <option value="">全部状态</option>
          <option v-for="(l, v) in WARNING_STATUS" :key="v" :value="v">{{ l }}</option>
        </select>
        <select v-model="followFilters.sourceCode" class="aa-select" @change="loadFollowList">
          <option value="">全部来源</option>
          <option v-for="(l, v) in WARNING_SOURCE" :key="v" :value="v">{{ l }}</option>
        </select>
      </div>
      <ErrorState v-if="listError" :description="listError" @retry="loadFollowList" />
      <LoadingState v-else-if="listLoading" />
      <EmptyState v-else-if="!rows.length" title="暂无预警" description="调整筛选条件，或前往「预警看板」执行扫描" />
      <DataTable v-else :columns="followColumns" :rows="rows" row-key="warningId" :pagination="pagination" @page-change="onFollowPageChange">
        <template #cell-level="{ row }"><RiskTag :level="row.level" /></template>
        <template #cell-status="{ row }"><StatusTag :type="warningStatusColor(row.status)" :label="WARNING_STATUS[row.status] || row.status" dot /></template>
        <template #cell-ops="{ row }"><button class="mp-link" @click="openFollowup(row.warningId)">处理 →</button></template>
      </DataTable>

      <AppDrawer :visible="detailVisible" title="预警跟进" @close="detailVisible = false">
        <div v-if="detailLoading" class="mp-note">加载中…</div>
        <ErrorState v-else-if="detailError" :description="detailError" @retry="() => openFollowup(detailId)" />
        <div v-else-if="detail" class="mp-stack">
          <section class="mp-card">
            <div class="mp-card__head">
              <span class="mp-card__title">{{ detail.student ? detail.student.studentName : '学生' }}</span>
              <span><RiskTag :level="detail.warning.level" /><StatusTag :type="warningStatusColor(detail.warning.status)" :label="WARNING_STATUS[detail.warning.status]" dot style="margin-left:8px" /></span>
            </div>
            <div class="mp-card__body">
              <div class="mp-kv"><span class="mp-kv__k">来源</span><span class="mp-kv__v">{{ detail.warning.sourceLabel }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">原因</span><span class="mp-kv__v">{{ detail.warning.reason }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">跟进人</span><span class="mp-kv__v">{{ detail.warning.owner || '未分配' }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">已提醒</span><span class="mp-kv__v">{{ detail.warning.remindCount }} 次</span></div>
              <div v-if="detail.student" class="mp-kv"><span class="mp-kv__k">班级</span><span class="mp-kv__v">{{ detail.student.className }}（{{ detail.student.collegeName }}）</span></div>
              <div v-if="detail.student" class="mp-kv"><span class="mp-kv__k">GPA / 学分</span><span class="mp-kv__v">{{ detail.student.gpa.toFixed(1) }} / {{ detail.student.obtainedCredits }}·{{ detail.student.requiredCredits }}</span></div>
            </div>
          </section>

          <section class="mp-card">
            <div class="mp-card__head"><span class="mp-card__title">跟进记录（{{ detail.interventions.length }}）</span></div>
            <div class="mp-card__body">
              <ul v-if="detail.interventions.length" class="mp-timeline">
                <li v-for="i in detail.interventions" :key="i.id" class="mp-timeline__item">
                  <div class="mp-timeline__title">{{ wayLabel(i.way) }} · {{ i.operator }}</div>
                  <div class="mp-timeline__desc">{{ i.content }}</div>
                  <div class="mp-timeline__time">{{ i.time }}</div>
                </li>
              </ul>
              <p v-else class="mp-note">暂无跟进记录</p>
            </div>
          </section>

          <AppActionBar>
            <AppButton size="small" :disabled="isClosed" @click="assignVisible = true">指派</AppButton>
            <AppButton size="small" :disabled="isClosed" @click="followVisible = true">＋ 新增跟进</AppButton>
            <AppButton size="small" variant="ghost" :disabled="isClosed" @click="remind">提醒</AppButton>
            <AppButton size="small" variant="warning" :disabled="isClosed" @click="escalateVisible = true">升级</AppButton>
            <AppButton size="small" variant="primary" :disabled="isClosed" @click="closeVisible = true">关闭</AppButton>
            <AppButton size="small" variant="danger" :disabled="detail.warning.recordStatus === 'VOIDED'" @click="voidVisible = true">作废（误报）</AppButton>
          </AppActionBar>
        </div>
      </AppDrawer>

      <AppDrawer :visible="assignVisible" title="指派跟进人" @close="assignVisible = false">
        <AppFormItem label="跟进人姓名" required><AppTextInput v-model="assignForm.ownerName" placeholder="如 王老师" :disabled="acting" /></AppFormItem>
        <AppFormItem label="跟进人用户ID（可选）"><AppTextInput v-model="assignForm.ownerId" placeholder="用于生成对方工作台待办" :disabled="acting" /></AppFormItem>
        <template #footer>
          <AppButton variant="ghost" :disabled="acting" @click="assignVisible = false">取消</AppButton>
          <AppButton variant="primary" :loading="acting" @click="submitAssign">确认指派</AppButton>
        </template>
      </AppDrawer>

      <AppDrawer :visible="followVisible" title="新增跟进记录" @close="followVisible = false">
        <AppFormItem label="跟进方式" required>
          <AppSelect v-model="followForm.way" :options="wayOptions" :disabled="acting" />
        </AppFormItem>
        <AppFormItem label="跟进内容" required>
          <AppTextarea ref="followInput" v-model="followForm.content" placeholder="记录本次跟进过程与学生情况（不少于5字）" :disabled="acting" />
          <AppQuickPhrases scene-key="aa.warning.follow" @pick="onPickFollow" />
        </AppFormItem>
        <AppFormItem label="跟进结果"><AppTextInput v-model="followForm.result" :disabled="acting" /></AppFormItem>
        <AppFormItem label="下一步计划"><AppTextInput v-model="followForm.nextPlan" :disabled="acting" /></AppFormItem>
        <template #footer>
          <AppButton variant="ghost" :disabled="acting" @click="followVisible = false">取消</AppButton>
          <AppButton variant="primary" :loading="acting" @click="submitFollowup">提交跟进</AppButton>
        </template>
      </AppDrawer>

      <AppConfirmDialog v-model:visible="escalateVisible" type="warning" title="升级预警" message="确认升级该预警为高风险？升级后需学院教务/教务处跟进关闭。" confirm-text="确认升级" require-reason phrase-scene-key="aa.warning.escalate" reason-label="升级说明" reason-placeholder="请说明升级依据（不少于5字）" :submitting="acting" @confirm="submitEscalate" />
      <AppConfirmDialog v-model:visible="closeVisible" type="primary" title="关闭预警" message="确认关闭该预警？" confirm-text="确认关闭" require-reason phrase-scene-key="aa.warning.close" reason-label="关闭说明" reason-placeholder="请说明关闭依据，如成绩回升/学分补齐（不少于5字）" :submitting="acting" @confirm="submitClose" />
      <AppConfirmDialog v-model:visible="voidVisible" type="danger" title="作废预警（误报）" message="作废为逻辑处理，预警与处理过程保留可追溯。" confirm-text="确认作废" require-reason phrase-scene-key="aa.warning.void" reason-label="误报说明" reason-placeholder="请说明误报原因（不少于5字）" :submitting="acting" @confirm="submitVoid" />
    </div>

    <!-- 预警统计 -->
    <div v-else-if="tab === 'stats'" class="mp-stack">
      <LoadingState v-if="summaryLoading" />
      <ErrorState v-else-if="summaryError" :description="summaryError" @retry="loadSummary" />
      <template v-else>
        <div class="aawc-metric-grid">
          <div class="aawc-metric aawc-metric--total"><div class="aawc-metric__value">{{ summary.total }}</div><div class="aawc-metric__label">在办预警总数</div></div>
        </div>
        <div class="aawc-section-title">按来源分布</div>
        <div class="aawc-bars">
          <div v-for="s in summary.bySource" :key="s.code" class="aawc-bar-row">
            <span class="aawc-bar-label">{{ s.label }}</span>
            <span class="aawc-bar-track"><span class="aawc-bar-fill" :style="{ width: barWidth(s.count, summary.bySource) }" /></span>
            <span class="aawc-bar-count">{{ s.count }}</span>
          </div>
        </div>
        <div class="aawc-section-title">按等级分布</div>
        <div class="aawc-bars">
          <div v-for="l in summary.byLevel" :key="l.level" class="aawc-bar-row">
            <span class="aawc-bar-label"><RiskTag :level="l.level" /></span>
            <span class="aawc-bar-track"><span class="aawc-bar-fill" :style="{ width: barWidth(l.count, summary.byLevel) }" /></span>
            <span class="aawc-bar-count">{{ l.count }}</span>
          </div>
        </div>
        <p class="mp-note">明细下钻请前往对应分类页签（挂科/学分/绩点/补考重修/毕业风险）查看名单；导出走各分类列表的教务统计域导出。</p>
      </template>
    </div>

    <!-- 预警通知 -->
    <div v-else-if="tab === 'notify'" class="mp-stack">
      <AppInlineAlert type="info" description="预警首次生成或再扫描升级等级时，系统自动通知学生本人与责任辅导员；「预警跟进」页的「提醒」按钮会追加一条人工提醒通知。以下为推送台账（站内通知，只读）。" />
      <LoadingState v-if="notifySummaryLoading" />
      <div v-else class="aawc-metric-grid">
        <div class="aawc-metric aawc-metric--total"><div class="aawc-metric__value">{{ notifySummary.total }}</div><div class="aawc-metric__label">累计已发通知</div></div>
        <div class="aawc-metric"><div class="aawc-metric__value">{{ notifySummary.unread }}</div><div class="aawc-metric__label">未读</div></div>
        <div class="aawc-metric"><div class="aawc-metric__value">{{ notifySummary.read }}</div><div class="aawc-metric__label">已读</div></div>
      </div>
      <ErrorState v-if="notifyError" :description="notifyError" @retry="loadNotifications" />
      <LoadingState v-else-if="notifyLoading" />
      <EmptyState v-else-if="!notifyRows.length" title="暂无预警通知" description="预警生成/升级，或在「预警跟进」页对某条预警点击「提醒」后，通知会在此留痕" />
      <DataTable v-else :columns="notifyColumns" :rows="notifyRows" row-key="id" :pagination="notifyPagination" @page-change="onNotifyPageChange">
        <template #cell-level="{ row }"><RiskTag :level="row.level" /></template>
        <template #cell-receiverType="{ row }">{{ NOTIFY_RECEIVER[row.receiverType] || row.receiverType }}</template>
        <template #cell-scene="{ row }">{{ NOTIFY_SCENE[row.scene] || row.scene }}</template>
        <template #cell-status="{ row }"><StatusTag :type="notifyStatusColor(row.status)" :label="NOTIFY_STATUS[row.status] || row.status" dot /></template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 学业预警 · 教务处控制台（/admin/academic-affairs/warnings/console）。
 * 10 个页签：看板 / 学分·挂科·绩点·补考重修·毕业风险（多维分类列表）/ 规则 / 跟进 / 统计 / 通知。
 * 通知页只读展示 t_unified_message 推送台账（预警生成/升级自动通知 + 跟进页「提醒」人工通知，见
 * academic_affairs_warning_service._push_warning_notice），不重复造发通知的写操作入口。
 * 「预警扫描与列表」单页（AaWarningView.vue，/admin/academic-affairs/warnings）保持不变，两页并存、数据同源（t_acad_warning）。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag as StatusTag, AppRiskTag as RiskTag, AppInlineAlert, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppNumberInput, AppConfirmDialog, AppActionBar, AppQuickPhrases } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi, academicAffairsWarningApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import {
  WARNING_LEVEL, WARNING_SOURCE, WARNING_STATUS, warningStatusColor,
  NOTIFY_SCENE, NOTIFY_RECEIVER, NOTIFY_STATUS, notifyStatusColor
} from '@/modules/academicAffairs/constants/grade-graduation'
import { toast } from '@/utils/toast'

// scanKey 对应 academicAffairsWarningApi.scan(key)：fail 历史挂 /warnings/scan，其余挂 /warnings/scan/{key}
const CATEGORY_BY_TAB = {
  credit: { sourceCode: 'CREDIT_SHORT', scanKey: 'credit', label: '学分预警' },
  fail: { sourceCode: 'EXAM_FAIL', scanKey: 'fail', label: '挂科预警' },
  gpa: { sourceCode: 'LOW_GPA', scanKey: 'gpa', label: '绩点预警' },
  retake: { sourceCode: 'RETAKE_EXCESS', scanKey: 'retake', label: '补考重修预警' },
  graduation: { sourceCode: 'GRAD_ABNORMAL', scanKey: 'graduation', label: '毕业风险预警' }
}

export default {
  name: 'AaWarningConsoleView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, StatusTag, RiskTag, AppInlineAlert,
    AppFormItem, AppTextInput, AppTextarea, AppSelect, AppNumberInput, AppConfirmDialog, AppActionBar, AppQuickPhrases,
    AppButton, AppDrawer
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      WARNING_LEVEL, WARNING_SOURCE, WARNING_STATUS, NOTIFY_SCENE, NOTIFY_RECEIVER, NOTIFY_STATUS,
      tab: 'dashboard',
      tabs: [
        { key: 'dashboard', label: '预警看板' },
        { key: 'credit', label: '学分预警' },
        { key: 'fail', label: '挂科预警' },
        { key: 'gpa', label: '绩点预警' },
        { key: 'retake', label: '补考重修预警' },
        { key: 'graduation', label: '毕业风险预警' },
        { key: 'rules', label: '预警规则' },
        { key: 'followup', label: '预警跟进' },
        { key: 'stats', label: '预警统计' },
        { key: 'notify', label: '预警通知' }
      ],
      scanning: false, scanResult: null,
      summary: { total: 0, bySource: [], byLevel: [], byStatus: [] }, summaryLoading: true, summaryError: '',
      rows: [], listLoading: false, listError: '',
      pagination: { page: 1, pageSize: 20, total: 0 },
      catFilters: { level: '', status: '' },
      followFilters: { status: '', sourceCode: '' },
      listColumns: [
        { key: 'studentName', title: '学生' }, { key: 'className', title: '班级' }, { key: 'level', title: '级别' },
        { key: 'reason', title: '原因' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }
      ],
      followColumns: [
        { key: 'studentName', title: '学生' }, { key: 'sourceLabel', title: '来源' }, { key: 'level', title: '级别' },
        { key: 'owner', title: '跟进人' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }
      ],
      notifyRows: [], notifyLoading: false, notifyError: '',
      notifyPagination: { page: 1, pageSize: 20, total: 0 },
      notifySummary: { total: 0, unread: 0, read: 0 }, notifySummaryLoading: true,
      notifyColumns: [
        { key: 'studentName', title: '学生' }, { key: 'sourceLabel', title: '预警来源' },
        { key: 'level', title: '级别' }, { key: 'receiverType', title: '接收对象' },
        { key: 'title', title: '通知标题' }, { key: 'scene', title: '触发场景' },
        { key: 'status', title: '状态' }, { key: 'sentAt', title: '发送时间' }
      ],
      rulesLoading: true, rulesError: '', rules: [], ruleEdits: {}, ruleSaving: '',
      detailVisible: false, detailLoading: false, detailError: '', detailId: '', detail: null,
      assignVisible: false, assignForm: { ownerId: '', ownerName: '' },
      followVisible: false, followForm: { way: 'TALK', content: '', result: '', nextPlan: '' },
      escalateVisible: false, closeVisible: false, voidVisible: false, acting: false,
      wayOptions: [
        { value: 'TALK', label: '当面谈话' }, { value: 'PHONE', label: '电话联系' },
        { value: 'FAMILY', label: '家校联系' }, { value: 'PLAN', label: '帮扶计划' }
      ]
    }
  },
  computed: {
    category() { return CATEGORY_BY_TAB[this.tab] || null },
    dashboardSources() { return this.summary.bySource },
    scanResultText() {
      if (!this.scanResult) return ''
      if (this.scanResult.created !== undefined) return `扫描完成：新增 ${this.scanResult.created} · 更新 ${this.scanResult.updated}`
      const keys = Object.keys(this.scanResult)
      const c = keys.reduce((s, k) => s + (this.scanResult[k].created || 0), 0)
      const u = keys.reduce((s, k) => s + (this.scanResult[k].updated || 0), 0)
      return `一键扫描完成：合计新增 ${c} · 更新 ${u}`
    },
    isClosed() { return !this.detail || this.detail.warning.status === 'CLOSED' || this.detail.warning.recordStatus === 'VOIDED' }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.enter()
  },
  methods: {
    warningStatusColor,
    onPickFollow(text) {
      const el = this.$refs.followInput && this.$refs.followInput.$refs.el
      const { value, selStart, selEnd } = insertAtCursor(el, this.followForm.content, text)
      this.followForm.content = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    wayLabel(w) { return (this.wayOptions.find((o) => o.value === w) || {}).label || w },
    barWidth(count, list) {
      const max = Math.max(1, ...(list || []).map((s) => s.count))
      return `${Math.max(4, Math.round((count / max) * 100))}%`
    },
    switchTab(k) {
      this.tab = k
      this.$router.replace({ query: { ...this.$route.query, tab: k } }).catch(() => {})
      this.enter()
    },
    jumpToCategory(sourceCode) {
      const key = Object.keys(CATEGORY_BY_TAB).find((k) => CATEGORY_BY_TAB[k].sourceCode === sourceCode)
      if (key) this.switchTab(key)
    },
    enter() {
      this.scanResult = null
      if (this.tab === 'dashboard') this.loadSummary()
      else if (this.category) { this.pagination.page = 1; this.loadList() }
      else if (this.tab === 'rules') this.loadRules()
      else if (this.tab === 'followup') { this.pagination.page = 1; this.loadFollowList() }
      else if (this.tab === 'stats') this.loadSummary()
      else if (this.tab === 'notify') { this.notifyPagination.page = 1; this.loadNotifications(); this.loadNotifySummary() }
    },
    async loadSummary() {
      this.summaryLoading = true; this.summaryError = ''
      const res = await api.summary()
      if (res.code === 0) this.summary = res.data
      else this.summaryError = res.message
      this.summaryLoading = false
    },
    async loadList() {
      if (!this.category) return
      this.listLoading = true; this.listError = ''
      const res = await api.list({
        sourceCode: this.category.sourceCode, level: this.catFilters.level || undefined,
        status: this.catFilters.status || undefined, page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else this.listError = res.message
      this.listLoading = false
    },
    onPageChange(p) { this.pagination.page = p; this.loadList() },
    async loadFollowList() {
      this.listLoading = true; this.listError = ''
      const res = await api.list({
        status: this.followFilters.status || undefined, sourceCode: this.followFilters.sourceCode || undefined,
        page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else this.listError = res.message
      this.listLoading = false
    },
    onFollowPageChange(p) { this.pagination.page = p; this.loadFollowList() },
    notifyStatusColor,
    async loadNotifySummary() {
      this.notifySummaryLoading = true
      const res = await api.notificationSummary()
      if (res.code === 0) this.notifySummary = res.data
      this.notifySummaryLoading = false
    },
    async loadNotifications() {
      this.notifyLoading = true; this.notifyError = ''
      const res = await api.notifications({ page: this.notifyPagination.page, pageSize: this.notifyPagination.pageSize })
      if (res.code === 0) { this.notifyRows = res.data.list; this.notifyPagination.total = res.data.total }
      else this.notifyError = res.message
      this.notifyLoading = false
    },
    onNotifyPageChange(p) { this.notifyPagination.page = p; this.loadNotifications() },
    async scanOne(key) {
      if (this.scanning) return
      this.scanning = true
      const res = await api.scan(key)
      this.scanning = false
      if (res.code === 0) {
        this.scanResult = res.data
        toast.success('扫描完成')
        if (this.tab === 'dashboard') this.loadSummary()
        else if (this.category) this.loadList()
      } else toast.error(res.message || '扫描失败')
    },
    async loadRules() {
      this.rulesLoading = true; this.rulesError = ''
      const res = await api.getRules()
      if (res.code === 0) {
        this.rules = res.data.items
        this.ruleEdits = Object.fromEntries(this.rules.map((r) => [r.key, r.value]))
      } else this.rulesError = res.message
      this.rulesLoading = false
    },
    async saveRuleValue(r) {
      this.ruleSaving = r.key
      const res = await api.saveRule(r.key, this.ruleEdits[r.key])
      this.ruleSaving = ''
      if (res.code === 0) { toast.success('规则已保存，下次扫描生效'); this.loadRules() }
      else toast.error(res.message)
    },
    async openFollowup(warningId) {
      this.detailId = warningId
      this.detailVisible = true
      this.detailLoading = true
      this.detailError = ''
      const res = await api.detail(warningId)
      this.detailLoading = false
      if (res.code === 0) this.detail = res.data
      else this.detailError = res.message
    },
    reloadDetailAndList() {
      this.openFollowup(this.detailId)
      if (this.tab === 'followup') this.loadFollowList()
      else if (this.category) this.loadList()
    },
    async submitAssign() {
      if (!this.assignForm.ownerName) { toast.error('请填写跟进人姓名'); return }
      this.acting = true
      const res = await api.assign(this.detailId, this.assignForm.ownerId || undefined, this.assignForm.ownerName)
      this.acting = false
      if (res.code === 0) { toast.success('已指派'); this.assignVisible = false; this.assignForm = { ownerId: '', ownerName: '' }; this.reloadDetailAndList() }
      else toast.error(res.message)
    },
    async submitFollowup() {
      if (!this.followForm.content || this.followForm.content.trim().length < 5) { toast.error('跟进内容不少于5字'); return }
      this.acting = true
      const res = await api.addIntervention(this.detailId, this.followForm)
      this.acting = false
      if (res.code === 0) { toast.success('跟进已记录'); this.followVisible = false; this.followForm = { way: 'TALK', content: '', result: '', nextPlan: '' }; this.reloadDetailAndList() }
      else toast.error(res.message)
    },
    async remind() {
      const res = await api.remind(this.detailId)
      if (res.code === 0) {
        const n = res.data && res.data.notified
        toast.success(n ? `已提醒，推送通知 ${n} 条` : '已提醒（未解析到可通知对象，请检查该生班级/辅导员绑定）')
        this.reloadDetailAndList()
      } else toast.error(res.message)
    },
    async submitEscalate({ reason }) {
      this.acting = true
      const res = await api.escalate(this.detailId, reason)
      this.acting = false
      if (res.code === 0) { toast.success('已升级'); this.escalateVisible = false; this.reloadDetailAndList() } else toast.error(res.message)
    },
    async submitClose({ reason }) {
      this.acting = true
      const res = await api.close(this.detailId, reason)
      this.acting = false
      if (res.code === 0) { toast.success('已关闭'); this.closeVisible = false; this.reloadDetailAndList() } else toast.error(res.message)
    },
    async submitVoid({ reason }) {
      this.acting = true
      const res = await api.void(this.detailId, reason)
      this.acting = false
      if (res.code === 0) { toast.success('已作废'); this.voidVisible = false; this.reloadDetailAndList() } else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aawc-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; flex-wrap: wrap; }
.aawc-tab { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; white-space: nowrap; }
.aawc-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aawc-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
.aa-filter { display: flex; gap: 12px; align-items: center; }
.aa-select { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aawc-metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 8px; }
.aawc-metric { padding: 16px; background: var(--fill-light, #f8fafc); border-radius: 10px; }
.aawc-metric--total { background: var(--primary-50, #eff6ff); }
.aawc-metric__value { font-size: 26px; font-weight: 700; color: var(--primary-color, #2563eb); }
.aawc-metric__label { margin-top: 4px; font-size: 13px; color: var(--text-secondary, #64748b); }
.aawc-section-title { font-weight: 500; margin: 12px 0 8px; font-size: 14px; }
.aawc-bars { display: flex; flex-direction: column; gap: 8px; }
.aawc-bar-row { display: flex; align-items: center; gap: 10px; }
.aawc-bar-label { width: 110px; flex-shrink: 0; font-size: 13px; }
.aawc-bar-track { flex: 1; height: 10px; background: var(--fill-light, #f1f5f9); border-radius: 5px; overflow: hidden; }
.aawc-bar-fill { display: block; height: 100%; background: var(--primary-color, #2563eb); border-radius: 5px; }
.aawc-bar-count { width: 40px; text-align: right; font-size: 13px; color: var(--text-secondary, #64748b); }
.aawc-rule-row { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; background: var(--fill-light, #f8fafc); border-radius: 10px; }
.aawc-rule-label { font-size: 14px; font-weight: 500; }
.aawc-rule-edit { display: flex; align-items: center; gap: 8px; }
.aawc-rule-edit :deep(.app-number-input), .aawc-rule-edit :deep(input) { width: 100px; }
</style>
