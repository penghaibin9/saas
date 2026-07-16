<template>
  <ModulePageShell
    title="教务归档 · 控制台"
    subtitle="按学年学期归档 · 9数据域完整性检查 · 确认归档封存学期"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="openCreate">新建归档批次</AppButton>
    </template>

    <div class="aaar-layout">
      <div class="aaar-list">
        <LoadingState v-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无归档批次" description="按学期新建归档批次" />
        <ul v-else class="aaar-items">
          <li v-for="b in rows" :key="b.batchId" :class="['aaar-item', { 'is-active': current && current.batchId === b.batchId }]" @click="select(b)">
            <span>{{ b.batchName }}</span>
            <StatusTag :type="sType(b.status)" :label="sLabel(b.status)" dot />
          </li>
        </ul>
      </div>

      <div class="aaar-detail">
        <EmptyState v-if="!current" title="选择批次" description="从左侧选择归档批次执行完整性检查与归档" />
        <template v-else>
          <div class="aaar-head">
            <div><div class="aaar-title">{{ current.batchName }}</div><StatusTag :type="sType(current.status)" :label="sLabel(current.status)" dot /></div>
            <div class="aaar-actions">
              <AppButton v-if="['DRAFT','MISSING_ITEMS','READY'].includes(current.status)" size="small" variant="ghost" @click="doCheck">完整性检查</AppButton>
              <AppButton v-if="current.status === 'READY'" size="small" variant="primary" @click="doConfirm(false)">确认归档</AppButton>
              <AppButton v-if="current.status === 'MISSING_ITEMS'" size="small" variant="warning" @click="doConfirm(true)">强制归档</AppButton>
              <AppButton v-if="current.status === 'ARCHIVED'" size="small" variant="ghost" @click="doUnfreeze">特批解冻</AppButton>
              <AppButton v-if="!['ARCHIVED','CANCELLED'].includes(current.status)" size="small" variant="ghost" @click="doCancel">取消</AppButton>
            </div>
          </div>
          <div v-if="current.missingCount != null" class="aaar-summary">
            <span :class="{ 'is-bad': current.missingCount }">缺失数据域 {{ current.missingCount }} / 9</span>
            <span v-if="current.archivedAt">归档于 {{ fmt(current.archivedAt) }}（学期已封存）</span>
          </div>
          <div class="aaar-section-title">9 数据域完整性</div>
          <EmptyState v-if="!items.length" title="未检查" description="点击「完整性检查」聚合各数据域" />
          <DataTable v-else :columns="itemColumns" :rows="items" row-key="domain">
            <template #cell-domain="{ row }">{{ row.domainLabel }}</template>
            <template #cell-present="{ row }"><StatusTag :type="row.present ? 'success' : 'danger'" :label="row.present ? '有数据' : '缺失'" dot /></template>
          </DataTable>
        </template>
      </div>
    </div>

    <AppDrawer :visible="createVisible" title="新建归档批次" @close="createVisible = false">
      <div class="aaar-form">
        <AppFormItem label="学期 ID" required><AppTextInput v-model="form.termId" placeholder="要归档的学期 ID（一学期一批次）" :disabled="saving" /></AppFormItem>
        <AppInlineAlert type="warning" description="确认归档后该学期将被封存（status→ARCHIVED），此后该学期教务写操作应被拦截；如需修改须走特批解冻。" />
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
    <AppConfirmDialog
      v-model:visible="reasonDialog.visible" title="特批解冻（仅学校管理员）" type="danger"
      require-reason phrase-scene-key="aa.archive.unfreeze" reason-label="解冻原因（≥5字）"
      :submitting="reasonDialog.submitting" @confirm="onReasonConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 教务归档 · 控制台（/admin/academic-affairs/archive）：批次+9数据域完整性检查+确认归档封存。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppFormItem, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsArchiveApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _SL = { DRAFT: '草稿', CHECKING: '检查中', READY: '完整可归档', MISSING_ITEMS: '有缺失', ARCHIVED: '已归档', CANCELLED: '已取消' }

