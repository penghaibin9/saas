<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="成绩认定/课程替代" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="section-head">
          <text class="section-head__title">我的认定申请</text>
          <text class="section-head__more" @click="showForm = !showForm">{{ showForm ? '收起' : '+ 新增申请' }}</text>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <text class="rg__group">校外/原修课程</text>
          <input class="rg__input" v-model="form.sourceCourseName" placeholder="原课程名称（必填）" placeholder-class="rg__ph" />
          <view class="rg__row">
            <input class="rg__input rg__half" type="number" v-model="form.sourceScore" placeholder="原成绩（≥60）" placeholder-class="rg__ph" />
            <input class="rg__input rg__half" type="digit" v-model="form.sourceCredit" placeholder="原学分" placeholder-class="rg__ph" />
          </view>
          <input class="rg__input" v-model="form.sourceOrigin" placeholder="来源说明（原专业/原学校/证书折算）" placeholder-class="rg__ph" />
          <text class="rg__group">替代的校内计划课程</text>
          <input class="rg__input" v-model="form.targetCourseName" placeholder="目标课程名称（必填，需与培养计划一致）" placeholder-class="rg__ph" />
          <textarea class="rg__textarea" v-model="form.reason" :maxlength="200" placeholder="申请理由（选填）" placeholder-class="rg__ph" />
          <button class="btn btn-primary" :disabled="!canSubmit || submitting" @click="submit">
            {{ submitting ? '提交中…' : '提交认定申请' }}
          </button>
        </view>

        <view class="list-group" v-if="d.items && d.items.length">
          <view v-for="r in d.items" :key="r.recognitionId" class="list-row rg__item">
            <view class="flex-1">
              <text class="t-md">{{ r.sourceCourseName }} → {{ r.targetCourseName }}</text>
              <text class="rg__sub">{{ r.sourceScore }} 分 · {{ r.sourceCredit != null ? r.sourceCredit + ' 学分' : '学分未填' }} · {{ r.sourceOrigin || '来源未注明' }}</text>
              <text v-if="r.reviewReason && r.status === 'REJECTED'" class="rg__reason">{{ r.reviewReason }}</text>
            </view>
            <MobileStatusTag :status="r.status" />
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无认定申请" description="点击右上角新增申请，用已修课程替代培养计划课程。" />
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)

export default {
  data() {
    return {
      d: null, state: 'loading', showForm: false, submitting: false,
      form: { sourceCourseName: '', sourceScore: '', sourceCredit: '', sourceOrigin: '', targetCourseName: '', reason: '' }
    }
  },
  computed: {
    canSubmit() {
      const s = Number(this.form.sourceScore)
      return this.form.sourceCourseName.trim() && this.form.targetCourseName.trim() && s >= 60 && s <= 100
    }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getMyRecognition().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    submit() {
      if (!this.canSubmit || this.submitting) return
      this.submitting = true
      const body = {
        sourceCourseName: this.form.sourceCourseName.trim(),
        sourceScore: Number(this.form.sourceScore),
        sourceCredit: this.form.sourceCredit ? Number(this.form.sourceCredit) : undefined,
        sourceOrigin: this.form.sourceOrigin.trim() || undefined,
        targetCourseName: this.form.targetCourseName.trim(),
        reason: this.form.reason.trim() || undefined
      }
      submitLock.run(() => studentApi.submitRecognition(body))
        .then(() => {
          uni.showToast({ title: '认定申请已提交', icon: 'success' })
          this.showForm = false
          this.form = { sourceCourseName: '', sourceScore: '', sourceCredit: '', sourceOrigin: '', targetCourseName: '', reason: '' }
          this.load()
        }).catch((e) => {
          if (e && e.code === 'LOCKED') return
          toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试')
        }).finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.rg__group { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); font-weight: 600; margin-top: var(--space-1); }
.rg__input { width: 100%; height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.rg__row { display: flex; gap: var(--space-2); }
.rg__half { flex: 1; }
.rg__textarea { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; }
.rg__ph { color: var(--text-tertiary); }
.rg__item { align-items: flex-start; }
.rg__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.rg__reason { display: block; font-size: var(--font-size-xs); color: var(--danger-600); margin-top: 4px; }
</style>
