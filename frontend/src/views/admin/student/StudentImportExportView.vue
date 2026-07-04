<template>
  <ModulePageShell
    title="导入导出管理"
    subtitle="模板下载 · 字段校验 · 错误预览 · 脱敏水印 · 审计回执"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="学生数据导入导出"
  >
    <AppGlobalState
      v-if="forbidden"
      state="forbidden"
      title="暂无导入导出权限"
      :description="forbiddenReason"
    />
    <div v-else class="mp-stack">
      <div class="mp-grid-2">
        <!-- 导入 -->
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">批量导入</span>
            <span v-if="!canImport" class="mp-note">{{ reason('importStudents') }}</span>
          </div>
          <div class="mp-card__body mp-stack">
            <div>
              <div class="ie-label">1. 下载导入模板</div>
              <div v-for="t in templates" :key="t.id" class="ie-tpl">
                <div>
                  <div class="mp-cell-main">{{ t.name }}</div>
                  <div class="mp-cell-sub">{{ t.description }} · {{ t.fieldCount }} 个字段 · 更新于 {{ t.updatedAt }}</div>
                </div>
                <AppButton variant="ghost" @click="downloadTemplate(t)">下载模板</AppButton>
              </div>
            </div>

            <div>
              <div class="ie-label">2. 选择模板与数据文件</div>
              <div class="ie-row">
                <select v-model="importForm.templateId" class="ie-control" :disabled="!canImport">
                  <option value="">请选择导入模板</option>
                  <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
                </select>
                <AppButton variant="secondary" :disabled="!canImport" @click="pickFile">
                  {{ importForm.fileName || '选择数据文件（xlsx / csv）' }}
                </AppButton>
                <input
                  ref="fileInput"
                  type="file"
                  accept=".xlsx,.csv"
                  style="display: none"
                  @change="onFilePicked"
                />
              </div>
            </div>

            <div>
              <div class="ie-label">3. 校验与导入</div>
              <div class="ie-row">
                <AppButton variant="primary" :disabled="!canImport || validating" @click="validate">
                  {{ validating ? '校验中…' : '开始校验' }}
                </AppButton>
                <label v-if="validateResult && !realImport" class="ie-check">
                  <input v-model="importForm.skipErrors" type="checkbox" />
                  跳过错误行继续导入
                </label>
                <AppButton
                  v-if="validateResult"
                  variant="primary"
                  :disabled="!canImport || importing || (validateResult.errorRows > 0 && (realImport || !importForm.skipErrors))"
                  @click="confirmImport"
                >
                  {{ importing ? '导入中…' : '确认导入' }}
                </AppButton>
              </div>
              <p v-if="importError" class="mp-form-err">{{ importError }}</p>

              <template v-if="validateResult">
                <div class="ie-validate">
                  校验完成：共 {{ validateResult.totalRows }} 行，可导入
                  <span class="ie-ok">{{ validateResult.validRows }}</span> 行，错误
                  <span class="ie-bad">{{ validateResult.errorRows }}</span> 行
                </div>
                <table v-if="validateResult.errors.length" class="mp-audit">
                  <thead>
                    <tr><th>行号</th><th>字段</th><th>原始值</th><th>错误说明</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="e in validateResult.errors" :key="e.row">
                      <td class="is-who">第 {{ e.row }} 行</td>
                      <td>{{ e.field }}</td>
                      <td>{{ e.rawValue || '—' }}</td>
                      <td>{{ e.message }}</td>
                    </tr>
                  </tbody>
                </table>
              </template>
            </div>
          </div>
        </section>

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
/** 导入导出管理（/admin/student/import-export）：模板 → 校验 → 错误预览 → 回执；导出脱敏 + 水印 + 审计。 */
import { ModulePageShell, StatusTag as AppStatusTag, EmptyState } from '@/components/business'
import { AppGlobalState, AppConfirmDialog } from '@/components/common'
import { AppButton } from '@/components/ui'
import { studentApi } from '@/modules/student/api/student.api'
import { shouldTryReal } from '@/services/http/client'
import { confirmStudentImport, validateStudentImportFile } from '@/services/http/adapters'
import { toast } from '@/utils/toast'

