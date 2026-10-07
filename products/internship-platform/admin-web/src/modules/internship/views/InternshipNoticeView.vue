<template>
  <ModulePageShell
    title="通知公告"
    subtitle="发布岗位实习通知，支持指定学院、紧急强弹、有效期和多格式附件。"
    :watermark="false"
  >
    <div class="inot-grid">
      <section class="inot-card">
        <header class="inot-head">
          <div>
            <h2>发布通知</h2>
            <p>重要/紧急通知会在学生和教师移动端强制弹框，明确确认后才记为已读。</p>
          </div>
        </header>

        <div v-if="!canManage" class="inot-readonly">当前账号只有查看权限，不能发布或撤回通知。</div>

        <div class="inot-form">
          <label>
            <span>公告类型</span>
            <AppSelect v-model="form.noticeType" :options="typeOptions" :disabled="!canManage || submitting" />
          </label>
          <label>
            <span>紧急程度</span>
            <AppSelect v-model="form.urgency" :options="urgencyOptions" :disabled="!canManage || submitting" />
          </label>
          <label>
            <span>接收范围</span>
            <AppSelect v-model="form.audienceScope" :options="audienceOptions" :disabled="!canManage || submitting" @change="onAudienceChange" />
          </label>
          <label v-if="form.audienceScope === 'COLLEGE'" class="inot-full">
            <span>指定学院</span>
            <AppCollegePicker
              v-model="form.recipientCollegeIds"
              multiple
              :disabled="!canManage || submitting"
              placeholder="请选择接收学院"
              data-scope-hint="仅显示当前账号授权范围内学院"
            />
          </label>
          <label class="inot-full">
            <span>通知标题</span>
            <input v-model.trim="form.title" class="inot-input" maxlength="200" :disabled="!canManage || submitting" placeholder="请输入通知标题" />
          </label>
          <label class="inot-full">
            <span>通知正文</span>
            <textarea v-model="form.content" class="inot-textarea" maxlength="5000" :disabled="!canManage || submitting" placeholder="请输入通知正文" />
          </label>
          <label>
            <span>有效期开始</span>
            <input v-model="form.validFrom" class="inot-input" type="date" :disabled="!canManage || submitting" />
          </label>
          <label>
            <span>有效期结束</span>
            <input v-model="form.validUntil" class="inot-input" type="date" :disabled="!canManage || submitting" />
          </label>

          <div class="inot-full inot-attachments">
            <div class="inot-attachments-head">
              <span>附件</span>
              <small>支持 RAR、ZIP、WORD、EXCEL、PDF，最多 9 个</small>
            </div>
            <div v-for="(file, index) in form.attachments" :key="file.fileId" class="inot-file">
              <button type="button" class="inot-file-name" @click="previewAttachment(file)">{{ file.fileName }}</button>
              <span>{{ formatSize(file.sizeBytes) }}</span>
              <button type="button" class="mp-link danger" :disabled="submitting || uploading" @click="removeAttachment(index)">移除</button>
            </div>
            <div class="inot-upload-row">
              <input ref="fileInput" type="file" class="inot-file-input" accept=".rar,.zip,.doc,.docx,.pdf,.xls,.xlsx" @change="onFilePicked" />
              <AppButton variant="ghost" :disabled="!canManage || submitting || uploading || form.attachments.length >= 9" @click="$refs.fileInput?.click()">
                {{ uploading ? '上传中…' : '添加附件' }}
              </AppButton>
            </div>
          </div>
        </div>

        <div class="inot-actions">
          <AppButton variant="primary" :disabled="!canManage || submitting || uploading" @click="publish">
            {{ submitting ? '发布中…' : '发布通知' }}
          </AppButton>
          <span v-if="form.urgency !== 'NORMAL'" class="inot-warning">该通知将触发移动端强制确认。</span>
        </div>
      </section>

      <section class="inot-card">
        <header class="inot-head">
          <div>
            <h2>本批次通知记录</h2>
            <p>保留已撤回记录，便于审计和验收。</p>
          </div>
          <AppButton variant="ghost" :disabled="loading" @click="load">{{ loading ? '刷新中…' : '刷新' }}</AppButton>
        </header>

        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <div v-else-if="notices.length" class="inot-list">
          <article v-for="row in notices" :key="row.id" class="inot-notice">
            <div class="row-between">
              <div class="inot-title-wrap">
                <strong>{{ row.title }}</strong>
                <span>{{ typeLabel(row.noticeType) }} · {{ urgencyLabel(row.urgency) }} · {{ audienceLabel(row) }}</span>
              </div>
              <AppStatusTag :type="row.status === 'PUBLISHED' ? (row.urgency === 'URGENT' ? 'danger' : 'warning') : 'default'">
                {{ row.status === 'PUBLISHED' ? '已发布' : '已撤回' }}
              </AppStatusTag>
            </div>
            <p>{{ row.content }}</p>
            <div class="inot-meta">
              <span>发布人：{{ row.senderName || '学校' }}</span>
              <span>发布时间：{{ formatTime(row.publishedAt) }}</span>
              <span>接收学生：{{ row.recipientCount }} 人</span>
              <span v-if="row.validFrom || row.validUntil">有效期：{{ formatDate(row.validFrom) }} 至 {{ formatDate(row.validUntil) }}</span>
            </div>
            <div v-if="row.attachments?.length" class="inot-attachment-list">
              <button v-for="file in row.attachments" :key="file.fileId" type="button" class="inot-attachment-chip" @click="previewAttachment(file)">
                {{ file.fileName || '附件' }}
              </button>
            </div>
            <div v-if="row.status === 'PUBLISHED' && canManage" class="inot-row-actions">
              <AppButton variant="ghost" :disabled="withdrawingId === String(row.id)" @click="withdraw(row)">
                {{ withdrawingId === String(row.id) ? '撤回中…' : '撤回通知' }}
              </AppButton>
            </div>
          </article>
        </div>
        <EmptyState v-else title="当前批次暂无通知" description="发布后会保留在这里，并按接收范围投递到学生和教师端。" />
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSelect, AppCollegePicker, AppStatusTag } from '@/components/common'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { canCode } from '@/modules/internship/composables/permission'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { fileSdk } from '@/services/file/fileSdk'
import { toast } from '@/utils/toast'

