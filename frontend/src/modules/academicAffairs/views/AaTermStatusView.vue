<template>
  <ModulePageShell
    title="学期状态"
    subtitle="管理学期从编制、发布到冻结的状态流转 · 当前学期结论统一来自 A-C1"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
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
          <div class="mp-cell-main">{{ row.yearCode }} 第 {{ row.termNo }} 学期</div>
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
        <template #cell-actions="{ row }">
          <AppButton
            v-if="row.status === 'PUBLISHED'"
            size="small"
            variant="ghost"
            :loading="acting === row.termId"
            @click="askFreeze(row)"
          >冻结</AppButton>
          <AppButton
            v-else-if="row.status === 'FROZEN'"
            size="small"
            variant="ghost"
            :loading="acting === row.termId"
            @click="askUnfreeze(row)"
          >解冻</AppButton>
          <span v-else class="mp-cell-sub">{{ row.status === 'DRAFT' ? '未发布，不可冻结' : '已归档，只读' }}</span>
        </template>
      </DataTable>
    </div>

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
        <p class="mp-note">解冻「{{ unfreezeDrawer.row && unfreezeDrawer.row.yearCode }} 第 {{ unfreezeDrawer.row && unfreezeDrawer.row.termNo }} 学期」并恢复为进行中，需填写原因（至少 5 字），并留痕审计。</p>
        <AppFormItem label="解冻原因" required>
          <AppTextarea v-model="unfreezeReason" :rows="3" placeholder="至少 5 字，如：误操作冻结需恢复排课" maxlength="200" />
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
import { AppStatusTag, AppConfirmDialog, AppFormItem, AppTextarea, AppInlineAlert } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { safeEnumLabel } from '@/utils/presentationSafety'

const STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '进行中', FROZEN: '已冻结', ARCHIVED: '已归档' }
const STATUS_TYPE = { DRAFT: 'default', PUBLISHED: 'success', FROZEN: 'warning', ARCHIVED: 'info' }

export default {
  name: 'AaTermStatusView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppConfirmDialog, AppFormItem, AppTextarea, AppInlineAlert, AppButton, AppDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
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
        { key: 'actions', title: '操作', width: '160px' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    statusLabel(s) { return safeEnumLabel({ value: s, dictionary: STATUS_LABEL, unknownLabel: '状态待确认' }) },
    statusType(s) { return STATUS_TYPE[s] || 'default' },
    isResolvedCurrent(row) {
      return Boolean(this.currentContext?.termId) && String(row.termId) === String(this.currentContext.termId)
    },
    async loadCurrentContext() {
      this.currentError = ''
      const res = await academicAffairsApi.getCurrentTerm()
      if (res.code === 0) {
        this.currentContext = res.data || null
      } else {
        this.currentContext = null
        this.currentError = res.message || '当前学期解析失败'
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const [res] = await Promise.all([
        academicAffairsApi.getTerms({ page: 1, pageSize: 100 }),
        this.loadCurrentContext()
      ])
      if (res.code === 0) {
        this.rows = res.data.list
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    askFreeze(row) {
      this.freezeDialog = {
        visible: true,
        submitting: false,
        row,
        message: `确认冻结「${row.yearCode} 第 ${row.termNo} 学期」？冻结后排课/选课/考试等结构性变更将受限，可随时解冻。`
      }
    },
    async doFreeze() {
      const row = this.freezeDialog.row
      if (!row) return
      this.freezeDialog.submitting = true
      this.acting = row.termId
      const res = await academicAffairsApi.freezeTerm(row.termId)
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
      this.unfreezeReason = ''
      this.unfreezeError = ''
      this.unfreezeDrawer = { visible: true, submitting: false, row }
    },
    async doUnfreeze() {
      const row = this.unfreezeDrawer.row
      if (!row) return
      const reason = (this.unfreezeReason || '').trim()
      if (reason.length < 5) {
        this.unfreezeError = '解冻原因至少 5 字'
        return
      }
      this.unfreezeDrawer.submitting = true
      this.acting = row.termId
      const res = await academicAffairsApi.unfreezeTerm(row.termId, reason)
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
</style>
