<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="新增指导记录" subtitle="对本人指导学生的过程指导留痕" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="state === 'ready'">
        <view class="card ig__batch" v-if="batches.length">
          <text class="ig__label">实习批次</text>
          <picker class="ig__picker" mode="selector" :range="batchLabels" :value="batchIndex" @change="onBatch">
            <view class="ig__pick-val">{{ batchLabels[batchIndex] || '请选择批次' }}<text class="ig__arrow">▾</text></view>
          </picker>
        </view>
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可办理的实习批次。" />
        <MobileGlobalState v-else-if="!students.length" state="empty" title="暂无可记录学生"
          description="当前批次仅可对本人指导的实习学生新增指导记录。" />
        <view class="card ig__form" v-else>
          <view class="ig__row">
            <text class="ig__label">指导学生</text>
            <picker class="ig__picker" mode="selector" :range="studentLabels" :value="studentIndex" @change="onStudent">
              <view class="ig__pick-val">{{ studentLabels[studentIndex] || '请选择' }}<text class="ig__arrow">▾</text></view>
            </picker>
          </view>
          <view class="ig__row">
            <text class="ig__label">指导方式</text>
            <picker class="ig__picker" mode="selector" :range="methodLabels" :value="methodIndex" @change="onMethod">
              <view class="ig__pick-val">{{ methodLabels[methodIndex] }}<text class="ig__arrow">▾</text></view>
            </picker>
          </view>
          <view class="ig__row">
            <text class="ig__label">指导主题</text>
            <input class="ig__input" v-model="topic" placeholder="如：岗位适应情况回访" maxlength="50" />
          </view>
          <view class="ig__row ig__row--top">
            <text class="ig__label">指导内容</text>
            <textarea class="ig__textarea" v-model="content" :maxlength="500" placeholder="请填写指导内容（必填）" placeholder-class="ig__ph" />
          </view>
          <text class="ig__count">{{ content.length }}/500</text>
          <view class="ig__row ig__row--top">
            <text class="ig__label">处理建议</text>
            <textarea class="ig__textarea ig__textarea--sm" v-model="suggestion" :maxlength="200" placeholder="可填写下一步建议（可选）" placeholder-class="ig__ph" />
          </view>
          <view class="ig__row">
            <text class="ig__label">下次跟进</text>
            <picker class="ig__picker" mode="date" :value="nextFollowDate" @change="onFollow">
              <view class="ig__pick-val">{{ nextFollowDate || '不设置' }}<text class="ig__arrow">▾</text></view>
            </picker>
          </view>
          <view class="ig__row">
            <text class="ig__label">标记为风险</text>
            <switch :checked="toRisk" color="var(--danger-500)" @change="(e) => toRisk = e.detail.value" />
          </view>
          <view class="ig__row" style="border-bottom:none;">
            <text class="ig__label">通知辅导员</text>
            <switch :checked="notifyCounselor" color="var(--teacher-600)" @change="(e) => notifyCounselor = e.detail.value" />
          </view>
        </view>

        <MobileInlineAlert v-if="toRisk" type="warning" description="标记为风险将自动生成一条风险单，进入风险处置流程。" />
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="state === 'ready' && students.length">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '保存指导记录' }}</button>
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
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) }
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
.ig__batch { display: flex; align-items: center; min-height: 48px; margin-bottom: var(--space-3); padding: 0 var(--space-3); }
.ig__form { display: flex; flex-direction: column; }
.ig__row { display: flex; align-items: center; min-height: 48px; border-bottom: 1px solid var(--border-light); }
.ig__row--top { align-items: flex-start; padding-top: var(--space-3); border-bottom: none; }
.ig__label { width: 80px; flex-shrink: 0; font-size: var(--font-size-base); color: var(--text-secondary); }
.ig__picker { flex: 1; }
.ig__pick-val { font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.ig__arrow { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-left: 4px; }
.ig__input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.ig__textarea { flex: 1; min-height: 80px; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; }
.ig__textarea--sm { min-height: 56px; }
.ig__ph { color: var(--text-tertiary); }
.ig__count { display: block; text-align: right; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: -4px; margin-bottom: 4px; }
</style>
