<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data">
        <view class="ma__tabs page-pad">
          <MobileSegmented :items="data.tabs" v-model="tab" />
        </view>
        <view class="page-pad" style="padding-top:0;">
          <MobileGlobalState v-if="!filtered.length" state="empty" title="暂无相关申请" description="切换其他分类查看，或到服务大厅发起新申请。" />
          <view v-else class="stack">
            <view v-for="a in pagedSlice(filtered)" :key="a.id" class="ma__item card" @click="detail(a)">
              <view class="row-between">
                <text class="t-md t-bold flex-1 ellipsis">{{ a.name }}</text>
                <MobileStatusTag :status="a.status" />
              </view>
              <text class="ma__no">单号 {{ a.no }}</text>
              <view class="ma__meta">
                <text class="ma__meta-item">{{ a.dept }}</text>
                <text class="ma__meta-item">申请 {{ a.applyTime.slice(5, 16) }}</text>
                <text class="ma__meta-item">预计 {{ a.eta }}</text>
              </view>
              <view class="ma__opinion" :class="{ 'is-return': a.status === 'RETURNED', 'is-reject': a.status === 'REJECTED' }">
                <text class="ma__opinion-label">最新处理</text>
                <text class="ma__opinion-text flex-1">{{ a.lastOpinion }}</text>
              </view>
              <view class="ma__actions">
                <text v-if="a.status === 'RETURNED'" class="ma__btn is-primary" @click.stop="resubmit(a)">重新提交</text>
                <text v-if="a.hasResult" class="ma__btn" @click.stop="toast('结果凭证下载即将开放')">结果凭证</text>
                <text class="ma__btn" @click.stop="detail(a)">办理详情</text>
              </view>
            </view>
            <view v-if="pagedFooter(filtered) === 'more'" class="ma__paging" @click="pagedLoadMore">上拉加载更多</view>
            <view v-else-if="pagedFooter(filtered) === 'end'" class="ma__paging is-end">没有更多了</view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { useSubmissionsStore } from '@/stores/submissions'
import { listPaging } from '@/utils/listPaging'
import { toast } from '@/utils/nav'
export default {
  mixins: [listPaging(20)],
  data() { return { data: null, state: 'loading', tab: 'all' } },
  onLoad() { this.load() },
  // onReachBottom 必须写在页面本身，mp-weixin 才会注册
  onReachBottom() { this.pagedReachBottom() },
  watch: {
    tab() { this.pagedReset() }
  },
  computed: {
    allItems() {
      const mine = useSubmissionsStore().applications || []
      const base = (this.data && this.data.list) || []
      return [...mine, ...base]
    },
    filtered() {
      if (!this.data) return []
      return this.tab === 'all' ? this.allItems : this.allItems.filter((a) => a.group === this.tab)
    }
  },
  methods: {
    toast,
    pagingList() { return this.filtered },
    load() {
      this.state = 'loading'
      this.pagedReset()
      studentApi.getApplications().then((d) => { this.data = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    detail(a) { toast(a.name + '：' + (a.statusText || a.status || '处理中') + (a.lastOpinion ? '，意见：' + a.lastOpinion : '')) },
    resubmit(a) {
      uni.navigateTo({ url: '/pages/student/service-apply/index?name=' + encodeURIComponent(a.name || '服务申请') })
    }
  }
}
</script>

<style scoped>
.ma__tabs { padding-bottom: var(--space-3); }
.ma__no { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 4px; }
.ma__meta { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-top: var(--space-2); }
.ma__meta-item { font-size: var(--font-size-sm); color: var(--text-secondary); }
.ma__opinion { display: flex; gap: var(--space-2); margin-top: var(--space-3); background: var(--gray-50); border-radius: var(--radius-base); padding: var(--space-2) var(--space-3); }
.ma__opinion.is-return { background: var(--warning-50); }
.ma__opinion.is-reject { background: var(--danger-50); }
.ma__opinion-label { font-size: var(--font-size-xs); color: var(--text-tertiary); flex-shrink: 0; }
.ma__opinion-text { font-size: var(--font-size-sm); color: var(--text-secondary); }
.ma__actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
.ma__btn { font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 5px 12px; }
.ma__btn.is-primary { color: var(--brand-primary); border-color: var(--brand-primary); }
.ma__paging { text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-sm); color: var(--brand-primary); }
.ma__paging.is-end { color: var(--text-tertiary); }
</style>
