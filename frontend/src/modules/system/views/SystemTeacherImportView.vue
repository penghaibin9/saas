<template>
  <ModulePageShell
    title="教职工导入"
    subtitle="批量创建教职工账号、绑定预设角色与数据范围"
    :watermark="true"
    watermark-purpose="教职工导入"
  >
    <AppGlobalState v-if="!canImport" state="forbidden" title="暂无教职工导入权限"
                    :description="'请联系系统管理员开通「批量创建账号」权限'" />
    <div v-else class="sti">
      <section class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">导入内容</span></div>
        <div class="mp-card__body">
          <ul class="sti__points">
            <li>创建教职工登录账号并生成短期有效、可撤销的初始密码回执</li>
            <li>按「预设角色编码」绑定角色（可多个，逗号/分号/竖线分隔）</li>
            <li>配置数据范围：SCHOOL / COLLEGE / CLASS / ADVISOR</li>
            <li>辅导员必须填写 CLASS 或 ADVISOR 范围及对应班级</li>
          </ul>
          <p class="sti__note">
            原始 Excel、安全扫描、错误回执和初始凭据回执会进入
            <button class="mp-link" @click="$router.push('/admin/system/data-exchange')">数据交换任务中心</button>，
            凭据回执过期或撤销后将无法继续下载。
          </p>
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
          <AppButton variant="primary" @click="importOpen = true">开始导入教职工</AppButton>
        </div>
      </section>
    </div>

    <ImportDialog
      v-model:visible="importOpen"
      :template="template"
      :run-validate="validateFile"
      :run-import="confirmJob"
      :run-download-template="api.downloadTeacherImportTemplate"
      @done="$router.push('/admin/system/data-exchange')"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 系统管理 › 身份与账号 › 教职工导入。
 * 上传后创建统一 ImportJob；确认只传 jobId + expectedVersion，禁止前端回传 rows。
 */
import { ModulePageShell } from '@/components/business'
import { AppGlobalState } from '@/components/common'
import { AppButton } from '@/components/ui'
import ImportDialog from '@/modules/system/components/ImportDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { dataExchangeApi } from '@/modules/system/api/dataExchange.api'

function apiError(error) {
  return { code: error?.code || 1, data: null, message: error?.message || '请求失败' }
}

export default {
  name: 'SystemTeacherImportView',
  components: { ModulePageShell, AppGlobalState, AppButton, ImportDialog },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      importOpen: false,
      api: systemApi,
      template: { name: '教职工导入', description: '仅教职工字段：工号、姓名、部门、岗位、预设角色、数据范围' }
    }
  },
  computed: {
    canImport() {
      const pa = (this.ctx && this.ctx.permissionActions) || {}
      const item = pa.importUsers
      return item ? !!(item.visible && item.allowed) : true
    }
  },
  methods: {
    async validateFile(file) {
      try {
        const job = await dataExchangeApi.validateIdentity('teachers', file)
        const invalid = Number(job.invalidRows || 0)
        return {
          code: 0,
          data: {
            ...job,
            jobId: job.id,
            total: Number(job.totalRows || 0),
            valid: Number(job.validRows || 0),
            invalid,
            errors: invalid
              ? [{ row: 0, field: '预检结果', message: `发现 ${invalid} 行错误，完整回执已进入数据交换任务中心` }]
              : []
          },
          message: '教职工名单解析及预检完成'
        }
      } catch (error) {
        return apiError(error)
      }
    },
    async confirmJob(jobId) {
      try {
        const current = await dataExchangeApi.getImport(jobId)
        const data = await dataExchangeApi.confirmImport(jobId, current.version)
        const result = data.result || {}
        const entities = result.entities || {}
        const created = entities.teachers?.created || data.confirmedRows || 0
        return {
          code: 0,
          data: {
            ...data,
            receipt: `已完成教职工账号处理 ${created} 条；初始凭据请到数据交换任务中心安全下载`
          },
          message: '教职工账号已整批创建'
        }
      } catch (error) {
        return apiError(error)
      }
    }
  }
}
</script>

<style scoped>
.sti { display: flex; flex-direction: column; gap: 16px; }
.sti__points { margin: 0 0 10px; padding-left: 18px; line-height: 1.9; color: var(--mp-text-secondary, #5b6472); }
.sti__note { margin: 6px 0 0; color: var(--mp-text-tertiary, #8a94a6); font-size: 13px; line-height: 1.7; }
</style>
