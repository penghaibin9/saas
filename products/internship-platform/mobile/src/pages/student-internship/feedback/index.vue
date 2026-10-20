<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="意见反馈" show-back />
    <MobilePrivacyGate />
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack">
        <view class="card">
          <text class="card-title">意见反馈</text>
          <text class="fb__hint">把实习过程中的建议、想法或体验问题反馈给学校。请选择学院级或系部级，学校会在现有受理台账中跟进。</text>
        </view>

        <MobileInlineAlert v-if="historyMode" type="info" title="历史实习记录" description="历史批次仅可查看反馈记录，不可新增反馈。" />
        <MobileInlineAlert v-if="errorMessage" type="warning" title="本次操作未完成" :description="errorMessage" />

        <view v-if="records.length" class="card stack">
          <text class="card-title">我的反馈记录</text>
          <view v-for="item in records" :key="item.id" class="fb__record">
            <view class="row-between">
              <view class="fb__record-main">
                <text class="fb__record-title">{{ item.title }}</text>
                <text class="fb__meta">{{ item.feedbackLevelLabel }} · {{ formatTime(item.createdAt) }}</text>
              </view>
              <MobileStatusTag :label="item.statusLabel || item.status" :type="statusTone(item.status)" />
            </view>
            <text class="fb__content">{{ item.content }}</text>
            <text v-if="item.imageFileIds?.length" class="fb__meta">已上传 {{ item.imageFileIds.length }} 张图片</text>
            <view v-if="item.conclusion" class="fb__reply">
              <text class="fb__reply-label">学校处理意见</text>
              <text>{{ item.conclusion }}</text>
            </view>
            <view v-if="item.followupResult" class="fb__reply">
              <text class="fb__reply-label">回访结果</text>
              <text>{{ item.followupResult }}</text>
            </view>
            <button
              v-if="['RECEIVED', 'ACCEPTED'].includes(item.status) && !historyMode"
              class="btn btn-ghost fb__withdraw"
              :disabled="submitting"
              @click="withdraw(item)"
            >撤回反馈</button>
          </view>
        </view>

        <MobileInlineAlert v-else type="info" description="暂无反馈记录。你可以在下方提交本次实习的建议或想法。" />

        <view v-if="!historyMode" class="card stack">
          <view class="fb__field">
            <text class="fb__label">反馈级别 <text class="fb__req">*</text></text>
            <picker mode="selector" :range="levelLabels" :value="levelIndex" @change="onLevel">
              <view class="fb__picker">{{ levelLabels[levelIndex] }} <text>▾</text></view>
            </picker>
            <text class="fb__field-tip">学院级：面向学院层面的问题或建议；系部级：面向具体系部/专业教学组织的问题或建议。</text>
          </view>
          <view class="fb__field">
            <text class="fb__label">反馈标题 <text class="fb__req">*</text></text>
            <input v-model.trim="form.title" class="fb__input" maxlength="200" placeholder="用一句话概括你的建议或问题" />
          </view>
          <view class="fb__field">
            <text class="fb__label">反馈内容 <text class="fb__req">*</text></text>
            <textarea v-model="form.content" class="fb__textarea" maxlength="4000" placeholder="请描述具体情况、建议和希望学校改进的内容" />
            <text class="fb__count">{{ (form.content || '').length }}/4000</text>
          </view>
          <view class="fb__field fb__images">
            <view class="row-between">
              <text class="fb__label">图片（选传，最多9张）</text>
              <text class="fb__meta">{{ form.images.length }}/9</text>
            </view>
            <view v-if="form.images.length" class="fb__image-list">
              <view v-for="(image, index) in form.images" :key="image.fileId" class="fb__image-item">
                <text class="fb__image-name">{{ image.fileName || `图片 ${index + 1}` }}</text>
                <text class="fb__remove" @click="removeImage(index)">移除</text>
              </view>
            </view>
            <button v-if="form.images.length < 9" class="btn btn-ghost fb__upload" :disabled="uploading || submitting" @click="addImage">
              {{ uploading ? '上传中…' : '添加图片' }}
            </button>
          </view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="pageState === 'ready' && !historyMode">
      <button class="btn btn-primary flex-1" :disabled="submitting || uploading" @click="submit">
        {{ submitting ? '提交中…' : '提交意见反馈' }}
      </button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
import { toast } from '@/utils/nav'

const LEVELS = [
  { value: 'COLLEGE', label: '学院级' },
  { value: 'DEPARTMENT', label: '系部级' }
]
const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'heic', 'heif']

