<template>
  <ModulePageShell
    title="教务归档 · 控制台"
    subtitle="按学年学期归档 · 数据域完整性检查 · 确认归档后历史事实不可普通解冻"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" :disabled="actionBusy" @click="openCreate">新建归档批次</AppButton>
    </template>

    <div class="aaar-layout">
      <div class="aaar-list">
        <LoadingState v-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无归档批次" description="按学期新建归档批次" />
        <ul v-else class="aaar-items">
          <li
            v-for="b in rows"
            :key="b.batchId"
            :class="['aaar-item', { 'is-active': current && current.batchId === b.batchId }]"
            role="button"
            tabindex="0"
            :aria-current="current && current.batchId === b.batchId ? 'true' : undefined"
            @click="select(b)"
            @keydown.enter.prevent="select(b)"
            @keydown.space.prevent="select(b)"
          >
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
              <AppButton v-if="['DRAFT','MISSING_ITEMS','READY'].includes(current.status)" size="small" variant="ghost" :loading="actionBusy" @click="doCheck">完整性检查</AppButton>
              <AppButton v-if="current.status === 'READY'" size="small" variant="primary" :disabled="actionBusy" @click="doConfirm">确认归档</AppButton>
              <AppButton v-if="!['ARCHIVED','CANCELLED'].includes(current.status)" size="small" variant="ghost" :disabled="actionBusy" @click="doCancel">取消</AppButton>
            </div>
          </div>
          <div v-if="current.missingCount != null" class="aaar-summary">
            <span :class="{ 'is-bad': current.missingCount }">阻断数据域 {{ current.missingCount }}</span>
            <span v-if="current.archivedAt">归档于 {{ fmt(current.archivedAt) }}（历史事实已封存）</span>
          </div>
          <AppInlineAlert
            v-if="current.status === 'MISSING_ITEMS'"
            type="warning"
            description="当前仍有 BLOCKED / UNKNOWN 数据域，整体强制归档已停用。请处理阻断 / 待治理域后重新执行完整性检查。"
          />
          <AppInlineAlert
            v-if="current.status === 'ARCHIVED'"
            type="info"
            description="该学期已经形成正式归档事实，普通解冻入口已关闭。后续发现错误时必须走归档后纠错，保留原归档版本、纠错原因和新版本审计链。"
          />

          <AaArchiveCorrectionWorkspace
            v-if="current.status === 'ARCHIVED'"
            :batch="current"
            :items="items"
            @refresh-batch="refreshCurrentFromServer"
          />
          <template v-else>
            <div class="aaar-section-title">数据域完整性</div>
            <EmptyState v-if="!items.length" title="未检查" description="点击「完整性检查」聚合各数据域" />
            <DataTable v-else :columns="itemColumns" :rows="items" row-key="domain">
              <template #cell-domain="{ row }">{{ row.domainLabel }}</template>
              <template #cell-result="{ row }"><StatusTag :type="itemType(row)" :label="itemLabel(row)" dot /></template>
            </DataTable>
          </template>
        </template>
      </div>
    </div>

    <AppDrawer :visible="createVisible" title="新建归档批次" mode="modal" size="small" @close="createVisible = false">
      <div class="aaar-form">
        <AppFormItem label="学期" required><AppTermEntityPicker v-model="form.termId" placeholder="选择要归档的学期（一学期一批次）" :disabled="saving" /></AppFormItem>
        <AppInlineAlert type="warning" description="确认归档后该学期将成为不可普通回退的历史事实，教务写操作会被拦截；如后续发现错误，必须走归档后纠错并保留原版本。" />
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmVisible"
      :title="confirmTitle"
      :message="confirmMessage"
      :submitting="actionBusy"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 教务归档 · 控制台（/admin/academic-affairs/archive）：批次+数据域四态检查+不可逆归档封存。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppFormItem, AppConfirmDialog, AppInlineAlert, AppTermEntityPicker } from '@/components/common'
