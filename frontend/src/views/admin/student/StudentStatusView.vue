<template>
  <div class="sp-page">
    <AppSectionHeader
      title="学生状态管理"
      subtitle="学籍状态数据管理与状态变更（多角色工作台由 09A 承载，本页只管状态数据）"
    />

    <StudentStateBlock :loading="loading" :error="error" :empty="!all.length" :no-permission="noPermission" @retry="load">
      <div class="sp-grid">
        <AppCard v-for="d in distribution" :key="d.status" class="sp-metric">
          <span class="sp-metric__label">{{ d.label }}</span>
          <span class="sp-metric__value">{{ d.count }}</span>
        </AppCard>
      </div>

      <AppCard class="sp-card">
        <AppSectionHeader title="学生状态列表" compact />
        <table class="sp-table">
          <thead>
            <tr><th>姓名</th><th>学号</th><th>班级</th><th>当前状态</th><th>学业状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="s in pageList" :key="s.studentId">
              <td>{{ s.name }}</td>
              <td>{{ s.studentNo }}</td>
              <td>{{ s.className }}</td>
              <td><StudentStatusTag :status="s.studentStatus" /></td>
              <td>{{ academicText(s.academicStatus) }}</td>
              <td>
                <AppButton
                  variant="secondary"
                  :disabled="!canChange || !allowedNext(s).length"
                  :title="allowedNext(s).length ? '' : '当前状态为终态'"
                  @click="openChange(s)"
                >变更状态</AppButton>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="sp-pager">
          <AppButton variant="ghost" :disabled="page <= 1" @click="turnPage(-1)">上一页</AppButton>
          <span>第 {{ page }} / {{ maxPage }} 页</span>
          <AppButton variant="ghost" :disabled="page >= maxPage" @click="turnPage(1)">下一页</AppButton>
        </div>
      </AppCard>

      <AppCard class="sp-card">
        <AppSectionHeader title="最近状态变更时间线" compact />
        <StudentTimeline :items="recentChanges" />
      </AppCard>
    </StudentStateBlock>

    <AppDrawer :visible="changeVisible" :title="changeTarget ? `变更 ${changeTarget.name} 的学生状态` : '变更状态'" @update:visible="changeVisible = $event">
      <div v-if="changeTarget" class="ss-change">
        <div class="ss-change__row">
          <span class="ss-change__label">当前状态</span>
          <StudentStatusTag :status="changeTarget.studentStatus" />
        </div>
        <div class="ss-change__row">
          <span class="ss-change__label">目标状态</span>
          <select v-model="targetStatus" class="sp-select">
            <option value="">请选择</option>
            <option v-for="st in allowedNext(changeTarget)" :key="st" :value="st">{{ statusText(st) }}</option>
          </select>
        </div>
        <div>
          <span class="ss-change__label">变更原因（必填）</span>
          <textarea v-model="reason" rows="3" class="sp-textarea" placeholder="请填写变更原因，将写入时间线与审计" />
          <div class="sp-count" :class="{ 'is-invalid': !reasonCheck.valid }">
            当前 {{ reasonCheck.length }} 字 / 至少 {{ reasonCheck.minLength }} 字
          </div>
        </div>
        <div class="stu-panel__actions" style="display: flex; justify-content: flex-end; gap: var(--space-3)">
          <AppButton variant="secondary" @click="changeVisible = false">取消</AppButton>
          <AppButton
            variant="primary"
            :disabled="!targetStatus || !reasonCheck.valid || submitting"
            :loading="submitting"
            @click="onChangeConfirm"
          >确认变更</AppButton>
        </div>
      </div>
    </AppDrawer>
  </div>
</template>

<script>
/** 页面 6：/admin/student/status 学生状态管理（只管状态数据，不做 09A 工作台） */
import { AppCard, AppButton, AppDrawer, AppSectionHeader } from '@/components/ui'
import StudentStateBlock from '@/modules/student/components/StudentStateBlock.vue'
import StudentStatusTag from '@/modules/student/components/StudentStatusTag.vue'
import StudentTimeline from '@/modules/student/components/StudentTimeline.vue'
import {
  studentProvider,
  hasStudentPermission,
  STUDENT_PERMISSION,
  STUDENT_STATUS_LABELS,
  formatStudentStatus,
  formatAcademicStatus,
  getAllowedNextStatuses,
  validateStatusChangeReason
} from '@/modules/student'
import { toast } from '@/utils/toast'

export default {
  name: 'StudentStatusView',
  components: { AppCard, AppButton, AppDrawer, AppSectionHeader, StudentStateBlock, StudentStatusTag, StudentTimeline },
  data() {
    return {
      loading: false,
      error: '',
      all: [],
      recentChanges: [],
      page: 1,
      pageSize: 10,
      changeVisible: false,
      changeTarget: null,
      targetStatus: '',
      reason: '',
      submitting: false
    }
  },
  computed: {
    noPermission() {
      return !hasStudentPermission(STUDENT_PERMISSION.PROFILE_VIEW)
    },
    canChange() {
      return hasStudentPermission(STUDENT_PERMISSION.STATUS_UPDATE)
    },
    distribution() {
      return Object.entries(STUDENT_STATUS_LABELS).map(([status, label]) => ({
        status,
        label,
        count: this.all.filter((s) => s.studentStatus === status).length
      }))
    },
    pageList() {
      return this.all.slice((this.page - 1) * this.pageSize, this.page * this.pageSize)
    },
    maxPage() {
      return Math.max(1, Math.ceil(this.all.length / this.pageSize))
    },
    reasonCheck() {
      return validateStatusChangeReason(this.reason)
    }
  },
  created() {
    if (!this.noPermission) this.load()
  },
  methods: {
    statusText: formatStudentStatus,
    academicText: formatAcademicStatus,
    allowedNext(s) {
      return getAllowedNextStatuses(s.studentStatus)
    },
    turnPage(delta) {
      const next = this.page + delta
      if (next < 1 || next > this.maxPage) return
      this.page = next
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const [listRes, overviewRes] = await Promise.all([
          studentProvider.getStudentList({ page: 1, pageSize: 100 }),
          studentProvider.getStudentOverview()
        ])
        if (listRes.code === 0) this.all = listRes.data.list
        else this.error = listRes.message
        if (overviewRes.code === 0) this.recentChanges = overviewRes.data.recentStatusChanges
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    openChange(s) {
      this.changeTarget = s
      this.targetStatus = ''
      this.reason = ''
      this.changeVisible = true
    },
    async onChangeConfirm() {
      if (!this.changeTarget || !this.targetStatus || !this.reasonCheck.valid) return
      this.submitting = true
      try {
        const res = await studentProvider.changeStudentStatus(this.changeTarget.studentId, {
          targetStatus: this.targetStatus,
          reason: this.reason.trim()
        })
        if (res.code === 0) {
          toast.success('状态已变更，原因已写入时间线与审计')
          this.changeVisible = false
          await this.load()
        } else toast.warning(res.message)
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
@import './student-page.css';
.ss-change { display: flex; flex-direction: column; gap: var(--space-4); }
.ss-change__row { display: flex; align-items: center; gap: var(--space-3); }
.ss-change__label { font-size: var(--font-size-sm); color: var(--text-secondary); white-space: nowrap; display: inline-block; margin-bottom: var(--space-2); }
</style>
