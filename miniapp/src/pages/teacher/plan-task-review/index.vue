<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习计划任务确认" subtitle="按批次确认本人数据范围内学生任务" show-back />

    <view class="page-pad">
      <view class="card pt__batch" v-if="batches.length">
        <text class="pt__label">实习批次</text>
        <picker class="pt__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="!!actingId" @change="onBatch">
          <view class="pt__pick-val">{{ batchLabels[batchIndex] || '请选择批次' }}<text class="pt__arrow">▾</text></view>
        </picker>
      </view>
      <MobileInlineAlert type="info" description="仅处理当前批次、本人指导或授权范围内的任务。退回后学生可按同一任务版本修改重交。" />
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可办理的岗位实习批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="暂无待确认任务"
          description="当前批次学生提交任务完成情况后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="p in list" :key="p.id" class="card pt">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ p.studentName || '—' }}</text>
                <text class="pt__sub">{{ p.studentNo || '' }} · 任务{{ p.taskSortOrder }} · {{ p.taskName }}</text>
              </view>
              <MobileStatusTag :label="p.statusLabel" type="warning" />
            </view>
            <view class="pt__note" v-if="p.studentNote"><text class="flex-1 t-sm">{{ p.studentNote }}</text></view>
            <button v-if="p.evidenceFileId" class="pt__evidence" :disabled="previewingId === p.id" @click="previewEvidence(p)">
              {{ previewingId === p.id ? '正在打开凭证…' : '查看学生完成凭证' }}
            </button>
            <text class="pt__missing" v-else>学生未上传完成凭证，请结合任务要求判断是否可确认。</text>
            <text class="pt__time" v-if="p.submittedAt">提交于 {{ fmt(p.submittedAt) }}</text>
            <text class="pt__version">数据版本 v{{ p.version }}</text>
            <view class="pt__actions" v-if="canReview">
              <button class="pt__reject flex-1" :disabled="actingId === p.id" @click="review(p, 'REJECT')">退回修改</button>
              <button class="pt__approve flex-1" :disabled="actingId === p.id" @click="review(p, 'APPROVE')">确认完成</button>
            </view>
            <MobileInlineAlert v-else type="warning" description="当前身份仅可查看，无任务确认权限。" />
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherInternshipPlanTasks, teacherInternshipPlanTaskReview } from '@/services/internshipApi'
import { openBusinessFile } from '@/services/fileApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      list: null, state: 'loading', actingId: '', previewingId: '', batches: [], batchId: '', batchIndex: 0
    }
  },
  computed: {
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) },
    canReview() { return useInternshipContextStore().can('internship.task.review') }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    fmt(value) { return value ? String(value).slice(0, 16).replace('T', ' ') : '—' },
    async load(done) {
      this.state = 'loading'
      try {
        const context = useInternshipContextStore()
        context.restore()
        await context.load(true)
        this.batches = context.batches || []
        this.batchId = context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) { this.list = []; this.state = 'ready'; return }
        const data = await teacherInternshipPlanTasks(this.batchId)
        this.list = (data && data.list) || []
        this.state = 'ready'
      } catch (e) {
        this.list = []
        this.state = 'error'
        toast((e && e.message) || '计划任务加载失败')
      } finally { if (done) done() }
    },
    async onBatch(e) {
      if (this.actingId) return
      this.batchIndex = Number(e.detail.value)
      const batch = this.batches[this.batchIndex]
      const context = useInternshipContextStore()
      context.selectBatch(batch && batch.id)
      this.batchId = context.selectedBatchId
      await this.load()
    },
    async previewEvidence(item) {
      if (!item.evidenceFileId || this.previewingId) return
      this.previewingId = item.id
      try { await openBusinessFile(item.evidenceFileId) }
      catch (e) { toast((e && e.message) || '凭证打开失败') }
      finally { this.previewingId = '' }
    },
    review(p, action) {
      if (!this.canReview || this.actingId) return
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '退回任务' : '确认完成',
        editable: true,
        placeholderText: reject ? '请填写具体退回原因（至少5字）' : '可填写确认意见',
        content: '',
        success: async (r) => {
          if (!r.confirm) return
          const comment = (r.content || '').trim()
          if (reject && comment.length < 5) { toast('退回原因至少5个字'); return }
          this.actingId = p.id
          try {
            await teacherInternshipPlanTaskReview(p.id, {
              action, comment, expectedVersion: p.version, batchId: this.batchId
            })
            toast(reject ? '已退回学生修改' : '已确认任务完成')
            await this.load()
          } catch (e) {
            if (String(e && e.code) === 'DATA_CONFLICT') {
              toast((e && e.message) || '任务已被其他人处理，正在刷新')
              await this.load()
            } else toast((e && e.message) || '任务处理失败，请重试')
          } finally { this.actingId = '' }
        }
      })
    }
  }
}
</script>

<style scoped>
.pt__batch { display:flex;align-items:center;min-height:48px;margin-bottom:var(--space-3);padding:0 var(--space-3); }
.pt__label { width:88px;flex-shrink:0;font-size:var(--font-size-base);color:var(--text-secondary); }
.pt__picker { flex:1; }
.pt__pick-val { text-align:right;color:var(--text-primary);font-size:var(--font-size-base); }
.pt__arrow { margin-left:4px;color:var(--text-tertiary); }
.pt { display:flex;flex-direction:column;gap:var(--space-2); }
.pt__sub { display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:2px; }
.pt__note { background:var(--gray-50);border-radius:var(--radius-md);padding:var(--space-2) var(--space-3); }
.pt__evidence { min-height:40px;padding:0 var(--space-3);border:1px solid var(--success-500);border-radius:var(--radius-md);background:var(--success-50);color:var(--success-700);font-size:var(--font-size-sm);text-align:left; }
.pt__evidence::after { border:none; }
.pt__missing { font-size:var(--font-size-xs);color:var(--warning-700); }
.pt__time,.pt__version { font-size:var(--font-size-xs);color:var(--text-tertiary); }
.pt__actions { display:flex;gap:var(--space-2);margin-top:var(--space-1); }
.pt__reject,.pt__approve { min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md); }
.pt__reject { border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600); }
.pt__approve { border:none;background:var(--teacher-600);color:#fff; }
.pt__reject::after,.pt__approve::after { border:none; }
.pt__reject[disabled],.pt__approve[disabled],.pt__evidence[disabled] { opacity:.55; }
</style>
