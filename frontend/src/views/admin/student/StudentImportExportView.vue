<template>
  <div class="sp-page" style="position: relative">
    <SecurityWatermark purpose="学生主档导入导出" />
    <AppSectionHeader
      title="导入导出"
      subtitle="本页为 01-P1 预留：仅 mock 校验与审计演示，不解析真实文件、不产生真实下载（真实导入导出在 01-P2 开发）"
    />

    <StudentStateBlock :no-permission="noPermission">
      <div class="sp-cols">
        <AppCard class="sp-card">
          <AppSectionHeader title="学生主档导入（预留）" compact />
          <p class="ie-text">
            支持按模板批量导入学生主档。导入流程：下载模板 → 填写 → 上传 → Dry-Run 校验 → 确认导入。
            上传文件将经安全基线校验（类型白名单 pdf/doc/docx/jpg/jpeg/png/zip/rar/xlsx/pptx，单文件 ≤ 50MB）。
          </p>
          <AppInlineAlert type="info" description="当前为校验演示：点击下方按钮查看 mock 校验结果，不会上传或解析任何真实文件。" />
          <div class="stu-panel__actions" style="display: flex; justify-content: flex-end; gap: var(--space-3)">
            <AppButton
              variant="primary"
              :disabled="!canImport || importing"
              :loading="importing"
              :title="canImport ? '' : '当前账号无导入权限'"
              @click="onValidateImport"
            >执行导入校验（mock）</AppButton>
          </div>
          <template v-if="importResult">
            <AppSectionHeader title="校验结果" compact />
            <div class="ie-result">
              <span>总行数 {{ importResult.totalRows }}</span>
              <span class="ie-ok">有效 {{ importResult.validRows }}</span>
              <span class="ie-bad">异常 {{ importResult.errorRows }}</span>
            </div>
            <table class="sp-table">
              <thead><tr><th>行号</th><th>字段</th><th>问题</th></tr></thead>
              <tbody>
                <tr v-for="(e, i) in importResult.errors" :key="i">
                  <td>{{ e.row }}</td><td>{{ e.field }}</td><td>{{ e.message }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </AppCard>

        <AppCard class="sp-card">
          <AppSectionHeader title="学生主档导出（预留）" compact />
          <p class="ie-text">
            导出分三档：台账导出 / 加密档案 / 脱敏外发。所有导出默认脱敏、携带页面水印口径、强制写入审计事件；
            超出行数上限需走异步导出。
          </p>
          <AppInlineAlert type="info" description="当前为导出演示：经 security 导出闸口校验并写入审计事件，不生成真实文件。" />
          <div class="stu-panel__actions" style="display: flex; justify-content: flex-end; gap: var(--space-3)">
            <AppButton
              variant="primary"
              :disabled="!canExport || exporting"
              :loading="exporting"
              :title="canExport ? '' : '当前账号无导出权限'"
              @click="onExport"
            >执行导出（mock）</AppButton>
          </div>
          <template v-if="exportResult">
            <AppInlineAlert
              type="success"
              :description="`导出任务已创建（mock）：任务号 ${exportResult.taskId}，共 ${exportResult.rowCount} 行，已附水印标识并写入导出审计。`"
            />
          </template>
          <template v-if="exportError">
            <AppInlineAlert type="warning" :description="`导出被安全闸口拦截：${exportError}`" />
          </template>
        </AppCard>
      </div>
    </StudentStateBlock>
  </div>
</template>

<script>
/** 页面 7：/admin/student/import-export 导入导出（仅 mock 预留；真实实现属 01-P2） */
import { AppCard, AppButton, AppSectionHeader } from '@/components/ui'
import AppInlineAlert from '@/components/common/AppInlineAlert.vue'
import { SecurityWatermark } from '@/security'
import StudentStateBlock from '@/modules/student/components/StudentStateBlock.vue'
import { studentProvider, hasStudentPermission, STUDENT_PERMISSION } from '@/modules/student'
import { toast } from '@/utils/toast'

export default {
  name: 'StudentImportExportView',
  components: { AppCard, AppButton, AppSectionHeader, AppInlineAlert, SecurityWatermark, StudentStateBlock },
  data() {
    return {
      importing: false,
      exporting: false,
      importResult: null,
      exportResult: null,
      exportError: ''
    }
  },
  computed: {
    noPermission() {
      return !hasStudentPermission(STUDENT_PERMISSION.PROFILE_VIEW)
    },
    canImport() {
      return hasStudentPermission(STUDENT_PERMISSION.IMPORT)
    },
    canExport() {
      return hasStudentPermission(STUDENT_PERMISSION.EXPORT)
    }
  },
  methods: {
    async onValidateImport() {
      this.importing = true
      try {
        const res = await studentProvider.validateStudentImport({})
        if (res.code === 0) {
          this.importResult = res.data
          toast.success('导入校验完成（mock），已写入审计')
        } else toast.warning(res.message)
      } finally {
        this.importing = false
      }
    },
    async onExport() {
      this.exporting = true
      this.exportError = ''
      this.exportResult = null
      try {
        const res = await studentProvider.exportStudents({ exportType: 'LIST', purpose: '主档台账核对' })
        if (res.code === 0) {
          this.exportResult = res.data
          toast.success('导出任务已创建（mock），审计已留痕')
        } else {
          this.exportError = res.message
        }
      } finally {
        this.exporting = false
      }
    }
  }
}
</script>

<style scoped>
@import './student-page.css';
.ie-text { margin: 0; font-size: var(--font-size-sm); color: var(--text-secondary); line-height: var(--line-height-base); }
.ie-result { display: flex; gap: var(--space-4); font-size: var(--font-size-sm); color: var(--text-secondary); }
.ie-ok { color: var(--success-600); }
.ie-bad { color: var(--danger-600); }
</style>