export default {
  data() {
    return {
      pageState: 'loading', requestedBatchId: '', context: {}, historyMode: false,
      records: [], levelIndex: 0, levelLabels: LEVELS.map((item) => item.label),
      form: { title: '', content: '', images: [] },
      submitting: false, uploading: false, errorMessage: ''
    }
  },
  onLoad(options = {}) {
    this.requestedBatchId = String(options.batchId || '')
    this.load()
  },
  onPullDownRefresh() {
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '—' },
    statusTone(status) {
      if (['RESOLVED', 'CLOSED'].includes(status)) return 'success'
      if (status === 'REJECTED') return 'danger'
      if (['ACCEPTED', 'INVESTIGATING'].includes(status)) return 'info'
      return 'warning'
    },
    async load(done) {
      this.pageState = 'loading'
      this.errorMessage = ''
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId)
        this.context = { batchId: dashboard?.batchId || '', internshipId: dashboard?.recordId || '' }
        this.historyMode = !!dashboard?.historyMode
        const data = await studentApi.getInternshipFeedback(this.context.batchId, this.context.internshipId)
        this.records = data?.items || []
        this.pageState = 'ready'
      } catch (error) {
        this.errorMessage = error?.message || '意见反馈读取失败'
        this.pageState = 'error'
      } finally {
        done?.()
      }
    },
    onLevel(event) {
      this.levelIndex = Number(event.detail.value) || 0
    },
    async addImage() {
      if (this.uploading || this.submitting || this.form.images.length >= 9) return
      this.uploading = true
      this.errorMessage = ''
      try {
        const file = await chooseSingleFile()
        if (!file) return
        const name = String(file.name || file.path || '')
        const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : ''
        const type = String(file.type || '').toLowerCase()
        if (!(type.startsWith('image/') || IMAGE_EXTENSIONS.includes(ext))) {
          return toast('意见反馈仅支持上传图片')
        }
        if (Number(file.size || 0) > 20 * 1024 * 1024) return toast('单张图片不能超过20MB')
        const uploaded = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_FEEDBACK' })
        if (!uploaded?.fileId) throw new Error('图片上传结果不完整')
        if (!this.form.images.some((item) => String(item.fileId) === String(uploaded.fileId))) {
          this.form.images.push({
            fileId: uploaded.fileId,
            fileName: uploaded.fileName || file.name || '反馈图片'
          })
        }
        toast('图片上传成功')
      } catch (error) {
        this.errorMessage = error?.message || '图片上传失败'
      } finally {
        this.uploading = false
      }
    },
    removeImage(index) {
      if (this.submitting || this.uploading) return
      this.form.images.splice(index, 1)
    },
    async submit() {
      if (this.submitting || this.uploading || this.historyMode) return
      const title = (this.form.title || '').trim()
      const content = (this.form.content || '').trim()
      if (title.length < 2) return toast('反馈标题不少于2个字')
      if (content.length < 5) return toast('反馈内容不少于5个字')
      this.submitting = true
      this.errorMessage = ''
      try {
        await studentApi.submitInternshipFeedback({
          ...this.context,
          title,
          feedbackLevel: LEVELS[this.levelIndex]?.value || 'COLLEGE',
          content,
          imageFileIds: this.form.images.map((item) => item.fileId)
        })
        toast('意见反馈已提交')
        this.form = { title: '', content: '', images: [] }
        this.levelIndex = 0
        await this.load()
      } catch (error) {
        this.errorMessage = error?.message || '意见反馈提交失败'
      } finally {
        this.submitting = false
      }
    },
    async withdraw(item) {
      if (this.submitting || !item?.id) return
      this.submitting = true
      this.errorMessage = ''
      try {
        await studentApi.withdrawInternshipFeedback(item.id, {
          ...this.context,
          expectedVersion: item.version
        })
        toast('意见反馈已撤回')
        await this.load()
      } catch (error) {
        this.errorMessage = error?.message || '撤回失败，请刷新后重试'
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
.fb__hint{display:block;margin-top:8px;color:var(--text-secondary);font-size:var(--font-size-sm);line-height:1.6}.fb__field{margin-bottom:14px}.fb__label{display:block;margin-bottom:6px;font-size:var(--font-size-sm);font-weight:500}.fb__req{color:var(--danger-600)}.fb__picker,.fb__input,.fb__textarea{width:100%;box-sizing:border-box;border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;background:var(--bg-card);font-size:var(--font-size-sm)}.fb__textarea{min-height:120px}.fb__field-tip,.fb__meta,.fb__count{display:block;margin-top:5px;color:var(--text-tertiary);font-size:var(--font-size-xs);line-height:1.5}.fb__count{text-align:right}.fb__images{padding:12px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--gray-50)}.fb__image-list{display:flex;flex-direction:column;gap:7px;margin-top:6px}.fb__image-item{display:flex;justify-content:space-between;gap:12px;padding:8px 10px;border-radius:8px;background:var(--bg-card);font-size:var(--font-size-xs)}.fb__image-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.fb__remove{flex:0 0 auto;color:var(--danger-600)}.fb__upload{margin-top:10px}.fb__record{padding:12px 0;border-bottom:1px solid var(--border-light)}.fb__record:last-child{border-bottom:0}.fb__record-main{min-width:0;display:flex;flex-direction:column}.fb__record-title{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.fb__content{display:block;margin-top:8px;font-size:var(--font-size-sm);line-height:1.6;white-space:pre-wrap;word-break:break-word}.fb__reply{margin-top:10px;padding:10px;border-radius:8px;background:var(--gray-50);font-size:var(--font-size-sm);line-height:1.6}.fb__reply-label{display:block;margin-bottom:4px;font-weight:600}.fb__withdraw{margin-top:9px}
</style>
