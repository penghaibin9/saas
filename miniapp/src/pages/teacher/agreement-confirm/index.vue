<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="三方协议学校确认" subtitle="企业签署由学校代录纸质件 · 确认后生效" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待确认协议"
          description="学校代录企业纸质签署并上传扫描件后，待学校确认的协议会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="a in list" :key="a.id" class="card ac">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ a.studentName || '—' }}</text>
                <text class="ac__sub">{{ a.studentNo || '' }} · {{ a.enterpriseName || '—' }} · {{ a.positionName || '—' }}</text>
              </view>
              <MobileStatusTag label="待学校确认" type="warning" />
            </view>
            <view class="ac__confirms">
              <text class="ac__confirm-item">学生 {{ a.studentConfirmLabel }}</text>
              <text class="ac__confirm-item">企业 {{ a.enterpriseConfirmLabel }}</text>
              <text class="ac__confirm-item" :class="{ 'ac__confirm-warn': !a.hasFile }">{{ a.hasFile ? '已上传签署扫描件' : '未上传扫描件' }}</text>
            </view>
            <button class="btn btn-primary" :disabled="acting" @click="confirm(a)">确认生效</button>
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
      teacherApi.getAgreementPendingSchool()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    confirm(a) {
      if (this.acting) return
      uni.showModal({
        title: '确认协议生效',
        content: `确认「${a.studentName}」与「${a.enterpriseName}」的三方协议？确认后立即生效，不可撤销。`,
        success: (r) => {
          if (!r.confirm) return
          this.acting = true
          teacherApi.confirmAgreementSchool(a.id)
            .then(() => { toast('已确认生效'); this.load() })
            .catch((e) => {
              const code = e && String(e.code)
              if (code === 'DATA_CONFLICT') { toast((e && e.message) || '当前状态不可确认，正在刷新'); this.load() }
              else if (code && code.startsWith('403')) toast((e && e.message) || '不在你的数据范围内')
              else toast((e && e.message) || '确认失败，请重试')
            })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.ac { display: flex; flex-direction: column; gap: var(--space-2); }
.ac__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ac__confirms { display: flex; flex-wrap: wrap; gap: var(--space-3); background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.ac__confirm-item { font-size: var(--font-size-xs); color: var(--text-secondary); }
.ac__confirm-warn { color: var(--danger-600); }
</style>
