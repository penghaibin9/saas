<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习保险核验" subtitle="核对保单信息与原始凭证" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack">
        <view v-if="batches.length" class="card iv__batch">
          <view class="iv__batch-copy">
            <text class="iv__eyebrow">当前核验批次</text>
            <text class="iv__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
          </view>
          <picker class="iv__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="acting" @change="onBatch">
            <view class="iv__pick">切换批次 <text>▾</text></view>
          </picker>
        </view>

        <view v-if="batches.length" class="card iv__summary">
          <view class="iv__summary-main">
            <text class="iv__summary-label">待核验保险</text>
            <view class="iv__summary-number"><text>{{ list.length }}</text><text>条</text></view>
            <text class="iv__summary-note">{{ summaryConclusion }}</text>
          </view>
          <view class="iv__summary-metrics">
            <view class="iv__metric"><text>{{ completeFileCount }}</text><text>凭证齐全</text></view>
            <view class="iv__metric is-danger"><text>{{ missingFileCount }}</text><text>缺少凭证</text></view>
          </view>
        </view>

        <MobileInlineAlert type="info" description="先核对承保单位、保单号、保障期和原始凭证，再执行通过或驳回。学生重交后请刷新，以最新版本为准。" />
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前身份的数据范围内没有可核验批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="当前批次没有待核验保险" description="学生提交保险凭证后会出现在这里。" />

        <view v-for="item in list" :key="item.id" class="card iv">
          <view class="row-between iv__head">
            <view class="flex-1 iv__identity">
              <text class="t-md t-bold">{{ item.studentName || '—' }}</text>
              <text class="iv__sub">{{ item.studentNo || '' }} · {{ item.enterpriseName || '企业待落实' }}</text>
            </view>
            <MobileStatusTag :label="item.statusLabel" type="warning" />
          </view>

          <view class="iv__detail-box">
            <view class="iv__row"><text class="iv__row-k">承保单位</text><text class="iv__row-v">{{ item.insurerName || '—' }}</text></view>
            <view class="iv__row"><text class="iv__row-k">保单号</text><text class="iv__row-v iv__policy">{{ item.policyNo || '—' }}</text></view>
            <view class="iv__row"><text class="iv__row-k">保障期</text><text class="iv__row-v">{{ item.effectiveDate || '—' }} ~ {{ item.expiryDate || '—' }}</text></view>
          </view>

          <view class="iv__evidence" :class="{ 'is-missing': !item.hasFile }">
            <view class="iv__evidence-copy">
              <text class="iv__evidence-title">原始保险凭证</text>
              <text class="iv__evidence-text">{{ item.hasFile ? '已上传，可按保单信息进行核验。' : '尚未上传，当前记录禁止通过。' }}</text>
            </view>
            <MobileStatusTag :label="item.hasFile ? '已上传' : '缺失'" :type="item.hasFile ? 'success' : 'danger'" />
          </view>

          <view class="iv__meta"><text>记录版本 v{{ item.version }}</text><text>{{ item.hasFile ? '下一步：核对后审批' : '下一步：驳回补充凭证' }}</text></view>
          <view class="iv__actions">
            <button class="iv__reject flex-1" :disabled="acting" @click="verify(item, 'REJECT')">驳回补充</button>
            <button class="iv__approve flex-1" :disabled="acting || !item.hasFile" @click="verify(item, 'APPROVE')">核验通过</button>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { useInternshipContextStore } from '@/stores/internshipContext'
import { teacherInternshipInsurancePending, teacherInternshipInsuranceVerify } from '@/services/internshipApi'
import { toast } from '@/utils/nav'

