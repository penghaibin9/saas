<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习过程办理" subtitle="周报批阅 · 指导巡访 · 打卡异常" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data">
        <view class="ir__tabs page-pad">
          <MobileSegmented :items="tabs" v-model="tab" />
        </view>
        <view class="page-pad ir__page" style="padding-top:0;">
          <view class="card ir__summary">
            <view class="ir__summary-main">
              <text class="ir__summary-label">{{ tabSummaryLabel }}</text>
              <view class="ir__summary-value"><text>{{ tabSummaryCount }}</text><text>{{ tabSummaryUnit }}</text></view>
              <text class="ir__summary-note">{{ tabSummaryConclusion }}</text>
            </view>
            <view class="ir__summary-metrics" v-if="tab === 'weekly'">
              <view class="ir__metric"><text>{{ weeklyPendingCount }}</text><text>待批阅</text></view>
              <view class="ir__metric is-danger"><text>{{ overdueCount }}</text><text>逾期</text></view>
              <view class="ir__metric is-warning"><text>{{ weeklyRiskCount }}</text><text>风险提示</text></view>
            </view>
            <view class="ir__summary-metrics" v-else-if="tab === 'visit'">
              <view class="ir__metric"><text>{{ visitPlans.length }}</text><text>巡访计划</text></view>
              <view class="ir__metric is-success"><text>{{ visitedStudentCount }}</text><text>已巡访学生</text></view>
              <view class="ir__metric is-warning"><text>{{ pendingVisitStudentCount }}</text><text>待巡访学生</text></view>
            </view>
            <view class="ir__summary-metrics" v-else>
              <view class="ir__metric is-danger"><text>{{ abnormalPendingCount }}</text><text>待处理</text></view>
              <view class="ir__metric"><text>{{ abnormalCompletedCount }}</text><text>已处理</text></view>
              <view class="ir__metric"><text>{{ data.abnormal.length }}</text><text>异常总数</text></view>
            </view>
          </view>

          <MobileInlineAlert :type="tab === 'abnormal' ? 'warning' : 'info'" :description="tabHelpText" />

          <!-- 周报批阅 -->
          <view v-if="tab === 'weekly'" class="stack">
            <MobileGlobalState v-if="!data.reports.length" state="empty" title="暂无周报" description="学生提交的实习周报会出现在这里等待批阅。" />
            <view v-for="w in pagedSlice(data.reports)" :key="w.id" class="ir card" :class="{ 'is-risk': w.riskFlag || w.overdue }">
              <view class="row-between ir__head">
                <view class="flex-1 ir__identity">
                  <view class="row" style="gap:6px;">
                    <text class="t-md t-bold">{{ w.student }}</text>
                    <text class="ir__week">{{ w.week }}</text>
                  </view>
                  <text class="ir__company">{{ w.company }}{{ w.post ? ' · ' + w.post : '' }}</text>
                </view>
                <MobileStatusTag :status="w.status" :label="w.statusLabel" />
              </view>

              <MobileInlineAlert v-if="w.overdue" type="danger" description="本周周报逾期未提交，建议及时联系学生并关注持续逾期风险。" />
              <template v-else>
                <view class="ir__meta">
                  <view><text>正文长度</text><text>{{ w.wordCount || 0 }} 字</text></view>
                  <view><text>提交版本</text><text>{{ w.isResubmit ? `重交第 ${w.version || 1} 版` : `第 ${w.version || 1} 版` }}</text></view>
                  <view :class="{ 'is-danger': w.riskFlag }"><text>内容风险</text><text>{{ w.riskFlag ? '有风险提示' : '未标记' }}</text></view>
                </view>

                <view v-if="w._body === 'ready'" class="ir__body">
                  <view class="ir__section"><text class="ir__label">本周工作</text><text class="ir__text">{{ w.tasks || '—' }}</text></view>
                  <view class="ir__section"><text class="ir__label">主要收获</text><text class="ir__text">{{ w.gain || '—' }}</text></view>
                  <view class="ir__section"><text class="ir__label">问题与计划</text><text class="ir__text">{{ w.problem || '—' }}</text></view>
                </view>
                <view v-else-if="w._body === 'loading'" class="ir__bodyhint">正在加载周报正文…</view>
                <view v-else-if="w._body === 'error'" class="ir__bodyhint is-link" @click="loadBody(w)">正文加载失败，点击重试</view>
                <view v-else class="ir__bodybtn" @click="loadBody(w)"><text>展开查看完整正文 ▾</text></view>
                <view v-if="w.feedback" class="ir__feedback">
                  <text class="ir__feedback-label">最近评阅意见</text>
                  <text class="ir__feedback-text">{{ w.feedback }}</text>
                  <text v-if="w.score" class="ir__score">评级 {{ w.score }}</text>
                </view>
                <view class="ir__next">
                  <text class="ir__next-label">批阅重点</text>
                  <text class="ir__next-text">先阅读完整正文，核对工作内容、收获和问题是否具体；退回时写明可执行修改要求。</text>
                </view>
              </template>

              <view class="ir__actions">
                <template v-if="w.overdue">
                  <button class="btn btn-ghost flex-1" @click="toast('催交提醒将随消息推送功能开放，可先线下联系')">查看催办提示</button>
                  <button class="ir__risk flex-1" @click="toast('可在「打卡异常」中将异常转为风险跟进')">查看风险处理提示</button>
                </template>
                <template v-else-if="w.status === 'PENDING_REVIEW'">
                  <button class="btn btn-ghost flex-1" :disabled="acting" @click="review(w, 'return')">退回修改</button>
                  <button class="ir__pass flex-1" :disabled="acting" @click="review(w, 'pass')">批阅通过</button>
                </template>
                <text v-else class="ir__done-text flex-1">该周报已完成批阅</text>
              </view>
            </view>
            <view v-if="pagedFooter(data.reports) === 'more'" class="ir__paging" @click="pagedLoadMore">上拉加载更多</view>
            <view v-else-if="pagedFooter(data.reports) === 'end'" class="ir__paging is-end">没有更多了</view>
          </view>

          <!-- 指导巡访 -->
          <view v-else-if="tab === 'visit'" class="stack">
            <MobileGlobalState v-if="visitState === 'loading'" state="loading" />
            <MobileGlobalState v-else-if="!visitPlans.length" state="empty" title="本月暂无巡访计划" description="学院或教务下发巡访计划后会出现在这里。" />
            <template v-else>
              <view v-for="p in visitPlans" :key="p.id" class="ir card">
                <view class="row-between ir__head">
                  <view class="flex-1 ir__identity">
                    <text class="t-md t-bold">{{ p.enterpriseName || '企业待定' }}</text>
                    <text class="ir__company" v-if="p.location">{{ p.location }}</text>
                  </view>
                  <text class="ir__week">{{ p.planDate || '待定日期' }}</text>
                </view>
                <view class="ir__visit-summary">
                  <text>计划学生 {{ (p.students || []).length }} 人</text>
                  <text>已巡访 {{ (p.students || []).filter((s) => s.visited).length }} 人</text>
                </view>
                <view class="ir__visit-students">
                  <view v-for="s in p.students" :key="s.name" class="ir__visit-row">
                    <view class="flex-1 ir__visit-copy"><text class="t-md">{{ s.name }}</text><text>{{ s.visited ? '本计划已留巡访记录' : '尚未记录巡访' }}</text></view>
                    <text v-if="s.visited" class="ir__visit-done">已巡访</text>
                    <button v-else class="ir__visit-btn" :disabled="!s.resolvable || visitActing" @click="recordVisit(s)">
                      {{ s.resolvable ? '记录巡访' : '未匹配学生' }}
                    </button>
                  </view>
                </view>
              </view>
            </template>
          </view>

          <!-- 打卡异常 -->
          <view v-else class="stack">
            <MobileGlobalState v-if="!data.abnormal.length" state="empty" title="暂无打卡异常" description="学生打卡异常（超范围或定位失败）会出现在这里。" />
            <view v-for="c in pagedSlice(data.abnormal)" :key="c.id" class="ir card is-risk">
              <view class="row-between ir__head">
                <view class="flex-1 ir__identity"><text class="t-md t-bold">{{ c.student }}</text><text class="ir__company">{{ c.time || '时间待核对' }}</text></view>
                <MobileStatusTag :status="c.status" :label="c.statusLabel" />
              </view>
              <view class="ir__ck">
                <view class="ir__ck-row"><text class="ir__label">异常类型</text><text class="ir__text is-danger">{{ c.type }}</text></view>
                <view class="ir__ck-row"><text class="ir__label">距离信息</text><text class="ir__text">{{ c.distance || '—' }}</text></view>
                <view class="ir__ck-row"><text class="ir__label">学生说明</text><text class="ir__text flex-1">{{ c.note || '学生未填写说明' }}</text></view>
              </view>
              <view class="ir__next is-warning">
                <text class="ir__next-label">处理原则</text>
                <text class="ir__next-text">超范围不直接认定作弊，应结合学生说明、定位信息和实际工作情况人工判断。</text>
              </view>
              <view class="ir__actions">
                <button class="btn btn-ghost flex-1" :disabled="acting" @click="ck(c, 'reject')">异常计入</button>
                <button class="ir__pass flex-1" :disabled="acting" @click="ck(c, 'ok')">认定有效</button>
              </view>
            </view>
            <view v-if="pagedFooter(data.abnormal) === 'more'" class="ir__paging" @click="pagedLoadMore">上拉加载更多</view>
            <view v-else-if="pagedFooter(data.abnormal) === 'end'" class="ir__paging is-end">没有更多了</view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { listPaging } from '@/utils/listPaging'
