<template>
  <ModulePageShell
    title="学生导入与账号开通"
    subtitle="创建或复用学生主档，并开通登录账号"
    :watermark="true"
    watermark-purpose="学生导入与账号开通"
  >
    <AppGlobalState v-if="!canImport" state="forbidden" title="暂无学生导入权限"
                    :description="'请联系系统管理员开通「批量创建账号」权限'" />
    <div v-else class="sii">
      <section class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">适用场景</span></div>
        <div class="mp-card__body">
          <ul class="sii__points">
            <li>学校未采购或暂未启用教务中心，需要先导入基础学生名单</li>
            <li>首次实施、从旧系统迁移学生数据</li>
            <li>只购买学工、实习、毕设等部分模块，仍需学生能登录</li>
          </ul>
          <p class="sii__note">
            已在教务建过学籍的学生，这里会<strong>复用原主档</strong>并只补开账号，不会重复建档；
            学号/姓名/证件号对不上，或已归属其它院系班时会阻断并提示走对应流程。
          </p>
        </div>
      </section>

      <section class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">批量导入</span></div>
        <div class="mp-card__body">
          <AppButton variant="primary" @click="importOpen = true">开始导入学生</AppButton>
        </div>
      </section>
    </div>

    <ImportDialog
      v-model:visible="importOpen"
      :template="template"
      :run-validate="api.validateStudentIdentityFile"
      :run-import="api.confirmStudentIdentityBatch"
      :run-download-template="api.downloadStudentImportTemplate"
      :run-download-errors="api.downloadIdentityImportErrors"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 系统管理 › 身份与账号 › 学生导入与账号开通（独立三级页面）。
 *
 * 与「教职工导入」拆成两个真实路由而非 query 参数：刷新后状态不丢、菜单能正确高亮、
 * 权限与页面说明各自独立、模板不会串用。两者共用 ImportDialog 与后端批次/事务/
 * 回执/审计能力，不复制第二套导入框架。
 */
import { ModulePageShell } from '@/components/business'
import { AppGlobalState } from '@/components/common'
import { AppButton } from '@/components/ui'
import ImportDialog from '@/modules/system/components/ImportDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'

export default {
  name: 'SystemStudentImportView',
  components: { ModulePageShell, AppGlobalState, AppButton, ImportDialog },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      importOpen: false,
      api: systemApi,
      template: { name: '学生导入', description: '仅学生字段：学号、姓名、学院、专业、班级、年级、性别、身份证号' }
    }
  },
  computed: {
    canImport() {
      const pa = (this.ctx && this.ctx.permissionActions) || {}
      const item = pa.importUsers
      // ctx 未下发时不误报无权限，后端仍是最终边界
      return item ? !!(item.visible && item.allowed) : true
    }
  }
}
</script>

<style scoped>
.sii { display: flex; flex-direction: column; gap: 16px; }
.sii__points { margin: 0 0 10px; padding-left: 18px; line-height: 1.9; color: var(--mp-text-secondary, #5b6472); }
.sii__note { margin: 6px 0 0; color: var(--mp-text-tertiary, #8a94a6); font-size: 13px; line-height: 1.7; }
</style>
