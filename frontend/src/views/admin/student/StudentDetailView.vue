<template>
  <div class="sp-page sp-detail" style="position: relative">
    <SecurityWatermark purpose="学生主档查阅" />
    <AppSectionHeader :title="student ? `${student.name} 的学生主档` : '学生详情'" subtitle="敏感字段默认脱敏；查看已留审计">
      <template #extra>
        <AppButton variant="ghost" @click="$router.push('/admin/student/list')">返回列表</AppButton>
      </template>
    </AppSectionHeader>

    <StudentStateBlock :loading="loading" :error="error" :empty="!student" :no-permission="noPermission" @retry="load">
      <template v-if="student">
        <StudentProfileCard :student="student">
          <template #actions>
            <StudentStatusTag :status="student.studentStatus" />
          </template>
        </StudentProfileCard>

        <div class="sp-cols">
          <div class="sp-detail__col">
            <StudentBasicInfoPanel :student="student" />
            <StudentContactPanel :student="student" />
            <StudentGuardianPanel :guardians="guardians" />
          </div>
          <div class="sp-detail__col">
            <StudentIdentityPanel
              :identity="identity"
              :can-verify="canVerify"
              :submitting="submitting"
              @verify="onVerify"
              @reject="onReject"
            />
            <StudentAcademicPanel :student="student" />
            <AppCard class="sp-card">
              <AppSectionHeader title="主档时间线" compact>
                <template #extra>
                  <AppButton v-if="canAudit" variant="ghost" @click="showAudit = !showAudit">
                    {{ showAudit ? '收起审计' : '查看审计记录' }}
                  </AppButton>
                </template>
              </AppSectionHeader>
              <StudentTimeline :items="timeline" />
              <template v-if="showAudit">
                <AppSectionHeader title="审计记录" compact />
                <table class="sp-table">
                  <thead><tr><th>时间</th><th>操作人</th><th>动作</th><th>变更</th></tr></thead>
                  <tbody>
                    <tr v-for="(a, i) in auditLogs" :key="i">
                      <td>{{ a.time }}</td><td>{{ a.operator }}</td><td>{{ a.action }}</td>
                      <td>{{ a.before ? `${a.before} → ${a.after}` : a.after }}</td>
                    </tr>
                  </tbody>
                </table>
              </template>
            </AppCard>
          </div>
        </div>
      </template>
    </StudentStateBlock>
  </div>
</template>

<script>
/** 页面 4：/admin/student/:studentId 学生详情（水印 + 全脱敏 + 审计入口） */
import { AppCard, AppButton, AppSectionHeader } from '@/components/ui'
import { SecurityWatermark } from '@/security'
import StudentStateBlock from '@/modules/student/components/StudentStateBlock.vue'
import StudentProfileCard from '@/modules/student/components/StudentProfileCard.vue'
import StudentBasicInfoPanel from '@/modules/student/components/StudentBasicInfoPanel.vue'
import StudentContactPanel from '@/modules/student/components/StudentContactPanel.vue'
import StudentGuardianPanel from '@/modules/student/components/StudentGuardianPanel.vue'
import StudentIdentityPanel from '@/modules/student/components/StudentIdentityPanel.vue'
import StudentAcademicPanel from '@/modules/student/components/StudentAcademicPanel.vue'
import StudentStatusTag from '@/modules/student/components/StudentStatusTag.vue'
import StudentTimeline from '@/modules/student/components/StudentTimeline.vue'
import { studentProvider, hasStudentPermission, STUDENT_PERMISSION } from '@/modules/student'
import { toast } from '@/utils/toast'

export default {
  name: 'StudentDetailView',
  components: {
    AppCard, AppButton, AppSectionHeader, SecurityWatermark,
    StudentStateBlock, StudentProfileCard, StudentBasicInfoPanel, StudentContactPanel,
    StudentGuardianPanel, StudentIdentityPanel, StudentAcademicPanel, StudentStatusTag, StudentTimeline
  },
  data() {
    return {
      loading: false,
      error: '',
      student: null,
      identity: {},
      guardians: [],
      timeline: [],
      auditLogs: [],
      showAudit: false,
      submitting: false
    }
  },
  computed: {
    studentId() {
      return this.$route.params.studentId
    },
    noPermission() {
      return !hasStudentPermission(STUDENT_PERMISSION.PROFILE_VIEW)
    },
    canVerify() {
      return hasStudentPermission(STUDENT_PERMISSION.IDENTITY_VERIFY)
    },
    canAudit() {
      return hasStudentPermission(STUDENT_PERMISSION.AUDIT_VIEW)
    }
  },
  watch: {
    studentId() {
      this.load()
    }
  },
  created() {
    if (!this.noPermission) this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        const [d, id, g, t, a] = await Promise.all([
          studentProvider.getStudentDetail(this.studentId),
          studentProvider.getStudentIdentity(this.studentId),
          studentProvider.getStudentGuardians(this.studentId),
          studentProvider.getStudentTimeline(this.studentId),
          studentProvider.getStudentAuditLogs(this.studentId)
        ])
        if (d.code === 0) this.student = d.data
        else this.error = d.message
        if (id.code === 0) this.identity = id.data
        if (g.code === 0) this.guardians = g.data.list
        if (t.code === 0) this.timeline = t.data.list
        if (a.code === 0) this.auditLogs = a.data.list
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    async onVerify() {
      this.submitting = true
      try {
        const res = await studentProvider.verifyStudentIdentity(this.studentId)
        if (res.code === 0) {
          toast.success('身份核验已通过，审计已留痕')
          await this.load()
        } else toast.warning(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onReject(reason) {
      this.submitting = true
      try {
        const res = await studentProvider.rejectStudentIdentity(this.studentId, { reason })
        if (res.code === 0) {
          toast.success('已退回，退回原因已写入记录')
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
.sp-detail__col { display: flex; flex-direction: column; gap: var(--space-5); }
</style>
