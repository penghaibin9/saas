<template>
  <view class="page-wrap">
    <MobileNavBar title="辅导员考评" subtitle="查看评分、发布结果与申诉进度" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack">
        <view class="card stack">
          <input v-model.trim="period" class="input" placeholder="按考评周期查询" maxlength="50" />
          <view class="ce-actions"><button class="btn btn-secondary" :disabled="busy" @click="search">查询</button><button v-if="capabilities.canScore" class="btn btn-primary" :disabled="busy" @click="edit()">录入评分</button></view>
          <text class="hint">评分指标与电脑端一致，按当前职责和授权范围办理。</text>
        </view>
        <view v-if="!items.length" class="card hint">当前范围内暂无符合条件的考评记录。</view>
        <view v-for="item in items" :key="item.evalId" class="card stack">
          <view class="ce-actions"><strong>{{ item.counselorName || '历史辅导员' }}</strong><text>{{ item.statusLabel }}</text></view>
          <text>{{ item.periodCode }}</text><text>总分：{{ item.totalScore == null ? '尚未评分' : item.totalScore }}</text>
          <text v-if="item.weightedTotalScore != null">加权总分：{{ item.weightedTotalScore }}</text>
          <view v-for="indicator in indicators" :key="indicator.indicatorId" class="ce-score"><text>{{ indicator.name }}</text><text>{{ item.scores?.[indicator.indicatorId] ?? '未评分' }}</text></view>
          <text v-if="item.appealReason">申诉：{{ item.appealReason }}</text><text v-if="item.appealOpinion">复核意见：{{ item.appealOpinion }}</text>
          <text v-if="item.appealStatus !== 'NONE'">{{ item.appealStatusLabel }}</text>
          <text v-if="item.reviewBlockReason" class="hint">{{ item.reviewBlockReason }}</text>
          <view class="ce-actions">
            <button v-if="allows(item, 'SCORE')" class="btn btn-secondary" :disabled="busy" @click="edit(item)">修改评分</button>
            <button v-if="allows(item, 'PUBLISH')" class="btn btn-primary" :disabled="busy" @click="publish(item)">发布结果</button>
            <button v-if="allows(item, 'APPEAL')" class="btn btn-secondary" :disabled="busy" @click="openText(item, 'APPEAL')">本人申诉</button>
            <button v-if="allows(item, 'REVIEW')" class="btn btn-primary" :disabled="busy" @click="openText(item, 'REVIEW')">复核申诉</button>
          </view>
        </view>
        <button v-if="items.length < total" class="btn btn-secondary" :disabled="busy" @click="load(true)">加载更多</button>
        <text v-if="listError" class="ce-error">{{ listError }}</text>
      </view>
    </MobileGlobalState>
    <view v-if="form" class="ce-mask"><view class="card ce-sheet stack">
      <strong>{{ mode === 'SCORE' ? '录入评分' : mode === 'APPEAL' ? '本人考评申诉' : '复核考评申诉' }}</strong>
      <template v-if="mode === 'SCORE'">
        <input v-model.trim="form.periodCode" class="input" placeholder="考评周期" :disabled="!!target || busy" maxlength="50" />
        <input v-model.trim="form.counselorKey" class="input" placeholder="辅导员工号或登录名" :disabled="!!target || busy" maxlength="100" />
        <text v-if="!indicators.length" class="hint">尚未配置指标，请先由学校在电脑端配置。</text>
        <label v-for="indicator in indicators" :key="indicator.indicatorId" class="stack"><text>{{ indicator.name }}（满分{{ indicator.maxScore }}）</text><input v-model="form.scores[indicator.indicatorId]" class="input" type="digit" :disabled="busy" /></label>
      </template>
      <template v-else>
        <view v-if="mode === 'REVIEW'" class="ce-actions"><button class="btn btn-secondary" :disabled="busy" @click="form.result = 'UPHELD'">{{ form.result === 'UPHELD' ? '已选：' : '' }}维持结果</button><button class="btn btn-secondary" :disabled="busy" @click="form.result = 'ADJUSTED'">{{ form.result === 'ADJUSTED' ? '已选：' : '' }}调整结果</button></view>
        <template v-if="mode === 'REVIEW' && form.result === 'ADJUSTED'"><label v-for="indicator in indicators" :key="indicator.indicatorId" class="stack"><text>{{ indicator.name }}</text><input v-model="form.scores[indicator.indicatorId]" class="input" type="digit" :disabled="busy" /></label></template>
        <textarea v-model.trim="form.reason" class="textarea" placeholder="填写原因或复核意见，至少5个字" maxlength="500" :disabled="busy" />
      </template>
      <text v-if="actionError" class="ce-error">{{ actionError }}</text>
      <view class="ce-actions"><button class="btn btn-secondary" :disabled="busy" @click="form = null">取消</button><button class="btn btn-primary" :disabled="busy" @click="submit">{{ busy ? '提交中…' : '确认提交' }}</button></view>
    </view></view>
  </view>
