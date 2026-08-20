<template>
  <view class="visit-evidence card">
    <view class="ve__head">
      <view class="flex-1">
        <text class="t-md t-bold">记录巡访执行证据 · {{ target.name }}</text>
        <text class="ve__sub">{{ target.enterpriseName || '实习单位' }} · 默认不采集教师位置</text>
      </view>
      <text class="ve__close" @click="$emit('cancel')">关闭</text>
    </view>

    <MobileInlineAlert type="info" description="只记录本次实际巡访/沟通事实与业务证据；不申请、不读取、不上传教师定位。" />
    <MobileInlineAlert v-if="contextState === 'error'" type="warning" description="巡访计划或实习版本读取失败，请关闭后刷新列表再试。" />

    <view class="ve__field" v-if="planOptions.length > 1">
      <text class="ve__label">执行计划 *</text>
      <picker :range="planLabels" :value="planIndex" @change="changePlan">
        <view class="ve__picker">{{ planLabels[planIndex] }} ›</view>
      </picker>
    </view>
    <view class="ve__field">
      <text class="ve__label">巡访方式 *</text>
      <picker :range="methodLabels" :value="methodIndex" @change="changeMethod">
        <view class="ve__picker">{{ methodLabels[methodIndex] }} ›</view>
      </picker>
    </view>
    <view class="ve__field"><text class="ve__label">企业联系人 *</text><input v-model="form.contactPerson" class="ve__input" maxlength="100" placeholder="如：企业导师王老师" /></view>
    <view class="ve__field"><text class="ve__label">学生当前工作状态 *</text><textarea v-model="form.workStatus" class="ve__textarea is-short" maxlength="300" placeholder="岗位任务、出勤、适应情况等" /></view>
    <view class="ve__field"><text class="ve__label">企业反馈 *</text><textarea v-model="form.enterpriseFeedback" class="ve__textarea" maxlength="1000" placeholder="企业对学生表现、技能、纪律等真实反馈" /></view>
    <view class="ve__field"><text class="ve__label">事实记录 *</text><textarea v-model="form.facts" class="ve__textarea" maxlength="1600" placeholder="至少 10 字，只记录本次实际沟通/巡访事实" /></view>
    <view class="ve__field"><text class="ve__label">发现问题</text><textarea v-model="form.issues" class="ve__textarea is-short" maxlength="500" placeholder="没有可留空；只写本次发现的问题事实" /></view>
    <view class="ve__field"><text class="ve__label">处理建议</text><textarea v-model="form.advice" class="ve__textarea is-short" maxlength="500" placeholder="给学生/企业的明确建议" /></view>

    <view class="ve__toggle"><view><text class="ve__label">需要后续跟进</text><text class="ve__hint">形成巡访整改待办</text></view><switch :checked="form.needFollow" @change="form.needFollow = !!$event.detail.value" /></view>
    <view class="ve__toggle"><view><text class="ve__label">转为实习风险</text><text class="ve__hint">在同一事务形成正式风险单</text></view><switch :checked="form.needRisk" @change="form.needRisk = !!$event.detail.value" /></view>
    <template v-if="form.needRisk">
      <view class="ve__field">
        <text class="ve__label">风险等级 *</text>
        <picker :range="riskLabels" :value="riskIndex" @change="riskIndex = Number($event.detail.value || 0)">
          <view class="ve__picker">{{ riskLabels[riskIndex] }} ›</view>
        </picker>
      </view>
      <view class="ve__field"><text class="ve__label">转风险原因 *</text><textarea v-model="form.riskReason" class="ve__textarea is-short" maxlength="500" placeholder="至少 5 字，写明需跟进的风险事实" /></view>
    </template>

    <view class="ve__field">
      <view class="row-between"><text class="ve__label">证据附件（最多 1 个）</text><text v-if="evidenceFile" class="ve__file">{{ evidenceFile.fileName || '已上传附件' }}</text></view>
      <view v-if="evidenceFile" class="ve__file-state">
        <text>{{ evidenceFile.statusText }}</text>
        <view class="ve__file-actions">
          <text v-if="evidenceFile.readyForBusiness" @click="previewFile">预览</text>
          <text v-else @click="refreshFile">刷新扫描状态</text>
          <text @click="removeFile">移除</text>
        </view>
      </view>
      <button v-else class="btn btn-ghost" :disabled="submitting || uploading" @click="chooseAndUpload">{{ uploading ? '上传中…' : '选择并上传证据' }}</button>
      <text class="ve__hint">上传后仅产生 TEMP_PRIVATE；保存巡访时由后端业务事务正式绑定，客户端不改绑文件。</text>
    </view>

    <view class="ve__actions">
      <button class="btn btn-ghost flex-1" :disabled="submitting" @click="$emit('cancel')">取消</button>
      <button class="ve__submit flex-1" :disabled="submitDisabled" @click="submit">{{ submitting ? '保存中…' : '保存执行证据' }}</button>
    </view>
  </view>
