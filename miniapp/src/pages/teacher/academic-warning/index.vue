<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="学业预警待处理" subtitle="本校范围内待处理的学业预警" show-back />

    <view class="aw__filter" v-if="list && list.length">
      <view class="aw__chip" :class="{ 'is-on': levelFilter === 'all' }" @click="levelFilter = 'all'">全部</view>
      <view v-for="lv in levelOptions" :key="lv.key" class="aw__chip" :class="{ 'is-on': levelFilter === lv.key }" @click="levelFilter = lv.key">{{ lv.label }}</view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待处理预警"
          description="学生触发学业预警后会出现在这里，可关闭或升级为风险。" />
        <view class="stack" v-else>
          <view v-for="w in filteredList" :key="w.id" class="card aw">
            <view class="row-between">
              <view class="flex-1">
                <view class="row" style="gap:6px;">
                  <text class="t-md t-bold">{{ w.name || '—' }}</text>
                  <MobileStatusTag :label="w.levelLabel || w.level" :type="levelTone(w.level)" />
                </view>
                <text class="aw__sub">{{ w.className || '' }} · {{ w.typeLabel || w.type }}</text>
              </view>
              <text class="aw__time">{{ (w.triggerTime || '').slice(5, 16) }}</text>
            </view>
            <view class="aw__reason" v-if="w.reason"><text class="flex-1 t-sm">{{ w.reason }}</text></view>
            <view class="aw__meta">
              <text class="aw__meta-item" v-if="w.deadline">处理时限 {{ w.deadline }}</text>
              <text class="aw__meta-item" v-if="w.remindCount">已催办 {{ w.remindCount }} 次</text>
              <text class="aw__meta-item aw__meta-status">{{ w.statusLabel || w.status }}</text>
            </view>
            <view class="aw__actions" v-if="w.status === 'PENDING_HANDLE' || w.status === 'ACTIVE'">
              <button class="aw__escalate flex-1" @click="handle(w, 'ESCALATE')">升级为风险</button>
              <button class="aw__close flex-1" @click="handle(w, 'CLOSE')">关闭预警</button>
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

const LEVELS = [{ key: 'HIGH', label: '高' }, { key: 'MEDIUM', label: '中' }, { key: 'LOW', label: '低' }]

export default {
  data() { return { list: null, state: 'loading', acting: false, levelFilter: 'all' } },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    levelOptions() {
      if (!this.list) return []
      const has = new Set(this.list.map((w) => w.level))
      return LEVELS.filter((l) => has.has(l.key))
    },
    filteredList() {
      if (!this.list) return []
      return this.levelFilter === 'all' ? this.list : this.list.filter((w) => w.level === this.levelFilter)
    }
  },
  methods: {
    levelTone(lv) { return lv === 'HIGH' ? 'danger' : lv === 'MEDIUM' ? 'warning' : 'default' },
    load(done) {
      this.state = 'loading'
      teacherApi.getAcademicWarnings()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    handle(w, action) {
      if (this.acting) return
      const close = action === 'CLOSE'
      uni.showModal({
        title: close ? '关闭预警' : '升级为风险',
        editable: true,
        placeholderText: close ? '请填写处理结论（≥5 字）' : '请填写升级说明（≥5 字）',
        content: '',
        success: (r) => {
          if (!r.confirm) return
          const note = (r.content || '').trim()
          if (note.length < 5) { toast('说明至少 5 个字'); return }
          this.acting = true
          teacherApi.handleWarning(w.id, action, note)
            .then(() => { toast(close ? '预警已关闭' : '已升级为风险'); this.load() })
            .catch((e) => {
              const code = e && String(e.code)
              if (code && code.startsWith('409')) { toast('该预警已被处理，正在刷新'); this.load() }
              else if (code && code.startsWith('403')) toast((e && e.message) || '不在你的数据范围内')
              else toast((e && e.message) || '处理失败，请重试')
            })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.aw__filter { display: flex; gap: var(--space-2); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.aw__chip { font-size: var(--font-size-sm); padding: 6px 13px; border-radius: var(--radius-full); background: var(--gray-50); color: var(--text-secondary); font-weight: var(--font-weight-medium); }
.aw__chip.is-on { background: var(--teacher-600); color: #fff; }
.aw { display: flex; flex-direction: column; gap: var(--space-2); }
.aw__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.aw__time { font-size: var(--font-size-xs); color: var(--text-tertiary); flex-shrink: 0; }
.aw__reason { background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.aw__meta { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.aw__meta-item { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.aw__meta-status { color: var(--teacher-700); font-weight: var(--font-weight-medium); }
.aw__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.aw__escalate { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.aw__escalate::after { border: none; }
.aw__close { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.aw__close::after { border: none; }
</style>