export default {
  name: 'StudentImportExportView',
  components: { ModulePageShell, AppStatusTag, EmptyState, AppGlobalState, AppConfirmDialog, AppButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      templates: [],
      tasks: [],
      audits: [],
      exportOpts: { scopes: [], fieldGroups: [], purposes: [] },
      importForm: { templateId: '', fileName: '', skipErrors: false },
      pickedFile: null,
      realBatchNo: '',
      realImport: false,
      validating: false,
      importing: false,
      validateResult: null,
      importError: '',
      exportForm: { scope: 'CURRENT_SCOPE', fieldKeys: ['name', 'studentNo', 'orgPath'], purpose: '', remark: '' },
      exportError: '',
      exportDialog: { visible: false, submitting: false }
    }
  },
  computed: {
    canImport() {
      const pa = this.ctx.permissionActions.importStudents
      return !!(pa && pa.visible && pa.allowed)
    },
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
      const importVisible = pa.importStudents && pa.importStudents.visible
      const exportVisible = pa.exportStudents && pa.exportStudents.visible
      return !importVisible && !exportVisible
    },
    forbiddenReason() {
      const pa = this.ctx.permissionActions
      return (pa.importStudents && pa.importStudents.reason) || (pa.exportStudents && pa.exportStudents.reason) || '请联系系统管理员开通'
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
    const [tplRes, optRes] = await Promise.all([studentApi.getImportTemplates(), studentApi.getExportOptions()])
    if (tplRes.code === 0) this.templates = tplRes.data
    if (optRes.code === 0) this.exportOpts = optRes.data
    this.refreshTasks()
    this.refreshAudits()
  },
  methods: {
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    downloadTemplate(t) {
      toast.success('模板「' + t.fileName + '」已开始下载（演示环境不产生真实文件）')
    },
    pickFile() {
      // 真实文件选择（后端在线走 /import/students/validate-file；离线回退 mock 演示）
      if (this.$refs.fileInput) {
        this.$refs.fileInput.value = ''
        this.$refs.fileInput.click()
        return
      }
      this.importForm.fileName = 'student-import-' + Date.now() + '.xlsx'
      this.validateResult = null
      this.importError = ''
    },
    onFilePicked(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.pickedFile = file
      this.importForm.fileName = file.name
      this.validateResult = null
      this.realBatchNo = ''
      this.realImport = false
      this.importError = ''
    },
    async validate() {
      this.importError = ''
      this.validating = true
      let res
      if (this.pickedFile && shouldTryReal()) {
        // 真实 Dry-Run：上传 xlsx/csv → 后端解析校验（失败自动回退 mock 演示流）
        res = await validateStudentImportFile(this.pickedFile).catch(() => null)
        if (res && res.code === 0) {
          this.realImport = true
          this.realBatchNo = res.data.batchNo
        }
      }
      if (!res) {
        this.realImport = false
        res = await studentApi.validateImport(this.importForm)
      }
      this.validating = false
      if (res.code === 0) {
        this.validateResult = res.data
        this.refreshAudits()
      } else {
        this.importError = res.message
      }
    },
    async confirmImport() {
      this.importError = ''
      this.importing = true
      let res
      if (this.realImport && this.realBatchNo) {
        res = await confirmStudentImport(this.realBatchNo).catch((e) => ({ code: -1, message: e.message }))
      } else {
        res = await studentApi.confirmImport(this.importForm)
      }
      this.importing = false
      if (res.code === 0) {
        toast.success(
          '导入完成：成功 ' + res.data.successRows + ' 条，失败 ' + res.data.failedRows + ' 条，批次 ' + res.data.auditId
        )
        const wasReal = this.realImport
        this.validateResult = null
        this.pickedFile = null
        this.realBatchNo = ''
        this.realImport = false
        this.importForm = { templateId: '', fileName: '', skipErrors: false }
        this.refreshTasks()
        this.refreshAudits()
        if (wasReal) {
          // 真实导入成功：跳转学生主档列表（列表挂载即从后端拉取最新数据）
          this.$router.push('/admin/student/list')
        }
      } else {
        this.importError = res.message
      }
    },
    toggleField(key, checked) {
      const list = this.exportForm.fieldKeys
      this.exportForm.fieldKeys = checked ? [...list, key] : list.filter((k) => k !== key)
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
