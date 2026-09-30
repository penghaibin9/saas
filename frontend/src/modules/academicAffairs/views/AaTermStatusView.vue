<template>
  <ModulePageShell
    title="学期状态"
    subtitle="管理学期从编制、发布到冻结的状态流转 · 当前学期结论统一来自 A-C1"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aa-state-layout"><div class="mp-stack">
      <AppSectionCard title="当前权威事实">
        <p v-if="currentError" class="mp-note">{{ currentError }}</p>
        <p v-else-if="!currentContext" class="mp-note">当前学期结论待核对。</p>
        <div v-else class="aa-state-facts">
          <span>当前学期<strong>{{ currentContext.termId ? `${currentContext.yearCode} 第 ${currentContext.termNo} 学期` : '尚未设置' }}</strong></span>
          <span>权威来源<strong>{{ currentContext.currentAuthority === 'CALENDAR_GOVERNANCE' ? '全校学期治理' : currentContext.canDirectSwitch === true ? '教务学期兼容管理' : '待核对' }}</strong></span>
          <span>教务侧直接切换<strong>{{ currentContext.currentAuthority === 'CALENDAR_GOVERNANCE' ? '不允许，由治理岗位统一激活' : currentContext.canDirectSwitch === true ? '按当前学期页面权限办理' : '当前结论不可直接切换' }}</strong></span>
          <span>学期定义状态<strong>{{ statusLabel(currentContext.status) || '待核对' }} · 定义与激活分开</strong></span>
        </div>
      </AppSectionCard>
      <AppSectionCard title="定义、当前与归档关系">
      <AppInlineAlert
        v-if="currentError"
        type="warning"
        :description="`当前学期解析失败，本页不再依据历史 isCurrent 标记猜测“当前”；状态台账与冻结/解冻仍按显式学期执行。${currentError}`"
      />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="还没有学年学期" description="请先到「学年学期」创建一个学期" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="termId">
        <template #cell-term="{ row }">
          <button class="aa-state-detail" @click="openTerm(row)">{{ row.yearCode }} 第 {{ row.termNo }} 学期</button>
          <div class="mp-cell-sub">{{ row.termName || '未命名' }}</div>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="statusType(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-current="{ row }">
          <AppStatusTag v-if="isResolvedCurrent(row)" type="success" dot>全校当前</AppStatusTag>
          <span v-else-if="currentError" class="mp-cell-sub">待核对</span>
          <span v-else class="mp-cell-sub">—</span>
        </template>
        <template #cell-scheduleReferences="{ row }">{{ row.scheduleReferenceCount }} 个正式课表范围</template>
        <template #cell-archiveState="{ row }">
          <AppStatusTag :type="row.archiveBatchStatus === 'ARCHIVED' ? 'success' : row.archiveBatchStatus === 'MISSING_ITEMS' ? 'danger' : 'default'" dot>
            {{ row.archiveBatchStatus ? archiveLabel(row.archiveBatchStatus) : '未建归档批次' }}
          </AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <AppButton
            v-if="canManage && row.status === 'PUBLISHED'"
            size="small"
            variant="ghost"
            :loading="acting === row.termId"
            :disabled="!!acting"
            @click="askFreeze(row)"
          >冻结</AppButton>
          <AppButton
            v-else-if="canManage && row.status === 'FROZEN'"
            size="small"
            variant="ghost"
            :loading="acting === row.termId"
            :disabled="!!acting"
            @click="askUnfreeze(row)"
          >解冻</AppButton>
          <span v-else class="mp-cell-sub">{{ !canManage ? '当前身份只读' : row.status === 'DRAFT' ? '未发布，不可冻结' : '已归档，只读' }}</span>
        </template>
      </DataTable>
      </AppSectionCard>
    </div><aside class="aa-state-boundary"><h2>可理解的操作边界</h2><section><strong>发布定义</strong><p>定义已发布不代表当前学期已经切换。</p></section><section><strong>冻结与解冻</strong><p>按明确的学期对象执行。解冻必须填写真实原因并留下审计记录。</p></section><section><strong>封存后的处理</strong><p>已归档学期保持只读，交归档责任岗办理受控纠错。</p></section></aside></div>

    <AppConfirmDialog
      v-model:visible="freezeDialog.visible"
      title="冻结学期"
      :message="freezeDialog.message"
      type="warning"
      confirm-text="确认冻结"
      :submitting="freezeDialog.submitting"
      @confirm="doFreeze"
    />

    <AppDrawer :visible="unfreezeDrawer.visible" title="解冻学期" mode="modal" size="small" @close="unfreezeDrawer.visible = false">
      <div class="aa-form">
        <p class="mp-note">解冻「{{ unfreezeDrawer.row && unfreezeDrawer.row.yearCode }} 第 {{ unfreezeDrawer.row && unfreezeDrawer.row.termNo }} 学期」（{{ unfreezeDrawer.row && unfreezeDrawer.row.termId }}）并恢复为已发布，需填写原因（至少 5 字），并留痕审计。</p>
        <AppFormItem label="解冻原因" required>
          <AppTextarea v-model="unfreezeReason" :rows="3" placeholder="至少 5 字，如：误操作冻结需恢复排课" :maxlength="200" />
        </AppFormItem>
        <AppInlineAlert v-if="unfreezeError" type="danger" :description="unfreezeError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="unfreezeDrawer.submitting" @click="unfreezeDrawer.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="unfreezeDrawer.submitting" @click="doUnfreeze">确认解冻</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** 学期状态（/admin/academic-affairs/terms/status）：状态写操作按显式 term；“当前”展示必须来自 A-C1 /terms/current。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppFormItem, AppTextarea, AppInlineAlert } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { safeEnumLabel } from '@/utils/presentationSafety'
