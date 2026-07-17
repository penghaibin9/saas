<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="工作量申报" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="section-head">
          <text class="section-head__title">我的工作量申报</text>
          <text class="section-head__more" @click="showForm = !showForm">{{ showForm ? '收起' : '+ 新增申报' }}</text>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <text class="wl__group">工作量类别</text>
          <picker mode="selector" :range="categoryLabels" @change="onCatChange">
            <view class="wl__input wl__picker">{{ categoryLabels[catIndex] }}</view>
          </picker>
          <view class="wl__row">
            <input class="wl__input wl__half" type="digit" v-model="form.hours" placeholder="申报课时（必填）" placeholder-class="wl__ph" />
            <input class="wl__input wl__half" v-model="form.termCode" placeholder="学期（选填）" placeholder-class="wl__ph" />
          </view>
          <textarea class="wl__textarea" v-model="form.description" :maxlength="200"
                    placeholder="工作说明（如：期末监考3场/批阅高数试卷）" placeholder-class="wl__ph" />
          <button class="btn btn-primary" :disabled="!canSubmit || submitting" @click="submit">
            {{ submitting ? '提交中…' : '提交申报' }}
          </button>
          <text class="wl__tip">申报经教务处审核通过后计入工作量统计（仅供教务参考，非薪酬核算）。</text>
        </view>

        <view class="list-group" v-if="d.items && d.items.length">
          <view v-for="r in d.items" :key="r.declarationId" class="list-row wl__item">
            <view class="flex-1">
              <text class="t-md">{{ r.categoryLabel }} · {{ r.hours }} 课时<text v-if="r.termCode"> · {{ r.termCode }}</text></text>
              <text class="wl__sub">{{ r.description || '无说明' }}</text>
              <text v-if="r.reviewNote" class="wl__note">审核意见：{{ r.reviewNote }}</text>
            </view>
            <MobileStatusTag :status="r.status" />
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无申报" description="点击右上角新增，申报教学/监考/阅卷等工作量。" />
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)
const CATS = [
  { value: 'TEACHING', label: '教学' }, { value: 'INVIGILATE', label: '监考' },
  { value: 'MARKING', label: '阅卷' }, { value: 'PAPER', label: '出卷' }, { value: 'OTHER', label: '其他' }
]

export default {
  data() {
    return { d: null, state: 'loading', showForm: false, submitting: false, catIndex: 0,
      form: { hours: '', termCode: '', description: '' } }
  },
  computed: {
    categoryLabels() { return CATS.map((c) => c.label) },
    canSubmit() { return Number(this.form.hours) > 0 }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      teacherApi.getWorkloadDeclarations().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    onCatChange(e) { this.catIndex = Number(e.detail.value) },
    submit() {
      if (!this.canSubmit || this.submitting) return
      this.submitting = true
      const body = {
        category: CATS[this.catIndex].value,
        hours: Number(this.form.hours),
        termCode: this.form.termCode.trim() || undefined,
        description: this.form.description.trim() || undefined
      }
      submitLock.run(() => teacherApi.submitWorkload(body))
        .then(() => {
          uni.showToast({ title: '申报已提交', icon: 'success' })
          this.showForm = false
          this.catIndex = 0
          this.form = { hours: '', termCode: '', description: '' }
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
.wl__group { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); font-weight: 600; margin-top: var(--space-1); }
.wl__input { width: 100%; height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.wl__picker { line-height: 40px; }
.wl__row { display: flex; gap: var(--space-2); }
.wl__half { flex: 1; }
.wl__textarea { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; }
.wl__ph { color: var(--text-tertiary); }
.wl__tip { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.wl__item { align-items: flex-start; }
.wl__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.wl__note { display: block; font-size: var(--font-size-xs); color: var(--text-secondary); margin-top: 4px; }
</style>
