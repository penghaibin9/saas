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
            @click="selectWeek(w.week)"
          >
            <text class="wr__week-num">第{{ w.week }}周</text>
            <text class="wr__week-tag">{{ w.tagText }}</text>
          </view>
        </view>

        <view v-if="receipt" class="card wr__receipt">
          <text class="t-md t-bold">{{ receipt.actionLabel }}</text>
          <text>#{{ receipt.id }} · v{{ receipt.version }} · {{ receipt.statusLabel }}</text>
          <text>{{ receipt.nextStep }}</text>
        </view>

        <!-- 当前可填写周 -->
        <template v-if="isEditableWeek">
          <view class="card wr__form">
            <view class="row-between"><text class="card-title">第 {{ selectedWeek }} 周 · {{ selectedReport ? '修改重交' : '填写中' }}</text><MobileStatusTag :label="selectedReport ? '已退回' : '填写中'" :type="selectedReport ? 'warning' : 'processing'" /></view>
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

          <MobileInlineAlert :type="selectedReport ? 'warning' : 'info'" :description="selectedReport ? ('教师意见：' + (selectedReport.reviewComment || '请修改后重新提交')) : '周报提交后由校内指导教师批阅；逾期未交会计入实习考核。'" />
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

        <view v-if="hasMore" class="wr__more">
          <button class="btn btn-secondary" :disabled="loadingMore" @click="loadMore">
            {{ loadingMore ? '加载中…' : '加载更多历史周报' }}
          </button>
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="loaded && isEditableWeek">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : (selectedReport ? '重新提交周报' : '提交周报') }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const STATUS_TAG = { PENDING_REVIEW: '待批阅', APPROVED: '已批阅', RETURNED: '已退回', OVERDUE: '已逾期' }

