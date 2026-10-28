<template>
  <view class="mobile-page mobile-student page-wrap">
    <MobileNavBar variant="brand" title="意见反馈" show-back :fallback-url="'/pages/student-internship/index' + (context.batchId ? '?batchId=' + encodeURIComponent(context.batchId) : '')" />
    <MobilePrivacyGate />
    <MobileGlobalState :state="pageState" :description="errorMessage" @retry="load()">
      <view class="page-pad stack">
        <MobileInlineAlert v-if="historyMode && records.length" type="info" description="历史反馈仅供查阅。" />
        <MobileInlineAlert v-if="errorMessage" type="warning" title="本次操作未完成" :description="errorMessage" />
        <view v-if="receipt" class="card stack" role="status">
          <text>反馈记录 #{{ receipt.id }} · {{ statusLabel(receipt.status) }}</text>
          <text>处理意见可在本页查看，请勿重复提交。</text>
        </view>
        <button class="mobile-control fb__refresh" :disabled="submitting || uploading" @click="load()">刷新记录</button>

        <view v-if="records.length" class="card stack">
          <text class="card-title">我的反馈记录</text>
          <view v-for="item in records" :key="item.id" class="fb__record">
            <view class="row-between">
              <view class="fb__record-main">
                <text class="fb__record-title">{{ item.title }}</text>
                <text class="fb__meta">{{ levelLabel(item.feedbackLevel) }} · {{ formatTime(item.createdAt) }}</text>
              </view>
              <MobileStatusTag :label="statusLabel(item.status)" :type="statusTone(item.status)" />
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
              class="mobile-control btn btn-ghost fb__withdraw"
              :disabled="!canWrite || submitting || uploading"
              @click="withdraw(item)"
            >撤回反馈</button>
          </view>
        </view>

        <MobileInlineAlert v-else type="info" :description="historyMode ? '暂无反馈记录，历史实习仅供查阅。' : '暂无反馈记录'" />

        <view v-if="!historyMode" class="card stack">
          <view class="fb__field">
            <text class="fb__label">反馈级别 <text class="fb__req">*</text></text>
            <picker class="mobile-picker" mode="selector" :range="levelLabels" :value="levelIndex" :disabled="!canWrite || submitting || uploading" @change="onLevel">
              <view class="fb__picker">{{ levelLabels[levelIndex] }} <text>▾</text></view>
            </picker>
            <text class="fb__field-tip">学院级面向学院事项，系部级面向所在系部或专业的问题。</text>
          </view>
          <view class="fb__field">
            <text class="fb__label">反馈标题 <text class="fb__req">*</text></text>
            <input v-model.trim="form.title" :disabled="!canWrite || submitting || uploading" class="mobile-input fb__input" maxlength="200" placeholder="用一句话概括你的建议或问题" />
          </view>
          <view class="fb__field">
            <text class="fb__label">反馈内容 <text class="fb__req">*</text></text>
            <textarea v-model="form.content" :disabled="!canWrite || submitting || uploading" class="mobile-textarea fb__textarea" maxlength="4000" placeholder="请描述具体情况、建议和希望学校改进的内容" />
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
            <button v-if="form.images.length < 9" class="mobile-control btn btn-ghost fb__upload" :disabled="!canWrite || uploading || submitting" @click="addImage">
              {{ uploading ? '上传中…' : '添加图片' }}
            </button>
          </view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="pageState === 'ready' && !historyMode">
      <button class="mobile-control btn btn-primary flex-1" :disabled="!canWrite || submitting || uploading" @click="submit">
        {{ submitting ? '提交中…' : '提交意见反馈' }}
      </button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
