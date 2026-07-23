<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="实习求助" show-back />
    <view class="page-pad stack">
      <view class="card">
        <text class="card-title">向指导教师求助</text>
        <text class="hp__hint">用于岗位不适、安全隐患、沟通困难等。提交后进入实习风险台，由指导教师跟进。不替代就业去向登记，也不会伪造监管上报。</text>
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
import { toast, back } from '@/utils/nav'

const LEVELS = [
  { v: 'LOW', l: '一般' },
  { v: 'MEDIUM', l: '较急' },
  { v: 'HIGH', l: '紧急' }
]

export default {
  data() {
    return {
      levelIndex: 1, levelLabels: LEVELS.map((x) => x.l),
      form: { title: '', content: '' }, submitting: false
    }
  },
  methods: {
    onLevel(e) { this.levelIndex = Number(e.detail.value) || 0 },
    submit() {
      if (this.submitting) return
      if ((this.form.content || '').trim().length < 5) return toast('情况说明不少于 5 字')
      this.submitting = true
      studentApi.reportInternshipHelp({
        title: this.form.title,
        content: this.form.content,
        riskLevel: LEVELS[this.levelIndex].v
      }).then((d) => {
        toast((d && d.message) || '求助已提交')
        setTimeout(() => back(), 600)
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
</style>
