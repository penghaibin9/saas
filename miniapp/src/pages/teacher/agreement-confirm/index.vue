<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="三方协议办理进度" subtitle="指导教师查看进度 · 学校终审在管理端完成" show-back />

    <view class="page-pad">
      <view class="card ac__batch" v-if="batches.length">
        <text class="ac__label">实习批次</text>
        <picker class="ac__picker" mode="selector" :range="batchLabels" :value="batchIndex" @change="onBatch">
          <view class="ac__pick-val">{{ batchLabels[batchIndex] || '请选择批次' }}<text class="ac__arrow">▾</text></view>
        </picker>
      </view>
      <MobileInlineAlert type="info" description="指导教师负责跟进学生与企业材料，学校确认生效属于终审动作，仅在学校管理端办理。此页只显示当前批次待终审协议。" />
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可查看的岗位实习批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="暂无待学校确认协议"
          description="当前批次学生与企业完成确认并上传签署扫描件后，会进入学校终审队列。" />
        <view class="stack" v-else>
          <view v-for="a in list" :key="a.id" class="card ac">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ a.studentName || '—' }}</text>
                <text class="ac__sub">{{ a.studentNo || '' }} · {{ a.enterpriseName || '—' }} · {{ a.positionName || '—' }}</text>
              </view>
              <MobileStatusTag label="待学校终审" type="warning" />
            </view>
            <view class="ac__confirms">
              <text class="ac__confirm-item">学生 {{ a.studentConfirmLabel || '待确认' }}</text>
              <text class="ac__confirm-item">企业 {{ a.enterpriseConfirmLabel || '待确认' }}</text>
              <text class="ac__confirm-item" :class="{ 'ac__confirm-warn': !a.hasFile }">{{ a.hasFile ? '已上传签署扫描件' : '未上传扫描件' }}</text>
            </view>
            <view class="ac__source">
              <text>证据来源：{{ a.sourceLabel || '历史来源未知' }}</text>
              <text>协议版本：{{ a.version }}</text>
            </view>
            <text class="ac__hint">{{ a.hasFile ? '材料已进入学校管理端终审队列' : '请提醒补齐企业签署扫描件后再送学校终审' }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherInternshipAgreements } from '@/services/internshipApi'
import { useInternshipContextStore } from '@/stores/internshipContext'

export default {
  data() {
    return { list: null, state: 'loading', batches: [], batchId: '', batchIndex: 0 }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) }
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
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) { this.list = []; this.state = 'ready'; return }
        const data = await teacherInternshipAgreements(this.batchId)
        this.list = (data && data.list) || []
        this.state = 'ready'
      } catch (e) {
        this.list = []
        this.state = 'error'
      } finally { if (done) done() }
    },
    async onBatch(e) {
      this.batchIndex = Number(e.detail.value)
      const batch = this.batches[this.batchIndex]
      const context = useInternshipContextStore()
      context.selectBatch(batch && batch.id)
      this.batchId = context.selectedBatchId
      await this.load()
    }
  }
}
</script>

<style scoped>
.ac__batch { display:flex;align-items:center;min-height:48px;margin-bottom:var(--space-3);padding:0 var(--space-3); }
.ac__label { width:88px;flex-shrink:0;font-size:var(--font-size-base);color:var(--text-secondary); }
.ac__picker { flex:1; }
.ac__pick-val { text-align:right;color:var(--text-primary);font-size:var(--font-size-base); }
.ac__arrow { margin-left:4px;color:var(--text-tertiary); }
.ac { display:flex;flex-direction:column;gap:var(--space-2); }
.ac__sub { display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:2px; }
.ac__confirms { display:flex;flex-wrap:wrap;gap:var(--space-3);background:var(--gray-50);border-radius:var(--radius-md);padding:var(--space-2) var(--space-3); }
.ac__confirm-item { font-size:var(--font-size-xs);color:var(--text-secondary); }
.ac__confirm-warn { color:var(--danger-600); }
.ac__source { display:flex;justify-content:space-between;gap:12px;font-size:var(--font-size-xs);color:var(--text-tertiary); }
.ac__hint { font-size:var(--font-size-xs);color:var(--text-tertiary); }
</style>
