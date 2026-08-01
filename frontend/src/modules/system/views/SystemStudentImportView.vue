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
          <p class="sii__note">
            原始 Excel、安全扫描、错误回执和初始凭据回执会进入
            <button class="mp-link" @click="$router.push('/admin/system/data-exchange')">数据交换任务中心</button>，
            刷新页面或切换设备后仍可继续处理。
          </p>
          <p class="sii__note">
            仅导入教职工请前往
            <button class="mp-link" @click="$router.push('/admin/system/identity-import/teachers')">教职工导入</button>。
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
      :run-validate="validateFile"
      :run-import="confirmJob"
      :run-download-template="api.downloadStudentImportTemplate"
      @done="$router.push('/admin/system/data-exchange')"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 系统管理 › 身份与账号 › 学生导入与账号开通。
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
      // ctx 未下发时不误报无权限，后端仍是最终边界。
      return item ? !!(item.visible && item.allowed) : true
    }
  },
  methods: {
    async validateFile(file) {
      try {
        const job = await dataExchangeApi.validateIdentity('students', file)
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
          message: '学生名单解析及预检完成'
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
        const created = entities.studentAccounts?.created || data.confirmedRows || 0
        return {
          code: 0,
          data: {
            ...data,
            receipt: `已完成学生主档与账号处理 ${created} 条；初始凭据请到数据交换任务中心安全下载`
          },
          message: '学生导入与账号开通已完成'
        }
      } catch (error) {
        return apiError(error)
      }
    }
  }
}
</script>

<style scoped>
.sii { display: flex; flex-direction: column; gap: 16px; }
.sii__points { margin: 0 0 10px; padding-left: 18px; line-height: 1.9; color: var(--mp-text-secondary, #5b6472); }
.sii__note { margin: 6px 0 0; color: var(--mp-text-tertiary, #8a94a6); font-size: 13px; line-height: 1.7; }
</style>
