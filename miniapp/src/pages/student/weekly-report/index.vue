<template>
  <view class="page-wrap wr">
    <view class="page-pad">
      <view class="wr__head card">
        <view class="row-between">
          <text class="card-title">{{ week }} 实习周报</text>
          <MobileStatusTag label="填写中" type="processing" />
        </view>
        <text class="wr__meta">{{ company }} · {{ post }}</text>
      </view>

      <view class="card wr__form">
        <view class="wr__field">
          <text class="wr__label">本周工作内容 <text class="wr__req">*</text></text>
          <textarea class="wr__textarea" v-model="tasks" :maxlength="500" placeholder="描述本周完成的主要任务" placeholder-class="wr__ph" />
        </view>
        <view class="wr__field">
          <text class="wr__label">本周收获 <text class="wr__req">*</text></text>
          <textarea class="wr__textarea" v-model="gain" :maxlength="500" placeholder="学到的技能、经验与体会" placeholder-class="wr__ph" />
        </view>
        <view class="wr__field">
          <text class="wr__label">存在问题 / 下周计划</text>
          <textarea class="wr__textarea" v-model="problem" :maxlength="500" placeholder="遇到的问题及下周安排（可选）" placeholder-class="wr__ph" />
        </view>
        <view class="wr__field wr__field--row">
          <text class="wr__label">本周工时</text>
          <input class="wr__input" v-model="hours" type="number" placeholder="如 40" placeholder-class="wr__ph" />
          <text class="wr__unit">小时</text>
        </view>
      </view>

      <MobileInlineAlert type="info" description="周报提交后由校内指导教师批阅；逾期未交会计入实习考核。" />
    </view>

    <MobileSafeAreaBar>
      <button class="btn btn-ghost flex-1" @click="saveDraft">存草稿</button>
      <button class="btn btn-primary flex-1" @click="submit">提交周报</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { useSubmissionsStore } from '@/stores/submissions'
import { toast, back } from '@/utils/nav'

export default {
  data() {
    return {
      week: '本周', company: '', post: '',
      tasks: '', gain: '', problem: '', hours: ''
    }
  },
  onLoad(q) {
    if (q && q.week) this.week = decodeURIComponent(q.week)
    if (q && q.company) this.company = decodeURIComponent(q.company)
    if (q && q.post) this.post = decodeURIComponent(q.post)
  },
  methods: {
    saveDraft() { toast('已存草稿（演示）') },
    submit() {
      if (!this.tasks.trim() || !this.gain.trim()) {
        toast('请填写本周工作内容与收获')
        return
      }
      useSubmissionsStore().addWeeklyReport({
        week: this.week, company: this.company, post: this.post,
        tasks: this.tasks.trim(), gain: this.gain.trim(), problem: this.problem.trim(), hours: this.hours
      })
      uni.showToast({ title: '周报已提交', icon: 'success' })
      setTimeout(() => back(), 700)
    }
  }
}
</script>

<style scoped>
.wr__meta { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 4px; }
.wr__form { margin-top: var(--card-gap-mobile); }
.wr__field { padding: var(--space-3) 0; border-bottom: 1px solid var(--border-light); }
.wr__field:last-child { border-bottom: none; }
.wr__field--row { display: flex; align-items: center; gap: var(--space-2); }
.wr__label { display: block; font-size: var(--font-size-base); color: var(--text-secondary); margin-bottom: var(--space-2); }
.wr__field--row .wr__label { margin-bottom: 0; width: 80px; flex-shrink: 0; }
.wr__req { color: var(--danger-500); }
.wr__textarea { width: 100%; min-height: 80px; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; }
.wr__input { flex: 1; height: 40px; font-size: var(--font-size-base); color: var(--text-primary); }
.wr__unit { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.wr__ph { color: var(--text-tertiary); }
</style>
