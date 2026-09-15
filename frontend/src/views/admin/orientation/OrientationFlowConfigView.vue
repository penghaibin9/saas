<template>
  <ModulePageShell title="报到流程配置" subtitle="维护供新批次采用的报到环节" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="报到流程配置">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <section class="flow-scope" aria-label="配置生效范围">
        <strong>这里配置的是新批次模板，不是已启用批次的办理进度。</strong>
        <p>批次启用或首次创建学生时会绑定流程版本。之后修改这里，不会覆盖已绑定批次的环节与学生办理记录。</p>
        <button type="button" @click="$router.push('/admin/orientation/batches')">查看迎新批次</button>
        <button v-if="missingStandardSteps.length" type="button" class="flow-scope__primary" :disabled="!canManage || restoreSubmitting" :title="canManage ? '' : manageReason" @click="restoreVisible = true">补齐 {{ missingStandardSteps.length }} 个标准环节</button>
        <span v-else-if="!loading && !error" class="flow-complete">标准七环节已齐全</span>
      </section>
      <p v-if="!loading && !error && hasLegacySteps" class="flow-warning" role="status">当前配置含历史环节：身份核验或绿色通道。补齐标准流程时会保留这些历史定义并将其停用，避免新批次重复办理；已绑定批次保持原流程。</p>
      <ModuleToolbar :actions="[]" :hint="`共 ${rows.length} 个报到环节 · 调整全程留痕`" />
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id">
        <template #cell-sortOrder="{ row }">
          <span>第 {{ row.displayOrder }} 步</span>
        </template>
        <template #cell-enabled="{ row }">
          <StatusTag :type="row.enabled ? 'success' : 'default'" :label="row.enabled ? '已启用' : '已停用'" dot />
        </template>
        <template #cell-required="{ row }">
          <StatusTag :type="row.required ? 'primary' : 'default'" :label="row.required ? '必办' : '选办'" />
        </template>
        <template #cell-kind="{ row }">
          <StatusTag :type="isLegacy(row) ? 'warning' : 'success'" :label="isLegacy(row) ? '历史兼容' : '标准环节'" />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
      <AppConfirmDialog
        v-model:visible="restoreVisible"
        title="补齐标准报到环节"
        :message="`将新增或恢复：${missingStandardNames.join('、')}；同时停用与标准流程重叠的历史兼容环节。已绑定批次和学生办理记录均保持不变。`"
        confirm-text="确认补齐标准环节"
        :submitting="restoreSubmitting"
        @confirm="completeStandard"
      />
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const STANDARD_STEPS = [
  { key: 'ACTIVATE', name: '账号激活' }, { key: 'INFO', name: '信息核对' },
  { key: 'MATERIAL', name: '材料上传' }, { key: 'PAYMENT', name: '缴费/绿色通道' },
  { key: 'DORM', name: '宿舍确认' }, { key: 'CHECKIN', name: '现场报到' },
  { key: 'CONFIRM', name: '学院确认' }
]

