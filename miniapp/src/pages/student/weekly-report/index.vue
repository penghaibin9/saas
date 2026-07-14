<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="实习周报" :subtitle="company + ' · ' + post" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="loaded">
        <view class="card wr__weeks">
          <view
            v-for="w in weekTabs"
            :key="w.week"
            class="wr__week"
            :class="{ 'is-on': selectedWeek === w.week }"
            @click="selectedWeek = w.week"
          >
            <text class="wr__week-num">第{{ w.week }}周</text>
            <text class="wr__week-tag">{{ w.tagText }}</text>
          </view>
        </view>

        <!-- 当前可填写周 -->
        <template v-if="isEditableWeek">
          <view class="card wr__form">
            <view class="row-between"><text class="card-title">第 {{ selectedWeek }} 周 · 填写中</text><MobileStatusTag label="填写中" type="processing" /></view>
            <view class="wr__field">
              <text class="wr__label">本周工作内容 <text class="wr__req">*</text></text>
              <textarea class="wr__textarea" v-model="form.workContent" :maxlength="500" placeholder="描述本周完成的主要任务" placeholder-class="wr__ph" />
            </view>
            <view class="wr__field">
              <text class="wr__label">本周收获 <text class="wr__req">*</text></text>
              <textarea class="wr__textarea" v-model="form.harvestContent" :maxlength="500" placeholder="学到的技能、经验与体会" placeholder-class="wr__ph" />
            </view>
            <view class="wr__field">
              <text class="wr__label">存在问题 / 下周计划</text>
              <textarea class="wr__textarea" v-model="form.planContent" :maxlength="500" placeholder="遇到的问题及下周安排（可选）" placeholder-class="wr__ph" />
            </view>
          </view>

          <view v-if="lastFeedback" class="card wr__fb">
            <text class="card-title">上周指导反馈</text>
            <view class="wr__fb-row">
              <view class="wr__fb-avatar">{{ (schoolMentor || '师').slice(0,1) }}</view>
              <view class="flex-1">
                <text class="t-md t-bold">{{ schoolMentor || '校内导师' }}</text>
                <text class="wr__fb-text">{{ lastFeedback }}</text>
              </view>
            </view>
          </view>

          <MobileInlineAlert type="info" description="周报提交后由校内指导教师批阅；逾期未交会计入实习考核。" />
        </template>

        <!-- 历史周只读 -->
        <template v-else-if="selectedReport">
          <view class="card wr__ro">
            <view class="row-between"><text class="card-title">第 {{ selectedReport.week }} 周 · 已提交</text><MobileStatusTag :status="selectedReport.status" /></view>
            <view class="wr__ro-block"><text class="wr__ro-label">本周工作内容</text><text class="wr__ro-text">{{ selectedReport.workContent || '—' }}</text></view>
            <view class="wr__ro-block"><text class="wr__ro-label">本周收获</text><text class="wr__ro-text">{{ selectedReport.harvestContent || '—' }}</text></view>
            <view v-if="selectedReport.planContent" class="wr__ro-block"><text class="wr__ro-label">存在问题 / 下周计划</text><text class="wr__ro-text">{{ selectedReport.planContent }}</text></view>
          </view>
          <view v-if="selectedReport.reviewComment" class="card wr__fb">
            <text class="card-title">导师批阅</text>
            <view class="wr__fb-row">
              <view class="wr__fb-avatar">{{ (schoolMentor || '师').slice(0,1) }}</view>
              <view class="flex-1">
                <text class="t-md t-bold">{{ schoolMentor || '校内导师' }}</text>
                <text class="wr__fb-text">{{ selectedReport.reviewComment }}</text>
              </view>
            </view>
          </view>
        </template>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="loaded && isEditableWeek">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '提交周报' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)
const STATUS_TAG = { PENDING_REVIEW: '待批阅', APPROVED: '已批阅', RETURNED: '已退回', OVERDUE: '已逾期' }

