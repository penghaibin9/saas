<template>
  <ModulePageShell
    title="成绩更正"
    subtitle="已发布成绩纠错留痕：教师发起 → 学院初审 → 教务处终审生效，原值 append-only 留痕"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <!-- 发起更正 -->
      <AppSectionCard title="发起更正申请">
        <div class="aa-grid2">
          <label class="aa-field"><span class="req">成绩录入任务ID</span><input v-model.trim="reqForm.taskId" class="aa-input" placeholder="从成绩录入/成绩总览页可查" /></label>
          <label class="aa-field"><span class="req">成绩明细记录ID</span><input v-model.trim="reqForm.recordId" class="aa-input" placeholder="对应学生的成绩明细ID" /></label>
          <label class="aa-field"><span>新平时分</span><input v-model.number="reqForm.newUsualScore" type="number" min="0" max="100" class="aa-input" placeholder="不改则留空" /></label>
          <label class="aa-field"><span>新期末分</span><input v-model.number="reqForm.newFinalScore" type="number" min="0" max="100" class="aa-input" placeholder="不改则留空" /></label>
        </div>
        <label class="aa-field aa-field--full"><span class="req">更正原因（≥5字）</span>
          <textarea ref="reasonInput" v-model.trim="reqForm.reason" class="aa-textarea" rows="2" maxlength="500"></textarea>
          <AppQuickPhrases scene-key="aa.grade.change" @pick="onPickReason" />
        </label>
        <div class="aa-actions">
          <button class="mp-btn mp-btn--primary" :disabled="requesting" @click="submitRequest">{{ requesting ? '提交中…' : '提交更正申请' }}</button>
        </div>
        <p class="mp-note">仅已发布成绩可申请更正；已归档学期需线下特批。同一条成绩同时只能有一个在途更正申请。</p>
      </AppSectionCard>

      <!-- 更正审核 -->
      <AppSectionCard title="更正审核（学院初审 / 教务处终审）">
        <div class="aa-grid2">
          <label class="aa-field"><span class="req">成绩明细记录ID</span><input v-model.trim="reviewForm.recordId" class="aa-input" /></label>
          <label class="aa-field"><span class="req">审核节点</span>
            <select v-model="reviewForm.node" class="aa-input">
              <option value="college">学院初审</option>
              <option value="academic">教务处终审</option>
            </select>
          </label>
        </div>
        <div class="aa-review-btns">
          <button class="mp-btn mp-btn--primary" :disabled="reviewing" @click="doReview('APPROVE')">通过</button>
          <button class="mp-btn mp-btn--danger" :disabled="reviewing" @click="openReject">驳回</button>
        </div>
        <p class="mp-note">教务处终审通过后：新值生效、原值留痕可查、投影回写成绩台账、联动预警扫描、学生收到通知。驳回后原值不变。</p>
      </AppSectionCard>
    </div>

    <AppConfirmDialog
      v-model:visible="rejectDlg.visible"
      title="驳回更正申请"
      type="danger"
      confirm-text="确认驳回"
      :require-reason="true"
      phrase-scene-key="aa.grade.changeReject"
      reason-label="驳回原因"
      :submitting="rejectDlg.submitting"
      @confirm="doRejectConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 成绩更正（/admin/academic-affairs/grade-change）：发起+两级审核。 */
import { ModulePageShell } from '@/components/business'
import { AppSectionCard, AppConfirmDialog, AppQuickPhrases } from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaGradeChangeView',
  components: { ModulePageShell, AppSectionCard, AppConfirmDialog, AppQuickPhrases },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      reqForm: { taskId: '', recordId: '', newUsualScore: null, newFinalScore: null, reason: '' },
      requesting: false,
      reviewForm: { recordId: '', node: 'college' },
      reviewing: false,
      rejectDlg: { visible: false, submitting: false }
    }
  },
  methods: {
    onPickReason(text) {
      const el = this.$refs.reasonInput
      const { value, selStart, selEnd } = insertAtCursor(el, this.reqForm.reason, text)
      this.reqForm.reason = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    async submitRequest() {
      if (this.requesting) return
      if (!this.reqForm.taskId || !this.reqForm.recordId) { toast.error('请填写任务ID与记录ID'); return }
      if (this.reqForm.reason.length < 5) { toast.error('更正原因至少5字'); return }
      this.requesting = true
      const res = await academicAffairsApi.requestGradeChange(this.reqForm.taskId, this.reqForm.recordId, {
        newUsualScore: this.reqForm.newUsualScore != null ? this.reqForm.newUsualScore : undefined,
        newFinalScore: this.reqForm.newFinalScore != null ? this.reqForm.newFinalScore : undefined,
        reason: this.reqForm.reason
      })
      this.requesting = false
      if (res.code === 0) {
        toast.success('更正申请已提交，进入学院初审')
        this.reqForm = { taskId: '', recordId: '', newUsualScore: null, newFinalScore: null, reason: '' }
      } else toast.error(res.message || '提交失败')
    },
    async doReview(action) {
      if (this.reviewing) return
      if (!this.reviewForm.recordId) { toast.error('请填写成绩明细记录ID'); return }
      this.reviewing = true
      const fn = this.reviewForm.node === 'college' ? academicAffairsApi.changeCollegeReview : academicAffairsApi.changeAcademicReview
      const res = await fn(this.reviewForm.recordId, action, '')
      this.reviewing = false
      if (res.code === 0) {
        toast.success(res.data.final ? '教务终审通过，新成绩已生效' : '已处理')
        this.reviewForm.recordId = ''
      } else toast.error(res.message || '处理失败')
    },
    openReject() {
      if (!this.reviewForm.recordId) { toast.error('请填写成绩明细记录ID'); return }
      this.rejectDlg = { visible: true, submitting: false }
    },
    async doRejectConfirm(payload) {
      const reason = (payload && payload.reason) || ''
      this.rejectDlg.submitting = true
      const fn = this.reviewForm.node === 'college' ? academicAffairsApi.changeCollegeReview : academicAffairsApi.changeAcademicReview
      const res = await fn(this.reviewForm.recordId, 'REJECT', reason)
      this.rejectDlg.submitting = false
      if (res.code === 0) {
        this.rejectDlg.visible = false
        toast.success('已驳回，原成绩保持不变')
        this.reviewForm.recordId = ''
      } else toast.error(res.message || '驳回失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-grid2 { display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 14px 24px; }
.aa-field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); margin-top: 14px; }
.aa-field--full { grid-column: 1 / -1; }
.aa-field .req::before { content: '*'; color: var(--danger-600, #f53f3f); margin-right: 4px; }
.aa-input, .aa-textarea { padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-input { height: 34px; }
.aa-textarea { padding: 8px 12px; }
.aa-actions { margin-top: 16px; }
.aa-review-btns { margin-top: 16px; display: flex; gap: 12px; }
</style>
