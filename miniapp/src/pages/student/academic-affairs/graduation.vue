<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="毕业进度" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <view class="gr__empty" v-if="!data.hasAudit"><text>{{ data.note || '尚未纳入毕业预审' }}</text></view>
        <template v-else>
          <view class="gr__overall" :class="data.overall === 'SYSTEM_PASSED' ? 'is-ok' : 'is-warn'">
            <text class="gr__overall-t">{{ data.overall === 'SYSTEM_PASSED' ? '预审通过' : '存在待完善项' }}</text>
            <text class="gr__overall-c" v-if="data.conclusion">结论：{{ concText(data.conclusion) }}</text>
          </view>
          <view class="stack">
            <view v-for="it in data.items" :key="it.item" class="gr__item">
              <text class="gr__item-name">{{ ITEM[it.item] || it.item }}</text>
              <view class="gr__item-r">
                <text class="gr__badge" :class="badge(it.result)">{{ res(it.result) }}</text>
                <text class="gr__ev">{{ it.evidence }}</text>
              </view>
            </view>
          </view>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
const ITEM = { STATUS: '学籍在籍', CREDIT: '学分达标', INTERNSHIP: '岗位实习', GRADUATION_DESIGN: '毕业设计',
  DISCIPLINE: '处分情况', EMPLOYMENT: '就业填报', ARCHIVE: '档案归档' }
const CONC = { GRADUATED: '毕业', COMPLETED: '结业', DELAYED: '延期毕业' }
export default {
  data() { return { data: null, state: 'loading', ITEM } },
  onLoad() { this.load() },
  methods: {
    res(r) { return r === 'PASS' ? '通过' : r === 'FAIL' ? '未达标' : '待核' },
    concText(c) { return CONC[c] || c },
    badge(r) { return r === 'PASS' ? 'is-ok' : r === 'FAIL' ? 'is-bad' : 'is-wait' },
    load() {
      this.state = 'loading'
      studentApi.getMyGraduation().then((d) => { this.data = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.gr__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.gr__overall { border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-4); color: #fff; }
.gr__overall.is-ok { background: #16a34a; }
.gr__overall.is-warn { background: #d97706; }
.gr__overall-t { display: block; font-size: 18px; font-weight: 700; }
.gr__overall-c { display: block; margin-top: 4px; font-size: var(--font-size-sm); opacity: 0.9; }
.gr__item { background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3) var(--space-4); margin-bottom: var(--space-2); box-shadow: var(--shadow-card); }
.gr__item-name { display: block; font-weight: 600; margin-bottom: 4px; }
.gr__item-r { display: flex; align-items: center; gap: var(--space-2); }
.gr__badge { font-size: var(--font-size-xs); padding: 2px 10px; border-radius: var(--radius-full); }
.gr__badge.is-ok { background: rgba(34,197,94,0.14); color: #16a34a; }
.gr__badge.is-bad { background: rgba(239,68,68,0.14); color: #dc2626; }
.gr__badge.is-wait { background: rgba(234,179,8,0.16); color: #b45309; }
.gr__ev { font-size: var(--font-size-sm); color: var(--text-tertiary); }
</style>