import { matchPermission } from '@/config/navPlan'

const STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '已发布', FROZEN: '已冻结', ARCHIVED: '已归档' }
const STATUS_TYPE = { DRAFT: 'default', PUBLISHED: 'success', FROZEN: 'warning', ARCHIVED: 'info' }

export default {
  name: 'AaTermStatusView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag, AppConfirmDialog, AppFormItem, AppTextarea, AppInlineAlert, AppButton, AppDrawer },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  computed: { canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.term.manage') } },
  data() {
    return {
      loading: true, disposed: false, listVersion: 0, currentVersion: 0, scopeVersion: 0,
      error: '',
      rows: [],
      currentContext: null,
      currentError: '',
      acting: '',
      freezeDialog: { visible: false, submitting: false, row: null, message: '' },
      unfreezeDrawer: { visible: false, submitting: false, row: null },
      unfreezeReason: '',
      unfreezeError: '',
      columns: [
        { key: 'term', title: '学年学期' },
        { key: 'status', title: '状态' },
        { key: 'current', title: '当前学期' },
        { key: 'scheduleReferences', title: '课表引用' },
        { key: 'archiveState', title: '归档状态' },
        { key: 'actions', title: '操作', width: '160px' }
      ]
    }
  },
  created() {
    this.load()
  },
  watch: { ctx: { deep: true, handler() { this.scopeVersion++; this.freezeDialog.visible = false; this.unfreezeDrawer.visible = false; this.acting = ''; this.load() } } },
  beforeUnmount() { this.disposed = true; this.listVersion++; this.currentVersion++ },
  methods: {
    openTerm(row) { const returnToken = this.academicFlow?.captureReturn(); this.$router.push({ name: 'aa-term-detail', params: { termId: row.termId }, query: returnToken ? { returnToken } : {} }) },
    contextKey() { return JSON.stringify([this.disposed, this.scopeVersion, this.academicFlow?.identity() || JSON.stringify(this.ctx), this.$route?.fullPath]) },
    statusLabel(s) { return safeEnumLabel({ value: s, dictionary: STATUS_LABEL, unknownLabel: '状态待确认' }) },
    statusType(s) { return STATUS_TYPE[s] || 'default' },
    archiveLabel(s) { return { DRAFT: '归档草稿', CHECKING: '检查中', READY: '待封存', MISSING_ITEMS: '存在缺失', ARCHIVED: '已封存', CANCELLED: '已取消' }[s] || '待核对' },
    isResolvedCurrent(row) {
      return Boolean(this.currentContext?.termId) && String(row.termId) === String(this.currentContext.termId)
    },
    async loadCurrentContext() {
      const version = ++this.currentVersion, context = this.contextKey()
      this.currentError = ''
      this.currentContext = null
      const res = await academicAffairsApi.getCurrentTerm()
      if (version !== this.currentVersion || context !== this.contextKey()) return
      if (res.code === 0) {
        this.currentContext = res.data || null
      } else {
        this.currentContext = null
        this.currentError = res.message || '当前学期解析失败'
      }
    },
    async load() {
      const version = ++this.listVersion, context = this.contextKey()
      this.loading = true
      this.error = ''
      const [res, archive] = await Promise.all([
        academicAffairsApi.getTerms({ page: 1, pageSize: 100 }),
        academicAffairsApi.getTermArchiveOverview(),
        this.loadCurrentContext()
      ])
      if (version !== this.listVersion || context !== this.contextKey()) return
      if (res.code === 0) {
        const archiveByTerm = new Map((archive.code === 0 ? archive.data || [] : []).map(row => [String(row.termId), row]))
        this.rows = res.data.list.map(row => ({ scheduleReferenceCount: 0, ...row, ...(archiveByTerm.get(String(row.termId)) || {}) }))
      } else {
        this.error = res.message
      }
      this.loading = false
      this.academicFlow?.restorePosition?.()
    },
    askFreeze(row) {
      if (!this.canManage || this.acting || row.status !== 'PUBLISHED') return
      this.freezeDialog = {
        visible: true,
        submitting: false,
        row: { ...row }, context: this.contextKey(),
        message: `确认冻结「${row.yearCode} 第 ${row.termNo} 学期」（${row.termId}）？冻结后排课/选课/考试等结构性变更将受限，恢复办理需填写解冻原因。`
      }
    },
    async doFreeze() {
      const row = this.freezeDialog.row
      if (!row || !this.canManage || this.acting || this.freezeDialog.submitting || this.freezeDialog.context !== this.contextKey()) return
      const context = this.freezeDialog.context
      this.freezeDialog.submitting = true
      this.acting = row.termId
      const res = await academicAffairsApi.freezeTerm(row.termId)
      if (context !== this.contextKey()) return
      this.freezeDialog.submitting = false
      this.acting = ''
      if (res.code === 0) {
        this.freezeDialog.visible = false
        toast.success('已冻结')
        this.load()
      } else {
        toast.error(res.message || '冻结失败')
      }
    },
    askUnfreeze(row) {
      if (!this.canManage || this.acting || row.status !== 'FROZEN') return
      this.unfreezeReason = ''
      this.unfreezeError = ''
      this.unfreezeDrawer = { visible: true, submitting: false, row: { ...row }, context: this.contextKey() }
    },
    async doUnfreeze() {
      const row = this.unfreezeDrawer.row
      if (!row || !this.canManage || this.acting || this.unfreezeDrawer.submitting || this.unfreezeDrawer.context !== this.contextKey()) return
      const context = this.unfreezeDrawer.context
      const reason = (this.unfreezeReason || '').trim()
      if (reason.length < 5) {
        this.unfreezeError = '解冻原因至少 5 字'
        return
      }
      this.unfreezeDrawer.submitting = true
      this.acting = row.termId
      const res = await academicAffairsApi.unfreezeTerm(row.termId, reason)
      if (context !== this.contextKey()) return
      this.unfreezeDrawer.submitting = false
      this.acting = ''
      if (res.code === 0) {
        this.unfreezeDrawer.visible = false
        toast.success('已解冻')
        this.load()
      } else {
        this.unfreezeError = res.message || '解冻失败'
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-form { display: flex; flex-direction: column; gap: 12px; }
.aa-state-layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; align-items: start; gap: 16px; }
.aa-state-facts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; font-size: 12px; color: var(--text-secondary); }
.aa-state-facts strong { display: block; margin-top: 8px; color: var(--text-primary); font-size: 14px; }
.aa-state-facts > span { border: 1px solid var(--border-base); border-radius: 8px; padding: 12px; background: var(--bg-page); }
.aa-state-detail { border: 0; padding: 0; background: transparent; color: var(--pri); font: inherit; font-weight: 600; cursor: pointer; }
.aa-state-boundary { border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.aa-state-boundary h2 { margin: 0; padding: 16px; font-size: 14px; border-bottom: 1px solid var(--border-base); }
.aa-state-boundary section { padding: 0 16px; margin: 20px 0; font-size: 13px; }
.aa-state-boundary p { font-size: 12px; color: var(--text-secondary); line-height: 1.7; }
@media (max-width: 1100px) { .aa-state-layout { grid-template-columns: minmax(0, 1fr); } }
</style>