const TYPES = [
  { value: 'AGREEMENT', label: '实习协议' },
  { value: 'TRAINING', label: '岗前培训' },
  { value: 'SAFETY', label: '安全条例' },
  { value: 'NOTICE', label: '通知公告' },
  { value: 'OTHER', label: '其他' }
]
const URGENCY = [
  { value: 'NORMAL', label: '普通' },
  { value: 'IMPORTANT', label: '重要' },
  { value: 'URGENT', label: '紧急' }
]
const AUDIENCE = [
  { value: 'ALL', label: '全校当前批次' },
  { value: 'COLLEGE', label: '指定学院' }
]
const blankForm = () => ({
  noticeType: 'NOTICE',
  urgency: 'IMPORTANT',
  audienceScope: 'ALL',
  recipientCollegeIds: [],
  title: '',
  content: '',
  validFrom: '',
  validUntil: '',
  attachments: []
})

export default {
  name: 'InternshipNoticeView',
  components: {
    ModulePageShell, LoadingState, ErrorState, EmptyState,
    AppButton, AppSelect, AppCollegePicker, AppStatusTag
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      typeOptions: TYPES,
      urgencyOptions: URGENCY,
      audienceOptions: AUDIENCE,
      form: blankForm(),
      notices: [],
      loading: false,
      error: '',
      submitting: false,
      uploading: false,
      withdrawingId: '',
      loadTicket: 0
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    canManage() { return canCode(this.ctx, 'internship.communication.manage') }
  },
  watch: {
    'batchStore.selectedBatchId': {
      immediate: true,
      handler() {
        this.form = blankForm()
        this.notices = []
        this.load()
      }
    }
  },
  methods: {
    typeLabel(value) { return TYPES.find((x) => x.value === value)?.label || '通知公告' },
    urgencyLabel(value) { return URGENCY.find((x) => x.value === value)?.label || '普通' },
    audienceLabel(row) {
      if (row.audienceScope !== 'COLLEGE') return '全校当前批次'
      const count = (row.recipientCollegeIds || []).length
      return `指定学院（${count} 个）`
    },
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '—' },
    formatDate(value) { return value ? String(value).slice(0, 10) : '不限' },
    formatSize(value) {
      const size = Number(value || 0)
      if (!size) return ''
      if (size < 1024) return `${size} B`
      if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
      return `${(size / 1024 / 1024).toFixed(1)} MB`
    },
    onAudienceChange() {
      if (this.form.audienceScope !== 'COLLEGE') this.form.recipientCollegeIds = []
    },
    async load() {
      const batchId = this.batchStore.selectedBatchId
      const ticket = ++this.loadTicket
      this.error = ''
      this.notices = []
      if (!batchId) {
        this.loading = false
        this.error = '请先选择实习批次'
        return
      }
      this.loading = true
      const res = await internshipApi.getInternshipNotices(batchId, true)
      if (ticket !== this.loadTicket || batchId !== this.batchStore.selectedBatchId) return
      if (res.code === 0) this.notices = Array.isArray(res.data) ? res.data : []
      else this.error = res.message || '通知记录加载失败'
      this.loading = false
    },
    async onFilePicked(event) {
      const input = event.target
      const file = input?.files?.[0]
      input.value = ''
      if (!file || this.uploading || this.submitting) return
      const ext = String(file.name || '').split('.').pop().toLowerCase()
      if (!['rar', 'zip', 'doc', 'docx', 'pdf', 'xls', 'xlsx'].includes(ext)) {
        toast.error('附件仅支持 RAR、ZIP、WORD、EXCEL、PDF')
        return
      }
      if (this.form.attachments.length >= 9) {
        toast.error('通知附件最多 9 个')
        return
      }
      this.uploading = true
      try {
        const task = fileSdk.upload(file, { bizType: 'INTERNSHIP_NOTICE', clientType: 'ADMIN_PC' })
        const uploaded = await task.promise
        if (!uploaded?.fileId) throw new Error('附件上传结果不完整')
        if (!this.form.attachments.some((item) => String(item.fileId) === String(uploaded.fileId))) {
          this.form.attachments.push({
            fileId: String(uploaded.fileId),
            fileName: uploaded.fileName || file.name,
            sizeBytes: uploaded.sizeBytes || file.size
          })
        }
        toast.success('通知附件上传成功')
      } catch (error) {
        toast.error(error?.message || '附件上传失败')
      } finally {
        this.uploading = false
      }
    },
    removeAttachment(index) {
      if (this.submitting || this.uploading) return
      this.form.attachments.splice(index, 1)
    },
    async previewAttachment(file) {
      try { await fileSdk.preview(String(file.fileId)) }
      catch (error) { toast.error(error?.message || '附件暂时无法预览') }
    },
    async publish() {
      const batchId = this.batchStore.selectedBatchId
      if (!this.canManage || !batchId || this.submitting || this.uploading) return
      if ((this.form.title || '').trim().length < 2) return toast.error('通知标题不少于 2 个字')
      if ((this.form.content || '').trim().length < 5) return toast.error('通知正文不少于 5 个字')
      if (this.form.audienceScope === 'COLLEGE' && !this.form.recipientCollegeIds.length) return toast.error('请至少选择一个接收学院')
      if (this.form.validFrom && this.form.validUntil && this.form.validFrom > this.form.validUntil) return toast.error('有效期结束日期不能早于开始日期')

      this.submitting = true
      const res = await internshipApi.publishInternshipNotice({
        batchId: Number(batchId),
        noticeType: this.form.noticeType,
        urgency: this.form.urgency,
        audienceScope: this.form.audienceScope,
        recipientCollegeIds: this.form.audienceScope === 'COLLEGE'
          ? this.form.recipientCollegeIds.map((id) => Number(id))
          : [],
        title: this.form.title.trim(),
        content: this.form.content.trim(),
        validFrom: this.form.validFrom ? this.form.validFrom + 'T00:00:00' : null,
        validUntil: this.form.validUntil ? this.form.validUntil + 'T23:59:59' : null,
        attachmentFileIds: this.form.attachments.map((item) => String(item.fileId))
      })
      this.submitting = false
      if (res.code !== 0) {
        toast.error(res.message || '通知发布失败')
        return
      }
      toast.success('通知已发布')
      this.form = blankForm()
      await this.load()
    },
    async withdraw(row) {
      if (!this.canManage || !row?.id || this.withdrawingId) return
      this.withdrawingId = String(row.id)
      const res = await internshipApi.withdrawInternshipNotice(row.id, '管理员主动撤回')
      this.withdrawingId = ''
      if (res.code !== 0) {
        toast.error(res.message || '通知撤回失败')
        return
      }
      toast.success('通知已撤回')
      await this.load()
    }
  }
}
</script>