</template>

<script>
import { teacherInternshipEvidenceV3Api } from '@/services/teacherInternshipEvidenceV3Api'
import { fileSdk } from '@/services/fileSdk'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const METHODS = ['ONSITE', 'ONLINE', 'PHONE', 'VIDEO', 'OTHER']
const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH']

export default {
  props: {
    target: { type: Object, required: true },
    submitting: { type: Boolean, default: false }
  },
  emits: ['submit', 'cancel'],
  data() {
    return {
      contextState: 'loading', planOptions: [], planIndex: 0,
      methodLabels: ['现场巡访', '线上沟通', '电话沟通', '视频沟通', '其他'], methodIndex: 0,
      riskLabels: ['低风险', '中风险', '高风险'], riskIndex: 1,
      evidenceFile: null, uploading: false,
      form: {
        contactPerson: '', workStatus: '', enterpriseFeedback: '', facts: '', issues: '', advice: '',
        needFollow: false, needRisk: false, riskReason: ''
      }
    }
  },
  computed: {
    planLabels() {
      return this.planOptions.map((item) => `${item.planDate || '日期待定'} · ${item.enterpriseName || this.target.enterpriseName || '实习单位'}`)
    },
    selectedPlan() { return this.planOptions[this.planIndex] || null },
    submitDisabled() {
      return this.submitting || this.uploading || this.contextState !== 'ready' || !this.selectedPlan ||
        !!(this.evidenceFile && !this.evidenceFile.readyForBusiness)
    }
  },
  created() { this.loadContext() },
  methods: {
    loadContext() {
      this.contextState = 'loading'
      const internshipId = String(this.target && this.target.internshipId || '')
      teacherInternshipEvidenceV3Api.visitTargets().then((data) => {
        const matches = []
        for (const plan of (data && data.plans) || []) {
          for (const student of plan.students || []) {
            if (String(student.internshipId || '') !== internshipId || !student.resolvable) continue
            const expectedVersion = Number(student.expectedVersion)
            if (!Number.isInteger(expectedVersion) || expectedVersion < 0) continue
            matches.push({
              planId: String(student.planId || plan.id || ''),
              expectedVersion,
              planDate: plan.planDate || '',
              enterpriseName: plan.enterpriseName || '',
              positionName: student.positionName || ''
            })
          }
        }
        this.planOptions = matches.filter((item) => /^\d+$/.test(item.planId))
        this.planIndex = 0
        this.contextState = this.planOptions.length ? 'ready' : 'error'
        if (!this.planOptions.length) toast('当前巡访计划已变化，请刷新后重试')
      }).catch((e) => {
        this.contextState = 'error'
        toast(normalizeError(e).text)
      })
    },
    changePlan(e) { this.planIndex = Math.max(0, Math.min(this.planOptions.length - 1, Number(e.detail.value || 0))) },
    changeMethod(e) { this.methodIndex = Math.max(0, Math.min(METHODS.length - 1, Number(e.detail.value || 0))) },
    async chooseAndUpload() {
      if (this.uploading || this.submitting) return
      this.uploading = true
      try {
        const picked = await fileSdk.choose({ count: 1 })
        if (!picked) return
        const uploaded = await fileSdk.upload(picked, { bizType: 'INTERNSHIP_VISIT', bizId: this.target.internshipId })
        this.evidenceFile = uploaded
        toast(uploaded.readyForBusiness ? '证据附件已上传并可使用' : uploaded.statusText || '附件已上传，等待安全扫描')
      } catch (e) {
        toast(normalizeError(e).text)
      } finally {
        this.uploading = false
      }
    },
    async refreshFile() {
      if (!this.evidenceFile || !this.evidenceFile.fileId) return
      try {
        this.evidenceFile = await fileSdk.metadata(this.evidenceFile.fileId)
        toast(this.evidenceFile.readyForBusiness ? '附件安全扫描已完成' : this.evidenceFile.statusText)
      } catch (e) { toast(normalizeError(e).text) }
    },
    async previewFile() {
      if (!this.evidenceFile || !this.evidenceFile.fileId || !this.evidenceFile.readyForBusiness) return
      try { await fileSdk.open(this.evidenceFile.fileId) } catch (e) { toast(normalizeError(e).text) }
    },
    removeFile() { if (!this.submitting) this.evidenceFile = null },
    submit() {
      if (this.submitDisabled) return
      const p = this.selectedPlan
      const f = this.form
      if (f.contactPerson.trim().length < 2) return toast('企业联系人至少 2 字')
      if (f.workStatus.trim().length < 2) return toast('请填写学生当前工作状态')
      if (f.enterpriseFeedback.trim().length < 2) return toast('请填写企业反馈')
      if (f.facts.trim().length < 10) return toast('事实记录至少 10 字')
      if (f.needRisk && f.riskReason.trim().length < 5) return toast('转风险原因至少 5 字')
      this.$emit('submit', {
        planId: Number(p.planId),
        visitType: METHODS[this.methodIndex],
        contactPerson: f.contactPerson.trim(),
        workStatus: f.workStatus.trim(),
        enterpriseFeedback: f.enterpriseFeedback.trim(),
        facts: f.facts.trim(),
        issues: f.issues.trim() || null,
        advice: f.advice.trim() || null,
        needFollow: !!f.needFollow,
        needRisk: !!f.needRisk,
        riskLevel: f.needRisk ? RISK_LEVELS[this.riskIndex] : null,
        riskReason: f.needRisk ? f.riskReason.trim() : null,
        fileIds: this.evidenceFile ? [String(this.evidenceFile.fileId)] : [],
        location: null,
        expectedVersion: p.expectedVersion
      })
    }
  }
}
</script>

