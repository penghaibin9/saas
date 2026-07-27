<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="新增指导记录" subtitle="记录指导内容、问题和下一步跟进" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad ig__page" v-if="state === 'ready'">
        <view class="card ig__batch" v-if="batches.length">
          <view class="ig__batch-copy">
            <text class="ig__eyebrow">当前记录批次</text>
            <text class="ig__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
          </view>
          <picker class="ig__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="submitting" @change="onBatch">
            <view class="ig__pick-val">切换批次 <text class="ig__arrow">▾</text></view>
          </picker>
        </view>

        <MobileInlineAlert type="info" description="先选择学生和指导方式，再记录本次沟通事实、发现的问题与下一步建议；需要持续关注时可设置跟进日期或转为风险。" />

        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可办理的实习批次。" />
        <MobileGlobalState v-else-if="!students.length" state="empty" title="暂无可记录学生"
          description="当前批次仅可对本人指导的实习学生新增指导记录。" />

        <template v-else>
          <view class="card ig__selected">
            <view class="ig__selected-copy">
              <text class="ig__selected-label">本次指导对象</text>
              <text class="ig__selected-name">{{ selectedStudent?.name || '请选择学生' }}</text>
              <text class="ig__selected-meta">{{ selectedStudent?.studentNo || '—' }} · {{ selectedStudent?.enterpriseName || '企业待落实' }}</text>
            </view>
            <text class="ig__selected-method">{{ methodLabels[methodIndex] }}</text>
          </view>

          <view class="card ig__section">
            <view class="ig__section-head">
              <text class="ig__step">1</text>
              <view><text class="ig__section-title">基本信息</text><text class="ig__section-hint">明确本次指导对象和沟通方式</text></view>
            </view>
            <view class="ig__row">
              <text class="ig__label">指导学生 <text class="ig__required">*</text></text>
              <picker class="ig__picker" mode="selector" :range="studentLabels" :value="studentIndex" @change="onStudent">
                <view class="ig__pick-field">{{ studentLabels[studentIndex] || '请选择' }}<text class="ig__arrow">▾</text></view>
              </picker>
            </view>
            <view class="ig__row">
              <text class="ig__label">指导方式 <text class="ig__required">*</text></text>
              <picker class="ig__picker" mode="selector" :range="methodLabels" :value="methodIndex" @change="onMethod">
                <view class="ig__pick-field">{{ methodLabels[methodIndex] }}<text class="ig__arrow">▾</text></view>
              </picker>
            </view>
            <view class="ig__row">
              <text class="ig__label">指导主题</text>
              <input class="ig__input" v-model="topic" placeholder="如：岗位适应情况回访" maxlength="50" />
            </view>
          </view>

          <view class="card ig__section">
            <view class="ig__section-head">
              <text class="ig__step">2</text>
              <view><text class="ig__section-title">指导内容</text><text class="ig__section-hint">记录真实沟通内容，不只写“已联系”</text></view>
            </view>
            <view class="ig__field">
              <text class="ig__field-label">本次指导内容 <text class="ig__required">*</text></text>
              <textarea class="ig__textarea" v-model="content" :maxlength="500" placeholder="说明学生当前表现、遇到的问题和本次指导过程" placeholder-class="ig__ph" />
              <text class="ig__count">{{ content.length }}/500</text>
            </view>
            <view class="ig__field">
              <text class="ig__field-label">处理建议</text>
              <textarea class="ig__textarea ig__textarea--sm" v-model="suggestion" :maxlength="200" placeholder="填写学生下一步可执行的改进建议（可选）" placeholder-class="ig__ph" />
              <text class="ig__count">{{ suggestion.length }}/200</text>
            </view>
          </view>

          <view class="card ig__section">
            <view class="ig__section-head">
              <text class="ig__step">3</text>
              <view><text class="ig__section-title">后续安排</text><text class="ig__section-hint">决定是否继续跟进、转风险或通知辅导员</text></view>
            </view>
            <view class="ig__row">
              <text class="ig__label">下次跟进</text>
              <picker class="ig__picker" mode="date" :value="nextFollowDate" @change="onFollow">
                <view class="ig__pick-field">{{ nextFollowDate || '暂不设置' }}<text class="ig__arrow">▾</text></view>
              </picker>
            </view>
            <view class="ig__switch-row">
              <view class="ig__switch-copy"><text class="ig__switch-title">标记为风险</text><text class="ig__switch-hint">保存后自动生成风险单并进入处置流程</text></view>
              <switch :checked="toRisk" color="var(--danger-500)" @change="(e) => toRisk = e.detail.value" />
            </view>
            <view class="ig__switch-row">
              <view class="ig__switch-copy"><text class="ig__switch-title">通知辅导员</text><text class="ig__switch-hint">用于需要班级协同或家校跟进的情况</text></view>
              <switch :checked="notifyCounselor" color="var(--teacher-600)" @change="(e) => notifyCounselor = e.detail.value" />
            </view>
          </view>

          <MobileInlineAlert v-if="toRisk" type="warning" description="本次记录会同步生成风险单，请确保指导内容和风险事实描述完整。" />
        </template>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="state === 'ready' && students.length">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '保存中…' : '保存指导记录' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { teacherInternshipMyStudents } from '@/services/internshipApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)
