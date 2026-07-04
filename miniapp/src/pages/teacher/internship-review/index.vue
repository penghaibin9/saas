<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data">
        <view class="ir__tabs page-pad">
          <MobileSegmented :items="tabs" v-model="tab" />
        </view>
        <view class="page-pad" style="padding-top:0;">
          <!-- 周报批阅 -->
          <view v-if="tab === 'weekly'" class="stack">
            <view v-for="w in data.reports" :key="w.id" class="ir card">
              <view class="row-between">
                <view class="flex-1">
                  <view class="row" style="gap:6px;">
                    <text class="t-md t-bold">{{ w.student }}</text>
                    <text class="ir__week">{{ w.week }}</text>
                  </view>
                  <text class="ir__company">{{ w.company }} · {{ w.post }}</text>
                </view>
                <MobileStatusTag :status="w.status" />
              </view>

              <MobileInlineAlert v-if="w.overdue" type="danger" description="本周周报逾期未提交，建议催交或记录风险。" />
              <template v-else>
                <view class="ir__section"><text class="ir__label">本周工作</text><text class="ir__text">{{ w.tasks }}</text></view>
                <view class="ir__section"><text class="ir__label">收获</text><text class="ir__text">{{ w.gain }}</text></view>
                <view class="ir__section"><text class="ir__label">问题</text><text class="ir__text">{{ w.problem }}</text></view>
                <view v-if="w.feedback" class="ir__feedback">
                  <text class="ir__feedback-label">我的评阅</text>
                  <text class="ir__feedback-text">{{ w.feedback }}</text>
                  <text v-if="w.score" class="ir__score">评级 {{ w.score }}</text>
                </view>
              </template>

              <view class="ir__actions">
                <template v-if="w.overdue">
                  <button class="btn btn-ghost flex-1" @click="toast('已催交（演示）')">催交周报</button>
                  <button class="ir__risk flex-1" @click="toast('已记录风险（演示）')">记录风险</button>
                </template>
                <template v-else-if="w.status === 'PENDING_REVIEW'">
                  <button class="btn btn-ghost flex-1" @click="review(w, 'return')">退回</button>
                  <button class="ir__pass flex-1" @click="review(w, 'pass')">批阅通过</button>
                </template>
                <text v-else class="ir__done-text flex-1">已批阅</text>
              </view>
            </view>
          </view>

          <!-- 打卡异常 -->
          <view v-else class="stack">
            <MobileGlobalState v-if="!data.abnormal.length" state="empty" title="暂无打卡异常" description="学生打卡异常（超范围/定位失败）会出现在这里。" />
            <view v-for="c in data.abnormal" :key="c.id" class="ir card">
              <view class="row-between">
                <text class="t-md t-bold">{{ c.student }}</text>
                <MobileStatusTag :status="c.status" />
              </view>
              <view class="ir__ck">
                <view class="ir__ck-row"><text class="ir__label">异常类型</text><text class="ir__text is-danger">{{ c.type }}</text></view>
                <view class="ir__ck-row"><text class="ir__label">时间 / 距离</text><text class="ir__text">{{ c.time }} · {{ c.distance }}</text></view>
                <view class="ir__ck-row"><text class="ir__label">学生说明</text><text class="ir__text flex-1">{{ c.note }}</text></view>
              </view>
              <MobileInlineAlert type="info" description="超范围不直接认定作弊，请结合说明人工审核。" />
              <view class="ir__actions">
                <button class="btn btn-ghost flex-1" @click="ck(c, 'reject')">异常计入</button>
                <button class="ir__pass flex-1" @click="ck(c, 'ok')">认定有效</button>
              </view>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'
export default {
  data() {
    return {
      data: null, state: 'loading', tab: 'weekly',
      tabs: [{ key: 'weekly', label: '周报批阅' }, { key: 'abnormal', label: '打卡异常' }]
    }
  },
  onLoad() { this.load() },
  methods: {
    toast,
    load() {
      this.state = 'loading'
      teacherApi.getWeeklyReports().then((d) => {
        this.data = d
        this.tabs[0].badge = d.reports.filter((r) => r.status === 'PENDING_REVIEW').length
        this.tabs[1].badge = d.abnormal.filter((a) => a.status === 'PENDING_HANDLE').length
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    review(w, type) {
      const label = type === 'pass' ? '通过' : '退回'
      uni.showModal({ title: '周报' + label, editable: true, placeholderText: '填写评阅意见', success: (r) => {
        if (!r.confirm) return
        w.status = type === 'pass' ? 'APPROVED' : 'RETURNED'
        w.feedback = r.content || (type === 'pass' ? '内容充实，通过。' : '请补充产出细节。')
        toast('已' + label + '（演示）')
      } })
    },
    ck(c, type) { c.status = type === 'ok' ? 'COMPLETED' : 'ABNORMAL'; toast('已处理（演示）') }
  }
}
</script>

<style scoped>
.ir__tabs { padding-bottom: var(--space-3); }
.ir__week { font-size: var(--font-size-xs); color: var(--teacher-700); background: var(--teacher-50); padding: 2px 8px; border-radius: var(--radius-full); }
.ir__company { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 3px; }
.ir__section { margin-top: var(--space-3); }
.ir__label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ir__text { display: block; font-size: var(--font-size-base); color: var(--text-primary); margin-top: 3px; line-height: 1.5; }
.ir__text.is-danger { color: var(--danger-600); }
.ir__ck { background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); margin: var(--space-3) 0; }
.ir__ck-row { display: flex; gap: var(--space-3); padding: 5px 0; }
.ir__feedback { margin-top: var(--space-3); background: var(--teacher-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.ir__feedback-label { font-size: var(--font-size-xs); color: var(--teacher-700); }
.ir__feedback-text { display: block; font-size: var(--font-size-sm); color: var(--text-primary); margin-top: 3px; }
.ir__score { display: inline-block; margin-top: 4px; font-size: var(--font-size-xs); color: var(--success-700); }
.ir__actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
.ir__pass { min-height: var(--touch-target-min); border-radius: var(--radius-md); border: none; background: var(--teacher-600); color: #fff; font-size: var(--font-size-md); }
.ir__pass::after { border: none; }
.ir__risk { min-height: var(--touch-target-min); border-radius: var(--radius-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); font-size: var(--font-size-md); }
.ir__risk::after { border: none; }
.ir__done-text { text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); line-height: var(--touch-target-min); }
</style>
