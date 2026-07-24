<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="宿舍待办" subtitle="调宿审批 / 异常处置" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <view class="seg">
          <button class="seg__btn" :class="{ on: tab === 'transfer' }" @click="tab = 'transfer'">调宿待审 ({{ transfers.length }})</button>
          <button class="seg__btn" :class="{ on: tab === 'exception' }" @click="tab = 'exception'">异常待处置 ({{ exceptions.length }})</button>
        </view>

        <MobileGlobalState
          v-if="tab === 'transfer' && !transfers.length"
          state="empty"
          title="暂无调宿待审"
          description="有学生调宿进入辅导员/宿管节点时会出现在这里。"
        />
        <view class="stack" v-else-if="tab === 'transfer'">
          <view v-for="x in transfers" :key="x.transferId" class="card ar">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.realName || '—' }}</text>
                <text class="ar__sub">{{ x.studentNo || '' }} · {{ x.status || x.currentNode || '' }}</text>
              </view>
              <MobileStatusTag :label="x.status || '待审'" type="warning" />
            </view>
            <text class="ar__sub" v-if="x.reason">事由：{{ x.reason }}</text>
            <view class="ar__actions">
              <button class="ar__no flex-1" :disabled="acting" @click="reviewTransfer(x, 'REJECT')">驳回</button>
              <button class="ar__ok flex-1" :disabled="acting" @click="reviewTransfer(x, 'APPROVE')">通过</button>
            </view>
          </view>
        </view>

        <MobileGlobalState
          v-if="tab === 'exception' && !exceptions.length"
          state="empty"
          title="暂无宿舍异常"
          description="查寝异常、夜不归宿等待处置记录会显示在这里。"
        />
        <view class="stack" v-else-if="tab === 'exception'">
          <view v-for="x in exceptions" :key="x.exceptionId" class="card ar">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.realName || '房间级异常' }}</text>
                <text class="ar__sub">{{ x.studentNo || '' }} · {{ x.excType || '异常' }}</text>
              </view>
              <MobileStatusTag :label="x.status || '待处置'" type="warning" />
            </view>
            <text class="ar__sub" v-if="x.detail">{{ x.detail }}</text>
            <button class="ar__ok" style="margin-top:10px" :disabled="acting" @click="handleException(x)">登记处置</button>
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
      state: 'loading', acting: false, tab: 'transfer',
      transfers: [], exceptions: []
    }
  },
  onLoad(q) {
    if (q && q.tab === 'exception') this.tab = 'exception'
    this.load()
  },
  onShow() { if (this.state === 'ready') this.load() },
  methods: {
    load() {
      this.state = 'loading'
      teacherApi.getAffairsDormPending().then((d) => {
        this.transfers = (d && d.transfers) || []
        this.exceptions = (d && d.exceptions) || []
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    reviewTransfer(x, action) {
      const run = (reason) => {
        this.acting = true
        teacherApi.reviewAffairsDormTransfer(x.transferId, { action, reason }).then(() => {
          toast(action === 'APPROVE' ? '已通过' : '已驳回')
          this.load()
        }).catch((e) => {
          toast((e && e.message) || '处理失败')
        }).finally(() => { this.acting = false })
      }
      if (action === 'REJECT') {
        uni.showModal({
          title: '驳回调宿',
          editable: true,
          placeholderText: '驳回原因不少于5字',
          success: (r) => {
            if (!r.confirm) return
            const reason = (r.content || '').trim()
            if (reason.length < 5) return toast('驳回原因至少5字')
            run(reason)
          }
        })
      } else {
        run('')
      }
    },
    handleException(x) {
      uni.showModal({
        title: '处置说明',
        editable: true,
        placeholderText: '处置说明不少于5字',
        success: (r) => {
          if (!r.confirm) return
          const note = (r.content || '').trim()
          if (note.length < 5) return toast('处置说明至少5字')
          this.acting = true
          teacherApi.handleAffairsDormException(x.exceptionId, note).then(() => {
            toast('已处置')
            this.load()
          }).catch((e) => {
            toast((e && e.message) || '处置失败')
          }).finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.seg { display: flex; gap: 8px; margin-bottom: 12px; }
.seg__btn { flex: 1; font-size: 13px; background: #f1f5f9; color: #334155; border: none; border-radius: 8px; padding: 8px; }
.seg__btn.on { background: #2563eb; color: #fff; }
.ar { margin-bottom: 10px; }
.row-between { display: flex; justify-content: space-between; gap: 8px; }
.ar__sub { display: block; font-size: 12px; color: #64748b; margin-top: 4px; }
.ar__actions { display: flex; gap: 8px; margin-top: 10px; }
.ar__ok { background: #16a34a; color: #fff; border: none; border-radius: 8px; padding: 8px; font-size: 13px; }
.ar__no { background: #fee2e2; color: #b91c1c; border: none; border-radius: 8px; padding: 8px; font-size: 13px; }
</style>