<style scoped>
.inot-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:16px;align-items:start}.inot-card{padding:16px;border:1px solid var(--border-light);border-radius:12px;background:var(--card);box-shadow:var(--shadow-xs)}.inot-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px}.inot-head h2{margin:0;font-size:16px}.inot-head p{margin:5px 0 0;color:var(--t3);font-size:12px;line-height:1.55}.inot-readonly{margin-bottom:14px;padding:10px 12px;border-radius:8px;background:#fff7ed;color:#9a3412;font-size:12px}.inot-form{display:grid;grid-template-columns:1fr 1fr;gap:14px}.inot-form label{display:flex;flex-direction:column;gap:6px;color:var(--t2);font-size:12px}.inot-full{grid-column:1/-1}.inot-input,.inot-textarea{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:8px;padding:10px 12px;background:var(--card);color:var(--t1);font:inherit}.inot-textarea{min-height:130px;resize:vertical}.inot-attachments{padding:12px;border:1px solid var(--border-light);border-radius:10px;background:var(--bg-soft)}.inot-attachments-head{display:flex;justify-content:space-between;gap:12px;margin-bottom:8px}.inot-attachments-head small{color:var(--t3)}.inot-file{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:10px;align-items:center;padding:8px 0;border-top:1px solid var(--border-light);font-size:12px}.inot-file-name{padding:0;border:0;background:none;text-align:left;color:var(--primary-600);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer}.inot-file-input{display:none}.inot-upload-row{margin-top:10px}.inot-actions{display:flex;align-items:center;gap:12px;margin-top:16px}.inot-warning{font-size:12px;color:#b45309}.inot-list{display:flex;flex-direction:column;gap:12px}.inot-notice{padding:14px;border:1px solid var(--border-light);border-radius:10px;background:var(--bg-soft)}.inot-title-wrap{min-width:0;display:flex;flex-direction:column;gap:4px}.inot-title-wrap strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.inot-title-wrap span,.inot-meta{font-size:12px;color:var(--t3)}.inot-notice p{margin:10px 0;white-space:pre-wrap;word-break:break-word;line-height:1.65;color:var(--t2)}.inot-meta{display:flex;flex-wrap:wrap;gap:6px 14px}.inot-attachment-list{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.inot-attachment-chip{padding:6px 9px;border:1px solid var(--border-light);border-radius:999px;background:var(--card);color:var(--primary-600);cursor:pointer;font-size:12px}.inot-row-actions{margin-top:10px}.danger{color:#b91c1c}@media(max-width:1100px){.inot-grid{grid-template-columns:1fr}}
</style>
