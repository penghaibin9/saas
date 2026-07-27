<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="答辩评分" subtitle="本人担任评委的答辩学生" show-back />
    <MobileGlobalState :state="state" :description="loadError" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待评分学生"
          description="答辩安排发布后，本人所在评委面板的学生会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="d in list" :key="d.gdStudentId" class="card ds">
            <view class="row-between" @click="toggle(d)">
              <view class="flex-1">
                <text class="t-md t-bold">{{ d.studentName || '—' }}</text>
                <text class="ds__sub">{{ d.studentNo || '' }} · {{ d.groupName }} · {{ d.defenseDate }} {{ d.location }}</text>
              </view>
              <MobileStatusTag :label="d.myStatusLabel" :type="statusTone(d.myStatus)" />
            </view>
            <text class="ds__topic">{{ d.topicTitle }}</text>

            <template v-if="expanded === d.gdStudentId">
              <view class="ds__row">
                <text class="ds__row-k">缺席</text>
                <switch :checked="drafts[d.gdStudentId].absent" color="var(--danger-500)"
                  @change="(e) => drafts[d.gdStudentId].absent = e.detail.value" />
              </view>
              <view class="ds__row" v-if="!drafts[d.gdStudentId].absent">
                <text class="ds__row-k">评分</text>
                <input class="ds__input" type="number" v-model="drafts[d.gdStudentId].score" placeholder="0-100" />
              </view>
              <view class="ds__row ds__row--top" v-if="drafts[d.gdStudentId].absent">
                <text class="ds__row-k">缺席原因</text>
                <textarea class="ds__textarea ds__textarea--sm" v-model="drafts[d.gdStudentId].absentReason"
                  :maxlength="200" placeholder="请填写缺席原因（必填）" placeholder-class="ds__ph" />
              </view>
              <view class="ds__row ds__row--top">
                <text class="ds__row-k">评语</text>
                <textarea class="ds__textarea" v-model="drafts[d.gdStudentId].comment" :maxlength="500"
                  placeholder="可选" placeholder-class="ds__ph" />
              </view>
              <button class="btn btn-primary" :disabled="acting" @click="submit(d)">
                {{ d.myStatus === 'PENDING' ? '提交评分' : '更新评分' }}
              </button>
            </template>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'

function errorText(error) {
  const code = String(error?.code || '')
  if (code.startsWith('403') || code === 'NO_PERMISSION' || code === 'NO_DATA_SCOPE') {
    return error?.message || '当前账号没有答辩评分权限，或尚未绑定稳定评委身份'
  }
  if (code.startsWith('409') || code === 'DATA_CONFLICT') {
    return error?.message || '答辩安排已变化，请刷新后重试'
  }
  return error?.message || '答辩评分队列加载失败，请检查网络后重试'
}

export default {
  data() {
    return {
      list: null, state: 'loading', loadError: '', expanded: null, drafts: {}, acting: false
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    statusTone(s) { return s === 'CONFIRMED' ? 'success' : s === 'SCORED' ? 'warning' : 'default' },
    load(done) {
      this.state = 'loading'
      this.loadError = ''
      teacherApi.getGraduationDefenseScorePending()
        .then((d) => { this.list = Array.isArray(d) ? d : []; this.state = 'ready' })
        .catch((e) => {
          this.list = null
          this.loadError = errorText(e)
          this.state = 'error'
        })
        .finally(() => { if (done) done() })
    },
    toggle(d) {
      if (d.myStatus === 'CONFIRMED') { toast('已确认成绩，不可再修改'); return }
      if (this.expanded === d.gdStudentId) { this.expanded = null; return }
      this.expanded = d.gdStudentId
      if (!this.drafts[d.gdStudentId]) {
        const draft = {
          score: d.myScore != null ? String(d.myScore) : '',
          comment: d.myComment || '',
          absent: !!d.myAbsent,
          absentReason: d.myAbsentReason || ''
        }
        this.$set ? this.$set(this.drafts, d.gdStudentId, draft) : (this.drafts[d.gdStudentId] = draft)
      }
    },
    submit(d) {
      if (this.acting) return
      const draft = this.drafts[d.gdStudentId] || {}
      const body = { comment: (draft.comment || '').trim(), absent: !!draft.absent }
      if (draft.absent) {
        if ((draft.absentReason || '').trim().length < 2) { toast('缺席原因至少 2 个字'); return }
        body.absentReason = draft.absentReason.trim()
      } else {
        const v = draft.score
        if (v === '' || v === null || v === undefined || Number(v) < 0 || Number(v) > 100) {
          toast('评分必须是 0-100 的数字'); return
        }
        body.score = Number(v)
      }
      this.acting = true
      teacherApi.submitGraduationDefenseScore(d.gdStudentId, body)
        .then(() => { toast('已保存'); this.expanded = null; this.load() })
        .catch((e) => {
          const code = String(e?.code || '')
          if (code.startsWith('409') || code === 'DATA_CONFLICT') {
            toast(e?.message || '当前状态不可修改，正在刷新')
            this.load()
          } else {
            toast(errorText(e))
          }
        })
        .finally(() => { this.acting = false })
    }
  }
}
</script>

<style scoped>
.ds { display: flex; flex-direction: column; gap: var(--space-2); }
.ds__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ds__topic { font-size: var(--font-size-sm); color: var(--text-secondary); }
.ds__row { display: flex; align-items: center; justify-content: space-between; min-height: 36px; }
.ds__row--top { flex-direction: column; align-items: stretch; min-height: 0; gap: 4px; }
.ds__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.ds__input { width: 100px; text-align: right; font-size: var(--font-size-base); color: var(--text-primary); }
.ds__textarea { min-height: 56px; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2); }
.ds__textarea--sm { min-height: 44px; }
.ds__ph { color: var(--text-tertiary); }
</style>
