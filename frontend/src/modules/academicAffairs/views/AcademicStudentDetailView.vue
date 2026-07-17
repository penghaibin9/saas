<template>
  <ModulePageShell
    :title="detail ? detail.student.name + ' · 学业详情' : '学业详情'"
    :subtitle="detail ? detail.student.className + ' · ' + maskNo(detail.student.studentNo) : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-grid-2">
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">学业画像</span>
            <span>
              <StatusTag
                :type="detail.student.academicStatus === 'NORMAL' ? 'success' : detail.student.academicStatus === 'HELPING' ? 'processing' : 'warning'"
                :label="statusLabel(detail.student.academicStatus)"
                dot
              />
              <RiskTag v-if="detail.student.warningLevel !== 'NONE'" :level="detail.student.warningLevel" style="margin-left: var(--space-2)" />
            </span>
          </div>
          <div class="mp-card__body">
            <AppDescriptionList :items="profileItems" :columns="2" />
          </div>
        </section>

        <section v-if="detail.credit" class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">学分分类完成情况</span></div>
          <div class="mp-card__body">
            <div v-for="c in detail.credit.categories" :key="c.key" class="asd-credit">
              <div class="asd-credit__head">
                <span>{{ c.label }}</span>
                <span class="mp-note">{{ c.obtained }} / {{ c.required }}</span>
              </div>
              <div class="asd-credit__bar">
                <div class="asd-credit__fill" :class="{ 'is-low': c.obtained / c.required < 0.5 }" :style="{ width: Math.min(100, (c.obtained / c.required) * 100) + '%' }" />
              </div>
            </div>
            <p class="mp-note" style="margin-top: var(--space-3)">
              学分口径同步自教务系统（{{ detail.credit.term }}），缺口 {{ detail.credit.gap }} 学分。
            </p>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">学业预警</span></div>
          <div class="mp-card__body">
            <ul v-if="detail.warnings.length" class="mp-timeline">
              <li v-for="w in detail.warnings" :key="w.id" class="mp-timeline__item" :class="w.level === 'HIGH' ? 'is-danger' : 'is-warning'">
                <div class="mp-timeline__title">
                  {{ w.code }} · {{ typeLabel(w.type) }}
                  <RiskTag :level="w.level" />
                  <StatusTag :status="w.status" :label="warnStatusLabel(w.status)" />
                </div>
                <div class="mp-timeline__desc">{{ w.reason }}</div>
                <div class="mp-timeline__time">
                  {{ w.triggerTime }} ·
                  <button class="mp-link" @click="$router.push('/admin/academic/warnings/' + w.id)">跟进详情 →</button>
                </div>
              </li>
            </ul>
            <EmptyState v-else title="暂无学业预警" description="该学生当前没有触发任何预警规则" />
          </div>
        </section>
      </div>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-tabs" style="padding: 0 var(--space-4)">
            <button v-for="t in tabs" :key="t.key" class="mp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">
              {{ t.label }}
            </button>
          </div>
          <div class="mp-card__body">
            <table v-if="tab === 'grades'" class="mp-audit">
              <thead><tr><th>课程</th><th>学期</th><th>学分</th><th>成绩</th><th>类型</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="g in detail.grades" :key="g.id">
                  <td class="is-who">{{ g.courseName }}</td>
                  <td>{{ g.term }}</td>
                  <td>{{ g.creditValue }}</td>
                  <td :class="{ 'asd-bad': g.score < 60 }">{{ g.score }}</td>
                  <td>{{ examTypeLabel(g.examType) }}</td>
                  <td><StatusTag :type="g.passStatus === 'PASSED' ? 'success' : 'danger'" :label="g.passStatus === 'PASSED' ? '通过' : '未通过'" /></td>
                </tr>
                <tr v-if="!detail.grades.length"><td colspan="6" class="mp-note">暂无成绩记录</td></tr>
              </tbody>
            </table>
            <table v-else-if="tab === 'exams'" class="mp-audit">
              <thead><tr><th>课程</th><th>类型</th><th>时间</th><th>结果</th></tr></thead>
              <tbody>
                <tr v-for="e in detail.exams" :key="e.id">
                  <td class="is-who">{{ e.courseName }}</td>
                  <td>{{ examTypeLabel(e.examType) }}</td>
                  <td>{{ e.examDate }}</td>
                  <td>{{ e.result }}</td>
                </tr>
                <tr v-if="!detail.exams.length"><td colspan="4" class="mp-note">暂无考试记录</td></tr>
              </tbody>
            </table>
            <table v-else-if="tab === 'makeup'" class="mp-audit">
              <thead><tr><th>课程</th><th>原成绩</th><th>安排</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="m in detail.makeups" :key="m.id">
                  <td class="is-who">{{ m.courseName }}</td>
                  <td>{{ m.originScore }} 分</td>
                  <td>{{ m.examDate }}</td>
                  <td><StatusTag :type="m.status === 'PASSED' ? 'success' : m.status === 'PENDING_EXAM' ? 'warning' : 'danger'" :label="makeupLabel(m.status)" /></td>
                </tr>
                <tr v-for="r in detail.retakes" :key="r.id">
                  <td class="is-who">{{ r.courseName }}（重修）</td>
                  <td>—</td>
                  <td>{{ r.retakeTerm }}</td>
                  <td><StatusTag :type="r.status === 'PASSED' ? 'success' : 'processing'" :label="retakeLabel(r.status)" /></td>
                </tr>
                <tr v-if="!detail.makeups.length && !detail.retakes.length"><td colspan="4" class="mp-note">暂无补考/重修记录</td></tr>
              </tbody>
            </table>
            <table v-else class="mp-audit">
              <thead><tr><th>时间</th><th>方式</th><th>内容 / 结果</th><th>记录人</th></tr></thead>
              <tbody>
                <tr v-for="i in detail.interventions" :key="i.id">
                  <td>{{ i.time }}</td>
                  <td class="is-who">{{ i.wayLabel }}</td>
                  <td>
                    {{ i.content }}
                    <div class="mp-cell-sub">结果：{{ i.result || '—' }}</div>
                  </td>
                  <td>{{ i.operator }}</td>
                </tr>
                <tr v-if="!detail.interventions.length"><td colspan="4" class="mp-note">暂无干预/跟进记录</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">审计留痕（本学生学业档案）</span></div>
          <div class="mp-card__body">
            <table class="mp-audit">
              <thead><tr><th>操作人</th><th>时间</th><th>动作</th><th>明细</th></tr></thead>
              <tbody>
                <tr v-for="a in detail.auditLogs" :key="a.id">
                  <td class="is-who">{{ a.operator }}<div class="mp-cell-sub">{{ a.roleName }}</div></td>
                  <td>{{ a.time }}</td>
                  <td>{{ a.action }}</td>
                  <td>{{ a.detail }}</td>
                </tr>
                <tr v-if="!detail.auditLogs.length"><td colspan="4" class="mp-note">暂无审计记录</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学生学业详情（/admin/academic/students/:id）：画像 + 学分 + 预警 + 四页签（成绩/考试/补考重修/干预）+ 审计留痕。 */
import { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDescriptionList } from '@/components/common'
import { getStudentAcademicDetail, batchRemindStudents } from '@/modules/academicAffairs/api/academic.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AcademicStudentDetailView',
  components: { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState, AppDescriptionList },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      detail: null,
      tab: 'grades',
      tabs: [
        { key: 'grades', label: '课程成绩' },
        { key: 'exams', label: '考试记录' },
        { key: 'makeup', label: '补考重修' },
        { key: 'interventions', label: '干预跟进' }
      ]
    }
  },
  computed: {
    profileItems() {
      const s = this.detail && this.detail.student
      if (!s) return []
      return [
        { label: '学院 / 专业', value: s.collegeName + ' · ' + s.majorName },
        { label: 'GPA / 平均成绩', value: s.gpa.toFixed(1) + ' / ' + s.avgScore + ' 分' },
        { label: '挂科门数', value: s.failedCount + ' 门' },
        { label: '学分进度', value: s.obtainedCredits + ' / ' + s.requiredCredits + '（中期应达 60）' },
        { label: '补考 / 重修', value: s.makeupCount + ' / ' + s.retakeCount },
        { label: '辅导员', value: s.counselor },
        { label: '联系电话', value: s.phone || '未登记' },
        { label: '更新时间', value: s.updateTime }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'remind', permission: 'academic.record.batchRemind', label: '发送提醒' },
        { key: 'warning', permission: 'academic.warning.create', label: '＋ 新增预警', variant: 'primary' }
      ]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    maskNo(v) {
      return v ? v.slice(0, -4) + '**' + v.slice(-2) : ''
    },
    statusLabel(v) {
      return (this.ctx.statusOptions.academicStatus.find((o) => o.value === v) || {}).label || v
    },
    typeLabel(v) {
      return (this.ctx.statusOptions.warningType.find((o) => o.value === v) || {}).label || v
    },
    warnStatusLabel(v) {
      return (this.ctx.statusOptions.warningStatus.find((o) => o.value === v) || {}).label || v
    },
    examTypeLabel(v) {
      return (this.ctx.statusOptions.examType.find((o) => o.value === v) || {}).label || v
    },
    makeupLabel(v) {
      return (this.ctx.statusOptions.makeupStatus.find((o) => o.value === v) || {}).label || v
    },
    retakeLabel(v) {
      return (this.ctx.statusOptions.retakeStatus.find((o) => o.value === v) || {}).label || v
    },
    async onToolbar(key) {
      if (key === 'remind') {
        const res = await batchRemindStudents([this.detail.student.id], '学业进度与考核安排')
        if (res.code === 0) toast.success('提醒已发送（站内信 + 小程序），已写入审计日志')
        else toast.error(res.message)
      } else if (key === 'warning') {
        this.$router.push('/admin/academic/warnings?create=' + this.detail.student.id)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await getStudentAcademicDetail(this.$route.params.id)
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.asd-bad {
  color: var(--danger-600);
  font-weight: var(--font-weight-semibold);
}
.asd-credit {
  margin-bottom: var(--space-3);
}
.asd-credit__head {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-1);
}
.asd-credit__bar {
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--gray-100);
  overflow: hidden;
}
.asd-credit__fill {
  height: 100%;
  border-radius: var(--radius-full);
  background: var(--primary-500);
  transition: width var(--motion-normal) var(--ease-standard);
}
.asd-credit__fill.is-low {
  background: var(--danger-500);
}
</style>
