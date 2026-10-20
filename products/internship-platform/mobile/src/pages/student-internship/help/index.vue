<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="实习求助" show-back />
    <view class="page-pad stack">
      <view class="card">
        <text class="card-title">智能客服</text>
        <text class="hp__hint">先从岗位实习 FAQ 快速找答案。每次回答后由你判断是否解决；连续 3 次明确“没解决”，系统会自动携带最近对话转给指导教师。</text>
        <view class="hp__quick">
          <text v-for="item in quickQuestions" :key="item" class="hp__chip" @click="askQuick(item)">{{ item }}</text>
        </view>
      </view>

      <MobileInlineAlert v-if="support.status === 'TRANSFERRED'" type="success" title="已自动转人工"
        :description="`最近对话已交给指导教师，求助记录 #${support.transferredRiskId || '—'}，无需重复描述。`" />

      <view v-if="support.history.length" class="card stack">
        <text class="card-title">本次咨询</text>
        <view v-for="(item, index) in support.history" :key="index" class="hp__chat">
          <view class="hp__bubble hp__bubble--me"><text>{{ item.question }}</text></view>
          <view class="hp__bubble hp__bubble--bot"><text>{{ item.answer }}</text></view>
        </view>
        <view v-if="awaitingFeedback && support.status === 'ACTIVE'" class="hp__feedback">
          <text class="hp__hint">这个回答解决了吗？未解决累计 {{ support.unresolvedCount }}/3。</text>
          <view class="hp__feedback-actions">
            <button class="btn btn-ghost flex-1" :disabled="supporting" @click="markUnresolved">没解决</button>
            <button class="btn btn-primary flex-1" :disabled="supporting" @click="markSolved">已解决</button>
          </view>
        </view>
      </view>

      <view v-if="support.status !== 'TRANSFERRED'" class="card">
        <view class="hp__field">
          <text class="hp__label">继续提问</text>
          <textarea v-model="question" class="hp__textarea hp__textarea--ask" maxlength="500" placeholder="例如：为什么今天打卡提示定位异常？" />
        </view>
        <button class="btn btn-primary hp__ask" :disabled="supporting || awaitingFeedback" @click="askSupport">
          {{ supporting ? '处理中…' : (awaitingFeedback ? '请先确认上个回答' : '发送问题') }}
        </button>
        <text v-if="support.status === 'ACTIVE'" class="hp__counter">再有 {{ support.remainingBeforeHuman }} 次明确“没解决”将自动转人工。</text>
      </view>

      <view v-if="receipt" class="card hp__receipt">
        <text class="t-bold">✓ 求助已提交 · {{ receipt.statusLabel || receipt.status }}</text>
        <text>记录 #{{ receipt.id }}，指导教师将在风险处置台持续跟进。</text>
      </view>
      <view v-if="records.length" class="card stack">
        <text class="card-title">我的人工求助进度</text>
        <view v-for="item in records" :key="item.id" class="hp__record">
          <view class="row-between"><text class="t-bold">{{ item.title }}</text><MobileStatusTag :label="item.statusLabel" :type="item.status === 'CLOSED' ? 'success' : item.status === 'PROCESSING' ? 'info' : 'warning'" /></view>
          <text class="hp__hint">{{ item.latestFeedback || '已提交，等待指导教师受理。' }}</text>
          <text class="hp__time">更新于 {{ formatTime(item.updatedAt) }}</text>
        </view>
      </view>

      <view class="card stack">
        <view>
          <text class="card-title">直接人工求助</text>
          <text class="hp__hint">安全隐患、权益受损等紧急问题无需先走 FAQ，可直接提交给指导教师。</text>
        </view>
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
        <button class="btn btn-primary" :disabled="submitting" @click="submitManual">{{ submitting ? '提交中…' : '提交人工求助' }}</button>
      </view>
    </view>
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
      quickQuestions: ['打卡定位异常', '周报怎么提交', '请假要什么材料', '三方协议进度', '免实习怎么申请', '成绩有异议'],
      form: { title: '', content: '' }, submitting: false, supporting: false,
      question: '', awaitingFeedback: false,
      context: {}, records: [], receipt: null,
      support: { sessionId: '', status: 'NEW', unresolvedCount: 0, remainingBeforeHuman: 3, history: [], transferredRiskId: '' }
    }
  },
  onLoad(options = {}) { this.load(options.batchId) },
  methods: {
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '—' },
    async load(batchId = '') {
      try {
        const dashboard = await studentApi.getInternship(batchId)
        this.context = { batchId: dashboard?.batchId || '', internshipId: dashboard?.recordId || '' }
        const [help, support] = await Promise.all([
          studentApi.getInternshipHelp(this.context.batchId, this.context.internshipId),
          studentApi.getInternshipSupport(this.context.batchId, this.context.internshipId)
        ])
        this.records = help?.items || []
        this.support = { ...this.support, ...(support || {}), history: support?.history || [] }
        this.awaitingFeedback = false
      } catch (e) {
        toast(e?.message || '求助信息加载失败')
      }
    },
    askQuick(text) {
      if (this.supporting || this.awaitingFeedback || this.support.status === 'TRANSFERRED') return
      this.question = text
      this.askSupport()
    },
    async askSupport() {
      if (this.supporting || this.awaitingFeedback || this.support.status === 'TRANSFERRED') return
      const message = (this.question || '').trim()
      if (message.length < 2) return toast('请至少输入2个字的问题')
      this.supporting = true
      try {
        const result = await studentApi.askInternshipSupport({ ...this.context, message })
        this.support = { ...this.support, ...(result || {}), history: result?.history || this.support.history }
        this.question = ''
        this.awaitingFeedback = true
      } catch (e) {
        toast(e?.message || '智能客服暂时不可用')
      } finally {
        this.supporting = false
      }
    },
    async markSolved() {
      if (!this.support.sessionId || this.supporting || !this.awaitingFeedback) return
      this.supporting = true
      try {
        const result = await studentApi.solveInternshipSupport(this.support.sessionId, this.context)
        this.support = { ...this.support, ...(result || {}) }
        this.awaitingFeedback = false
        toast('已记录为解决')
      } catch (e) {
        toast(e?.message || '状态保存失败')
      } finally {
        this.supporting = false
      }
    },
    async markUnresolved() {
      if (!this.support.sessionId || this.supporting || !this.awaitingFeedback) return
      this.supporting = true
      try {
        const result = await studentApi.unresolvedInternshipSupport(this.support.sessionId, this.context)
        this.support = { ...this.support, ...(result || {}) }
        this.awaitingFeedback = false
        if (result?.transferred) {
          toast(result.message || '已自动转人工')
          await this.load(this.context.batchId)
        } else {
          toast(`已记录未解决（${result?.unresolvedCount || 0}/3），请继续补充问题`)
        }
      } catch (e) {
        toast(e?.message || '状态保存失败')
      } finally {
        this.supporting = false
      }
    },
    onLevel(e) { this.levelIndex = Number(e.detail.value) || 0 },
    submitManual() {
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
.hp__hint{display:block;margin-top:8px;font-size:var(--font-size-sm);color:var(--text-secondary);line-height:1.55}.hp__quick{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.hp__chip{padding:7px 10px;border-radius:999px;background:var(--brand-50);color:var(--brand-primary);font-size:var(--font-size-xs)}
.hp__chat{display:flex;flex-direction:column;gap:8px}.hp__bubble{max-width:88%;padding:10px 12px;border-radius:12px;font-size:var(--font-size-sm);line-height:1.6;white-space:pre-wrap;word-break:break-word}.hp__bubble--me{align-self:flex-end;background:var(--brand-primary);color:#fff}.hp__bubble--bot{align-self:flex-start;background:var(--gray-100);color:var(--text-primary)}
.hp__feedback{padding-top:4px}.hp__feedback-actions{display:flex;gap:10px;margin-top:10px}.hp__counter{display:block;margin-top:8px;font-size:var(--font-size-xs);color:var(--text-tertiary)}
.hp__field{margin-bottom:12px}.hp__label{display:block;font-size:var(--font-size-sm);color:var(--text-secondary);margin-bottom:6px}.hp__req{color:var(--danger-500)}.hp__input,.hp__picker,.hp__textarea{width:100%;border:1px solid var(--border-base);border-radius:var(--radius-sm);padding:10px 12px;font-size:var(--font-size-sm);box-sizing:border-box}.hp__textarea{min-height:120px}.hp__textarea--ask{min-height:78px}.hp__ask{width:100%;margin:0}
.hp__receipt{display:flex;flex-direction:column;gap:5px;border-color:var(--success-300,#86efac);background:var(--success-50,#f0fdf4);font-size:var(--font-size-xs);color:var(--success-800,#166534)}.hp__record{padding:10px 0;border-bottom:1px solid var(--border-light)}.hp__record:last-child{border-bottom:0}.hp__time{display:block;margin-top:5px;font-size:10px;color:var(--text-tertiary)}
</style>
