<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="转交学生" subtitle="把本人负责的学生转给其他就业老师" show-back />

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无本人负责的学生"
          description="当前没有分配到你名下的就业学生。" />
        <view class="stack" v-else>
          <view v-for="s in list" :key="s.id" class="card et">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ s.name }}</text>
                <text class="et__sub">{{ s.studentNo || '' }} · {{ s.className || '' }}</text>
              </view>
              <button class="et__btn" :disabled="acting" @click="doTransfer(s)">转交</button>
            </view>
            <view class="et__row" v-if="s.destinationLabel"><text class="et__row-k">去向</text><text class="flex-1 t-sm">{{ s.destinationLabel }}</text></view>
          </view>
        </view>
        <view class="et__note">仅可转交当前由本人负责的学生；转交后该学生归属新就业老师。</view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'

export default {
  data() { return { list: [], state: 'loading', acting: false } },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    load(done) {
      this.state = 'loading'
      teacherApi.getEmploymentMyStudents().then((d) => {
        this.list = (d && d.list) || []
        this.state = 'ready'
      }).catch(() => { this.state = 'error' }).finally(() => { if (done) done() })
    },
    doTransfer(s) {
      if (this.acting) return
      uni.showModal({
        title: '转交学生', editable: true,
        placeholderText: '请输入接收就业老师姓名', content: '',
        success: (r) => {
          if (!r.confirm) return
          const newTeacher = (r.content || '').trim()
          if (!newTeacher) { toast('请填写接收就业老师姓名'); return }
          this.acting = true
          teacherApi.transferEmploymentStudent(s.id, newTeacher)
            .then(() => { toast('已转交'); this.load() })
            .catch((e) => {
              const code = e && String(e.code)
              if (code && code.startsWith('403')) toast((e && e.message) || '只能转交本人负责的学生')
              else toast((e && e.message) || '转交失败，请重试')
            })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.et { display: flex; flex-direction: column; gap: var(--space-2); }
.et__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.et__row { display: flex; gap: var(--space-3); }
.et__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 40px; flex-shrink: 0; }
.et__btn { font-size: var(--font-size-sm); color: #fff; background: var(--teacher-600); border-radius: var(--radius-md); padding: 4px 14px; line-height: 1.6; }
.et__btn::after { border: none; }
.et__note { margin-top: var(--space-3); font-size: var(--font-size-xs); color: var(--text-tertiary); line-height: 1.6; }
</style>