export default {
  name: 'AaArchiveConsoleView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, EmptyState, AppButton, AppDrawer, AppTextInput, AppFormItem, AppConfirmDialog, AppInlineAlert },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, rows: [], current: null, items: [],
      itemColumns: [{ key: 'domain', title: '数据域' }, { key: 'recordCount', title: '记录数' }, { key: 'present', title: '完整性' }, { key: 'remark', title: '备注' }],
      createVisible: false, form: { termId: '' }, formError: '', saving: false,
      confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      reasonDialog: { visible: false, submitting: false, action: null }
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
  },
  methods: {
    sLabel(s) { return _SL[s] || s },
    sType(s) { return s === 'ARCHIVED' ? 'success' : s === 'MISSING_ITEMS' ? 'danger' : s === 'READY' ? 'primary' : 'default' },
    fmt(s) { return s ? s.replace('T', ' ').slice(0, 16) : '' },
    async load() {
      this.loading = true
      const res = await api.listBatches({ pageSize: 100 })
      this.rows = res.code === 0 ? res.data.list : []
      this.loading = false
    },
    async select(b) {
      const res = await api.getBatch(b.batchId)
      if (res.code === 0) { this.current = res.data; this.items = res.data.items || [] }
    },
    openCreate() { this.form = { termId: '' }; this.formError = ''; this.createVisible = true },
    async submitCreate() {
      if (!this.form.termId) { this.formError = '学期 ID 必填'; return }
      this.saving = true
      const res = await api.createBatch({ termId: this.form.termId })
      this.saving = false
      if (res.code === 0) { toast.success('已创建'); this.createVisible = false; this.load() } else this.formError = res.message
    },
    async doCheck() {
      const res = await api.check(this.current.batchId)
      if (res.code === 0) { toast.success('已检查'); this.current = res.data; this.items = res.data.items || []; this.load() } else toast.error(res.message)
    },
    doConfirm(force) {
      this.confirmTitle = force ? '强制归档' : '确认归档'
      this.confirmMessage = `确认归档「${this.current.batchName}」？归档后该学期将被封存，教务写操作受限。` + (force ? '（存在缺失数据域，强制归档）' : '')
      this.pendingAction = async () => {
        const res = await api.confirm(this.current.batchId, force)
        if (res.code === 0) { toast.success('已归档'); await this.load(); const b = this.rows.find(x => x.batchId === this.current.batchId); if (b) await this.select(b) }
        else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    doUnfreeze() {
      this.reasonDialog = {
        visible: true, submitting: false,
        action: async (reason) => {
          const res = await api.unfreeze(this.current.batchId, reason)
          if (res.code !== 0) { toast.error(res.message); return false }
          toast.success('已解冻'); await this.load(); await this.select(this.current); return true
        }
      }
    },
    /** 失败时保留弹窗与已填内容，仅成功才关闭 */
    async onReasonConfirm({ reason }) {
      const action = this.reasonDialog.action
      if (!action) return
      this.reasonDialog.submitting = true
      const ok = await action(reason)
      this.reasonDialog.submitting = false
      if (ok) this.reasonDialog.visible = false
    },
    doCancel() {
      this.confirmTitle = '取消批次'; this.confirmMessage = `确认取消归档批次「${this.current.batchName}」？`
      this.pendingAction = async () => {
        const res = await api.cancel(this.current.batchId)
        if (res.code === 0) { toast.success('已取消'); this.load() } else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() }
  }
}
</script>

<style scoped>
.aaar-layout { display: grid; grid-template-columns: 280px 1fr; gap: 16px; }
.aaar-items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aaar-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aaar-item.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aaar-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.aaar-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
.aaar-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.aaar-summary { display: flex; gap: 16px; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
.aaar-summary .is-bad { color: var(--danger-color, #dc2626); font-weight: 600; }
.aaar-section-title { font-weight: 500; margin: 12px 0 8px; }
.aaar-form { display: flex; flex-direction: column; gap: 12px; }
</style>