</template>
<script>
import { affairsContractApi as api } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { toast } from '@/utils/nav'
export default {
  data: () => ({ state: 'loading', items: [], indicators: [], capabilities: {}, total: 0, page: 1, period: '', appliedPeriod: '', busy: false, requestSeq: 0, generation: null, listError: '', actionError: '', form: null, target: null, mode: '' }),
  onShow() { this.load() }, onHide() { this.requestSeq++ }, onUnload() { this.requestSeq++ },
  onPullDownRefresh() { this.load().finally(() => uni.stopPullDownRefresh()) },
  onBackPress() { if (this.form) { if (!this.busy) this.form = null; return true } return false },
  methods: {
    allows(item, action) { return (item.allowedActions || []).includes(action) },
    search() { this.appliedPeriod = this.period; return this.load() },
    async load(more = false) {
      more = more === true
      const seq = ++this.requestSeq, generation = currentSessionGeneration()
      if (this.generation !== generation) { this.form = null; this.items = []; this.capabilities = {}; this.appliedPeriod = ''; this.period = ''; this.generation = generation }
      const page = more ? this.page + 1 : 1
      if (!more) this.state = 'loading'
      this.listError = ''
      try {
        const [data, indicators] = await Promise.all([api.getCounselorEvals({ periodCode: this.appliedPeriod, page, pageSize: 20 }), api.getEvalIndicators()])
        if (seq !== this.requestSeq || generation !== currentSessionGeneration()) return
        this.items = more ? [...new Map([...this.items, ...data.items].map(row => [row.evalId, row])).values()] : data.items
        this.indicators = indicators.items || []; this.capabilities = data.capabilities || {}; this.total = data.total; this.page = page; this.state = 'ready'
      } catch (e) { if (seq === this.requestSeq) { this.listError = normalizeError(e).text || '加载失败，请重试'; if (!more) this.state = normalizeError(e).pageState || 'error' } }
    },
    edit(item = null) { this.target = item; this.mode = 'SCORE'; this.actionError = ''; this.form = { periodCode: item?.periodCode || this.appliedPeriod, counselorKey: item?.counselorKey || '', scores: { ...(item?.scores || {}) }, remark: item?.remark || '', version: item?.version } },
    openText(item, mode) { this.target = item; this.mode = mode; this.actionError = ''; this.form = { reason: '', result: 'UPHELD', scores: { ...item.scores } } },
    numericScores() { const scores = { ...this.form.scores }; for (const indicator of this.indicators) { const value = this.form.scores[indicator.indicatorId]; if (value === '' || value == null) { delete scores[indicator.indicatorId]; continue } const score = Number(value); if (!Number.isFinite(score) || score < 0 || score > indicator.maxScore) throw new Error('请核对各指标分值及满分'); scores[indicator.indicatorId] = score } return scores },
    async submit() {
      if (this.busy || !this.form) return
      this.actionError = ''
      try {
        let run
        if (this.mode === 'SCORE') { if (!this.form.periodCode || !this.form.counselorKey || !this.indicators.length) throw new Error('请填写周期、辅导员工号，并核对评分指标'); const data = { ...this.form, scores: this.numericScores() }; run = () => api.saveCounselorEval(data) }
        else { if (this.form.reason.length < 5) throw new Error('请填写至少5个字的原因或意见'); run = this.mode === 'APPEAL' ? () => api.appealCounselorEval(this.target.evalId, this.form.reason, this.target.version) : () => api.reviewCounselorEval(this.target.evalId, { result: this.form.result, opinion: this.form.reason, scores: this.form.result === 'ADJUSTED' ? this.numericScores() : undefined, version: this.target.version }) }
        await this.run(run)
      } catch (e) { this.actionError = normalizeError(e).text || e.message || '提交失败，填写内容已保留' }
    },
    async run(action) { this.busy = true; const generation = currentSessionGeneration(); try { await action(); if (generation !== currentSessionGeneration()) return; this.form = null; toast('已保存，请核对最新进度'); await this.load() } finally { this.busy = false } },
    publish(item) { uni.showModal({ title: '确认发布考评？', content: '发布后不能直接修改评分，请核对当前结果。', success: async result => { if (!result.confirm || this.busy) return; try { await this.run(() => api.publishCounselorEval(item.evalId, item.version)) } catch (e) { toast(normalizeError(e).text || '发布失败，请刷新核对') } } }) }
  }
}
</script>
<style scoped>
.ce-actions,.ce-score{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}.ce-actions .btn{margin:0;font-size:14px}.ce-error{color:#b42318;line-height:1.6}.ce-mask{position:fixed;inset:0;z-index:1000;background:rgba(15,23,42,.5);display:flex;align-items:flex-end}.ce-sheet{box-sizing:border-box;width:100%;max-height:90vh;overflow:auto;padding:20px}.ce-score{font-size:14px;color:var(--text-secondary)}
</style>
