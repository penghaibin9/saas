<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="实习求助" show-back />
    <view class="page-pad stack">
      <view class="card">
        <text class="card-title">向指导教师求助</text>
        <text class="hp__hint">用于岗位不适、安全隐患、沟通困难等。提交后进入实习风险台，由指导教师跟进。不替代就业去向登记，也不会伪造监管上报。</text>
      </view>
      <view v-if="receipt" class="card hp__receipt">
        <text class="t-bold">✓ 求助已提交 · {{ receipt.statusLabel || receipt.status }}</text>
        <text>记录 #{{ receipt.id }}，指导教师将在风险处置台持续跟进。</text>
      </view>
      <view v-if="records.length" class="card stack">
        <text class="card-title">我的求助进度</text>
        <view v-for="item in records" :key="item.id" class="hp__record">
          <view class="row-between"><text class="t-bold">{{ item.title }}</text><MobileStatusTag :label="item.statusLabel" :type="item.status === 'CLOSED' ? 'success' : item.status === 'PROCESSING' ? 'info' : 'warning'" /></view>
          <text class="hp__hint">{{ item.latestFeedback || '已提交，等待指导教师受理。' }}</text>
          <text class="hp__time">更新于 {{ formatTime(item.updatedAt) }}</text>
        </view>
      </view>
      <view class="card stack">
        <view class="hp__field">
          <text class="hp__label">紧急程度</text>
          <picker mode="selector" :range="levelLabels" @change="onLevel">
            <view class="hp__picker">{{ levelLabels[levelIndex] }}</view>
          </picker>
        </view>
        <view class="hp__field">
          <text class="hp__label">标题</text>
          <input v-model="form.title" class="hp__input" maxlength="40" placeholder="可选，默认「学生实习求助」" />
        </view>
        <view class="hp__field">
          <text class="hp__label">情况说明 <text class="hp__req">*</text></text>
          <textarea v-model="form.content" class="hp__textarea" maxlength="500" placeholder="不少于 5 字，请客观描述现状与诉求" />
        </view>
      </view>
    </view>
    <MobileSafeAreaBar>
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '提交求助' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'

const LEVELS = [
  { v: 'LOW', l: '一般' },
  { v: 'MEDIUM', l: '较急' },
  { v: 'HIGH', l: '紧急' }
]

export default {
  data() {
    return {
      levelIndex: 1, levelLabels: LEVELS.map((x) => x.l),
      form: { title: '', content: '' }, submitting: false,
      context: {}, records: [], receipt: null
    }
  },
  onLoad(options = {}) { this.load(options.batchId) },
  methods: {
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '—' },
    async load(batchId = '') {
      try {
        const dashboard = await studentApi.getInternship(batchId)
        this.context = { batchId: dashboard?.batchId || '', internshipId: dashboard?.recordId || '' }
        const data = await studentApi.getInternshipHelp(this.context.batchId, this.context.internshipId)
        this.records = data?.items || []
      } catch (e) {
        toast(e?.message || '求助进度加载失败')
      }
    },
    onLevel(e) { this.levelIndex = Number(e.detail.value) || 0 },
    submit() {
      if (this.submitting) return
      if ((this.form.content || '').trim().length < 5) return toast('情况说明不少于 5 字')
      this.submitting = true
      studentApi.reportInternshipHelp({
        ...this.context,
        title: this.form.title,
        content: this.form.content,
        riskLevel: LEVELS[this.levelIndex].v
      }).then((d) => {
        this.receipt = d || null
        toast((d && d.message) || '求助已提交')
        this.form = { title: '', content: '' }
        this.load(this.context.batchId)
      }).catch((e) => toast((e && e.message) || '提交失败'))
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.hp__hint { display: block; margin-top: 8px; font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.5; }
.hp__field { margin-bottom: 12px; }
.hp__label { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-bottom: 6px; }
.hp__req { color: var(--danger-500); }
.hp__input, .hp__picker, .hp__textarea {
  width: 100%; border: 1px solid var(--border-base); border-radius: var(--radius-sm);
  padding: 10px 12px; font-size: var(--font-size-sm); box-sizing: border-box;
}
.hp__textarea { min-height: 120px; }
.hp__receipt{display:flex;flex-direction:column;gap:5px;border-color:var(--success-300,#86efac);background:var(--success-50,#f0fdf4);font-size:var(--font-size-xs);color:var(--success-800,#166534)}
.hp__record{padding:10px 0;border-bottom:1px solid var(--border-light)}.hp__record:last-child{border-bottom:0}.hp__time{display:block;margin-top:5px;font-size:10px;color:var(--text-tertiary)}
</style>
