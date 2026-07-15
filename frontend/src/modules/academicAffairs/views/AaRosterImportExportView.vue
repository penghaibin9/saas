<template>
  <ModulePageShell
    title="学籍导入导出"
    subtitle="学籍名册批量建档（Excel）与台账导出 · 数据落 t_student_profile"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AppSectionCard title="学籍导入" subtitle="批量建立学籍档案（不可用于变更在籍学生的学籍状态，休学/退学等请走「学籍异动」）">
        <p class="mp-note">
          导入用于学校历史学籍数据初始化或批量新增学生主档：学号/姓名/班级必填，班级须为「学院专业班级」中已建好的
          行政班（按名称精确匹配）；初始学籍状态仅允许 待注册/正常/在籍注册。导入全流程：下载模板 → 上传解析 →
          预校验（失败行不导入）→ 确认导入，写入审计与导入作业记录。
        </p>
        <button class="mp-btn mp-btn--primary" @click="importVisible = true">打开批量导入</button>
      </AppSectionCard>

      <AppSectionCard title="学籍导出" subtitle="导出当前学籍名册台账（脱敏 + 水印 + 审计）">
        <div class="aa-export-row">
          <label class="aa-filter__item">
            关键字
            <input v-model.trim="exportFilters.keyword" class="aa-input" placeholder="姓名 / 学号（可选）" />
          </label>
          <label class="aa-filter__item">
            学籍状态
            <select v-model="exportFilters.status" class="aa-select">
              <option value="">全部</option>
              <option v-for="(label, val) in STATUS_LABEL" :key="val" :value="val">{{ label }}</option>
            </select>
          </label>
          <button class="mp-btn" :disabled="exporting" @click="doExport">{{ exporting ? '导出中…' : '导出 Excel' }}</button>
        </div>
        <p class="mp-note">导出需填写用途（不少于 5 个字），文件首行带水印，身份证等敏感字段仍按脱敏规则导出。</p>
      </AppSectionCard>
    </div>

    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入学籍名册"
      template-name="学籍导入模板.xlsx"
      :required-fields="['学号', '姓名', '班级']"
      :preview-fields="['studentNo', 'realName', 'className', 'initialStatus']"
      :download-template-fn="() => academicAffairsApi.downloadRosterImportTemplate()"
      :upload-fn="(file) => academicAffairsApi.uploadRosterImportXlsx(file)"
      :confirm-fn="({ rows }) => academicAffairsApi.rosterImportConfirm(rows)"
      :download-errors-fn="({ rows, errors }) => academicAffairsApi.downloadRosterImportErrors(rows, errors)"
      @imported="onImported"
    />
  </ModulePageShell>
</template>

<script>
/** 学籍导入导出（/admin/academic-affairs/roster/import-export）。
 * 导入：复用公共 Excel 底座（app.services.excel ImportSpec）+ AppExcelImportDrawer，模板/预校验/错误行/确认导入
 * 全走真实后端，不 mock；数据落 t_student_profile（不与「学籍异动」重复实现，导入初始状态被限制在
 * 待注册/正常/在籍注册三态，休学/退学等仍须导入建档后走学籍异动办理）。
 * 导出：与本模块既有 export_unregistered_xlsx 同款 xlsx_util 直出 + 用途必填≥5字口径一致。 */
import { ModulePageShell } from '@/components/business'
import { AppSectionCard } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const STATUS_LABEL = {
  NORMAL: '正常', PENDING_REGISTER: '待注册', REGISTERED: '在籍注册', UNREGISTERED: '未注册',
  SUSPENDED: '休学', RETAINED: '留级', WITHDRAWN: '退学', TRANSFER_SCHOOL: '转学',
  GRADUATED: '毕业', COMPLETED: '结业', INCOMPLETE: '肄业'
}

export default {
  name: 'AaRosterImportExportView',
  components: { ModulePageShell, AppSectionCard, AppExcelImportDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      academicAffairsApi,
      STATUS_LABEL,
      importVisible: false,
      exporting: false,
      exportFilters: { keyword: '', status: '' }
    }
  },
  methods: {
    onImported(data) {
      toast.success(`已导入 ${data?.created ?? 0} 名学生学籍档案`)
    },
    async doExport() {
      const purpose = window.prompt('请填写导出用途（≥5 字，将写入审计与文件水印）：', '')
      if (purpose === null) return
      if (!purpose || purpose.trim().length < 5) {
        toast.error('导出用途必填且不少于 5 个字')
        return
      }
      this.exporting = true
      const res = await academicAffairsApi.exportRoster({
        purpose: purpose.trim(),
        keyword: this.exportFilters.keyword || undefined,
        status: this.exportFilters.status || undefined
      })
      this.exporting = false
      if (res.code !== 0) {
        toast.error(res.message || '导出失败')
        return
      }
      const href = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = href
      a.download = `学籍名册-${Date.now()}.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(href)
      toast.success('导出成功')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-export-row { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; margin-bottom: var(--space-2); }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input, .aa-select {
  height: 32px; padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px;
}
</style>
