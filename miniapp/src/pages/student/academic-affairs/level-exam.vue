<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="等级考试报名" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="section-head"><text class="section-head__title">可报名考试</text></view>
        <view class="list-group" v-if="d.openExams && d.openExams.length">
          <view v-for="e in d.openExams" :key="e.examId" class="list-row lv__item">
            <view class="flex-1">
              <text class="t-md">{{ e.examName }}</text>
              <text class="lv__sub">{{ catLabel(e.category) }}{{ e.level ? ' · ' + e.level : '' }}{{ e.examDate ? ' · ' + e.examDate : '' }}{{ e.fee != null ? ' · 报名费¥' + e.fee : '' }}</text>
            </view>
            <button v-if="!isRegistered(e.examId)" class="btn btn-primary btn-sm" :disabled="acting" @click="register(e)">报名</button>
            <text v-else class="lv__done">已报名</text>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无开放报名的考试" description="等级考试开放报名后在此显示。" />

        <template v-if="d.myRegs && d.myRegs.length">
          <view class="section-head"><text class="section-head__title">我的报名</text></view>
          <view class="list-group">
            <view v-for="r in d.myRegs" :key="r.regId" class="list-row lv__item">
              <view class="flex-1">
                <text class="t-md">{{ examName(r.examId) }}</text>
                <text class="lv__sub">
                  {{ r.feeStatus === 'PAID' ? '已缴费' : '待缴费' }}
                  <template v-if="r.status === 'SCORED'"> · {{ r.result === 'PASS' ? '通过' : '未通过' }}{{ r.score != null ? '（' + r.score + '分）' : '' }}{{ r.certNo ? ' · ' + r.certNo : '' }}</template>
                </text>
              </view>
              <MobileStatusTag :status="r.status" />
              <text v-if="r.status === 'REGISTERED' && canCancel(r)" class="lv__cancel" @click="cancel(r)">取消</text>
            </view>
          </view>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const actLock = createSubmitLock(1200)
const _CAT = { CET: '大学英语', PUTONGHUA: '普通话', SKILL: '技能证书', OTHER: '其他' }

export default {
  data() {
    return { d: null, state: 'loading', acting: false }
  },
  onLoad() { this.load() },
  methods: {
    catLabel(c) { return _CAT[c] || c },
    load() {
      this.state = 'loading'
      studentApi.getMyLevelExam().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    isRegistered(examId) {
      return (this.d.myRegs || []).some((r) => String(r.examId) === String(examId) && r.status === 'REGISTERED')
    },
    examName(examId) {
      const e = (this.d.openExams || []).find((x) => String(x.examId) === String(examId))
      return e ? e.examName : '考试#' + examId
    },
    canCancel(r) {
      // 仅当该考试仍在开放报名时可取消（openExams 含即为开放中）
      return (this.d.openExams || []).some((x) => String(x.examId) === String(r.examId))
    },
    register(e) {
      if (this.acting) return
      this.acting = true
      actLock.run(() => studentApi.registerLevelExam(e.examId))
        .then(() => { uni.showToast({ title: '报名成功', icon: 'success' }); this.load() })
        .catch((err) => { if (err && err.code === 'LOCKED') return; toast(err && err.biz ? normalizeError(err).text : '报名失败') })
        .finally(() => { this.acting = false })
    },
    cancel(r) {
      if (this.acting) return
      this.acting = true
      actLock.run(() => studentApi.cancelLevelExam(r.examId))
        .then(() => { uni.showToast({ title: '已取消', icon: 'success' }); this.load() })
        .catch((err) => { if (err && err.code === 'LOCKED') return; toast(err && err.biz ? normalizeError(err).text : '取消失败') })
        .finally(() => { this.acting = false })
    }
  }
}
</script>

<style scoped>
.lv__item { align-items: center; gap: var(--space-2); }
.lv__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.lv__done { font-size: var(--font-size-xs); color: var(--success-600); }
.lv__cancel { font-size: var(--font-size-xs); color: var(--danger-600); margin-left: var(--space-2); }
.btn-sm { height: 30px; line-height: 30px; padding: 0 var(--space-3); font-size: var(--font-size-sm); }
</style>
