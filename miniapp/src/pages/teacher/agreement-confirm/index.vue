<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="三方协议办理进度" subtitle="指导教师查看进度 · 学校终审在管理端完成" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileInlineAlert type="info" description="指导教师负责跟进学生与企业材料，学校确认生效属于终审动作，仅在学校管理端办理。" />
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待学校确认协议"
          description="学生与企业完成确认并上传签署扫描件后，协议会进入学校终审队列。" />
        <view class="stack" v-else>
          <view v-for="a in list" :key="a.id" class="card ac">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ a.studentName || '—' }}</text>
                <text class="ac__sub">{{ a.studentNo || '' }} · {{ a.enterpriseName || '—' }} · {{ a.positionName || '—' }}</text>
              </view>
              <MobileStatusTag label="待学校终审" type="warning" />
            </view>
            <view class="ac__confirms">
              <text class="ac__confirm-item">学生 {{ a.studentConfirmLabel }}</text>
              <text class="ac__confirm-item">企业 {{ a.enterpriseConfirmLabel }}</text>
              <text class="ac__confirm-item" :class="{ 'ac__confirm-warn': !a.hasFile }">{{ a.hasFile ? '已上传签署扫描件' : '未上传扫描件' }}</text>
            </view>
            <text class="ac__hint">{{ a.hasFile ? '材料已进入学校管理端终审队列' : '请提醒补齐企业签署扫描件后再送学校终审' }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'

export default {
  data() { return { list: null, state: 'loading' } },
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
.ac__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); }
</style>
