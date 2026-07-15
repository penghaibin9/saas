<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="发布通知" show-back />
    <view class="page-pad stack">
      <view class="card stack-sm">
        <input class="np__input" v-model="form.title" placeholder="通知标题（必填）" placeholder-class="np__ph" />
        <textarea class="np__textarea" v-model="form.content" :maxlength="500"
                  placeholder="通知内容（必填，不少于5字）" placeholder-class="np__ph" />

        <text class="np__label">接收范围</text>
        <view class="np__scopes">
          <text class="np__scope" :class="{ 'is-on': form.scopeType === 'CLASS' }" @click="form.scopeType = 'CLASS'">按班级</text>
          <text v-if="isAdmin" class="np__scope" :class="{ 'is-on': form.scopeType === 'COLLEGE' }" @click="form.scopeType = 'COLLEGE'">按学院</text>
          <text v-if="isAdmin" class="np__scope" :class="{ 'is-on': form.scopeType === 'SCHOOL' }" @click="form.scopeType = 'SCHOOL'">全校</text>
        </view>

        <template v-if="form.scopeType === 'CLASS'">
          <MobileGlobalState v-if="!myClasses.length" state="empty" title="暂无负责班级" description="如信息有误请联系系统管理员核实。" />
          <picker v-else mode="selector" :range="myClasses" range-key="className" @change="onClassChange">
            <view class="np__input">{{ selectedClassLabel }}</view>
          </picker>
        </template>
        <template v-else-if="form.scopeType === 'COLLEGE'">
          <input class="np__input" type="number" v-model="form.collegeId" placeholder="学院ID（必填）" placeholder-class="np__ph" />
        </template>
        <text v-else-if="form.scopeType === 'SCHOOL'" class="np__hint">将发送给全校在校学生，请谨慎操作。</text>

        <button class="btn btn-primary" :disabled="submitting || !canSubmit" @click="submit">
          {{ submitting ? '发布中…' : '发布通知' }}
        </button>
      </view>
    </view>
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const ADMIN_ROLES = ['college_admin', 'academic']

export default {
  data() {
    return {
      isAdmin: false, myClasses: [], selectedClassId: '', submitting: false,
      form: { title: '', content: '', scopeType: 'CLASS', collegeId: '' }
    }
  },
  computed: {
    selectedClassLabel() {
      const c = this.myClasses.find((x) => x.classId === this.selectedClassId)
      return c ? c.className : '选择班级'
    },
    canSubmit() {
      if (!this.form.title.trim() || this.form.content.trim().length < 5) return false
      if (this.form.scopeType === 'CLASS') return !!this.selectedClassId
      if (this.form.scopeType === 'COLLEGE') return !!this.form.collegeId
      return this.form.scopeType === 'SCHOOL'
    }
  },
  onLoad() {
    this.isAdmin = ADMIN_ROLES.includes(useSessionStore().currentRole)
    teacherApi.getMyClasses().then((d) => { this.myClasses = (d && d.items) || [] }).catch(() => {})
  },
  methods: {
    onClassChange(e) { this.selectedClassId = this.myClasses[e.detail.value].classId },
    submit() {
      if (this.submitting || !this.canSubmit) return
      this.submitting = true
      const body = { title: this.form.title.trim(), content: this.form.content.trim(), scopeType: this.form.scopeType }
      if (this.form.scopeType === 'CLASS') body.classId = this.selectedClassId
      if (this.form.scopeType === 'COLLEGE') body.collegeId = this.form.collegeId
      teacherApi.publishNotice(body).then((d) => {
        uni.showToast({ title: `已发布给 ${d.recipientCount} 名学生`, icon: 'success' })
        this.form = { title: '', content: '', scopeType: 'CLASS', collegeId: '' }
        this.selectedClassId = ''
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '发布失败，请稍后重试'))
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.np__input { width: 100%; height: 40px; line-height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.np__textarea { width: 100%; min-height: 100px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; }
.np__ph { color: var(--text-tertiary); }
.np__label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.np__scopes { display: flex; gap: var(--space-2); }
.np__scope { padding: 6px 16px; border-radius: var(--radius-full); background: var(--bg-secondary); font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); }
.np__scope.is-on { background: var(--teacher-600); color: #fff; border-color: var(--teacher-600); }
.np__hint { display: block; font-size: var(--font-size-sm); color: var(--warning-700); }
</style>