import { academicAffairsApi, academicAffairsArchiveApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import AaArchiveCorrectionWorkspace from '@/modules/academicAffairs/components/AaArchiveCorrectionWorkspace.vue'
import { toast } from '@/utils/toast'

const _SL = { DRAFT: '草稿', CHECKING: '检查中', READY: '完整可归档', MISSING_ITEMS: '有阻断', ARCHIVED: '已归档', CANCELLED: '已取消' }
const _IL = { PASS: '通过', BLOCKED: '阻断', UNKNOWN: '待治理', NOT_APPLICABLE: '不适用' }
const _IT = { PASS: 'success', BLOCKED: 'danger', UNKNOWN: 'warning', NOT_APPLICABLE: 'info' }

export default {
  name: 'AaArchiveConsoleView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, EmptyState, AppButton, AppDrawer, AppFormItem, AppConfirmDialog, AppInlineAlert, AppTermEntityPicker, AaArchiveCorrectionWorkspace },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, rows: [], current: null, items: [],
      itemColumns: [{ key: 'domain', title: '数据域' }, { key: 'recordCount', title: '记录数' }, { key: 'result', title: '归档状态' }, { key: 'remark', title: '备注' }],
      createVisible: false, form: { termId: '' }, formError: '', saving: false,
      confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      actionBusy: false
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
    itemState(row) { return String(row?.result || (row?.present ? 'PASS' : 'BLOCKED')).toUpperCase() },
    itemLabel(row) { const state = this.itemState(row); return _IL[state] || '待确认' },
    itemType(row) { const state = this.itemState(row); return _IT[state] || 'warning' },
    fmt(s) { return s ? s.replace('T', ' ').slice(0, 16) : '' },
    async load() {
      this.loading = true
      try {
        const pageSize = 100
        const all = []
        let page = 1
        let total = 0
        do {
          const res = await api.listBatches({ page, pageSize })
          if (res.code !== 0) {
            toast.error(res.message || '归档批次加载失败')
            return
          }
          const list = Array.isArray(res.data?.list) ? res.data.list : []
          all.push(...list)
          total = Number(res.data?.total || all.length)
          if (!list.length) break
          page += 1
        } while (all.length < total)
        this.rows = all
      } catch (e) {
        toast.error((e && e.message) || '归档批次加载失败')
      } finally {
        this.loading = false
      }
    },
    async select(b) {
      if (this.actionBusy) return
      const res = await api.getBatch(b.batchId)
      if (res.code === 0) { this.current = res.data; this.items = res.data.items || [] }
      else toast.error(res.message || '归档批次加载失败')
    },
    async refreshCurrentFromServer() {
      if (!this.current?.batchId || this.actionBusy) return
      const batchId = this.current.batchId
      const res = await api.getBatch(batchId)
      if (res.code === 0) {
        this.current = res.data
        this.items = res.data.items || []
        await this.load()
      } else toast.error(res.message || '归档批次刷新失败')
    },
    openCreate() { if (!this.actionBusy) { this.form = { termId: '' }; this.formError = ''; this.createVisible = true } },
    async submitCreate() {
      if (!this.form.termId) { this.formError = '请选择学期'; return }
      if (this.saving) return
      this.saving = true
      try {
        const res = await api.createBatch({ termId: this.form.termId })
        if (res.code === 0) { toast.success('已创建'); this.createVisible = false; await this.load() }
        else this.formError = res.message
      } catch (e) {
        this.formError = (e && e.message) || '创建失败'
      } finally {
        this.saving = false
      }
    },
    async doCheck() {
      if (!this.current || this.actionBusy) return
      this.actionBusy = true
      try {
        const res = await api.check(this.current.batchId)
        if (res.code === 0) {
          toast.success('已检查')
          this.current = res.data
          this.items = res.data.items || []
          await this.load()
        } else toast.error(res.message || '完整性检查失败')
      } catch (e) {
        toast.error((e && e.message) || '完整性检查失败')
      } finally {
        this.actionBusy = false
      }
    },
    doConfirm() {
      if (!this.current || this.actionBusy || this.current.status !== 'READY') return
      const batchId = this.current.batchId
      const batchName = this.current.batchName
      this.confirmTitle = '确认归档'
      this.confirmMessage = `确认归档「${batchName}」？归档后该学期将形成不可普通回退的历史事实，教务写操作受限。`
      this.pendingAction = async () => {
        const res = await api.confirm(batchId, false)
        if (res.code === 0) {
          toast.success('已归档')
          this.confirmVisible = false
          await this.load()
          const b = this.rows.find((x) => x.batchId === batchId)
          if (b) await this.selectAfterAction(b)
        } else toast.error(res.message || '归档失败')
      }
      this.confirmVisible = true
    },
    doCancel() {
      if (!this.current || this.actionBusy || ['ARCHIVED', 'CANCELLED'].includes(this.current.status)) return
      const batchId = this.current.batchId
      const batchName = this.current.batchName
      this.confirmTitle = '取消批次'
      this.confirmMessage = `确认取消归档批次「${batchName}」？`
      this.pendingAction = async () => {
        const res = await api.cancel(batchId)
        if (res.code === 0) {
          toast.success('已取消')
          this.confirmVisible = false
          await this.load()
          const b = this.rows.find((x) => x.batchId === batchId)
          if (b) await this.selectAfterAction(b)
        } else toast.error(res.message || '取消失败')
      }
      this.confirmVisible = true
    },
    async selectAfterAction(b) {
      const res = await api.getBatch(b.batchId)
      if (res.code === 0) { this.current = res.data; this.items = res.data.items || [] }
    },
    async onConfirm() {
      if (this.actionBusy || !this.pendingAction) return
      const action = this.pendingAction
      this.actionBusy = true
      try {
        await action()
      } catch (e) {
        toast.error((e && e.message) || '操作失败')
      } finally {
        this.actionBusy = false
      }
    }
  }
}
</script>

<style scoped>
.aaar-layout { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 16px; }
.aaar-list, .aaar-detail { min-width: 0; }
.aaar-items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aaar-item { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aaar-item.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aaar-item:focus-visible { outline: 2px solid var(--primary-color, #2563eb); outline-offset: 2px; }
.aaar-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.aaar-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; overflow-wrap: anywhere; }
.aaar-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.aaar-summary { display: flex; flex-wrap: wrap; gap: 8px 16px; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
.aaar-summary .is-bad { color: var(--danger-color, #dc2626); font-weight: 600; }
.aaar-section-title { font-weight: 500; margin: 12px 0 8px; }
.aaar-form { display: flex; flex-direction: column; gap: 12px; }
@media (max-width: 900px) {
  .aaar-layout { grid-template-columns: 1fr; }
  .aaar-list { max-height: 240px; overflow: auto; padding: 2px; }
}
@media (max-width: 600px) {
  .aaar-head { flex-direction: column; }
  .aaar-actions { width: 100%; }
  .aaar-summary { flex-direction: column; gap: 6px; }
}
</style>