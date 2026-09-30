<template>
  <ModulePageShell
    :title="appendMode ? '补充未发放学生' : '生成教材发放名单'"
    subtitle="选择行政班和本班学生，系统按征订来源与正式教学名单逐本匹配教材，再进入签收工作区"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push(returnPath)">返回来源队列</AppButton>
    </template>

    <div class="mp-stack">
      <AppInlineAlert v-if="appendMode" type="info" :description="`补充至原发放批次 ${appendToBatchId}。仅新增尚未列入名单的学生；已签收、已退领、已排除及费用记录全部保留。重复选择的已有学生不会重新发放。`" />
      <AppInlineAlert
        type="info"
        title="发放依据"
        description="只发放所选学生正式修读课程对应的教材；来源缺失或名单未锁定时需先核对。价格固定使用征订时的快照，后续修改目录定价不会改写本批次应收。"
      />
      <AppSectionCard title="发放范围">
        <div class="aa-form-grid">
          <AppFormItem label="征订批次" required>
            <AppTextInput :model-value="orderBatchId" disabled />
          </AppFormItem>
          <AppFormItem label="行政班" required>
            <AppClassPicker v-model="classId" :disabled="appendMode || submitting" placeholder="选择发放班级" />
          </AppFormItem>
          <AppFormItem class="aa-form-grid__wide" label="学生名单" required>
            <AppStudentPicker
              :key="classId || 'no-class'"
              v-model="studentIds"
              multiple
              :disabled="!classId || submitting"
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
          {{ appendMode ? '补充至原发放批次' : '生成发放名单' }}
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
import { currentUserFromToken } from '@/services/http/client'
import { textbookReturnPath } from '../components/textbooks/textbookNavigation.js'

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
      error: '', sequence: 0
    }
  },
  computed: {
    returnPath() { return textbookReturnPath(this.$route.query.returnTo, '/admin/academic-affairs/textbooks?tab=order') },
    identityKey() { return JSON.stringify([currentUserFromToken(), this.ctx]) },
    orderBatchId() { return String(this.$route.query.orderBatchId || '') },
    appendToBatchId() { return String(this.$route.query.appendToBatchId || '') },
    appendMode() { return Boolean(this.appendToBatchId) },
    appendClassId() { return String(this.$route.query.classId || '') },
    canSubmit() {
      return Boolean(this.orderBatchId && this.classId && (!this.appendMode || (/^[1-9]\d*$/.test(this.appendToBatchId) && this.classId === this.appendClassId)) && Array.isArray(this.studentIds) && this.studentIds.length)
    }
  },
  watch: {
    classId() { this.studentIds = [] },
    orderBatchId() { this.resetScope() },
    appendToBatchId() { this.resetScope() },
    appendClassId() { this.resetScope() },
    identityKey() { this.resetScope() }
  },
  beforeUnmount() { this.sequence++ },
  created() {
    if (this.appendMode) this.classId = this.appendClassId
    if (!this.orderBatchId) this.error = '缺少征订批次orderBatchId，请从征订到货页进入'
  },
  methods: {
    resetScope() { this.sequence++; this.classId = this.appendMode ? this.appendClassId : ''; this.studentIds = []; this.submitting = false; this.error = this.orderBatchId ? '' : '请从征订到货页选择批次' },
    async submit() {
      if (!this.canSubmit || this.submitting) return
      this.submitting = true
      this.error = ''
      const seq = ++this.sequence, identity = this.identityKey, returnTo = this.returnPath, appendToBatchId = this.appendToBatchId
      const body = {
        orderBatchId: this.orderBatchId,
        classId: String(this.classId),
        studentIds: this.studentIds.map(String)
      }
      if (appendToBatchId) body.appendToBatchId = appendToBatchId
      const current = () => seq === this.sequence && identity === this.identityKey && body.orderBatchId === this.orderBatchId && appendToBatchId === this.appendToBatchId
      try {
      const res = await api.generateDistribution(body)
      if (!current()) return
      if (res.code !== 0) {
        this.error = res.message || '生成发放名单失败'
        return
      }
      const batchId = res.data?.distributionBatchId
      if (!batchId) { this.error = '接口未返回发放批次，请回征订页核对，勿重复生成'; return }
      toast.success(res.data?.idempotent ? '名单已存在，已打开原批次' : appendToBatchId ? `已补充 ${res.data.addedRecordCount} 条教材记录` : '发放名单已生成')
      if (body.classId === String(this.classId) && JSON.stringify(body.studentIds) === JSON.stringify(this.studentIds.map(String))) this.$router.push({ name: 'aa-textbook-distribution-detail', params: { batchId }, query: { returnTo } })
      else this.error = `原选择的发放名单已生成（批次 ${batchId}），当前新选择已保留。请从发放批次核对。`
      } catch (error) { if (current()) this.error = error?.message || '生成结果未确认，请回征订页核对' }
      finally { if (current()) this.submitting = false }
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
