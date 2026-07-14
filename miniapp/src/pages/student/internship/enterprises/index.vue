<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="企业岗位库" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="d">
        <view class="ent__cats">
          <view class="ent__cat" :class="{ 'is-on': city === '' }" @click="city = ''">全部城市</view>
          <view v-for="c in d.cities" :key="c" class="ent__cat" :class="{ 'is-on': city === c }" @click="city = c">{{ c }}</view>
        </view>

        <MobileGlobalState v-if="!filtered.length" state="empty" title="暂无匹配岗位" description="换一个城市试试，或稍后再来看看。" />
        <view v-else class="stack">
          <view v-for="p in filtered" :key="p.id" class="card ent__item">
            <view class="row-between">
              <text class="ent__title">{{ p.title }}</text>
              <text v-if="p.salaryRange" class="ent__salary">{{ p.salaryRange }}</text>
            </view>
            <text class="ent__company">{{ p.companyName }}</text>
            <view class="ent__meta">
              <text class="ent__meta-tag">{{ p.workLocation || '地点面议' }}</text>
              <text class="ent__meta-tag">招 {{ p.remaining }} 人</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
export default {
  data() { return { d: null, state: 'loading', city: '' } },
  onLoad() { this.load() },
  computed: {
    filtered() {
      if (!this.d) return []
      return this.city ? this.d.items.filter((x) => x.workLocation === this.city) : this.d.items
    }
  },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getInternshipEnterprises().then((data) => {
        this.d = data
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.ent__cats { display: flex; gap: var(--space-2); overflow-x: auto; margin-bottom: var(--space-4); }
.ent__cat { flex-shrink: 0; font-size: var(--font-size-sm); padding: 6px 14px; border-radius: var(--radius-full); background: var(--gray-100); color: var(--text-secondary); font-weight: var(--font-weight-medium); }
.ent__cat.is-on { background: var(--brand-primary); color: #fff; }
.ent__title { font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.ent__salary { font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--success-600); background: var(--success-50); padding: 2px 8px; border-radius: var(--radius-base); flex-shrink: 0; }
.ent__company { display: block; margin-top: 4px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.ent__meta { display: flex; gap: var(--space-2); margin-top: var(--space-2); }
.ent__meta-tag { font-size: var(--font-size-xs); color: var(--text-tertiary); background: var(--gray-50); padding: 3px 8px; border-radius: var(--radius-base); }
</style>
