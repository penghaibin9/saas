<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习申请审核" subtitle="按批次审核正式实习申请" show-back />

    <view class="page-pad">
      <view class="card ap__batch" v-if="batches.length">
        <text class="ap__label">实习批次</text>
        <picker class="ap__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="!!actingId" @change="onBatch">
          <view class="ap__pick-val">{{ batchLabels[batchIndex] || '请选择批次' }}<text class="ap__arrow">▾</text></view>
        </picker>
      </view>
      <MobileInlineAlert type="warning" description="通过后会在同一事务内落实岗位或自主实习去向。请核对企业、岗位、联系人、证明材料及学生记录版本后再操作。" />
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可审核的岗位实习批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="暂无待审申请"
          description="当前批次学生提交正式实习申请后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="a in list" :key="a.id" class="card ap">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ a.studentName || '—' }}</text>
                <text class="ap__sub">{{ a.studentNo || '' }} · {{ a.applicationTypeLabel }}</text>
              </view>
              <MobileStatusTag :label="a.statusLabel" type="warning" />
            </view>
            <view class="ap__row"><text class="ap__row-k">企业/岗位</text><text class="flex-1 t-sm">{{ a.companyName || '—' }} · {{ a.positionName || '—' }}</text></view>
            <view class="ap__row" v-if="a.workAddress"><text class="ap__row-k">工作地点</text><text class="flex-1 t-sm">{{ a.workAddress }}</text></view>
            <view class="ap__row" v-if="a.contactName"><text class="ap__row-k">联系人</text><text class="flex-1 t-sm">{{ a.contactName }} {{ a.contactPhone || '' }}</text></view>
            <view class="ap__row" v-if="a.applicationNote"><text class="ap__row-k">申请说明</text><text class="flex-1 t-sm">{{ a.applicationNote }}</text></view>

            <button v-if="a.evidenceFileId" class="ap__evidence" :disabled="previewingId === a.id" @click="previewEvidence(a)">
              {{ previewingId === a.id ? '正在打开证明材料…' : '查看自主实习证明材料' }}
            </button>
            <view v-else-if="a.applicationType === 'SELF_ARRANGED'" class="ap__danger">自主实习申请缺少证明材料，不能通过</view>

            <view class="ap__row"><text class="ap__row-k">申请版本</text><text class="flex-1 t-sm">v{{ a.version }}</text></view>
            <view class="ap__row"><text class="ap__row-k">学生记录</text><text class="flex-1 t-sm">{{ a.recordVersion == null ? '版本缺失，请刷新' : `v${a.recordVersion}` }}</text></view>
            <text class="ap__time" v-if="a.submittedAt">提交于 {{ fmt(a.submittedAt) }}</text>

            <view class="ap__actions" v-if="canReview">
              <button class="ap__reject flex-1" :disabled="actingId === a.id" @click="review(a, 'REJECT')">驳回修改</button>
              <button class="ap__approve flex-1" :disabled="actingId === a.id || !canApprove(a)" @click="review(a, 'APPROVE')">{{ approveLabel(a) }}</button>
            </view>
            <MobileInlineAlert v-else type="warning" description="当前身份仅可查看，无正式实习申请审核权限。" />
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherInternshipApplications, teacherInternshipApplicationReview } from '@/services/internshipApi'
import { openBusinessFile } from '@/services/fileApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'

export default {
  data() {
    return { list: null, state: 'loading', actingId: '', previewingId: '', batches: [], batchId: '', batchIndex: 0 }
  },
  computed: {
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) },
    canReview() { return useInternshipContextStore().can('internship.application.review') }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    fmt(value) { return value ? String(value).slice(0, 16).replace('T', ' ') : '—' },
    approveLabel(a) { return a.applicationType === 'SELF_ARRANGED' ? '通过并确认自主实习' : '通过并落实岗位' },
    canApprove(a) {
      const evidenceOk = a.applicationType !== 'SELF_ARRANGED' || !!a.evidenceFileId
      return evidenceOk && a.recordVersion != null && a.version != null
    },
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
        const data = await teacherInternshipApplications(this.batchId)
        this.list = (data && data.list) || []
        this.state = 'ready'
      } catch (e) {
        this.list = []
        this.state = 'error'
        toast((e && e.message) || '实习申请加载失败')
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
      catch (e) { toast((e && e.message) || '证明材料打开失败') }
      finally { this.previewingId = '' }
    },
    review(a, action) {
      if (!this.canReview || this.actingId) return
      if (action === 'APPROVE' && !this.canApprove(a)) {
        toast(a.applicationType === 'SELF_ARRANGED' && !a.evidenceFileId
          ? '自主实习证明材料缺失，不能通过'
          : '申请或学生记录版本缺失，请刷新后再试')
        return
      }
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回申请' : this.approveLabel(a),
        editable: true,
        placeholderText: reject ? '请填写具体驳回原因（至少5字）' : '可填写审核意见',
        content: '',
        success: async (r) => {
          if (!r.confirm) return
          const comment = (r.content || '').trim()
          if (reject && comment.length < 5) { toast('驳回原因至少5个字'); return }
          this.actingId = a.id
          try {
            await teacherInternshipApplicationReview(a.id, {
              action,
              comment,
              expectedVersion: a.version,
              recordExpectedVersion: a.recordVersion,
              batchId: this.batchId
            })
            toast(reject ? '已驳回学生修改' : (a.applicationType === 'SELF_ARRANGED' ? '已确认自主实习去向' : '已通过并落实岗位'))
            await this.load()
          } catch (e) {
            if (String(e && e.code) === 'DATA_CONFLICT') {
              toast((e && e.message) || '申请或学生记录已变化，正在刷新')
              await this.load()
            } else toast((e && e.message) || '申请审核失败，请重试')
          } finally { this.actingId = '' }
        }
      })
    }
  }
}
</script>

<style scoped>
.ap__batch { display:flex;align-items:center;min-height:48px;margin-bottom:var(--space-3);padding:0 var(--space-3); }
.ap__label { width:88px;flex-shrink:0;font-size:var(--font-size-base);color:var(--text-secondary); }
.ap__picker { flex:1; }
.ap__pick-val { text-align:right;color:var(--text-primary);font-size:var(--font-size-base); }
.ap__arrow { margin-left:4px;color:var(--text-tertiary); }
.ap { display:flex;flex-direction:column;gap:var(--space-2); }
.ap__sub { display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:2px; }
.ap__row { display:flex;gap:var(--space-3); }
.ap__row-k { font-size:var(--font-size-sm);color:var(--text-tertiary);width:68px;flex-shrink:0; }
.ap__evidence { min-height:40px;padding:0 var(--space-3);border:1px solid var(--success-500);border-radius:var(--radius-md);background:var(--success-50);color:var(--success-700);font-size:var(--font-size-sm);text-align:left; }
.ap__evidence::after { border:none; }
.ap__danger { padding:var(--space-2);border-radius:var(--radius-md);background:var(--danger-50);color:var(--danger-600);font-size:var(--font-size-xs); }
.ap__time { font-size:var(--font-size-xs);color:var(--text-tertiary); }
.ap__actions { display:flex;gap:var(--space-2);margin-top:var(--space-1); }
.ap__reject,.ap__approve { min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md); }
.ap__reject { border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600); }
.ap__approve { border:none;background:var(--teacher-600);color:#fff; }
.ap__approve[disabled],.ap__reject[disabled],.ap__evidence[disabled] { opacity:.45; }
.ap__reject::after,.ap__approve::after { border:none; }
</style>
