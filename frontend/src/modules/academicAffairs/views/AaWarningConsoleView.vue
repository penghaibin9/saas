<template>
  <ModulePageShell
    :title="tabTitle"
    subtitle="多维度分类（学分/挂科/绩点/补考重修/毕业风险）· 预警规则 · 跟进闭环 · 统计"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <div class="aawc-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aawc-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <section v-if="actionReceipt" class="aawc-receipt" role="status">
      <div><strong>{{ actionReceipt.verified ? '✓' : '…' }} {{ actionReceipt.title }}</strong><span>{{ actionReceipt.studentName }} · 当前预警对象</span></div>
      <div><small>处理结果</small><b>{{ actionReceipt.result }}</b></div>
      <div><small>下一步</small><b>{{ actionReceipt.next }}</b></div>
      <AppButton size="small" variant="ghost" @click="reopenReceipt">查看该生预警</AppButton>
    </section>

    <!-- 预警看板 -->
    <div v-if="tab === 'dashboard'" class="mp-stack">
      <AppInlineAlert v-if="scanResult" type="success" :message="scanResultText" />
      <div class="aawc-bar">
        <AppButton variant="primary" size="small" :loading="scanning" :disabled="!canRule || !!scanPending" @click="askScan('all')">扫描全部预警规则</AppButton>
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
        <AppButton variant="primary" size="small" :loading="scanning" :disabled="!canRule || !!scanPending" @click="askScan(category.scanKey)">扫描本类预警</AppButton>
        <AppInlineAlert v-if="scanResult" type="success" :message="scanResultText" />
      </div>
      <div class="aa-filter">
        <AppSelect v-model="catFilters.level" :options="warningLevelOptions" placeholder="全部级别" @change="loadList" />
        <AppSelect v-model="catFilters.status" :options="warningStatusOptions" placeholder="全部状态" @change="loadList" />
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
            <AppButton size="small" variant="primary" :loading="ruleSaving === r.key" :disabled="!canRule" @click="saveRuleValue(r)">保存</AppButton>
          </div>
        </div>
      </template>
    </div>

    <!-- 预警跟进 -->
    <div v-else-if="tab === 'followup'" class="mp-stack">
      <div class="aa-filter">
        <AppSelect v-model="followFilters.status" :options="warningStatusOptions" placeholder="全部状态" @change="loadFollowList" />
        <AppSelect v-model="followFilters.sourceCode" :options="warningSourceOptions" placeholder="全部来源" @change="loadFollowList" />
      </div>
      <ErrorState v-if="listError" :description="listError" @retry="loadFollowList" />
      <LoadingState v-else-if="listLoading" />
      <EmptyState v-else-if="!rows.length" title="暂无预警" description="调整筛选条件，或前往「预警看板」执行扫描" />
      <DataTable v-else :columns="followColumns" :rows="rows" row-key="warningId" :pagination="pagination" @page-change="onFollowPageChange">
        <template #cell-level="{ row }"><RiskTag :level="row.level" /></template>
        <template #cell-status="{ row }"><StatusTag :type="warningStatusColor(row.status)" :label="WARNING_STATUS[row.status] || row.status" dot /></template>
        <template #cell-ops="{ row }"><button class="mp-link" @click="openFollowup(row.warningId)">处理 →</button></template>
      </DataTable>

      <AppDrawer :visible="detailVisible" title="预警跟进" mode="modal" size="xlarge" @close="detailVisible = false">
        <div v-if="detailLoading" class="mp-note">加载中…</div>
        <ErrorState v-else-if="detailError" :description="detailError" @retry="() => openFollowup(detailId)" />
        <div v-else-if="detail" class="mp-stack">
          <section class="mp-card">
            <div class="mp-card__head">
              <span class="mp-card__title">{{ detail.student ? detail.student.studentName : '学生' }}</span>
              <span><RiskTag :level="detail.warning.level" /><StatusTag :type="warningStatusColor(detail.warning.status)" :label="WARNING_STATUS[detail.warning.status]" dot style="margin-left:8px" /></span>
            </div>
            <div class="mp-card__body">
              <AppDescriptionList :items="detailDescItems" :columns="2" />
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
            <AppButton size="small" :disabled="isClosed || !canHandle || !!actionPending" @click="assignVisible = true">指派</AppButton>
            <AppButton size="small" :disabled="isClosed || !canHandle || !!actionPending" @click="followVisible = true">＋ 新增跟进</AppButton>
            <AppButton size="small" variant="ghost" :disabled="isClosed || !canHandle || !!actionPending" @click="remind">提醒</AppButton>
            <AppButton size="small" variant="warning" :disabled="isClosed || !canHandle || !!actionPending" @click="escalateVisible = true">升级</AppButton>
            <AppButton size="small" variant="primary" :disabled="isClosed || !canHandle || !!actionPending" @click="closeVisible = true">关闭</AppButton>
            <AppButton size="small" variant="danger" :disabled="detail.warning.recordStatus === 'VOIDED' || !canHandle || !!actionPending" @click="voidVisible = true">作废（误报）</AppButton>
          </AppActionBar>
        </div>
      </AppDrawer>

      <AppDrawer :visible="assignVisible" title="指派跟进人" mode="modal" size="small" @close="assignVisible = false">
        <AppFormItem label="跟进人" required><AppTeacherPicker v-model="assignForm.ownerId" placeholder="选择跟进教师" :disabled="acting" @change="onOwnerPicked" /></AppFormItem>
        <template #footer>
          <AppButton variant="ghost" :disabled="acting" @click="assignVisible = false">取消</AppButton>
          <AppButton variant="primary" :loading="acting" @click="submitAssign">确认指派</AppButton>
        </template>
      </AppDrawer>

      <AppDrawer :visible="followVisible" title="新增跟进记录" mode="modal" size="medium" @close="followVisible = false">
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
    <AppConfirmDialog v-model:visible="scanConfirm.visible" title="确认执行预警扫描" :message="scanConfirm.message" confirm-text="按当前规则扫描" :submitting="scanning" @confirm="scanOne" />
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
import { AppStatusTag as StatusTag, AppRiskTag as RiskTag, AppInlineAlert, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppNumberInput, AppConfirmDialog, AppActionBar, AppQuickPhrases, AppDescriptionList, AppTeacherPicker } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsWarningApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import {
  WARNING_LEVEL, WARNING_SOURCE, WARNING_STATUS, warningStatusColor,
  NOTIFY_SCENE, NOTIFY_RECEIVER, NOTIFY_STATUS, notifyStatusColor
} from '@/modules/academicAffairs/constants/grade-graduation'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'
import { gradeError } from './parallel-c/grade-review'

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
    AppFormItem, AppTextInput, AppTextarea, AppSelect, AppNumberInput, AppConfirmDialog, AppActionBar, AppQuickPhrases, AppTeacherPicker,
    AppDescriptionList, AppButton, AppDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      alive: true, scope: 0, readSeq: {},
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
      scanning: false, scanResult: null, scanPending: null, scanConfirm: { visible: false, key: '', rules: [], message: '' },
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
      rulesLoading: true, rulesError: '', rules: [], ruleEdits: {}, ruleSaving: '', ruleUncertain: {},
      detailVisible: false, detailLoading: false, detailError: '', detailId: '', detail: null,
      actionReceipt: null, actionPending: null,
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
    tabTitle() { return this.tabs.find(item => item.key === this.tab)?.label || '学业预警' },
    identity() { const u=currentUserFromToken()||{}; return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns]) },
    canHandle() { return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.warning.handle') },
    canRule() { return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.warning.rule.manage') },
    warningLevelOptions() { return Object.entries(WARNING_LEVEL).map(([value, label]) => ({ value, label })) },
    warningStatusOptions() { return Object.entries(WARNING_STATUS).map(([value, label]) => ({ value, label })) },
    warningSourceOptions() { return Object.entries(WARNING_SOURCE).map(([value, label]) => ({ value, label })) },
    category() { return CATEGORY_BY_TAB[this.tab] || null },
    dashboardSources() { return this.summary.bySource },
    scanResultText() {
      if (!this.scanResult) return ''
      if (this.scanResult.pending) return '扫描结果待核实：请读取当前名单，不要重复执行扫描。'
      if (this.scanResult.created !== undefined) return `扫描完成：新增 ${this.scanResult.created} · 更新 ${this.scanResult.updated} · ${this.scanResult.notificationState==='VERIFIED'&&Number.isFinite(this.scanResult.notified)?`通知对象 ${this.scanResult.notified} 个`:'通知结果待核对'}`
      const keys = Object.keys(this.scanResult)
      const c = keys.reduce((s, k) => s + (this.scanResult[k].created || 0), 0)
      const u = keys.reduce((s, k) => s + (this.scanResult[k].updated || 0), 0)
      return `一键扫描完成：合计新增 ${c} · 更新 ${u}`
    },
    isClosed() { return !this.detail || this.detail.warning.status === 'CLOSED' || this.detail.warning.recordStatus === 'VOIDED' },
    detailDescItems() {
      if (!this.detail) return []
      const w = this.detail.warning
      const s = this.detail.student
      const items = [
        { label: '来源', value: w.sourceLabel },
        { label: '原因', value: w.reason, span: 2 },
        { label: '跟进人', value: w.owner || '未分配' },
        { label: '已提醒', value: `${w.remindCount} 次` }
      ]
      if (s) {
        items.push({ label: '班级', value: `${s.className}（${s.collegeName}）` })
        const gpa=Number.isFinite(Number(s.gpa))?Number(s.gpa).toFixed(1):'待核对'
        const credits=s.obtainedCredits==null||s.requiredCredits==null?'待核对':`${s.obtainedCredits} / ${s.requiredCredits}`
        items.push({ label: 'GPA / 学分', value: `${gpa} / ${credits}` })
      }
      return items
    }
  },
  watch: {
    identity(){this.actionPending=null;this.scanPending=null;this.invalidatePrivate()},
    '$route.query':{deep:true,handler(query){const q=query?.tab;if(q&&this.tabs.some(t=>t.key===q)&&q!==this.tab){this.scope++;this.tab=q;this.enter()}if(query?.warningId&&String(query.warningId)!==String(this.detailId))this.openFollowup(query.warningId)}}
  },
  async created() {
    const query = (this.$route && this.$route.query) || {}
    const q = query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.enter()
    if (query.warningId) await this.openFollowup(query.warningId)
  },
  beforeUnmount(){this.alive=false;this.invalidatePrivate()},
  methods: {
    token(kind,extra=''){const seq=(this.readSeq[kind]||0)+1;this.readSeq[kind]=seq;return {kind,seq,scope:this.scope,identity:this.identity,tab:this.tab,extra:String(extra)}},
    current(c){return this.alive&&c.scope===this.scope&&c.identity===this.identity&&this.readSeq[c.kind]===c.seq},
    denied(err){return /403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' '))},
    invalidatePrivate(){this.scope++;this.readSeq={};this.rows=[];this.detail=null;this.detailId='';this.detailVisible=false;this.notifyRows=[];this.actionReceipt=null;this.assignVisible=false;this.followVisible=false;this.escalateVisible=false;this.closeVisible=false;this.voidVisible=false;this.acting=false},
    readFail(err,fallback){if(this.denied(err))this.invalidatePrivate();return gradeError(err,fallback)},
    onOwnerPicked(value, items) {
      this.assignForm.ownerId = value || ''
      this.assignForm.ownerName = items?.[0]?.raw?.teacherName || items?.[0]?.label || ''
    },
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
      if(this.acting||this.scanning)return
      this.scope++
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
      const c=this.token('summary');this.summaryLoading = true; this.summaryError = ''
      try{const res = await api.summary();if(!this.current(c))return;if(res.code !== 0)throw res;if(!Array.isArray(res.data?.bySource)||!Array.isArray(res.data?.byLevel)||!Array.isArray(res.data?.byStatus))throw {code:503};this.summary = res.data}
      catch(err){if(this.current(c))this.summaryError=this.readFail(err,'预警汇总读取失败，请重试。')}
      finally{if(this.current(c))this.summaryLoading=false}
    },
    async loadList() {
      if (!this.category) return
      const category={...this.category},page=this.pagination.page,c=this.token('list',category.sourceCode);this.listLoading = true; this.listError = ''
      try{const res = await api.list({
        sourceCode: this.category.sourceCode, level: this.catFilters.level || undefined,
        status: this.catFilters.status || undefined, page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if(!this.current(c)||this.category?.sourceCode!==category.sourceCode||this.pagination.page!==page)return;if(res.code!==0)throw res;if(!Array.isArray(res.data?.list))throw {code:503};this.rows=res.data.list;this.pagination.total=Number.isFinite(res.data.total)?res.data.total:res.data.list.length}
      catch(err){if(this.current(c))this.listError=this.readFail(err,'预警名单读取失败，请重试。')}
      finally{if(this.current(c))this.listLoading=false}
    },
    onPageChange(p) { this.pagination.page = p; this.loadList() },
    async loadFollowList() {
      const page=this.pagination.page,c=this.token('list','followup');this.listLoading = true; this.listError = ''
      try{const res = await api.list({
        status: this.followFilters.status || undefined, sourceCode: this.followFilters.sourceCode || undefined,
        page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if(!this.current(c)||this.tab!=='followup'||this.pagination.page!==page)return;if(res.code!==0)throw res;if(!Array.isArray(res.data?.list))throw {code:503};this.rows=res.data.list;this.pagination.total=Number.isFinite(res.data.total)?res.data.total:res.data.list.length}
      catch(err){if(this.current(c))this.listError=this.readFail(err,'预警跟进名单读取失败，请重试。')}
      finally{if(this.current(c))this.listLoading=false}
    },
    onFollowPageChange(p) { this.pagination.page = p; this.loadFollowList() },
    notifyStatusColor,
    async loadNotifySummary() {
      const c=this.token('notifySummary');this.notifySummaryLoading = true
      try{const res=await api.notificationSummary();if(!this.current(c))return;if(res.code!==0)throw res;this.notifySummary={total:res.data?.total??null,unread:res.data?.unread??null,read:res.data?.read??null}}
      catch(err){if(this.current(c))this.notifyError=this.readFail(err,'通知汇总读取失败，请重试。')}
      finally{if(this.current(c))this.notifySummaryLoading=false}
    },
    async loadNotifications() {
      const page=this.notifyPagination.page,c=this.token('notifications');this.notifyLoading = true; this.notifyError = ''
      try{const res=await api.notifications({page,pageSize:this.notifyPagination.pageSize});if(!this.current(c)||this.tab!=='notify'||this.notifyPagination.page!==page)return;if(res.code!==0)throw res;if(!Array.isArray(res.data?.list))throw {code:503};this.notifyRows=res.data.list;this.notifyPagination.total=Number.isFinite(res.data.total)?res.data.total:res.data.list.length}
      catch(err){if(this.current(c))this.notifyError=this.readFail(err,'预警通知读取失败，请重试。')}
      finally{if(this.current(c))this.notifyLoading=false}
    },
    onNotifyPageChange(p) { this.notifyPagination.page = p; this.loadNotifications() },
    async askScan(key){
      if(!this.canRule||this.scanning||this.scanPending)return
      const c=this.token('scanRules')
      try{const res=await api.getRules();if(!this.current(c))return;if(res.code!==0)throw res;if(!Array.isArray(res.data?.items))throw {code:503};const rules=res.data.items.map(r=>({key:String(r.key),label:String(r.label||r.key),value:r.value}));this.scanConfirm={visible:true,key,rules,message:`将按刚读取的 ${rules.length} 条正式规则执行${key==='all'?'全部':'本类'}扫描。扫描可能生成或更新预警，请确认。`}}
      catch(err){if(this.current(c))toast.error(this.readFail(err,'扫描规则读取失败，请重试。'))}
    },
    async scanOne() {
      const frozen=this.scanConfirm;if(!this.canRule||this.scanning||this.scanPending||!frozen.visible)return
      const c=this.token('scanExecute');this.scanning=true
      try{const currentRules=await api.getRules();if(!this.current(c))return;if(currentRules?.code!==0)throw currentRules;if(!Array.isArray(currentRules.data?.items))throw {code:503};const normalize=items=>items.map(r=>[String(r.key),r.value]).sort((a,b)=>a[0].localeCompare(b[0]));const same=JSON.stringify(normalize(currentRules.data.items))===JSON.stringify(normalize(frozen.rules));if(!same){this.scanConfirm.visible=false;toast.error('预警规则已变化，请重新确认后再扫描。');return}
        let res;try{res=await api.scan(frozen.key)}catch(err){res=err}
        if(!this.current(c))return
        this.scanConfirm.visible=false
        if(res?.code===0&&res.data&&typeof res.data==='object'){this.scanResult=res.data;toast.success('扫描回执已收到，正在读取当前名单。')}
        else if(/403|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){throw res}
        else{this.scanPending={key:frozen.key,rules:frozen.rules};this.scanResult={pending:true};toast.error('扫描结果待核实，请勿重复执行。')}
        if(this.tab==='dashboard')await this.loadSummary();else if(this.category)await this.loadList()
      }catch(err){if(this.current(c))toast.error(this.readFail(err,'扫描未执行，请核对权限和规则。'))}finally{if(this.current(c))this.scanning=false}
    },
    async loadRules() {
      const c=this.token('rules');this.rulesLoading = true; this.rulesError = ''
      try{const res=await api.getRules();if(!this.current(c))return;if(res.code!==0)throw res;if(!Array.isArray(res.data?.items))throw {code:503};this.rules=res.data.items;this.ruleEdits=Object.fromEntries(this.rules.map(r=>[r.key,r.value]))}
      catch(err){if(this.current(c))this.rulesError=this.readFail(err,'预警规则读取失败，请重试。')}
      finally{if(this.current(c))this.rulesLoading=false}
    },
    async saveRuleValue(r) {
      if(!this.canRule||this.ruleSaving||this.ruleUncertain[r.key])return
      const numeric=Number(this.ruleEdits[r.key]);if(!Number.isFinite(numeric)||numeric<Number(r.min)||numeric>Number(r.max)||(r.type==='int'&&!Number.isInteger(numeric))){toast.error(`请输入 ${r.min} 至 ${r.max} 范围内的${r.type==='int'?'整数':'数值'}`);return}
      const c=this.token('ruleWrite',r.key);this.ruleSaving=r.key
      try{const before=await api.getRules();if(!this.current(c))return;if(before?.code!==0)throw before;const old=before.data?.items?.find(item=>String(item.key)===String(r.key));if(!old||Number(old.value)!==Number(r.value)){toast.error('规则当前值已变化，请刷新后重新填写。');await this.loadRules();return}
        let res;try{res=await api.saveRule(r.key,numeric)}catch(err){res=err}
        if(!this.current(c))return
        if(res?.code!==0){if(/403|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' ')))throw res;this.ruleUncertain={...this.ruleUncertain,[r.key]:true}}
        const after=await api.getRules();if(after?.code!==0)throw after;const saved=after.data?.items?.find(item=>String(item.key)===String(r.key));if(Number(saved?.value)===numeric&&res?.code===0){toast.success('已核对正式规则值，下次扫描生效');this.ruleUncertain={...this.ruleUncertain,[r.key]:false}}else{this.ruleUncertain={...this.ruleUncertain,[r.key]:true};toast.error('规则结果待核实，请刷新规则，勿重复保存。')}this.rules=after.data.items;this.ruleEdits=Object.fromEntries(this.rules.map(item=>[item.key,item.value]))
      }catch(err){if(this.current(c))toast.error(this.readFail(err,'规则保存前核对未完成，请重试。'))}finally{if(this.current(c))this.ruleSaving=''}
    },
    async openFollowup(warningId) {
      if(!warningId)return
      if(this.tab!=='followup'){this.scope++;this.tab='followup';this.$router?.replace?.({query:{...this.$route.query,tab:'followup',warningId:String(warningId)}})?.catch?.(()=>{});this.pagination.page=1;this.loadFollowList()}
      this.detailId = String(warningId)
      this.detailVisible = true
      this.detailLoading = true
      this.detailError = ''
      const c=this.token('detail',warningId)
      try{const res=await api.detail(warningId);if(!this.current(c)||String(this.detailId)!==String(warningId))return;if(res.code!==0)throw res;if(String(res.data?.warning?.warningId)!==String(warningId)||!Array.isArray(res.data?.interventions))throw {code:503};this.detail=res.data}
      catch(err){if(this.current(c))this.detailError=this.readFail(err,'预警详情读取失败，请重试。')}
      finally{if(this.current(c))this.detailLoading=false}
    },
    reloadDetailAndList() {
      this.openFollowup(this.detailId)
      if (this.tab === 'followup') this.loadFollowList()
      else if (this.category) this.loadList()
    },
    recordActionReceipt(title, result, next, verified=true) {
      this.actionReceipt = {
        title, result, next, verified,
        warningId: this.detailId,
        studentName: this.detail?.student?.studentName || '学生'
      }
    },
    async performWarningAction(kind,send,verify,{title,result,next}){
      if(!this.canHandle||this.acting||this.actionPending||!this.detailId)return false
      const c=this.token('action',this.detailId);this.acting=true;this.actionPending={warningId:this.detailId,kind}
      try{let res;try{res=await send()}catch(err){res=err}if(!this.current(c))return false
        if(res?.code!==0&&/403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.actionPending=null;throw res}
        let fresh;try{fresh=await api.detail(c.extra)}catch(err){fresh=err}if(!this.current(c))return false
        const exact=fresh?.code===0&&String(fresh.data?.warning?.warningId)===c.extra
        if(res?.code===0&&exact&&verify(fresh.data)){this.detail=fresh.data;this.actionPending=null;this.recordActionReceipt(title,result,next,true);return true}
        this.recordActionReceipt('结果待核实','已读取当前预警，但不能证明本次操作完成','请勿重复操作，联系教务管理员核对操作记录',false);return false
      }catch(err){if(this.current(c))toast.error(this.readFail(err,'操作前核对未完成，请重试。'));return false}finally{if(this.current(c))this.acting=false}
    },
    reopenReceipt() {
      if (!this.actionReceipt?.warningId) return
      this.tab = 'followup'
      this.openFollowup(this.actionReceipt.warningId)
    },
    async submitAssign() {
      if (!this.assignForm.ownerId || !this.assignForm.ownerName) { toast.error('请选择跟进教师'); return }
      const frozen={ownerId:String(this.assignForm.ownerId),ownerName:this.assignForm.ownerName}
      const ok=await this.performWarningAction('assign',()=>api.assign(this.detailId,frozen.ownerId,frozen.ownerName),fresh=>fresh.warning.owner===frozen.ownerName,{title:'跟进责任已指派',result:frozen.ownerName,next:'跟进人记录干预并填写下一步计划'})
      if(ok){toast.success('已回读当前跟进人');this.assignVisible=false;this.assignForm={ownerId:'',ownerName:''};this.loadFollowList()}
    },
    async submitFollowup() {
      if (!this.followForm.content || this.followForm.content.trim().length < 5) { toast.error('跟进内容不少于5字'); return }
      const frozen={way:this.followForm.way,content:this.followForm.content.trim(),result:this.followForm.result||'',nextPlan:this.followForm.nextPlan||''};let interventionId=''
      const ok=await this.performWarningAction('followup',async()=>{const res=await api.addIntervention(this.detailId,frozen);interventionId=String(res?.data?.interventionId||'');return res},fresh=>!!interventionId&&fresh.interventions.some(item=>String(item.id)===interventionId&&item.way===frozen.way&&item.content===frozen.content&&String(item.result||'')===frozen.result&&String(item.nextPlan||'')===frozen.nextPlan),{title:'预警跟进已记录',result:this.wayLabel(frozen.way),next:frozen.nextPlan||'继续观察证据变化并按计划复查'})
      if(ok){toast.success('已回读正式跟进记录');this.followVisible=false;this.followForm={way:'TALK',content:'',result:'',nextPlan:''};this.loadFollowList()}
    },
    async remind() {
      const before=Number(this.detail?.warning?.remindCount);let notified=null
      const ok=await this.performWarningAction('remind',async()=>{const res=await api.remind(this.detailId);notified=Number.isFinite(Number(res?.data?.notified))?Number(res.data.notified):null;return res},fresh=>Number.isFinite(before)&&Number(fresh.warning.remindCount)>before,{title:'预警提醒已发送',result:notified==null?'通知对象数量待核对':`${notified} 个通知对象`,next:'通知送达和阅读状态请在通知台账继续核对'})
      if(ok){toast.success('已回读提醒计数');this.loadFollowList()}
    },
    async submitEscalate({ reason }) {
      const ok=await this.performWarningAction('escalate',()=>api.escalate(this.detailId,reason),fresh=>fresh.warning.status==='ESCALATED'&&fresh.warning.level==='HIGH',{title:'预警已升级',result:'当前状态：已升级',next:'升级原因需在审计记录中继续核对'})
      if(ok){toast.success('已回读升级状态');this.escalateVisible=false;this.loadFollowList()}
    },
    async submitClose({ reason }) {
      const frozen=String(reason||'')
      const ok=await this.performWarningAction('close',()=>api.close(this.detailId,frozen),fresh=>fresh.warning.status==='CLOSED'&&String(fresh.warning.closeResult||'')===frozen,{title:'预警已关闭',result:'当前状态：已关闭',next:'关闭说明已按本次内容回读'})
      if(ok){toast.success('已回读关闭状态');this.closeVisible=false;this.loadFollowList()}
    },
    async submitVoid({ reason }) {
      const frozen=String(reason||'')
      const ok=await this.performWarningAction('void',()=>api.void(this.detailId,frozen),fresh=>fresh.warning.recordStatus==='VOIDED'&&String(fresh.warning.voidReason||'')===frozen,{title:'误报预警已作废',result:'当前记录：已作废',next:'误报说明已按本次内容回读'})
      if(ok){toast.success('已回读作废状态');this.voidVisible=false;this.loadFollowList()}
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aawc-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; flex-wrap: wrap; }
.aawc-tab { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; white-space: nowrap; }
.aawc-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aawc-receipt { display: grid; grid-template-columns: minmax(0,1fr) auto minmax(200px,auto) auto; align-items: center; gap: 18px; margin-bottom: 16px; padding: 13px 15px; border: 1px solid #a7d7b4; border-radius: 11px; background: #f3fbf5; }
.aawc-receipt strong, .aawc-receipt span, .aawc-receipt small, .aawc-receipt b { display: block; }.aawc-receipt strong { color: #15803d; }.aawc-receipt span, .aawc-receipt small { margin-top: 3px; color: #64748b; font-size: 11px; }.aawc-receipt b { margin-top: 3px; font-size: 12px; }
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
@media (max-width: 760px) { .aawc-receipt { grid-template-columns: 1fr; gap: 10px; } }
.aawc-rule-row { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; background: var(--fill-light, #f8fafc); border-radius: 10px; }
.aawc-rule-label { font-size: 14px; font-weight: 500; }
.aawc-rule-edit { display: flex; align-items: center; gap: 8px; }
.aawc-rule-edit :deep(.app-number-input), .aawc-rule-edit :deep(input) { width: 100px; }
</style>
