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
            <view v-for="s in filtered" :key="s.id" class="ef card">
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
  data() { return { data: null, state: 'loading', tab: 'unemployed' } },
  onLoad() { this.load() },
  computed: {
    filtered() {
      if (!this.data) return []
      return this.data.list.filter((s) => s.group === this.tab)
    }
  },
  methods: {
    load() {
      this.state = 'loading'
      teacherApi.getEmployment().then((d) => { this.data = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    contact(s) { uni.makePhoneCall({ phoneNumber: '13600000000', fail: () => toast('联系 ' + s.name + '（演示）') }) },
    recommend(s) { toast('为 ' + s.name + ' 推荐岗位（演示）') },
    verify(s) { toast('核验 ' + s.name + ' 就业去向（演示）') }
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
</style>
