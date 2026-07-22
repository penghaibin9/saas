<template>
  <ModulePageShell title="重修 · 免修申请" subtitle="学生自助：重修报名（次数上限）· 免修申请（三级审批）">
    <div class="aamks-tabs">
      <button :class="['aamks-tab', { 'is-active': tab === 'retake' }]" @click="switchTab('retake')">我的重修</button>
      <button :class="['aamks-tab', { 'is-active': tab === 'exemption' }]" @click="switchTab('exemption')">我的免修</button>
    </div>

    <div class="aamks-bar">
      <AppButton variant="primary" size="small" @click="openApply">{{ tab === 'retake' ? '申请重修' : '申请免修' }}</AppButton>
    </div>

    <LoadingState v-if="loading" />
    <EmptyState v-else-if="!rows.length" :title="tab === 'retake' ? '暂无重修申请' : '暂无免修申请'" description="点击上方按钮发起申请" />
    <ul v-else class="aamks-list">
      <li v-for="r in rows" :key="r.applyId || r.exemptionId">
        <div>
          <div class="mp-cell-main">{{ r.courseName }}</div>
          <div class="mp-cell-sub">{{ r.termCode || '' }}<template v-if="r.retakeCount"> · 第{{ r.retakeCount }}次</template></div>
        </div>
        <StatusTag :type="stType(r.status)" :label="r.status" dot />
      </li>
    </ul>

    <AppDrawer :visible="applyVisible" :title="tab === 'retake' ? '申请重修' : '申请免修'" @close="applyVisible = false">
      <div class="aamks-form">
        <AppFormItem label="课程" required><AppCoursePicker v-model="selectedCourseId" :disabled="saving" @change="onCoursePicked" /></AppFormItem>
        <AppFormItem label="学期"><AppTermCodePicker v-model="form.termCode" :disabled="saving" /></AppFormItem>
        <!-- 未挂快捷用语：aa.makeup.reason 全部是「缓考」申请理由（缓考页在 AaExamConsoleView），
             与本页的重修/免修业务不符；配置方案未给重修/免修理由词条，不硬套 -->
        <AppFormItem label="理由">
          <AppTextarea v-model="form.reason" placeholder="选填" :disabled="saving" />
        </AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
        <AppInlineAlert v-if="tab === 'exemption'" type="info" description="免修需上传证书/先修证明材料（本页暂以理由说明，材料附件后续接入）。已获及格成绩的课程不可申请。" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="applyVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitApply">提交</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** 重修/免修学生自助（/admin/academic-affairs/my-makeup）：报名+申请+我的申请列表。 */
import { ModulePageShell, StatusTag, LoadingState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextarea, AppFormItem, AppInlineAlert, AppCoursePicker, AppTermCodePicker } from '@/components/common'
import { academicAffairsMakeupApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaMakeupStudentView',
  components: { ModulePageShell, StatusTag, LoadingState, EmptyState, AppButton, AppDrawer, AppTextarea, AppFormItem, AppInlineAlert, AppCoursePicker, AppTermCodePicker },
  data() {
    return {
      tab: 'retake', loading: true, rows: [],
      applyVisible: false, selectedCourseId: '', form: { courseName: '', termCode: '', reason: '' }, formError: '', saving: false
    }
  },
  created() { this.reload() },
  methods: {
    onCoursePicked(value, items) {
      const item = items?.[0]
      const course = item?.raw || item || {}
      this.form.courseName = course.courseName || course.name || item?.label || ''
    },
    stType(s) { return ['APPROVED', 'ENROLLED', 'FINISHED'].includes(s) ? 'success' : s === 'REJECTED' ? 'danger' : 'primary' },
    switchTab(k) { this.tab = k; this.reload() },
    async reload() {
      this.loading = true
      const res = this.tab === 'retake' ? await api.retakeMy() : await api.exemptionMy()
      this.rows = res.code === 0 ? (res.data.items || []) : []
      this.loading = false
    },
    openApply() { this.selectedCourseId = ''; this.form = { courseName: '', termCode: '', reason: '' }; this.formError = ''; this.applyVisible = true },
    async submitApply() {
      if (!this.form.courseName) { this.formError = '课程名必填'; return }
      this.saving = true
      const res = this.tab === 'retake' ? await api.retakeApply(this.form) : await api.exemptionApply(this.form)
      this.saving = false
      if (res.code === 0) { toast.success('已提交'); this.applyVisible = false; this.reload() }
      else this.formError = res.message
    }
  }
}
</script>

<style scoped>
.aamks-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 12px; }
.aamks-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aamks-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aamks-bar { margin-bottom: 12px; }
.aamks-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.aamks-list li { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; }
</style>
