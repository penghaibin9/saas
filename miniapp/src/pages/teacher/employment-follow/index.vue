<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data">
        <!-- 就业概览 -->
        <view class="page-pad">
          <view class="ef__stats card">
            <view class="ef__stat"><text class="ef__stat-val">{{ data.stats.rate }}%</text><text class="ef__stat-label">就业率</text></view>
            <view class="ef__stat"><text class="ef__stat-val">{{ data.stats.employed }}</text><text class="ef__stat-label">已就业</text></view>
            <view class="ef__stat"><text class="ef__stat-val is-warn">{{ data.stats.unemployed }}</text><text class="ef__stat-label">未就业</text></view>
            <view class="ef__stat"><text class="ef__stat-val">{{ data.stats.verified }}</text><text class="ef__stat-label">已核验</text></view>
          </view>
          <MobileSegmented :items="data.tabs" v-model="tab" style="margin-top:12px;" />
        </view>

        <view class="page-pad" style="padding-top:0;">
          <MobileGlobalState v-if="!filtered.length" state="empty" title="暂无学生" description="切换其他分类查看。" />
          <view v-else class="stack-sm">
            <view v-for="s in pagedSlice(filtered)" :key="s.id" class="ef card">
              <view class="row-between">
                <view class="flex-1">
                  <text class="t-md t-bold">{{ s.name }}</text>
                  <text class="ef__class">{{ s.className }}</text>
                </view>
                <MobileStatusTag :status="s.status" />
              </view>
              <view class="ef__info">
                <text class="ef__info-item">意向 {{ s.intention }}</text>
                <text v-if="s.company" class="ef__info-item">{{ s.company }}</text>
                <text v-if="s.city !== '—'" class="ef__info-item">{{ s.city }}</text>
              </view>
              <view class="ef__last">
                <text class="ef__last-label">联系 {{ s.contactTimes }} 次</text>
                <text class="ef__last-text flex-1">{{ s.last }}</text>
              </view>
              <view class="ef__actions">
                <text class="ef__btn" @click="contact(s)">跟进联系</text>
                <text v-if="s.group === 'unemployed'" class="ef__btn is-primary" @click="recommend(s)">推荐岗位</text>
                <text v-if="s.group === 'verify'" class="ef__btn is-primary" @click="verify(s)">去核验</text>
              </view>
            </view>
            <view v-if="pagedFooter(filtered) === 'more'" class="ef__paging" @click="pagedLoadMore">上拉加载更多</view>
            <view v-else-if="pagedFooter(filtered) === 'end'" class="ef__paging is-end">没有更多了</view>
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
  data() { return { data: null, state: 'loading', tab: 'unemployed', acting: false } },
  onLoad() { this.load() },
  // onReachBottom 必须写在页面本身，mp-weixin 才会注册
  onReachBottom() { this.pagedReachBottom() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  watch: {
    tab() { this.pagedReset() }
  },
  computed: {
    filtered() {
      if (!this.data) return []
      return this.data.list.filter((s) => s.group === this.tab)
    }
  },
  methods: {
    pagingList() { return this.filtered },
    load(done) {
      this.state = 'loading'
      this.pagedReset()
      teacherApi.getEmployment().then((d) => { this.data = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    /** 跟进联系：填写跟进内容 → 真实写入就业跟进记录（后端范围校验 + 审计） */
    contact(s) {
      if (this.acting) return
      uni.showModal({
        title: '记录跟进 · ' + s.name, editable: true,
        placeholderText: '填写本次联系内容（如电话沟通就业意向）',
        success: (r) => {
          if (!r.confirm || this.acting) return
          if (!r.content || r.content.trim().length < 2) {
            toast('请填写跟进内容')
            return
          }
          if (!/^\d+$/.test(String(s.id))) {
            toast('当前为离线数据，无法记录跟进，请恢复网络后重试')
            return
          }
          this.acting = true
          teacherApi.createFollowup({ studentId: s.id, way: 'PHONE', content: r.content.trim() })
            .then(() => {
              s.contactTimes = (s.contactTimes || 0) + 1
              s.last = r.content.trim()
              toast('跟进已记录')
            })
            .catch((e) => toast(normalizeError(e).text))
            .finally(() => { this.acting = false })
        }
      })
    },
    recommend(s) {
      // 推荐岗位属 PC 端完整流程；移动端引导记录一次“岗位推荐”跟进，不做假成功
      this.contact(s)
    },
    verify(s) { toast('去向核验需在 PC 端完成材料核对') }
  }
}
</script>

<style scoped>
.ef__stats { display: flex; }
.ef__stat { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px; }
.ef__stat-val { font-size: var(--font-size-metric-sm); font-weight: var(--font-weight-semibold); color: var(--teacher-700); }
.ef__stat-val.is-warn { color: var(--warning-600); }
.ef__stat-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ef__class { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ef__info { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
.ef__info-item { font-size: var(--font-size-sm); color: var(--text-secondary); background: var(--gray-100); padding: 2px 8px; border-radius: var(--radius-full); }
.ef__last { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
.ef__last-label { font-size: var(--font-size-xs); color: var(--text-tertiary); flex-shrink: 0; }
.ef__last-text { font-size: var(--font-size-sm); color: var(--text-secondary); }
.ef__actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
.ef__btn { font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 5px 12px; }
.ef__btn.is-primary { color: #fff; background: var(--teacher-600); border-color: var(--teacher-600); }
.ef__paging { text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-sm); color: var(--teacher-700); }
.ef__paging.is-end { color: var(--text-tertiary); }
</style>