<style scoped>
.visit-evidence{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3);border:1px solid var(--teacher-200,#bfdbfe)}.ve__head{display:flex;align-items:flex-start;gap:var(--space-2)}.ve__sub{display:block;margin-top:4px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ve__close{font-size:var(--font-size-sm);color:var(--teacher-700);flex-shrink:0}.ve__field{display:flex;flex-direction:column;gap:6px}.ve__label{display:block;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ve__hint{display:block;margin-top:2px;font-size:10px;line-height:1.45;color:var(--text-tertiary)}.ve__input,.ve__picker,.ve__textarea{box-sizing:border-box;width:100%;border:1px solid var(--border-base);border-radius:var(--radius-md);background:var(--bg-card);font-size:var(--font-size-base);color:var(--text-primary)}.ve__input,.ve__picker{min-height:var(--touch-target-min);padding:0 12px;display:flex;align-items:center}.ve__textarea{min-height:128px;padding:10px 12px;line-height:1.55}.ve__textarea.is-short{min-height:92px}.ve__toggle{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:10px 0;border-top:1px solid var(--border-light)}.ve__file{max-width:55%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px;color:var(--success-700)}.ve__file-state{display:flex;align-items:center;justify-content:space-between;gap:var(--space-2);padding:10px 12px;background:var(--gray-50);border-radius:var(--radius-md);font-size:var(--font-size-xs);color:var(--text-secondary)}.ve__file-actions{display:flex;gap:12px;color:var(--teacher-700);flex-shrink:0}.ve__actions{display:flex;gap:var(--space-2);padding-top:var(--space-1)}.ve__submit{min-height:var(--touch-target-min);border:0;border-radius:var(--radius-md);background:var(--teacher-600);color:#fff;font-size:var(--font-size-md)}.ve__submit::after{border:0}.ve__submit[disabled]{opacity:.55}
</style>
