<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="网上选课" back />
    <view class="sl__tabs">
      <text class="sl__tab" :class="{ 'is-active': tab === 'courses' }" @click="tab = 'courses'">可选课程</text>
      <text class="sl__tab" :class="{ 'is-active': tab === 'mine' }" @click="tab = 'mine'">我的选课（{{ mySelected.length }}）</text>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="loaded">
        <template v-if="tab === 'courses'">
          <MobileGlobalState v-if="!groups.length" state="empty" title="暂无开放中的选课批次" description="教务处开放选课后会显示在这里。" />
          <view v-for="g in groups" :key="g.batch.batchId" class="sl__group">
            <view class="section-head"><text class="section-head__title">{{ g.batch.batchName }}</text></view>
            <view class="list-group">
              <view v-for="c in g.courses" :key="c.selectionCourseId" class="list-row">
                <view class="flex-1">
                  <text class="t-md">{{ c.courseName }}</text>
                  <text class="sl__sub">{{ c.teacherName || '—' }} · {{ c.credit }}学分 · 余量{{ c.remain }}/{{ c.capacity }}</text>
                </view>
                <button
                  class="btn sl__btn"
                  :class="isSelected(c) ? 'btn-ghost' : 'btn-primary'"
                  :disabled="acting === c.selectionCourseId || (!isSelected(c) && c.remain <= 0)"
                  @click="isSelected(c) ? drop(c) : enroll(c)"
                >
                  {{ acting === c.selectionCourseId ? '处理中…' : isSelected(c) ? '退课' : (c.remain > 0 ? '选课' : '已满') }}
                </button>
              </view>
            </view>
          </view>
        </template>

        <template v-else>
          <MobileGlobalState v-if="!mySelected.length" state="empty" title="暂无选课记录" description="在「可选课程」中选课后会显示在这里。" />
          <view class="list-group" v-else>
            <view v-for="r in mySelected" :key="r.recordId" class="list-row">
              <view class="flex-1">
                <text class="t-md">{{ r.courseName }}</text>
                <text class="sl__sub">{{ r.credit }}学分 · {{ (r.enrolledAt || '').slice(0, 10) }}</text>
              </view>
              <MobileStatusTag :status="r.status" />
            </view>
          </view>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  data() { return { groups: [], selections: [], state: 'loading', loaded: false, tab: 'courses', acting: null } },
  computed: {
    mySelected() { return this.selections.filter((r) => r.status === 'SELECTED') }
  },
  onLoad() { this.load() },
  methods: {
    isSelected(c) {
      return this.selections.some((r) => r.selectionCourseId === c.selectionCourseId && r.status === 'SELECTED')
    },
    load() {
      this.state = 'loading'
      Promise.all([studentApi.getSelectionCourses(), studentApi.getMySelections()]).then(([groups, selections]) => {
        this.groups = groups || []
        this.selections = selections || []
        this.loaded = true
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    enroll(c) {
      if (this.acting) return
      this.acting = c.selectionCourseId
      studentApi.enrollSelection(c.selectionCourseId).then(() => {
        uni.showToast({ title: '选课成功', icon: 'success' })
        this.load()
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '选课失败，请稍后重试'))
        .finally(() => { this.acting = null })
    },
    drop(c) {
      if (this.acting) return
      this.acting = c.selectionCourseId
      studentApi.dropSelection(c.selectionCourseId).then(() => {
        uni.showToast({ title: '已退课', icon: 'success' })
        this.load()
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '退课失败，请稍后重试'))
        .finally(() => { this.acting = null })
    }
  }
}
</script>

<style scoped>
.sl__tabs { display: flex; background: var(--bg-card); padding: 0 var(--page-padding-mobile); border-bottom: 1px solid var(--border-light); }
.sl__tab { flex: 1; text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-base); color: var(--text-secondary); }
.sl__tab.is-active { color: var(--brand-primary); font-weight: var(--font-weight-semibold); border-bottom: 2px solid var(--brand-primary); }
.sl__group + .sl__group { margin-top: var(--space-4); }
.sl__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.sl__btn { flex-shrink: 0; min-height: 32px; padding: 0 var(--space-3); font-size: var(--font-size-sm); margin-left: var(--space-2); }
</style>
