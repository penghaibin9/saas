<template>
  <view class="page-wrap lv">
    <MobileGlobalState :state="pageState" @retry="loadList">
      <view class="page-pad stack">
        <view class="card lv__head">
          <text class="card-title">补卡申请</text>
          <text class="lv__hint">超范围补卡必须上传考勤、定位或现场佐证；教师查看材料并审批通过后才会补写打卡留痕。</text>
        </view>

        <view v-for="item in list" :key="item.id" class="card lv__item">
          <view class="row-between">
            <text class="lv__range">{{ item.checkinDate }}</text>
            <MobileStatusTag :status="item.status" />
          </view>
          <text class="lv__days">{{ item.makeupTypeLabel || item.makeupType }}</text>
          <text class="lv__reason">{{ item.reason }}</text>
          <text class="lv__meta">证据材料：{{ item.hasEvidence || item.evidenceFileId ? '已上传' : (item.evidenceRequired ? '缺少必需材料' : '未上传') }}</text>
          <text class="lv__meta">提交时间：{{ formatTime(item.submittedAt || item.createdAt) }}</text>
          <view v-if="item.reviewComment" class="lv__review">
            <text class="lv__review-title">审批意见</text>
            <text class="lv__review-text">{{ item.reviewComment }}</text>
          </view>
          <button v-if="item.status === 'PENDING'" class="btn btn-ghost lv__withdraw" :disabled="submitting" @click="withdraw(item)">撤回</button>
        </view>
        <MobileInlineAlert v-if="!list.length" type="info" description="暂无补卡申请，可点击下方按钮新建。" />
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar>
      <button class="btn btn-primary flex-1" :disabled="submitting || uploading" @click="openApply">新建补卡申请</button>
    </MobileSafeAreaBar>

    <view v-if="formVisible" class="lv__mask" @click.self="closeForm">
      <view class="lv__sheet card">
        <text class="card-title">补卡申请</text>
        <view class="lv__field">
          <text class="lv__label">补卡类型 <text class="lv__req">*</text></text>
          <picker mode="selector" :range="makeupTypeLabels" :value="makeupTypeIndex" @change="onMakeupType">
            <view class="lv__picker">{{ makeupTypeLabels[makeupTypeIndex] }} <text>▾</text></view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">缺卡日期 <text class="lv__req">*</text></text>
          <picker mode="date" :value="form.checkinDate" @change="onDate">
            <view class="lv__picker">{{ form.checkinDate || '请选择' }}</view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">补卡事由 <text class="lv__req">*</text></text>
          <textarea v-model="form.reason" class="lv__textarea" maxlength="300" placeholder="详细说明缺卡原因（不少于5字）" />
        </view>
        <view class="lv__field lv__evidence" :class="{ required: evidenceRequired }">
          <text class="lv__label">证据材料 {{ evidenceRequired ? '（必需）' : '（选传）' }}</text>
          <text class="lv__rule">{{ evidenceRuleText }}</text>
          <button class="btn btn-ghost lv__upload" :disabled="uploading || submitting" @click="chooseEvidence">
            {{ uploading ? '上传中…' : (form.fileName || '选择并上传证据') }}
          </button>
        </view>
        <view class="lv__actions">
          <button class="btn btn-ghost flex-1" :disabled="submitting || uploading" @click="closeForm">取消</button>
          <button class="btn btn-primary flex-1" :disabled="submitting || uploading" @click="submit">{{ submitting ? '提交中…' : '提交申请' }}</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import {
  studentInternshipMakeupApply,
  studentInternshipMakeups,
  studentInternshipMakeupWithdraw
} from '@/services/internshipApi'
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
import { toast } from '@/utils/nav'

const MAKEUP_TYPES = [
  { value: 'MISSING', label: '缺卡补录' },
  { value: 'OUT_OF_RANGE', label: '超范围补录' }
]

