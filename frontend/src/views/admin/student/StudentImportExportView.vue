<template>
  <ModulePageShell
    title="数据导出"
    subtitle="模板下载 · 字段校验 · 错误预览 · 脱敏水印 · 审计回执"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="学生数据导出"
  >
    <AppGlobalState
      v-if="forbidden"
      state="forbidden"
      title="暂无学生数据导出权限"
      :description="forbiddenReason"
    />
    <div v-else class="mp-stack">
      <AccountImportBoundaryNotice />

      <div class="mp-stack">
        <!-- 导出 -->
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">批量导出</span>
            <span v-if="!canExport" class="mp-note">{{ reason('exportStudents') }}</span>
          </div>
          <div class="mp-card__body mp-stack">
            <div>
              <div class="ie-label">导出范围</div>
              <label
                v-for="s in exportOpts.scopes"
                :key="s.value"
                class="mp-radio"
                :class="{ 'is-active': exportForm.scope === s.value }"
              >
                <input v-model="exportForm.scope" type="radio" :value="s.value" :disabled="!canExport" />
                <span>
                  <span class="mp-radio__title">{{ s.label }}</span>
                  <span class="mp-radio__desc">{{ s.desc }}</span>
                </span>
              </label>
            </div>

            <div>
              <div class="ie-label">导出字段（敏感字段导出后自动脱敏）</div>
              <div v-for="g in exportOpts.fieldGroups" :key="g.key" class="ie-group">
                <div class="ie-group__title">{{ g.label }}</div>
                <label v-for="f in g.fields" :key="f.key" class="ie-check">
                  <input
                    type="checkbox"
                    :checked="exportForm.fieldKeys.includes(f.key)"
                    :disabled="!canExport"
                    @change="toggleField(f.key, $event.target.checked)"
                  />
                  {{ f.label }}
                  <span v-if="f.sensitive" class="ie-sensitive">脱敏</span>
                </label>
              </div>
            </div>

            <div>
              <div class="ie-label">导出用途（写入审计）</div>
              <select v-model="exportForm.purpose" class="ie-control" :disabled="!canExport">
                <option value="">请选择用途</option>
                <option v-for="p in exportOpts.purposes" :key="p.value" :value="p.value">{{ p.label }}</option>
              </select>
              <textarea
                v-model="exportForm.remark"
                class="mp-textarea ie-remark"
                placeholder="补充说明（选填），将与用途一并写入审计日志"
                :disabled="!canExport"
              />
            </div>

            <p v-if="exportError" class="mp-form-err">{{ exportError }}</p>
            <div class="ie-row">
              <AppButton variant="primary" :disabled="!canExport" @click="openExportConfirm">创建导出任务</AppButton>
              <span class="mp-note">导出文件自动脱敏并附「{{ ctx.tenantBrandConfig.watermarkText }}」水印</span>
            </div>
          </div>
        </section>
      </div>

      <!-- 任务回执 -->
      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">导入导出任务回执</span>
          <span class="mp-note">每个任务对应一条审计编号，可追溯</span>
        </div>
        <div class="mp-card__body">
          <EmptyState v-if="!tasks.length" title="暂无任务记录" />
          <table v-else class="mp-audit">
            <thead>
              <tr>
                <th>类型</th>
                <th>任务</th>
                <th>行数（成功 / 失败）</th>
                <th>安全措施</th>
                <th>操作人</th>
                <th>时间</th>
                <th>审计编号</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in tasks" :key="t.id">
                <td class="is-who">{{ t.typeLabel }}</td>
                <td>
                  {{ t.title }}
                  <div class="mp-cell-sub">{{ t.fileName }}</div>
                </td>
                <td>{{ t.totalRows }}（{{ t.successRows }} / {{ t.failedRows }}）</td>
                <td>
                  <AppStatusTag v-if="t.masked" type="info" label="已脱敏" />
                  <AppStatusTag v-if="t.watermark" type="info" label="含水印" />
                  <span v-if="!t.masked && !t.watermark" class="mp-note">—</span>
                </td>
                <td>{{ t.operator }}（{{ t.roleName }}）</td>
                <td>{{ t.time }}</td>
                <td>{{ t.auditId }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 审计留痕 -->
      <section v-if="canAudit" class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">最近审计留痕</span></div>
        <div class="mp-card__body">
          <table class="mp-audit">
            <thead>
              <tr><th>时间</th><th>操作人</th><th>动作</th><th>对象</th><th>说明</th></tr>
            </thead>
            <tbody>
              <tr v-for="a in audits" :key="a.id">
                <td>{{ a.time }}</td>
                <td class="is-who">{{ a.operator }}（{{ a.roleName }}）</td>
                <td>{{ a.action }}</td>
                <td>{{ a.targetName }}</td>
                <td>{{ a.detail }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- 导出确认（审计确认） -->
    <AppConfirmDialog
      :visible="exportDialog.visible"
      type="warning"
      title="确认创建导出任务"
      :message="exportSummary"
      confirm-text="确认导出"
      :submitting="exportDialog.submitting"
      @update:visible="exportDialog.visible = $event"
      @confirm="submitExport"
    />
  </ModulePageShell>
</template>

<script>
/** 学生数据导出（/admin/student/import-export）：范围 → 字段 → 用途 → 任务；脱敏 + 水印 + 审计。
 *
 * 导入部分已迁出：学生主档只有教务学籍导入与系统管理学生导入两条正式写入路径，
 * 学工侧的「导入学生」改为分流页 StudentImportGatewayView，不再上传与写入。
 * 路径保持不变以免旧链接 404；菜单标签已改为「数据导出」。
 */
import { ModulePageShell, StatusTag as AppStatusTag, EmptyState } from '@/components/business'
import { AppGlobalState, AppConfirmDialog } from '@/components/common'
import AccountImportBoundaryNotice from '@/components/common/AccountImportBoundaryNotice.vue'
import { AppButton } from '@/components/ui'
import { studentApi } from '@/modules/student/api/student.api'
import { toast } from '@/utils/toast'

export default {
  name: 'StudentImportExportView',
  components: { ModulePageShell, AppStatusTag, EmptyState, AppGlobalState, AppConfirmDialog, AppButton, AccountImportBoundaryNotice },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tasks: [],
      audits: [],
      exportOpts: { scopes: [], fieldGroups: [], purposes: [] },
      exportForm: { scope: 'CURRENT_SCOPE', fieldKeys: ['name', 'studentNo', 'orgPath'], purpose: '', remark: '' },
      exportError: '',
      exportDialog: { visible: false, submitting: false }
    }
  },
  computed: {
    canExport() {
      const pa = this.ctx.permissionActions.exportStudents
      return !!(pa && pa.visible && pa.allowed)
    },
    canAudit() {
      const pa = this.ctx.permissionActions.viewAudit
      return !!(pa && pa.visible && pa.allowed)
    },
    forbidden() {
      const pa = this.ctx.permissionActions
      return !(pa.exportStudents && pa.exportStudents.visible)
    },
    forbiddenReason() {
      const pa = this.ctx.permissionActions
      return (pa.exportStudents && pa.exportStudents.reason) || '请联系系统管理员开通'
    },
    exportSummary() {
      const scope = this.exportOpts.scopes.find((s) => s.value === this.exportForm.scope)
      const purpose = this.exportOpts.purposes.find((p) => p.value === this.exportForm.purpose)
      const sensitiveCount = this.exportOpts.fieldGroups
        .flatMap((g) => g.fields)
        .filter((f) => this.exportForm.fieldKeys.includes(f.key) && f.sensitive).length
      return (
        '范围：' + (scope ? scope.label : '—') +
        '；字段 ' + this.exportForm.fieldKeys.length + ' 个（含敏感字段 ' + sensitiveCount + ' 个，导出后自动脱敏）' +
        '；用途：' + (purpose ? purpose.label : '—') +
        '。文件将附水印，本次导出写入审计日志。'
      )
    }
  },
  async created() {
    const optRes = await studentApi.getExportOptions()
    if (optRes.code === 0) this.exportOpts = optRes.data
    this.refreshTasks()
    this.refreshAudits()
  },
  methods: {
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    openExportConfirm() {
      this.exportError = ''
      if (!this.exportForm.fieldKeys.length) {
        this.exportError = '请至少选择一个导出字段'
        return
      }
      if (!this.exportForm.purpose) {
        this.exportError = '导出用途必选（用于审计留痕）'
        return
      }
      this.exportDialog = { visible: true, submitting: false }
    },
    async submitExport() {
      this.exportDialog.submitting = true
      const res = await studentApi.createExport(this.exportForm)
      this.exportDialog.submitting = false
      if (res.code === 0) {
        this.exportDialog.visible = false
        toast.success('导出任务已创建：已脱敏、含水印，审计编号 ' + res.data.auditId)
        this.exportForm.remark = ''
        this.refreshTasks()
        this.refreshAudits()
      } else {
        this.exportError = res.message
        this.exportDialog.visible = false
      }
    },
    async refreshTasks() {
      const res = await studentApi.getTransferTasks()
      if (res.code === 0) this.tasks = res.data
    },
    async refreshAudits() {
      if (!this.canAudit) return
      const res = await studentApi.getAuditLogs({ page: 1, pageSize: 6 })
      if (res.code === 0) this.audits = res.data.list
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

/* 步骤标题 */
.ie-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  margin-bottom: var(--space-2);
}
.ie-tpl {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-2);
}
.ie-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.ie-control {
  height: 34px;
  min-width: 220px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  outline: none;
}
.ie-control:focus {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-50);
}
.ie-check {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-right: var(--space-3);
  cursor: pointer;
}
.ie-validate {
  margin: var(--space-2) 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.ie-ok {
  color: var(--success-600);
  font-weight: var(--font-weight-semibold);
}
.ie-bad {
  color: var(--danger-600);
  font-weight: var(--font-weight-semibold);
}
.ie-group {
  margin-bottom: var(--space-2);
}
.ie-group__title {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-bottom: var(--space-1);
}
.ie-sensitive {
  display: inline-block;
  padding: 0 var(--space-1);
  border-radius: var(--radius-base);
  background: var(--warning-50);
  color: var(--warning-600);
  border: 1px solid var(--warning-100);
  font-size: var(--font-size-xs);
}
.ie-remark {
  margin-top: var(--space-2);
  min-height: 56px;
}
</style>
