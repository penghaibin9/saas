<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习申请审核" subtitle="本人指导学生的正式实习申请" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待审申请"
          description="本人指导学生提交正式实习申请后会出现在这里，通过后自动落岗。" />
        <view class="stack" v-else>
          <view v-for="a in list" :key="a.id" class="card ap">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ a.studentName || '—' }}</text>
                <text class="ap__sub">{{ a.studentNo || '' }} · {{ a.applicationTypeLabel }}</text>
              </view>
              <MobileStatusTag :label="a.statusLabel" type="warning" />
            </view>
            <view class="ap__row"><text class="ap__row-k">企业/岗位</text><text class="flex-1 t-sm">{{ a.companyName || '—' }} · {{ a.positionName || '—' }}</text></view>
            <view class="ap__row" v-if="a.workAddress"><text class="ap__row-k">工作地点</text><text class="flex-1 t-sm">{{ a.workAddress }}</text></view>
            <view class="ap__row" v-if="a.contactName"><text class="ap__row-k">联系人</text><text class="flex-1 t-sm">{{ a.contactName }} {{ a.contactPhone }}</text></view>
            <view class="ap__row" v-if="a.applicationNote"><text class="ap__row-k">说明</text><text class="flex-1 t-sm">{{ a.applicationNote }}</text></view>
            <text class="ap__file" v-if="a.evidenceFileId">已上传证明材料</text>
            <view class="ap__actions">
              <button class="ap__reject flex-1" :disabled="acting" @click="review(a, 'REJECT')">驳回</button>
              <button class="ap__approve flex-1" :disabled="acting" @click="review(a, 'APPROVE')">通过</button>
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
      teacherApi.getInternshipApplicationPending()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    review(a, action) {
      if (this.acting) return
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回申请' : '通过申请',
        editable: true, placeholderText: reject ? '请填写驳回原因（≥5 字）' : '可填写审核意见（可选）',
        content: '',
        success: (r) => {
          if (!r.confirm) return
          const comment = (r.content || '').trim()
          if (reject && comment.length < 5) { toast('驳回原因至少 5 个字'); return }
          this.acting = true
          teacherApi.reviewInternshipApplication(a.id, action, comment)
            .then(() => { toast(reject ? '已驳回' : '已通过并落岗'); this.load() })
            .catch((e) => {
              const code = e && String(e.code)
              if (code === 'DATA_CONFLICT') { toast((e && e.message) || '该申请已被处理，正在刷新'); this.load() }
              else if (code && code.startsWith('403')) toast((e && e.message) || '不在你的数据范围内')
              else toast((e && e.message) || (reject ? '驳回' : '通过') + '失败，请重试')
            })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.ap { display: flex; flex-direction: column; gap: var(--space-2); }
.ap__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ap__row { display: flex; gap: var(--space-3); }
.ap__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 64px; flex-shrink: 0; }
.ap__file { font-size: var(--font-size-xs); color: var(--success-600); }
.ap__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.ap__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.ap__reject::after { border: none; }
.ap__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.ap__approve::after { border: none; }
</style>
