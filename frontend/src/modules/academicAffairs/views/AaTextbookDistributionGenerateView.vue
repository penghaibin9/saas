<template>
  <ModulePageShell
    title="生成教材发放名单"
    subtitle="选择行政班和本班学生，生成后进入独立签收工作区；跨班学生与重复名单由后端再次校验"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/textbooks?tab=order')">返回征订</AppButton>
    </template>

    <div class="mp-stack">
      <AppInlineAlert
        type="info"
        title="发放依据"
        description="发放价格固定使用征订时的价格快照，后续修改教材目录定价不会改写本批次应收。"
      />
      <AppSectionCard title="发放范围">
        <div class="aa-form-grid">
          <AppFormItem label="征订批次" required>
            <AppTextInput :model-value="orderBatchId" disabled />
          </AppFormItem>
          <AppFormItem label="行政班" required>
            <AppClassPicker v-model="classId" placeholder="选择发放班级" />
          </AppFormItem>
          <AppFormItem class="aa-form-grid__wide" label="学生名单" required>
            <AppStudentPicker
              :key="classId || 'no-class'"
              v-model="studentIds"
              multiple
              :disabled="!classId"
              :query="{ classId }"
              placeholder="选择本班学生"
              data-scope-hint="后端将逐人校验学生属于所选班级"
            />
          </AppFormItem>
        </div>
      </AppSectionCard>
      <AppInlineAlert v-if="error" type="danger" :description="error" />
      <div class="aa-actions">
        <AppButton :disabled="!canSubmit" :loading="submitting" variant="primary" @click="submit">
          生成发放名单
        </AppButton>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import {
  AppClassPicker,
  AppFormItem,
  AppInlineAlert,
  AppSectionCard,
  AppStudentPicker,
  AppTextInput
} from '@/components/common'
import { academicAffairsTextbookApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTextbookDistributionGenerateView',
  components: {
    ModulePageShell,
    AppButton,
    AppClassPicker,
    AppFormItem,
    AppInlineAlert,
    AppSectionCard,
    AppStudentPicker,
    AppTextInput
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      classId: '',
      studentIds: [],
      submitting: false,
      error: ''
    }
  },
  computed: {
    orderBatchId() { return String(this.$route.query.orderBatchId || '') },
    canSubmit() {
      return Boolean(this.orderBatchId && this.classId && Array.isArray(this.studentIds) && this.studentIds.length)
    }
  },
  created() {
    if (!this.orderBatchId) this.error = '缺少征订批次orderBatchId，请从征订到货页进入'
  },
  methods: {
    async submit() {
      if (!this.canSubmit || this.submitting) return
      this.submitting = true
      this.error = ''
      const res = await api.generateDistribution({
        orderBatchId: this.orderBatchId,
        classId: String(this.classId),
        studentIds: this.studentIds.map(String)
      })
      this.submitting = false
      if (res.code !== 0) {
        this.error = res.message || '生成发放名单失败'
        return
      }
      const batchId = res.data?.distributionBatchId
      toast.success(res.data?.idempotent ? '已打开现有发放名单' : '发放名单已生成')
      if (batchId) this.$router.push(`/admin/academic-affairs/textbooks/distributions/${batchId}`)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.aa-form-grid__wide { grid-column: 1 / -1; }
.aa-actions { display: flex; justify-content: flex-end; }
@media (max-width: 760px) { .aa-form-grid { grid-template-columns: 1fr; } .aa-form-grid__wide { grid-column: auto; } }
</style>