export default {
  data() {
    return {
      state: 'loading', loaded: false,
      company: '', post: '', schoolMentor: '', lastFeedback: '',
      currentWeek: 1, weeklyList: [], selectedWeek: 1,
      form: { workContent: '', harvestContent: '', planContent: '' },
      submitting: false
    }
  },
  computed: {
    weekTabs() {
      const tabs = this.weeklyList.map((r) => ({ week: r.week, tagText: STATUS_TAG[r.status] || r.status }))
      if (!tabs.some((t) => t.week === this.currentWeek)) {
        tabs.push({ week: this.currentWeek, tagText: '填写中' })
      }
      return tabs.sort((a, b) => a.week - b.week)
    },
    selectedReport() {
      return this.weeklyList.find((r) => r.week === this.selectedWeek) || null
    },
    isEditableWeek() {
      return this.selectedWeek === this.currentWeek && !this.selectedReport
    }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getInternship().then((d) => {
        this.company = d.company || ''
        this.post = d.post || ''
        this.schoolMentor = d.schoolMentor || ''
        this.lastFeedback = (d.weekly && d.weekly.lastFeedback) || ''
        this.weeklyList = d.weeklyList || []
        const m = String((d.weekly && d.weekly.week) || '第 1 周').match(/\d+/)
        this.currentWeek = m ? Number(m[0]) : 1
        this.selectedWeek = this.currentWeek
        this.loaded = true
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    submit() {
      if (this.submitting) return
      if (this.form.workContent.trim().length < 10 || this.form.harvestContent.trim().length < 10) {
        toast('本周工作内容与本周收获均至少 10 个字')
        return
      }
      this.submitting = true
      submitLock.run(() => studentApi.submitWeeklyReport({
        weekNo: this.selectedWeek,
        workContent: this.form.workContent.trim(),
        harvestContent: this.form.harvestContent.trim(),
        planContent: this.form.planContent.trim()
      })).then(() => {
        uni.showToast({ title: '周报已提交', icon: 'success' })
        this.load()
      }).catch((e) => {
        if (e && e.code === 'LOCKED') return
        if (e && e.biz) {
          if (String(e.code).startsWith('409')) toast('本周周报已提交，请勿重复提交')
          else toast(normalizeError(e).text)
        } else {
          toast('网络异常，提交未成功，请稍后重试')
        }
      }).finally(() => {
        this.submitting = false
      })
    }
  }
}
</script>

<style scoped>
.wr__weeks { display: flex; gap: var(--space-2); overflow-x: auto; }
.wr__week { flex-shrink: 0; min-width: 64px; text-align: center; padding: var(--space-2) var(--space-1); border-radius: var(--radius-md); border: 1.5px solid var(--border-base); }
.wr__week.is-on { border-color: var(--brand-primary); background: var(--primary-50); }
.wr__week-num { display: block; font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--text-secondary); }
.wr__week.is-on .wr__week-num { color: var(--brand-primary); }
.wr__week-tag { display: block; font-size: 10px; color: var(--text-tertiary); margin-top: 2px; }
.wr__week.is-on .wr__week-tag { color: var(--brand-primary); }
.wr__form, .wr__ro { margin-top: var(--card-gap-mobile); }
.wr__field { padding: var(--space-3) 0; border-bottom: 1px solid var(--border-light); }
.wr__field:last-child { border-bottom: none; }
.wr__label { display: block; font-size: var(--font-size-base); color: var(--text-secondary); margin-bottom: var(--space-2); }
.wr__req { color: var(--danger-500); }
.wr__textarea { width: 100%; min-height: 80px; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; }
.wr__ph { color: var(--text-tertiary); }
.wr__ro-block { padding: var(--space-2) 0; }
.wr__ro-label { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-bottom: 4px; }
.wr__ro-text { display: block; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-3); }
.wr__fb { margin-top: var(--card-gap-mobile); }
.wr__fb-row { display: flex; gap: var(--space-3); margin-top: var(--space-2); }
.wr__fb-avatar { width: 36px; height: 36px; border-radius: var(--radius-md); background: var(--brand-gradient); color: #fff; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.wr__fb-text { display: block; margin-top: 4px; font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.5; }
</style>