export default {
  name: 'OrientationFlowConfigView',
  components: { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, TableActionColumn, NoPermissionState, AppConfirmDialog },
  data() { return { ctx: null, loading: true, error: '', rows: [], submitting: false, restoreVisible: false, restoreSubmitting: false } },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return this.ctx ? !p?.allowed : false },
    hasLegacySteps() { return this.rows.some(row => ['IDENTITY', 'FINANCE'].includes(row.stepKey)) },
    canManage() { return Boolean(this.perms['orientation.student.edit']?.allowed) },
    manageReason() { return this.perms['orientation.student.edit']?.reason || '当前身份不可调整流程' },
    missingStandardSteps() { const keys = new Set(this.rows.map(row => row.stepKey)); return STANDARD_STEPS.filter(step => !keys.has(step.key)) },
    missingStandardNames() { return this.missingStandardSteps.map(step => step.name) },
    tableColumns() { return [{ key: 'sortOrder', title: '顺序' }, { key: 'stepName', title: '环节' }, { key: 'kind', title: '类型' }, { key: 'enabled', title: '启用' }, { key: 'required', title: '必办' }, { key: 'actions', title: '操作' }] }
  },
  async created() { await this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      try {
        const c = await api.getOrientationContext()
        if (c.code !== 0) throw new Error(c.message || '权限上下文读取失败')
        this.ctx = c.data
        if (this.noPermission) { this.rows = []; return }
        const res = await api.getFlowConfig()
        if (res.code !== 0) throw new Error(res.message || '流程读取失败')
        this.rows = (res.data || []).map((row, index) => ({ ...row, displayOrder: index + 1 }))
      } catch (e) { this.rows = []; this.error = e.message || '加载失败' } finally { this.loading = false }
    },
    rowActions(row) {
      const permission = this.perms['orientation.student.edit']
      const legacy = this.isLegacy(row)
      return [{ key: 'toggleEnabled', label: row.enabled ? '停用' : '启用' }, { key: 'toggleRequired', label: row.required ? '设为选办' : '设为必办' }].map(action => ({ ...action, disabled: legacy || this.submitting || !permission?.allowed, disabledReason: legacy ? '历史兼容环节已冻结，请使用对应标准环节' : this.submitting ? '正在保存，请稍候' : permission?.reason || '当前身份不可调整流程' }))
    },
    isLegacy(row) { return ['IDENTITY', 'FINANCE'].includes(row?.stepKey) },
    async completeStandard() {
      if (this.restoreSubmitting || !this.canManage || !this.missingStandardSteps.length) return
      this.restoreSubmitting = true
      try {
        const res = await api.completeStandardFlowConfig()
        if (res.code !== 0) throw new Error(res.message || '标准环节补齐失败')
        this.rows = (res.data?.items || []).map((row, index) => ({ ...row, displayOrder: index + 1 }))
        this.restoreVisible = false
        const changed = Number(res.data?.addedCount || 0) + Number(res.data?.restoredCount || 0)
        toast.success(changed ? `已补齐 ${changed} 个标准环节，仅供后续批次采用` : '标准七环节已经齐全')
      } catch (e) { toast.error(e.message || '补齐失败，请重新读取后重试') }
      finally { this.restoreSubmitting = false }
    },
    async onRowAction(k, row) {
      if (this.submitting || !this.perms['orientation.student.edit']?.allowed || !['toggleEnabled', 'toggleRequired'].includes(k)) return
      this.submitting = true
      const payload = k === 'toggleEnabled' ? { enabled: !row.enabled } : { required: !row.required }
      try {
        const res = await api.updateFlowConfig(row.id, payload)
        if (res.code === 0) { toast.success('新批次模板已更新，已绑定批次保持原流程'); await this.load() } else toast.error(res.message || '更新失败')
      } catch (e) { toast.error(e.message || '更新失败，请重新读取后重试') }
      finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
.flow-scope{padding:16px 20px;border:1px solid var(--line,#dce5f3);border-radius:10px;background:var(--bg-card,#fff);color:var(--t1,#17385d);font-size:14px;line-height:1.7}.flow-scope p{margin:6px 0;color:var(--t2,#536984)}.flow-scope button{border:0;background:none;color:var(--pri,#2859b8);padding:6px 0;margin-right:18px;cursor:pointer;font:inherit}.flow-scope button:disabled{color:var(--text-disabled,#98a4b3);cursor:not-allowed}.flow-scope .flow-scope__primary{padding:7px 12px;border-radius:7px;background:var(--pri,#2859b8);color:#fff}.flow-complete{color:#087f5b;font-weight:600}.flow-warning{padding:12px 16px;margin:0;border:1px solid #efcb86;border-radius:8px;background:#fff8e8;color:#805413;font-size:14px;line-height:1.8}
</style>