import { toast } from '@/utils/nav'
export default {
  mixins: [listPaging(20)],
  data() {
    return {
      data: null, state: 'loading', tab: 'weekly', acting: false,
      tabs: [{ key: 'weekly', label: '周报批阅' }, { key: 'visit', label: '指导巡访' }, { key: 'abnormal', label: '打卡异常' }],
      visitPlans: [], visitState: 'loading', visitActing: false
    }
  },
  computed: {
    weeklyPendingCount() { return (this.data?.reports || []).filter((item) => item.status === 'PENDING_REVIEW').length },
    overdueCount() { return (this.data?.reports || []).filter((item) => item.overdue).length },
    weeklyRiskCount() { return (this.data?.reports || []).filter((item) => item.riskFlag).length },
    abnormalPendingCount() { return (this.data?.abnormal || []).filter((item) => item.status === 'PENDING_HANDLE').length },
    abnormalCompletedCount() { return (this.data?.abnormal || []).length - this.abnormalPendingCount },
    visitedStudentCount() { return this.visitPlans.reduce((total, plan) => total + (plan.students || []).filter((item) => item.visited).length, 0) },
    pendingVisitStudentCount() { return this.visitPlans.reduce((total, plan) => total + (plan.students || []).filter((item) => !item.visited).length, 0) },
    tabSummaryLabel() { return this.tab === 'weekly' ? '周报办理情况' : this.tab === 'visit' ? '指导巡访进度' : '打卡异常办理情况' },
    tabSummaryCount() { return this.tab === 'weekly' ? this.weeklyPendingCount : this.tab === 'visit' ? this.pendingVisitStudentCount : this.abnormalPendingCount },
    tabSummaryUnit() { return this.tab === 'visit' ? '人待巡访' : '条待处理' },
    tabSummaryConclusion() {
      if (this.tab === 'weekly') {
        if (this.overdueCount) return `有 ${this.overdueCount} 条逾期周报，先关注持续未提交学生。`
        if (this.weeklyRiskCount) return `有 ${this.weeklyRiskCount} 条内容风险提示，展开正文重点核对。`
        return this.weeklyPendingCount ? '按提交顺序展开正文并完成批阅。' : '当前没有待批阅周报。'
      }
      if (this.tab === 'visit') return this.pendingVisitStudentCount ? `尚有 ${this.pendingVisitStudentCount} 名学生未记录巡访。` : '当前巡访计划中的学生均已记录。'
      return this.abnormalPendingCount ? `有 ${this.abnormalPendingCount} 条异常需要人工判断。` : '当前没有待处理打卡异常。'
    },
    tabHelpText() {
      if (this.tab === 'weekly') return '先展开完整正文再批阅；退回应写明具体修改要求，避免只看字数直接处理。'
      if (this.tab === 'visit') return '按企业和计划日期查看待巡访学生，完成沟通后及时记录巡访。'
      return '定位超范围或失败不等于作弊，请结合学生说明和实际工作情况人工判断。'
    }
  },
  onLoad() {
    this.load()
    this.loadVisits()
  },
  onReachBottom() { this.pagedReachBottom() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  watch: {
    tab() { this.pagedReset() }
  },
  methods: {
    toast,
    pagingList() {
      if (!this.data) return []
      return this.tab === 'weekly' ? (this.data.reports || []) : (this.data.abnormal || [])
    },
    load(done) {
      this.state = 'loading'
      this.pagedReset()
      teacherApi.getWeeklyReports().then((d) => {
        d.reports.forEach((r) => { if (!r._body) r._body = 'idle' })
        this.data = d
        this.tabs[0].badge = d.reports.filter((r) => r.status === 'PENDING_REVIEW').length
        this.tabs[2].badge = d.abnormal.filter((a) => a.status === 'PENDING_HANDLE').length
        this.state = 'ready'
        this.data.reports.slice(0, 12).forEach((r) => this.loadBody(r))
      }).catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    loadBody(w) {
      if (!w || w._body === 'loading' || w._body === 'ready') return
      if (!/^\d+$/.test(String(w.id))) { w._body = 'error'; return }
      w._body = 'loading'
      teacherApi.getWeeklyDetail(w.id).then((d) => {
        w.tasks = d.work
        w.gain = d.harvest
        w.problem = d.plan
        if (d.positionName) w.post = d.positionName
        if (d.reviewComment && !w.feedback) w.feedback = d.reviewComment
        w._body = 'ready'
      }).catch((e) => {
        w._body = 'error'
        toast(normalizeError(e).text)
      })
    },
    loadVisits() {
      this.visitState = 'loading'
      teacherApi.getInternshipVisitPlans().then((d) => {
        this.visitPlans = (d && d.plans) || []
        this.tabs[1].badge = this.visitPlans.reduce((total, plan) => total + (plan.students || []).filter((item) => !item.visited).length, 0)
        this.visitState = 'ready'
      }).catch(() => { this.visitState = 'error' })
    },
    recordVisit(s) {
      if (this.visitActing || !s.internshipId) return
      this.visitActing = true
      teacherApi.recordInternshipVisit(s.internshipId).then(() => {
        s.visited = true
        this.tabs[1].badge = Math.max(0, Number(this.tabs[1].badge || 0) - 1)
        toast('已记录巡访')
      }).catch((e) => toast(normalizeError(e).text))
        .finally(() => { this.visitActing = false })
    },
    _actErr(e, refresh) {
      if (e && String(e.code).startsWith('409')) {
        toast('已被处理，正在刷新')
        if (refresh) this.load()
      } else {
        toast(normalizeError(e).text)
      }
    },
    review(w, type) {
      if (this.acting) return
      const label = type === 'pass' ? '通过' : '退回'
      uni.showModal({ title: '周报' + label, editable: true, placeholderText: '填写评阅意见', success: (r) => {
        if (!r.confirm || this.acting) return
        if (type !== 'pass' && (!r.content || r.content.trim().length < 5)) {
          toast('退回需填写至少 5 字意见')
          return
        }
        if (!/^\d+$/.test(String(w.id))) {
          toast('当前为离线数据，无法批阅，请恢复网络后重试')
          return
        }
        this.acting = true
        teacherApi.reviewWeekly(w.id, type === 'pass' ? 'APPROVE' : 'RETURN', r.content || '')
          .then((res) => {
            w.status = res.status || (type === 'pass' ? 'APPROVED' : 'RETURNED')
            w.feedback = r.content || ''
            toast('已' + label)
            this.load()
          })
          .catch((e) => this._actErr(e, true))
          .finally(() => { this.acting = false })
      } })
    },
    ck(c, type) {
      if (this.acting) return
      const action = type === 'ok' ? 'REASONABLE' : 'ABNORMAL'
      uni.showModal({ title: type === 'ok' ? '认定有效' : '异常计入', editable: true,
        placeholderText: '填写处理意见（至少 5 字）', success: (r) => {
          if (!r.confirm || this.acting) return
          if (!r.content || r.content.trim().length < 5) {
            toast('处理意见至少 5 字')
            return
          }
          if (!/^\d+$/.test(String(c.id))) {
            toast('当前为离线数据，无法处理，请恢复网络后重试')
            return
          }
          this.acting = true
          teacherApi.handleCheckin(c.id, action, r.content)
            .then((res) => {
              c.status = res.status || 'COMPLETED'
              toast(res.statusLabel || '已处理')
              this.load()
            })
            .catch((e) => this._actErr(e, true))
            .finally(() => { this.acting = false })
        } })
    }
  }
}
</script>

<style scoped>
.ir__tabs{padding-bottom:var(--space-3)}.ir__page{display:flex;flex-direction:column;gap:var(--space-3)}.ir__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.ir__summary-main{flex:1;min-width:0}.ir__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ir__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.ir__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.ir__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.ir__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ir__summary-metrics{width:50%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.ir__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 3px;border-left:1px solid var(--border-light);text-align:center}.ir__metric:first-child{border-left:0}.ir__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--text-primary)}.ir__metric.is-danger text:first-child{color:var(--danger-600)}.ir__metric.is-warning text:first-child{color:var(--warning-700)}.ir__metric.is-success text:first-child{color:var(--success-700)}.ir__metric text:last-child{font-size:10px;line-height:1.25;color:var(--text-tertiary)}.ir{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.ir.is-risk{border-left:4px solid var(--warning-500)}.ir__head{align-items:flex-start}.ir__identity{min-width:0}.ir__week{font-size:var(--font-size-xs);color:var(--teacher-700);background:var(--teacher-50);padding:2px 8px;border-radius:var(--radius-full)}.ir__company{display:block;font-size:var(--font-size-sm);color:var(--text-secondary);margin-top:3px;word-break:break-word}.ir__meta{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:var(--space-2);background:var(--gray-50);border-radius:var(--radius-md)}.ir__meta>view{min-width:0;display:flex;flex-direction:column;gap:3px}.ir__meta text:first-child{font-size:10px;color:var(--text-tertiary)}.ir__meta text:last-child{font-size:var(--font-size-xs);font-weight:600;color:var(--text-primary);word-break:break-word}.ir__meta>view.is-danger text:last-child{color:var(--danger-600)}.ir__body{padding:var(--space-2) var(--space-3);border:1px solid var(--border-light);border-radius:var(--radius-md)}.ir__section+.ir__section{margin-top:var(--space-3);padding-top:var(--space-3);border-top:1px dashed var(--border-light)}.ir__bodybtn{text-align:center;padding:10px;border:1px solid var(--teacher-200,#bfdbfe);border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.ir__bodybtn text{font-size:var(--font-size-sm);color:var(--teacher-700)}.ir__bodyhint{font-size:var(--font-size-sm);color:var(--text-tertiary);text-align:center;padding:var(--space-3) 0}.ir__bodyhint.is-link{color:var(--danger-600)}.ir__label{font-size:var(--font-size-xs);font-weight:600;color:var(--text-tertiary)}.ir__text{display:block;font-size:var(--font-size-base);color:var(--text-primary);margin-top:4px;line-height:1.65;white-space:pre-wrap;word-break:break-word}.ir__text.is-danger{color:var(--danger-600)}.ir__ck{background:var(--gray-50);border-radius:var(--radius-md);padding:var(--space-2) var(--space-3)}.ir__ck-row{display:flex;gap:var(--space-3);padding:5px 0}.ir__ck-row .ir__label{width:62px;flex-shrink:0}.ir__feedback{background:var(--success-50);border-radius:var(--radius-md);padding:var(--space-2) var(--space-3)}.ir__feedback-label{font-size:var(--font-size-xs);font-weight:600;color:var(--success-700)}.ir__feedback-text{display:block;font-size:var(--font-size-sm);color:var(--text-primary);margin-top:4px;line-height:1.55;word-break:break-word}.ir__score{display:inline-block;margin-top:5px;font-size:var(--font-size-xs);color:var(--success-700)}.ir__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.ir__next.is-warning{background:var(--warning-50,#fff7ed)}.ir__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ir__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ir__actions{display:flex;gap:var(--space-2)}.ir__pass{min-height:var(--touch-target-min);border-radius:var(--radius-md);border:none;background:var(--teacher-600);color:#fff;font-size:var(--font-size-md)}.ir__pass::after{border:none}.ir__risk{min-height:var(--touch-target-min);border-radius:var(--radius-md);border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600);font-size:var(--font-size-md)}.ir__risk::after{border:none}.ir__done-text{text-align:center;color:var(--text-tertiary);font-size:var(--font-size-sm);line-height:var(--touch-target-min)}.ir__paging{text-align:center;padding:var(--space-3) 0;font-size:var(--font-size-sm);color:var(--teacher-700)}.ir__paging.is-end{color:var(--text-tertiary)}.ir__visit-summary{display:flex;justify-content:space-between;gap:12px;padding:var(--space-2) var(--space-3);border-radius:var(--radius-md);background:var(--gray-50);font-size:var(--font-size-xs);color:var(--text-secondary)}.ir__visit-students{border-top:1px solid var(--border-light);padding-top:var(--space-2)}.ir__visit-row{display:flex;align-items:center;gap:var(--space-2);padding:var(--space-2) 0;border-bottom:1px solid var(--border-light)}.ir__visit-row:last-child{border-bottom:0}.ir__visit-copy{min-width:0}.ir__visit-copy>text:last-child{display:block;margin-top:2px;font-size:10px;color:var(--text-tertiary)}.ir__visit-done{font-size:var(--font-size-sm);color:var(--success-600)}.ir__visit-btn{font-size:var(--font-size-sm);color:#fff;background:var(--teacher-600);border:none;border-radius:var(--radius-md);padding:7px 14px;flex-shrink:0}.ir__visit-btn[disabled]{background:var(--gray-300);color:var(--text-tertiary)}@media(max-width:360px){.ir__summary{flex-direction:column}.ir__summary-metrics{width:100%}.ir__meta{grid-template-columns:1fr}.ir__ck-row{flex-direction:column;gap:3px}.ir__ck-row .ir__label{width:auto}}
</style>
