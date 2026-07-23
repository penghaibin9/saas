<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习风险处置" subtitle="本人指导学生 · 含学生求助" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待办风险"
          description="学生求助、超期未销假、打卡转风险等会出现在这里（非学工危机台）。" />
        <view class="stack" v-else>
          <view v-for="r in list" :key="r.id" class="card ir">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ r.studentName || '—' }}</text>
                <text class="ir__sub">{{ r.studentNo || '' }} · {{ r.riskTitle || r.riskCode }}</text>
              </view>
              <MobileStatusTag :label="r.statusLabel || r.status" :type="r.status === 'PENDING_HANDLE' ? 'warning' : 'default'" />
            </view>
            <view class="ir__row"><text class="ir__k">等级</text><text class="flex-1 t-sm">{{ r.riskLevelLabel || r.riskLevel }}</text></view>
            <view class="ir__row" v-if="r.lastFollowNote"><text class="ir__k">说明</text><text class="flex-1 t-sm">{{ r.lastFollowNote }}</text></view>
            <view class="ir__actions" v-if="r.status === 'PENDING_HANDLE'">
              <button class="btn btn-primary flex-1" :disabled="acting" @click="doHandle(r)">受理</button>
            </view>
            <view class="ir__actions" v-else-if="r.status === 'PROCESSING'">
              <button class="btn btn-ghost flex-1" :disabled="acting" @click="doFollow(r)">跟进</button>
              <button class="btn btn-primary flex-1" :disabled="acting" @click="doClose(r)">办结关闭</button>
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
  data() { return { list: null, state: 'loading', acting: false } },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    load(done) {
      this.state = 'loading'
      teacherApi.getInternshipRisks().then((d) => {
        this.list = (d && d.list) || []
        this.state = 'ready'
      }).catch(() => { this.state = 'error' }).finally(() => { if (done) done() })
    },
    doHandle(r) {
      uni.showModal({
        title: '受理风险', editable: true, placeholderText: '受理意见（不少于 5 字）',
        success: (res) => {
          if (!res.confirm) return
          const comment = String(res.content || '').trim()
          if (comment.length < 5) return toast('受理意见不少于 5 字')
          this.acting = true
          teacherApi.handleInternshipRisk(r.id, { comment }).then(() => {
            toast('已受理'); this.load()
          }).catch((e) => toast((e && e.message) || '受理失败')).finally(() => { this.acting = false })
        }
      })
    },
    doFollow(r) {
      uni.showModal({
        title: '跟进记录', editable: true, placeholderText: '跟进说明',
        success: (res) => {
          if (!res.confirm) return
          const note = String(res.content || '').trim()
          if (note.length < 2) return toast('跟进说明必填')
          this.acting = true
          teacherApi.followInternshipRisk(r.id, note).then(() => {
            toast('已跟进'); this.load()
          }).catch((e) => toast((e && e.message) || '跟进失败')).finally(() => { this.acting = false })
        }
      })
    },
    doClose(r) {
      uni.showModal({
        title: '办结关闭', editable: true, placeholderText: '关闭说明（不少于 5 字）',
        success: (res) => {
          if (!res.confirm) return
          const comment = String(res.content || '').trim()
          if (comment.length < 5) return toast('关闭说明不少于 5 字')
          this.acting = true
          teacherApi.closeInternshipRisk(r.id, { result: 'RESOLVED', comment }).then(() => {
            toast('已关闭'); this.load()
          }).catch((e) => toast((e && e.message) || '关闭失败')).finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.ir__sub { display: block; margin-top: 4px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ir__row { display: flex; gap: 8px; margin-top: 8px; }
.ir__k { width: 40px; color: var(--text-tertiary); font-size: var(--font-size-sm); }
.ir__actions { display: flex; gap: 8px; margin-top: 12px; }
</style>