export default {
  data() {
    return {
      state: 'loading', loaded: false,
      company: '', post: '', schoolMentor: '', lastFeedback: '',
      currentWeek: 1, weeklyList: [], selectedWeek: 1,
      form: { workContent: '', harvestContent: '', planContent: '' },
      submitting: false, receipt: null, loadSequence: 0, batchId: '', internshipId: '',
      // 来自正式消息 action 的对象聚焦。数据回读完成后才使用，避免旧列表或迟到
      // 响应把用户送回当前周而看不到退回原因。
      focusReportId: '', focusWeek: 0,
      weeklyPageSize: 20, weeklyTotal: 0, loadedWeeklyPages: [], hasMore: false, loadingMore: false
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
      return (!this.selectedReport && this.selectedWeek === this.currentWeek) || this.selectedReport?.status === 'RETURNED'
    }
  },
  onLoad(options = {}) {
    this.focusReportId = String(options.reportId || '').trim()
    this.focusWeek = Number(options.weekNo || 0) || 0
    this.load()
  },
  onReachBottom() { this.loadMore() },
  methods: {
    mergeWeeklyItems(items) {
      const rows = new Map(this.weeklyList.map((row) => [String(row.id), row]))
      for (const row of (items || [])) rows.set(String(row.id), row)
      this.weeklyList = Array.from(rows.values()).sort((a, b) => {
        const byWeek = Number(b.week || 0) - Number(a.week || 0)
        return byWeek || String(b.id).localeCompare(String(a.id))
      })
    },
    applyWeeklyPage(result) {
      const page = Number(result?.page || 1)
      this.mergeWeeklyItems(result?.items || [])
      this.weeklyTotal = Number(result?.total || 0)
      if (!this.loadedWeeklyPages.includes(page)) this.loadedWeeklyPages = [...this.loadedWeeklyPages, page].sort((a, b) => a - b)
      const totalPages = Math.ceil(this.weeklyTotal / this.weeklyPageSize)
      this.hasMore = this.loadedWeeklyPages.length < totalPages
    },
    async load() {
      const sequence = ++this.loadSequence
      this.state = 'loading'
      this.loadingMore = false
      try {
        const d = await studentApi.getInternship()
        if (sequence !== this.loadSequence) return
        this.company = d.company || ''
        this.post = d.post || ''
        this.schoolMentor = d.schoolMentor || ''
        this.lastFeedback = (d.weekly && d.weekly.lastFeedback) || ''
        this.batchId = d.batchId || ''
        this.internshipId = d.recordId || ''
        const result = await studentApi.getInternshipWeeklyReports(
          this.batchId, this.internshipId, 1, this.weeklyPageSize, this.focusReportId
        )
        if (sequence !== this.loadSequence) return
        this.weeklyList = []
        this.weeklyTotal = 0
        this.loadedWeeklyPages = []
        this.applyWeeklyPage(result)
        // 深链永远先取当前首屏，确保当前周的真实状态不会被遗漏；目标不在首屏时
        // 最多再请求目标所在的一页，而不是一次把整学期历史全部拉取。
        const focusPage = Number(result?.focusPage || 0)
        if (this.focusReportId && focusPage > 1) {
          const focused = await studentApi.getInternshipWeeklyReports(
            this.batchId, this.internshipId, focusPage, this.weeklyPageSize
          )
          if (sequence !== this.loadSequence) return
          this.applyWeeklyPage(focused)
        }
        const m = String((d.weekly && d.weekly.week) || '第 1 周').match(/\d+/)
        this.currentWeek = m ? Number(m[0]) : 1
        const focusedReport = this.weeklyList.find((row) => String(row.id) === this.focusReportId)
        const focusedWeek = Number(focusedReport?.week || this.focusWeek || 0)
        this.selectedWeek = focusedWeek || this.currentWeek
        this.selectWeek(this.selectedWeek)
        this.loaded = true
        this.state = 'ready'
      } catch (e) {
        if (sequence === this.loadSequence) this.state = 'error'
      }
    },
    async loadMore() {
      if (!this.loaded || this.loadingMore || !this.hasMore) return
      const totalPages = Math.ceil(this.weeklyTotal / this.weeklyPageSize)
      const nextPage = Array.from({ length: totalPages }, (_, index) => index + 1)
        .find((page) => !this.loadedWeeklyPages.includes(page))
      if (!nextPage) {
        this.hasMore = false
        return
      }
      const sequence = this.loadSequence
      this.loadingMore = true
      try {
        const result = await studentApi.getInternshipWeeklyReports(
          this.batchId, this.internshipId, nextPage, this.weeklyPageSize
        )
        if (sequence !== this.loadSequence) return
        this.applyWeeklyPage(result)
      } catch (e) {
        if (sequence === this.loadSequence) toast('历史周报加载失败，请检查网络后重试')
      } finally {
        if (sequence === this.loadSequence) this.loadingMore = false
      }
    },
    selectWeek(week) {
      if (this.submitting) return
      this.selectedWeek = Number(week)
      const row = this.weeklyList.find((item) => Number(item.week) === this.selectedWeek)
      if (row?.status === 'RETURNED') {
        this.form = { workContent: row.workContent || '', harvestContent: row.harvestContent || '', planContent: row.planContent || '' }
      } else if (!row) {
        this.form = { workContent: '', harvestContent: '', planContent: '' }
      }
    },
    async submit() {
      if (this.submitting) return
      if (this.form.workContent.trim().length < 10 || this.form.harvestContent.trim().length < 10) {
        toast('本周工作内容与本周收获均至少 10 个字')
        return
      }
      this.submitting = true
      const current = this.selectedReport
      try {
        const result = await studentApi.submitInternshipWeeklyReport({
          batchId: this.batchId, internshipId: this.internshipId,
          expectedVersion: current?.version ?? 0, weekNo: this.selectedWeek,
          workContent: this.form.workContent.trim(), harvestContent: this.form.harvestContent.trim(),
          planContent: this.form.planContent.trim()
        })
        this.receipt = {
          actionLabel: current ? '周报已重新提交' : '周报已提交', id: result.id,
          version: result.version, statusLabel: '待批阅', nextStep: '等待指导教师批阅；退回后可继续修改。'
        }
        await this.load()
      } catch (e) {
        if (e && e.code === 'LOCKED') return
        if (e && e.biz) {
          if (String(e.code).startsWith('409')) toast('周报已被更新，填写内容已保留，请刷新核对')
          else toast(normalizeError(e).text)
        } else {
          toast('网络异常，填写内容已保留，请稍后重试')
        }
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
.wr__weeks { display: flex; gap: var(--space-2); overflow-x: auto; }
.wr__receipt { display: flex; flex-direction: column; gap: 4px; margin-top: var(--card-gap-mobile); border-color: #86efac; background: #f0fdf4; color: #166534; font-size: var(--font-size-xs); }
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
.wr__more { margin: var(--card-gap-mobile) 0; }
.wr__more .btn { width: 100%; }
</style>
