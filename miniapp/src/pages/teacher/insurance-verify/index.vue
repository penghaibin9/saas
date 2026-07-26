<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习保险核验" subtitle="显式批次 · 原始凭证 · 版本审核" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack">
        <view v-if="batches.length" class="card iv__batch">
          <text class="iv__row-k">实习批次</text>
          <picker class="flex-1" mode="selector" :range="batchLabels" :value="batchIndex" @change="onBatch">
            <view class="iv__pick">{{ batchLabels[batchIndex] || '请选择批次' }} <text>▾</text></view>
          </picker>
        </view>
        <MobileInlineAlert type="info" description="核验与学校管理PC使用同一权限、数据范围和版本控制。学生重交后旧页面不能继续审核，须刷新查看最新凭证。" />
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前身份的数据范围内没有可核验批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="暂无待核验保险" description="当前批次学生提交保险凭证后会出现在这里。" />
        <view v-for="item in list" :key="item.id" class="card iv">
          <view class="row-between">
            <view class="flex-1">
              <text class="t-md t-bold">{{ item.studentName || '—' }}</text>
              <text class="iv__sub">{{ item.studentNo || '' }} · {{ item.enterpriseName || '企业待落实' }}</text>
            </view>
            <MobileStatusTag :label="item.statusLabel" type="warning" />
          </view>
          <view class="iv__row"><text class="iv__row-k">承保单位</text><text class="flex-1 t-sm">{{ item.insurerName || '—' }}</text></view>
          <view class="iv__row"><text class="iv__row-k">保单号</text><text class="flex-1 t-sm">{{ item.policyNo || '—' }}</text></view>
          <view class="iv__row"><text class="iv__row-k">保障期</text><text class="flex-1 t-sm">{{ item.effectiveDate || '—' }} ~ {{ item.expiryDate || '—' }}</text></view>
          <view class="iv__row"><text class="iv__row-k">凭证</text><text class="flex-1 t-sm" :class="{ 'iv__danger': !item.hasFile }">{{ item.hasFile ? '已上传原始保险凭证' : '缺少保险凭证，禁止通过' }}</text></view>
          <text class="iv__version">记录版本 {{ item.version }}</text>
          <view class="iv__actions">
            <button class="iv__reject flex-1" :disabled="acting" @click="verify(item, 'REJECT')">驳回</button>
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
    batchLabels() { return this.batches.map((x) => `${x.name} · ${x.status} · ${x.studentCount}人`) }
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
.iv { display:flex;flex-direction:column;gap:var(--space-2); }
.iv__batch { display:flex;align-items:center;gap:var(--space-3);min-height:48px; }
.iv__pick { text-align:right;color:var(--text-primary);font-size:var(--font-size-base); }
.iv__sub { display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:2px; }
.iv__row { display:flex;gap:var(--space-3); }
.iv__row-k { font-size:var(--font-size-sm);color:var(--text-tertiary);width:72px;flex-shrink:0; }
.iv__danger { color:var(--danger-600); }
.iv__version { font-size:var(--font-size-xs);color:var(--text-tertiary); }
.iv__actions { display:flex;gap:var(--space-2);margin-top:var(--space-1); }
.iv__reject,.iv__approve { min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md); }
.iv__reject { border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600); }
.iv__approve { border:none;background:var(--teacher-600);color:#fff; }
.iv__reject::after,.iv__approve::after { border:none; }
</style>
