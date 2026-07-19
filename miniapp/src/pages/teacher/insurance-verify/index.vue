<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习保险核验" subtitle="本人指导学生已提交的保险信息" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待核验保险"
          description="学生提交实习保险信息后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="x in list" :key="x.id" class="card iv">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.studentName || '—' }}</text>
                <text class="iv__sub">{{ x.studentNo || '' }} · {{ x.enterpriseName || '—' }}</text>
              </view>
              <MobileStatusTag :label="x.statusLabel" type="warning" />
            </view>
            <view class="iv__row"><text class="iv__row-k">承保单位</text><text class="flex-1 t-sm">{{ x.insurerName || '—' }}</text></view>
            <view class="iv__row"><text class="iv__row-k">保单号</text><text class="flex-1 t-sm">{{ x.policyNo || '—' }}</text></view>
            <view class="iv__row" v-if="x.coverageType"><text class="iv__row-k">保障类型</text><text class="flex-1 t-sm">{{ x.coverageType }}</text></view>
            <view class="iv__row" v-if="x.effectiveDate"><text class="iv__row-k">保障期</text><text class="flex-1 t-sm">{{ x.effectiveDate }} ~ {{ x.expiryDate || '—' }}</text></view>
            <text class="iv__file" v-if="!x.hasFile">未上传保单附件</text>
            <view class="iv__actions">
              <button class="iv__reject flex-1" :disabled="acting" @click="verify(x, 'REJECT')">驳回</button>
              <button class="iv__approve flex-1" :disabled="acting" @click="verify(x, 'APPROVE')">核验通过</button>
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
      teacherApi.getInsurancePending()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    verify(x, action) {
      if (this.acting) return
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回保险' : '核验通过',
        editable: true, placeholderText: reject ? '请填写驳回原因（≥5 字）' : '可填写核验备注（可选）',
        content: '',
        success: (r) => {
          if (!r.confirm) return
          const comment = (r.content || '').trim()
          if (reject && comment.length < 5) { toast('驳回原因至少 5 个字'); return }
          this.acting = true
          teacherApi.verifyInsurance(x.id, action, comment)
            .then(() => { toast(reject ? '已驳回' : '已核验通过'); this.load() })
            .catch((e) => {
              const code = e && String(e.code)
              if (code === 'DATA_CONFLICT') { toast('该记录已被处理，正在刷新'); this.load() }
              else if (code && code.startsWith('403')) toast((e && e.message) || '不在你的数据范围内')
              else toast((e && e.message) || (reject ? '驳回' : '核验') + '失败，请重试')
            })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.iv { display: flex; flex-direction: column; gap: var(--space-2); }
.iv__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.iv__row { display: flex; gap: var(--space-3); }
.iv__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 64px; flex-shrink: 0; }
.iv__file { font-size: var(--font-size-xs); color: var(--warning-600); }
.iv__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.iv__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.iv__reject::after { border: none; }
.iv__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.iv__approve::after { border: none; }
</style>