export default {
  data() {
    return { list: [], state: 'loading', acting: false, batches: [], batchId: '', batchIndex: 0 }
  },
  computed: {
    batchLabels() { return this.batches.map((x) => `${x.name} · ${x.status} · ${x.studentCount}人`) },
    missingFileCount() { return this.list.filter((item) => !item.hasFile).length },
    completeFileCount() { return this.list.length - this.missingFileCount },
    summaryConclusion() {
      if (!this.list.length) return '当前没有需要核验的保险记录。'
      if (this.missingFileCount) return `优先处理 ${this.missingFileCount} 条缺少原始凭证的记录。`
      return '所有待办均已上传凭证，可逐条核对保单信息。'
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    async load(done) {
      this.state = 'loading'
      try {
        const context = useInternshipContextStore()
        context.restore()
        await context.load(true)
        this.batches = context.batches || []
        this.batchId = context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((x) => String(x.id) === String(this.batchId)))
        if (!this.batchId) this.list = []
        else {
          const data = await teacherInternshipInsurancePending(this.batchId)
          this.list = data?.list || data?.items || []
        }
        this.state = 'ready'
      } catch (e) {
        this.state = 'error'
      } finally { if (done) done() }
    },
    async onBatch(e) {
      this.batchIndex = Number(e.detail.value)
      const selected = this.batches[this.batchIndex]
      const context = useInternshipContextStore()
      context.selectBatch(selected?.id)
      this.batchId = context.selectedBatchId
      await this.load()
    },
    verify(item, action) {
      if (this.acting) return
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回保险' : '核验通过',
        editable: true,
        placeholderText: reject ? '请填写驳回原因（至少5字）' : '可填写核验备注',
        content: '',
        success: async (result) => {
          if (!result.confirm) return
          const comment = String(result.content || '').trim()
          if (reject && comment.length < 5) return toast('驳回原因至少5个字')
          this.acting = true
          try {
            await teacherInternshipInsuranceVerify(item.id, {
              action, comment, expectedVersion: item.version
            })
            toast(reject ? '已驳回' : '已核验通过')
            await this.load()
          } catch (e) {
            if (String(e?.code || '').includes('409') || e?.code === 'DATA_CONFLICT') {
              toast('记录已被其他人处理或学生已重交，正在刷新')
              await this.load()
            } else toast(e?.message || '核验失败，请重试')
          } finally { this.acting = false }
        }
      })
    }
  }
}
</script>

<style scoped>
.iv__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.iv__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.iv__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.iv__batch-name{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.iv__picker{flex-shrink:0}.iv__pick{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap}.iv__summary{display:flex;gap:var(--space-3);align-items:stretch;padding:var(--space-3)}.iv__summary-main{flex:1;min-width:0}.iv__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.iv__summary-number{display:flex;align-items:baseline;gap:4px;margin-top:4px}.iv__summary-number text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.iv__summary-number text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.iv__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.iv__summary-metrics{width:42%;display:grid;grid-template-columns:1fr 1fr;background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.iv__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 5px;border-left:1px solid var(--border-light)}.iv__metric:first-child{border-left:0}.iv__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--success-700)}.iv__metric.is-danger text:first-child{color:var(--danger-600)}.iv__metric text:last-child{font-size:10px;color:var(--text-tertiary)}.iv{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.iv__head{align-items:flex-start}.iv__identity{min-width:0}.iv__sub{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:3px;word-break:break-word}.iv__detail-box{display:flex;flex-direction:column;gap:8px;padding:var(--space-2) var(--space-3);background:var(--gray-50);border-radius:var(--radius-md)}.iv__row{display:flex;gap:var(--space-3);min-width:0}.iv__row-k{font-size:var(--font-size-xs);color:var(--text-tertiary);width:62px;flex-shrink:0}.iv__row-v{min-width:0;flex:1;font-size:var(--font-size-sm);line-height:1.5;color:var(--text-primary);word-break:break-word}.iv__policy{font-family:monospace}.iv__evidence{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-2) var(--space-3);border:1px solid var(--success-200,#bbf7d0);border-radius:var(--radius-md);background:var(--success-50)}.iv__evidence.is-missing{border-color:var(--danger-200,#fecaca);background:var(--danger-50)}.iv__evidence-copy{min-width:0}.iv__evidence-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.iv__evidence-text{display:block;margin-top:3px;font-size:var(--font-size-xs);line-height:1.45;color:var(--text-secondary)}.iv__meta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:5px 12px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.iv__actions{display:flex;gap:var(--space-2)}.iv__reject,.iv__approve{min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md)}.iv__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.iv__approve{border:none;background:var(--teacher-600);color:#fff}.iv__reject::after,.iv__approve::after{border:none}.iv__reject[disabled],.iv__approve[disabled]{opacity:.5}@media(max-width:360px){.iv__summary{flex-direction:column}.iv__summary-metrics{width:100%}.iv__batch{align-items:flex-start}}
</style>