export default {
  data() {
    return {
      list: [], pageState: 'loading', formVisible: false,
      submitting: false, uploading: false, makeupTypeIndex: 0,
      form: { checkinDate: '', reason: '', makeupType: 'MISSING', evidenceFileId: '', fileName: '' }
    }
  },
  computed: {
    makeupTypeLabels() { return MAKEUP_TYPES.map((item) => item.label) },
    evidenceRequired() { return this.form.makeupType === 'OUT_OF_RANGE' },
    evidenceRuleText() {
      return this.evidenceRequired
        ? '超范围补卡必须上传考勤、定位截图或现场佐证。'
        : '普通缺卡可按学校要求选传考勤或现场佐证。'
    }
  },
  onLoad() { this.loadList() },
  onPullDownRefresh() { this.loadList(() => uni.stopPullDownRefresh()) },
  methods: {
    async loadList(done) {
      this.pageState = 'loading'
      try {
        const rows = await studentInternshipMakeups()
        this.list = Array.isArray(rows) ? rows : (rows?.items || [])
        this.pageState = 'ready'
      } catch (error) {
        this.pageState = 'error'
      } finally { done?.() }
    },
    openApply() {
      this.makeupTypeIndex = 0
      this.form = { checkinDate: '', reason: '', makeupType: 'MISSING', evidenceFileId: '', fileName: '' }
      this.formVisible = true
    },
    closeForm() {
      if (this.submitting || this.uploading) return
      this.formVisible = false
    },
    onMakeupType(event) {
      this.makeupTypeIndex = Number(event.detail.value)
      this.form.makeupType = MAKEUP_TYPES[this.makeupTypeIndex]?.value || 'MISSING'
    },
    onDate(event) { this.form.checkinDate = event.detail.value },
    async chooseEvidence() {
      if (this.uploading || this.submitting) return
      this.uploading = true
      try {
        const file = await chooseSingleFile()
        if (!file) return
        if (Number(file.size || 0) > 20 * 1024 * 1024) return toast('单个证据文件不能超过20MB')
        const uploaded = await uploadBusinessFile(file, { bizType: 'INTERNSHIP', bizId: '' })
        this.form.evidenceFileId = uploaded.fileId
        this.form.fileName = uploaded.fileName || file.name || '补卡证据'
        toast('证据材料上传成功')
      } catch (error) {
        toast(error?.message || '证据材料上传失败')
      } finally { this.uploading = false }
    },
    async submit() {
      if (this.submitting || this.uploading) return
      if (!this.form.checkinDate || this.form.reason.trim().length < 5) {
        return toast('请填写缺卡日期与详细事由（不少于5字）')
      }
      if (this.evidenceRequired && !this.form.evidenceFileId) return toast(this.evidenceRuleText)
      this.submitting = true
      try {
        await studentInternshipMakeupApply({
          checkinDate: this.form.checkinDate,
          reason: this.form.reason.trim(),
          makeupType: this.form.makeupType,
          evidenceFileId: this.form.evidenceFileId || ''
        })
        toast('补卡申请已提交')
        this.formVisible = false
        await this.loadList()
      } catch (error) {
        toast(error?.message || '提交失败，请稍后重试')
      } finally { this.submitting = false }
    },
    withdraw(item) {
      if (this.submitting) return
      uni.showModal({
        title: '撤回补卡', content: '确认撤回该待审核补卡申请？',
        success: async (result) => {
          if (!result.confirm) return
          this.submitting = true
          try {
            await studentInternshipMakeupWithdraw(item.id, item.version)
            toast('已撤回')
            await this.loadList()
          } catch (error) {
            toast(error?.message || '撤回失败')
            if (String(error?.code || '') === 'DATA_CONFLICT') await this.loadList()
          } finally { this.submitting = false }
        }
      })
    },
    formatTime(value) {
      if (!value) return '—'
      return String(value).replace('T', ' ').slice(0, 16)
    }
  }
}
</script>

<style scoped>
.lv__hint{display:block;margin-top:8rpx;color:var(--t3);font-size:24rpx;line-height:1.5}.lv__item{margin-bottom:16rpx}.lv__range{font-weight:600;color:var(--t1)}.lv__days{display:block;margin-top:8rpx;color:var(--t3);font-size:24rpx}.lv__reason{display:block;margin-top:8rpx;color:var(--t2);font-size:26rpx;line-height:1.5}.lv__meta{display:block;margin-top:6rpx;color:var(--text-tertiary);font-size:22rpx}.lv__review{margin-top:12rpx;padding:16rpx 18rpx;border-radius:12rpx;background:var(--warning-50,#fff7ed)}.lv__review-title{display:block;font-size:22rpx;font-weight:600;color:var(--warning-800,#9a3412)}.lv__review-text{display:block;margin-top:5rpx;font-size:25rpx;line-height:1.5}.lv__withdraw{margin-top:16rpx}.lv__mask{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:99;display:flex;align-items:flex-end}.lv__sheet{width:100%;border-radius:24rpx 24rpx 0 0;padding:32rpx;max-height:88vh;overflow-y:auto;box-sizing:border-box}.lv__field{margin-top:24rpx}.lv__label{display:block;margin-bottom:8rpx;color:var(--t2);font-size:26rpx}.lv__req{color:#c0392b}.lv__picker,.lv__textarea{background:var(--bg-soft,#f5f6f8);border-radius:12rpx;padding:20rpx}.lv__textarea{width:100%;min-height:160rpx;box-sizing:border-box}.lv__evidence{padding:20rpx;border:1px solid var(--border-base);border-radius:14rpx;background:var(--gray-50)}.lv__evidence.required{border-color:var(--warning-400,#fb923c);background:var(--warning-50,#fff7ed)}.lv__rule{display:block;color:var(--text-secondary);font-size:22rpx;line-height:1.45}.lv__upload{margin-top:14rpx}.lv__actions{display:flex;gap:16rpx;margin-top:32rpx}
</style>