import { toast } from '@/utils/nav'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { formatDateTime } from '@/utils/format'

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
      submitting: false, uploading: false, errorMessage: '', receipt: null,
      hidden: false, sequence: 0, generation: currentSessionGeneration()
    }
  },
  computed: {
    canWrite() { return this.pageState === 'ready' && !this.hidden && !this.historyMode && !!this.context.batchId && !!this.context.internshipId && this.generation === currentSessionGeneration() }
  },
  onLoad(options = {}) {
    this.requestedBatchId = String(options.batchId || '')
    this.load()
  },
  onPullDownRefresh() {
    if (this.submitting || this.uploading) return uni.stopPullDownRefresh()
    this.load().finally(() => uni.stopPullDownRefresh())
  },
  onShow() { if (this.hidden || this.generation !== currentSessionGeneration()) { this.hidden = false; this.load() } },
  onHide() { this.hidden = true; this.sequence++ },
  onUnload() { this.hidden = true; this.sequence++; this.records = []; this.context = {}; this.receipt = null; this.form = { title:'', content:'', images:[] } },
  methods: {
    formatTime: formatDateTime,
    statusLabel(status) { return ({ RECEIVED:'已提交', ACCEPTED:'已受理', INVESTIGATING:'处理中', RESOLVED:'已办结', REJECTED:'未采纳', WITHDRAWN:'已撤回', CLOSED:'已关闭' })[status] || '状态待确认' },
    levelLabel(level) { return LEVELS.find(item => item.value === level)?.label || '反馈级别待确认' },
    command() { return { sequence:this.sequence, generation:currentSessionGeneration(), batchId:this.context.batchId, internshipId:this.context.internshipId } },
    current(command) { return !this.hidden && command.sequence===this.sequence && command.generation===currentSessionGeneration() && command.batchId===this.context.batchId && command.internshipId===this.context.internshipId },
    statusTone(status) {
      if (['RESOLVED', 'CLOSED'].includes(status)) return 'success'
      if (status === 'REJECTED') return 'danger'
      if (['ACCEPTED', 'INVESTIGATING'].includes(status)) return 'info'
      return 'warning'
    },
    async load() {
      const sequence=++this.sequence,generation=currentSessionGeneration()
      const current=()=>!this.hidden && sequence===this.sequence && generation===currentSessionGeneration()
      if(this.generation!==generation){this.context={};this.form={title:'',content:'',images:[]};this.levelIndex=0;this.receipt=null}
      this.generation=generation;this.pageState='loading';this.errorMessage='';this.records=[];this.submitting=false;this.uploading=false
      try {
        const dashboard=await studentApi.getInternship(this.requestedBatchId)
        if(!current())return
        const context={batchId:String(dashboard?.batchId||''),internshipId:String(dashboard?.recordId||'')}
        if(this.context.batchId && (context.batchId!==this.context.batchId || context.internshipId!==this.context.internshipId)){this.form={title:'',content:'',images:[]};this.levelIndex=0;this.receipt=null}
        this.context=context;this.historyMode=dashboard?.historyMode===true
        if(!context.batchId || !context.internshipId){this.pageState='empty';this.errorMessage='当前没有可用实习记录，请先核对实习批次。';return}
        const data=await studentApi.getInternshipFeedback(context.batchId,context.internshipId)
        if(!current())return
        if(!Array.isArray(data?.items))throw Error('invalid feedback list')
        this.records=data.items;this.pageState='ready'
      } catch(error) {if(current()){this.errorMessage=normalizeError(error).text;this.pageState='error'}}
    },
    async refreshRecords(command) {
      try{
        const data=await studentApi.getInternshipFeedback(command.batchId,command.internshipId)
        if(!this.current(command))return
        if(!Array.isArray(data?.items)||!data.items.some(item=>String(item.id)===String(this.receipt?.id)))throw Error('feedback readback incomplete')
        this.records=data.items
      }catch(error){if(this.current(command))this.errorMessage='反馈办理已登记，列表回读未完成，请重新读取；无需重复提交。'}
    },
    onLevel(event) {if(this.canWrite && !this.submitting && !this.uploading)this.levelIndex=Number(event.detail.value)||0},
    async addImage() {
      if (!this.canWrite || this.uploading || this.submitting || this.form.images.length >= 9) return
      const command = this.command(), form = this.form
      const current = () => this.current(command) && form === this.form
      this.uploading = true
      this.errorMessage = ''
      try {
        const file = await chooseSingleFile()
        if (!file || !current()) return
        const name = String(file.name || file.path || '')
        const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : ''
        const type = String(file.type || '').toLowerCase()
        if (!(type.startsWith('image/') || IMAGE_EXTENSIONS.includes(ext))) {
          return toast('意见反馈仅支持上传图片')
        }
        if (Number(file.size || 0) > 20 * 1024 * 1024) return toast('单张图片不能超过20兆字节')
        const uploaded = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_FEEDBACK' })
        if (!current()) return
        if (!uploaded?.fileId) throw new Error('图片上传结果不完整')
        if (!this.form.images.some((item) => String(item.fileId) === String(uploaded.fileId))) {
          this.form.images.push({
            fileId: String(uploaded.fileId),
            fileName: uploaded.fileName || file.name || '反馈图片'
          })
        }
        toast('图片上传成功')
      } catch (error) {
        if (current()) this.errorMessage = normalizeError(error).text
      } finally {
        if (current()) this.uploading = false
      }
    },
    removeImage(index) {
      if (!this.canWrite || this.submitting || this.uploading) return
      this.form.images.splice(index, 1)
    },
    async submit() {
      if (!this.canWrite || this.submitting || this.uploading) return
      const title = (this.form.title || '').trim()
      const content = (this.form.content || '').trim()
      if (title.length < 2) return toast('反馈标题不少于2个字')
      if (content.length < 5) return toast('反馈内容不少于5个字')
      const command = this.command(), form = this.form
      this.submitting = true
      this.errorMessage = ''
      try {
        const result = await studentApi.submitInternshipFeedback({
          batchId: command.batchId, internshipId: command.internshipId,
          title,
          feedbackLevel: LEVELS[this.levelIndex]?.value || 'COLLEGE',
          content,
          imageFileIds: this.form.images.map((item) => item.fileId)
        })
        if (!this.current(command) || form !== this.form) return
        if (!result?.id) throw Error('invalid feedback receipt')
        this.receipt = result
        toast('意见反馈已提交')
        this.form = { title: '', content: '', images: [] }
        this.levelIndex = 0
        await this.refreshRecords(command)
      } catch (error) {
        if (this.current(command)) {
          const shown = normalizeError(error)
          this.errorMessage = ['network','unknown'].includes(shown.kind)
            ? shown.text + '。提交结果尚未确认，请先重新读取反馈记录，勿重复提交。'
            : shown.text
        }
      } finally {
        if (this.current(command)) this.submitting = false
      }
    },
    async withdraw(item) {
      if (!this.canWrite || this.submitting || this.uploading || !item?.id || !['RECEIVED','ACCEPTED'].includes(item.status)) return
      const command = this.command(), id = String(item.id), version = item.version
      this.submitting = true
      this.errorMessage = ''
      try {
        const result = await studentApi.withdrawInternshipFeedback(id, {
          batchId: command.batchId, internshipId: command.internshipId,
          expectedVersion: version
        })
        if (!this.current(command)) return
        if (String(result?.id) !== id) throw Error('invalid feedback receipt')
        this.receipt = result
        toast('意见反馈已撤回')
        await this.refreshRecords(command)
      } catch (error) {
        if (this.current(command)) this.errorMessage = normalizeError(error).text
      } finally {
        if (this.current(command)) this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
.fb__hint{display:block;margin-top:8px;color:var(--text-secondary);font-size:var(--font-size-base);line-height:1.6}.fb__field{margin-bottom:14px}.fb__label{display:block;margin-bottom:6px;font-size:var(--font-size-base);font-weight:500}.fb__req{color:var(--danger-600)}.fb__picker,.fb__input,.fb__textarea{width:100%;box-sizing:border-box;border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;background:var(--bg-card);font-size:var(--font-size-base)}.fb__textarea{min-height:120px}.fb__field-tip,.fb__meta,.fb__count{display:block;margin-top:5px;color:var(--text-tertiary);font-size:var(--font-size-base);line-height:1.5}.fb__count{text-align:right}.fb__images{padding:12px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--gray-50)}.fb__image-list{display:flex;flex-direction:column;gap:7px;margin-top:6px}.fb__image-item{display:flex;justify-content:space-between;gap:12px;padding:8px 10px;border-radius:8px;background:var(--bg-card);font-size:var(--font-size-base)}.fb__image-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.fb__remove{flex:0 0 auto;color:var(--danger-600)}.fb__upload{margin-top:10px}.fb__record{padding:12px 0;border-bottom:1px solid var(--border-light)}.fb__record:last-child{border-bottom:0}.fb__record-main{min-width:0;display:flex;flex-direction:column}.fb__record-title{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.fb__content{display:block;margin-top:8px;font-size:var(--font-size-base);line-height:1.6;white-space:pre-wrap;word-break:break-word}.fb__reply{margin-top:10px;padding:10px;border-radius:8px;background:var(--gray-50);font-size:var(--font-size-base);line-height:1.6}.fb__reply-label{display:block;margin-bottom:4px;font-weight:600}.fb__withdraw{margin-top:9px}
.fb__input{height:44px;min-height:44px;padding:0 12px}
.fb__refresh{align-self:flex-end;min-height:44px;margin:0;padding:0 8px;background:transparent;border:0;color:var(--text-link);font-size:var(--font-size-base);line-height:44px}.fb__refresh::after{border:0}.fb__picker{min-height:44px;display:flex;align-items:center;justify-content:space-between}.fb__images{padding:12px 0;border:0;background:transparent}.fb__remove{min-height:44px;display:flex;align-items:center}</style>