const METHODS = [
  { key: 'ONSITE', label: '现场' }, { key: 'ONLINE', label: '线上' }, { key: 'PHONE', label: '电话' },
  { key: 'VIDEO', label: '视频' }, { key: 'ENTERPRISE_FEEDBACK', label: '企业导师反馈' }
]

export default {
  data() {
    return {
      state: 'loading', students: [], studentIndex: 0,
      batches: [], batchId: '', batchIndex: 0,
      methodLabels: METHODS.map((m) => m.label), methodIndex: 0,
      topic: '', content: '', suggestion: '', nextFollowDate: '',
      toRisk: false, notifyCounselor: false, submitting: false
    }
  },
  onLoad() { this.load() },
  computed: {
    studentLabels() { return this.students.map((s) => `${s.name}（${s.studentNo}）· ${s.enterpriseName || '未落实企业'}`) },
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) },
    selectedStudent() { return this.students[this.studentIndex] || null }
  },
  methods: {
    async load() {
      this.state = 'loading'
      try {
        const context = useInternshipContextStore()
        context.restore()
        const selected = await context.load(true)
        this.batches = context.batches || []
        this.batchId = selected || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) {
          this.students = []
          this.state = 'ready'
          return
        }
        const data = await teacherInternshipMyStudents(this.batchId)
        this.students = (data && data.list) || []
        this.studentIndex = 0
        this.state = 'ready'
      } catch (e) {
        this.state = 'error'
      }
    },
    async onBatch(e) {
      this.batchIndex = Number(e.detail.value)
      const batch = this.batches[this.batchIndex]
      const context = useInternshipContextStore()
      context.selectBatch(batch && batch.id)
      this.batchId = context.selectedBatchId
      this.students = []
      this.state = 'loading'
      try {
        const data = await teacherInternshipMyStudents(this.batchId)
        this.students = (data && data.list) || []
        this.studentIndex = 0
        this.state = 'ready'
      } catch (err) {
        this.state = 'error'
      }
    },
    onStudent(e) { this.studentIndex = Number(e.detail.value) },
    onMethod(e) { this.methodIndex = Number(e.detail.value) },
    onFollow(e) { this.nextFollowDate = e.detail.value },
    submit() {
      if (this.submitting) return
      const stu = this.students[this.studentIndex]
      if (!stu) { toast('请选择指导学生'); return }
      if (this.content.trim().length < 2) { toast('指导内容至少 2 个字'); return }
      this.submitting = true
      submitLock.run(() => teacherApi.createInternshipGuidance({
        internshipId: stu.id, batchId: this.batchId, method: METHODS[this.methodIndex].key,
        topic: this.topic.trim(), content: this.content.trim(), suggestion: this.suggestion.trim(),
        nextFollowDate: this.nextFollowDate, toRisk: this.toRisk, notifyCounselor: this.notifyCounselor
      })).then((r) => {
        uni.showToast({ title: r && r.riskId ? '已记录并生成风险单' : '指导记录已保存', icon: 'none' })
        setTimeout(() => { uni.navigateBack({ delta: 1 }) }, 700)
      }).catch((e) => {
        if (e && e.code === 'LOCKED') return
        if (e && e.biz) toast(normalizeError(e).text)
        else toast('网络异常，提交未成功，请稍后重试')
      }).finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.ig__page{display:flex;flex-direction:column;gap:var(--space-3);padding-bottom:calc(var(--safe-bottom) + 92px)}.ig__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.ig__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.ig__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.ig__batch-name{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ig__picker{flex:1}.ig__pick-val{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap;text-align:right}.ig__pick-field{font-size:var(--font-size-sm);color:var(--text-primary);text-align:right;word-break:break-word}.ig__arrow{color:var(--text-tertiary);font-size:var(--font-size-xs);margin-left:4px}.ig__selected{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3);background:var(--teacher-50,#eff6ff);border-color:var(--teacher-200,#bfdbfe)}.ig__selected-copy{min-width:0}.ig__selected-label{display:block;font-size:10px;color:var(--text-tertiary)}.ig__selected-name{display:block;margin-top:3px;font-size:var(--font-size-md);font-weight:600;color:var(--text-primary)}.ig__selected-meta{display:block;margin-top:3px;font-size:var(--font-size-xs);color:var(--text-secondary);word-break:break-word}.ig__selected-method{flex-shrink:0;padding:5px 9px;border-radius:var(--radius-full);background:var(--bg-card);color:var(--teacher-700);font-size:var(--font-size-xs);font-weight:600}.ig__section{display:flex;flex-direction:column;padding:var(--space-3)}.ig__section-head{display:flex;align-items:center;gap:10px;padding-bottom:var(--space-2);border-bottom:1px solid var(--border-light)}.ig__step{display:flex;align-items:center;justify-content:center;width:26px;height:26px;flex-shrink:0;border-radius:50%;background:var(--teacher-600);color:#fff;font-size:var(--font-size-sm);font-weight:700}.ig__section-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.ig__section-hint{display:block;margin-top:2px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ig__row{display:flex;align-items:center;min-height:52px;border-bottom:1px solid var(--border-light);gap:var(--space-3)}.ig__label{width:84px;flex-shrink:0;font-size:var(--font-size-sm);color:var(--text-secondary)}.ig__required{color:var(--danger-600)}.ig__input{flex:1;min-width:0;font-size:var(--font-size-sm);color:var(--text-primary);text-align:right}.ig__field{display:flex;flex-direction:column;gap:7px;padding-top:var(--space-3)}.ig__field+.ig__field{padding-top:var(--space-4)}.ig__field-label{font-size:var(--font-size-sm);font-weight:600;color:var(--text-secondary)}.ig__textarea{width:100%;min-height:112px;box-sizing:border-box;font-size:var(--font-size-base);color:var(--text-primary);line-height:1.65;background:var(--gray-50);border:1px solid var(--border-light);border-radius:var(--radius-md);padding:var(--space-3)}.ig__textarea--sm{min-height:82px}.ig__ph{color:var(--text-tertiary)}.ig__count{align-self:flex-end;font-size:10px;color:var(--text-tertiary)}.ig__switch-row{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3) 0;border-bottom:1px solid var(--border-light)}.ig__switch-row:last-child{border-bottom:0;padding-bottom:0}.ig__switch-copy{min-width:0}.ig__switch-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.ig__switch-hint{display:block;margin-top:3px;font-size:var(--font-size-xs);line-height:1.45;color:var(--text-tertiary)}@media(max-width:360px){.ig__batch{align-items:flex-start}.ig__selected{align-items:flex-start}.ig__row{align-items:flex-start;padding:12px 0}.ig__pick-field{padding-top:1px}}
</style>
