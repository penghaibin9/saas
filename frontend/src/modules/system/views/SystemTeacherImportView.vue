<template>
  <ModulePageShell
    title="教师导入"
    subtitle="批量创建教职工账号、绑定预设角色与数据范围"
    :watermark="true"
    watermark-purpose="教师导入"
  >
    <AppGlobalState v-if="!canImport" state="forbidden" title="暂无教师导入权限"
                    :description="'请联系系统管理员开通「批量创建账号」权限'" />
    <div v-else class="sti">
      <section class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">导入内容</span></div>
        <div class="mp-card__body">
          <ul class="sti__points">
            <li>创建教职工登录账号并生成一次性初始密码回执</li>
            <li>按「预设角色编码」绑定角色（可多个，逗号/分号/竖线分隔）</li>
            <li>配置数据范围：SCHOOL / COLLEGE / CLASS / ADVISOR</li>
            <li>辅导员必须填写 CLASS 或 ADVISOR 范围及对应班级</li>
          </ul>
          <p class="sti__note">
            本模板<strong>不包含</strong>学生的学院、专业、班级、年级与学籍状态；
            导入学生请前往
            <button class="mp-link" @click="$router.push('/admin/system/identity-import/students')">学生导入与账号开通</button>。
          </p>
        </div>
      </section>

      <section class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">批量导入</span></div>
        <div class="mp-card__body">
          <AppButton variant="primary" @click="importOpen = true">开始导入教师</AppButton>
        </div>
      </section>
    </div>

    <ImportDialog
      v-model:visible="importOpen"
      :template="template"
      :run-validate="api.validateTeacherIdentityFile"
      :run-import="api.confirmTeacherIdentityBatch"
      :run-download-template="api.downloadTeacherImportTemplate"
      :run-download-errors="api.downloadIdentityImportErrors"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 系统管理 › 身份与账号 › 教师导入（独立三级页面）。
 * 角色绑定、数据范围、辅导员班级范围、初始密码回执、重复登录名校验、跨租户阻断、
 * 整批事务与错误回执等既有能力全部保留，仅把入口与模板同学生拆开。
 */
import { ModulePageShell } from '@/components/business'
import { AppGlobalState } from '@/components/common'
import { AppButton } from '@/components/ui'
import ImportDialog from '@/modules/system/components/ImportDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'

export default {
  name: 'SystemTeacherImportView',
  components: { ModulePageShell, AppGlobalState, AppButton, ImportDialog },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      importOpen: false,
      api: systemApi,
      template: { name: '教师导入', description: '仅教职工字段：工号、姓名、部门、岗位、预设角色、数据范围' }
    }
  },
  computed: {
    canImport() {
      const pa = (this.ctx && this.ctx.permissionActions) || {}
      const item = pa.importUsers
      return item ? !!(item.visible && item.allowed) : true
    }
  }
}
</script>

<style scoped>
.sti { display: flex; flex-direction: column; gap: 16px; }
.sti__points { margin: 0 0 10px; padding-left: 18px; line-height: 1.9; color: var(--mp-text-secondary, #5b6472); }
.sti__note { margin: 6px 0 0; color: var(--mp-text-tertiary, #8a94a6); font-size: 13px; line-height: 1.7; }
</style>
