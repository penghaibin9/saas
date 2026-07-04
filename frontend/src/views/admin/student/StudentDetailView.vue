<template>
  <ModulePageShell
    :title="detail ? detail.name + ' · 学生360' : '学生360'"
    subtitle="全生命周期档案 · 敏感字段按角色权限脱敏 · 查阅已留审计"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="学生360查阅"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" @back="$router.push('/admin/student/list')" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="detail" class="mp-stack">
      <!-- 档案头 -->
      <section class="mp-card sd-head">
        <div class="sd-head__avatar">{{ detail.name.slice(0, 1) }}</div>
        <div class="sd-head__main">
          <div class="sd-head__name">
            {{ detail.name }}
            <AppStatusTag :type="statusTone(detail.studentStatus)" :label="statusLabel(detail.studentStatus)" dot />
            <RiskTag v-if="detail.riskLevel !== 'NONE'" :level="detail.riskLevel" />
          </div>
          <div class="sd-head__sub">
            {{ detail.studentNo }} · {{ detail.collegeName }} / {{ detail.majorName }} / {{ detail.className }} ·
            {{ detail.grade }} · 辅导员 {{ detail.counselorName }}
          </div>
          <div class="sd-head__meta">
            <span>身份核验：{{ identityLabel(detail.identityVerifyStatus) }}</span>
            <span>账号：{{ bindLabel(detail.accountBindStatus) }}</span>
            <span>入学：{{ detail.enrollDate }}</span>
          </div>
        </div>
        <div class="sd-head__complete">
          <div class="sd-head__complete-num">{{ detail.dataCompleteness }}%</div>
          <div class="sd-head__complete-label">主档完整度</div>
          <div class="sd-head__bar">
            <span class="sd-head__bar-fill" :style="{ width: detail.dataCompleteness + '%' }" />
          </div>
        </div>
      </section>

      <p v-if="detail.voided" class="mp-form-err">该主档已作废：{{ detail.voidReason }}（逻辑删除，仅可查阅）</p>

      <!-- 页签 -->
      <nav class="sd-tabs">
        <button
          v-for="t in tabs"
          :key="t.key"
          type="button"
          class="sd-tab"
          :class="{ 'is-active': activeTab === t.key }"
          @click="activeTab = t.key"
        >
          {{ t.label }}
        </button>
      </nav>

      <!-- 基础信息 -->
      <section v-show="activeTab === 'basic'" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">基础信息</span>
          <span class="mp-note">{{ canSensitive ? '当前角色可见明文' : '敏感字段已脱敏' }}</span>
        </div>
        <div class="mp-card__body sd-kv-grid">
          <div v-for="kv in basicKvs" :key="kv.k" class="mp-kv">
            <span class="mp-kv__k">{{ kv.k }}</span>
            <span class="mp-kv__v">{{ kv.v }}</span>
          </div>
        </div>
      </section>

      <!-- 学籍与状态 -->
      <section v-show="activeTab === 'status'" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">学籍状态历史</span>
          <button class="mp-link" @click="$router.push('/admin/student/status')">学籍状态管理 ›</button>
        </div>
        <div class="mp-card__body">
          <EmptyState v-if="!detail.statusHistory.length" title="暂无状态变更记录" />
          <ul v-else class="mp-timeline">
            <li v-for="r in detail.statusHistory" :key="r.id" class="mp-timeline__item">
              <div class="mp-timeline__title">{{ statusLabel(r.fromStatus) }} → {{ statusLabel(r.toStatus) }}</div>
              <div class="mp-timeline__desc">{{ r.reason }}<template v-if="r.attachment"> · 附件：{{ r.attachment }}</template></div>
              <div class="mp-timeline__time">{{ r.operatedAt }} · {{ r.operator }}（{{ r.roleName }}）</div>
            </li>
          </ul>
        </div>
      </section>

      <!-- 迎新与在校服务 -->
      <div v-show="activeTab === 'campus'" class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">数字迎新</span></div>
          <div class="mp-card__body">
            <EmptyState v-if="!detail.orientation.steps.length" title="暂无迎新流程记录" />
            <ul v-else class="mp-timeline">
              <li v-for="s in detail.orientation.steps" :key="s.name" class="mp-timeline__item is-success">
                <div class="mp-timeline__title">{{ s.name }}</div>
                <div class="mp-timeline__time">{{ s.time }}</div>
              </li>
            </ul>
          </div>
        </section>
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">在校服务记录</span></div>
          <div class="mp-card__body">
            <EmptyState v-if="!detail.serviceRecords.length" title="暂无在校服务记录" />
            <div v-else>
              <div v-for="s in detail.serviceRecords" :key="s.id" class="mp-kv">
                <span class="mp-kv__k">{{ s.type }} · {{ s.time }}</span>
                <span class="mp-kv__v">
                  {{ s.title }}
                  <AppStatusTag :status="s.status" />
                </span>
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- 学业 -->
      <section v-show="activeTab === 'academic'" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">学业过程</span>
          <span v-if="detail.academic.warningLevel" class="mp-form-err">{{ detail.academic.warningLevel }}</span>
        </div>
        <div class="mp-card__body">
          <div class="sd-kv-grid">
            <div class="mp-kv"><span class="mp-kv__k">平均绩点</span><span class="mp-kv__v">{{ detail.academic.gpa }}</span></div>
            <div class="mp-kv">
              <span class="mp-kv__k">已修学分</span>
              <span class="mp-kv__v">{{ detail.academic.earnedCredits }} / {{ detail.academic.requiredCredits }}</span>
            </div>
          </div>
          <table v-if="detail.academic.courses.length" class="mp-audit sd-gap-top">
            <thead>
              <tr><th>课程</th><th>学期</th><th>成绩</th><th>重修</th></tr>
            </thead>
            <tbody>
              <tr v-for="c in detail.academic.courses" :key="c.name + c.term">
                <td class="is-who">{{ c.name }}</td>
                <td>{{ c.term }}</td>
                <td>{{ c.score }}</td>
                <td>{{ c.retake ? '是' : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 实习 / 毕设 / 就业 -->
      <div v-show="activeTab === 'career'" class="mp-grid-cards">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">岗位实习</span></div>
          <div class="mp-card__body">
            <EmptyState v-if="!detail.internship" title="暂无实习记录" description="学生尚未进入实习批次" />
            <template v-else>
              <div class="mp-kv"><span class="mp-kv__k">企业 / 岗位</span><span class="mp-kv__v">{{ detail.internship.enterpriseName }} · {{ detail.internship.positionName }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">状态</span><span class="mp-kv__v"><AppStatusTag :label="detail.internship.statusLabel" :type="detail.internship.status === 'ONBOARD' ? 'processing' : 'info'" /></span></div>
              <div class="mp-kv"><span class="mp-kv__k">近 30 日出勤率</span><span class="mp-kv__v">{{ detail.internship.attendanceRate }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">周报</span><span class="mp-kv__v">{{ detail.internship.reportSummary }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">指导教师</span><span class="mp-kv__v">{{ detail.internship.advisorName }}</span></div>
            </template>
          </div>
        </section>
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">毕业设计</span></div>
          <div class="mp-card__body">
            <EmptyState v-if="!detail.graduationDesign" title="暂无毕设记录" description="学生尚未进入毕设阶段" />
            <template v-else>
              <div class="mp-kv"><span class="mp-kv__k">课题</span><span class="mp-kv__v">{{ detail.graduationDesign.topic }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">指导教师</span><span class="mp-kv__v">{{ detail.graduationDesign.advisorName }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">当前阶段</span><span class="mp-kv__v">{{ detail.graduationDesign.stage }} <AppStatusTag :status="detail.graduationDesign.stageStatus" /></span></div>
              <div class="mp-kv"><span class="mp-kv__k">成绩</span><span class="mp-kv__v">{{ detail.graduationDesign.score || '未评定' }}</span></div>
            </template>
          </div>
        </section>
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">就业去向</span></div>
          <div class="mp-card__body">
            <EmptyState v-if="!detail.employment" title="暂无就业记录" description="学生尚未进入就业跟踪" />
            <template v-else>
              <div class="mp-kv"><span class="mp-kv__k">就业意向</span><span class="mp-kv__v">{{ detail.employment.intent }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">Offer 数</span><span class="mp-kv__v">{{ detail.employment.offerCount }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">协议状态</span><span class="mp-kv__v">{{ detail.employment.agreementStatus }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">跟踪状态</span><span class="mp-kv__v">{{ detail.employment.trackStatus }}</span></div>
            </template>
          </div>
        </section>
      </div>

      <!-- 风险与跟进 -->
      <section v-show="activeTab === 'risk'" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">风险标签与跟进</span>
          <button class="mp-link" @click="$router.push('/admin/student/risk-tags')">风险标签管理 ›</button>
        </div>
        <div class="mp-card__body">
          <EmptyState v-if="!detail.riskTags.length" title="暂无风险标签" description="该学生当前无生效中的风险标签" />
          <div v-else class="mp-stack">
            <div v-for="t in detail.riskTags" :key="t.id" class="sd-risk">
              <div class="sd-risk__head">
                <RiskTag :level="t.level" />
                <span class="sd-risk__title">{{ t.title }}</span>
                <AppStatusTag :label="riskStatusLabel(t.status)" :type="t.status === 'RESOLVED' ? 'success' : 'warning'" />
                <span class="mp-note">{{ t.tagTypeLabel }} · {{ t.sourceLabel }} · 责任人 {{ t.owner }}</span>
              </div>
              <p class="sd-risk__desc">{{ t.description }}</p>
              <ul v-if="t.followUps.length" class="mp-timeline">
                <li v-for="f in t.followUps" :key="f.time" class="mp-timeline__item">
                  <div class="mp-timeline__desc">{{ f.note }}</div>
                  <div class="mp-timeline__time">{{ f.time }} · {{ f.who }}</div>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <!-- 更正与审计 -->
      <div v-show="activeTab === 'audit'" class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">信息更正申请</span>
            <button class="mp-link" @click="$router.push('/admin/student/corrections')">更正审核 ›</button>
          </div>
          <div class="mp-card__body">
            <EmptyState v-if="!detail.corrections.length" title="暂无更正申请" />
            <div v-else>
              <div v-for="c in detail.corrections" :key="c.id" class="mp-kv">
                <span class="mp-kv__k">{{ c.fieldLabel }} · {{ c.submitTime }}</span>
                <span class="mp-kv__v"><AppStatusTag :status="c.status" /></span>
              </div>
            </div>
          </div>
        </section>
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">审计记录</span></div>
          <div class="mp-card__body">
            <EmptyState v-if="!detail.auditTrail.length" title="暂无审计记录" />
            <table v-else class="mp-audit">
              <thead>
                <tr><th>时间</th><th>操作人</th><th>动作</th><th>说明</th></tr>
              </thead>
              <tbody>
                <tr v-for="a in detail.auditTrail" :key="a.id">
                  <td>{{ a.time }}</td>
                  <td class="is-who">{{ a.operator }}</td>
                  <td>{{ a.action }}</td>
                  <td>{{ a.detail }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>

    <!-- 编辑基础信息 -->
    <AppDrawer :visible="editDrawer.visible" title="编辑基础信息" @update:visible="editDrawer.visible = $event">
      <div class="mp-stack">
        <label class="sd-field">
          <span class="sd-field__label">姓名</span>
          <input v-model="editDrawer.form.name" class="sd-field__control" />
        </label>
        <label class="sd-field">
          <span class="sd-field__label">手机号</span>
          <input v-model="editDrawer.form.phone" class="sd-field__control" />
        </label>
        <label class="sd-field">
          <span class="sd-field__label">辅导员</span>
          <select v-model="editDrawer.form.counselorName" class="sd-field__control">
            <option v-for="c in ctx.filterOptions.counselors" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </label>
        <p v-if="editDrawer.error" class="mp-form-err">{{ editDrawer.error }}</p>
        <div class="sd-drawer-ops">
          <AppButton variant="ghost" @click="editDrawer.visible = false">取消</AppButton>
          <AppButton variant="primary" :disabled="editDrawer.submitting" @click="submitEdit">保存变更</AppButton>
        </div>
        <p class="mp-note">变更将写入字段级审计留痕；证件类关键字段请走「信息更正审核」流程。</p>
      </div>
    </AppDrawer>

    <!-- 导出档案确认 -->
    <AppConfirmDialog
      :visible="exportDialog.visible"
      type="warning"
      title="导出学生档案"
      :message="detail ? '将导出 ' + detail.name + ' 的全生命周期档案：敏感字段自动脱敏，文件附水印，导出行为写入审计日志。' : ''"
      confirm-text="确认导出"
      require-reason
      reason-label="导出用途"
      reason-placeholder="如：学籍异动材料归档（不少于 5 个字）"
      :submitting="exportDialog.submitting"
      @update:visible="exportDialog.visible = $event"
      @confirm="submitExport"
    />
  </ModulePageShell>
</template>

<script>
/** 学生360（/admin/student/:studentId）：全生命周期档案 + 编辑 + 导出 + 审计。 */
import {
  ModulePageShell,
  ModuleToolbar,
  StatusTag as AppStatusTag,
  RiskTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { studentApi } from '@/modules/student/api/student.api'
import { toast } from '@/utils/toast'

export default {
  name: 'StudentDetailView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AppStatusTag,
    RiskTag,
    LoadingState,
    ErrorState,
    EmptyState,
    AppConfirmDialog,
    AppButton,
    AppDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      detail: null,
      activeTab: 'basic',
      tabs: [
        { key: 'basic', label: '基础信息' },
        { key: 'status', label: '学籍状态' },
        { key: 'campus', label: '迎新与在校' },
        { key: 'academic', label: '学业过程' },
        { key: 'career', label: '实习 · 毕设 · 就业' },
        { key: 'risk', label: '风险与跟进' },
        { key: 'audit', label: '更正与审计' }
      ],
      editDrawer: { visible: false, form: { name: '', phone: '', counselorName: '' }, error: '', submitting: false },
      exportDialog: { visible: false, submitting: false }
    }
  },
  computed: {
    canSensitive() {
      const pa = this.ctx.permissionActions.viewSensitive
      return !!(pa && pa.visible && pa.allowed)
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'back', label: '返回列表', variant: 'ghost', perm: 'viewList' },
        { key: 'edit', label: '编辑基础信息', perm: 'editStudent' },
        { key: 'export', label: '导出学生档案', perm: 'exportArchive' }
      ]
        .filter((a) => pa[a.perm] && pa[a.perm].visible)
        .map((a) => ({ ...a, disabled: !pa[a.perm].allowed, disabledReason: pa[a.perm].reason }))
    },
    basicKvs() {
      const d = this.detail
      return [
        { k: '姓名', v: d.name },
        { k: '学号', v: d.studentNo },
        { k: '性别', v: d.gender },
        { k: '手机号', v: this.mask(d.phone, 'phone') },
        { k: '身份证号', v: this.mask(d.idCard, 'idCard') },
        { k: '学院', v: d.collegeName },
        { k: '专业', v: d.majorName },
        { k: '班级', v: d.className },
        { k: '年级', v: d.grade },
        { k: '入学日期', v: d.enrollDate },
        { k: '辅导员', v: d.counselorName },
        { k: '最近更新', v: d.updatedAt }
      ]
    }
  },
  watch: {
    '$route.params.studentId'() {
      this.load()
    }
  },
  created() {
    this.load()
  },
  methods: {
    mask(v, type) {
      if (!v) return '未登记'
      if (this.canSensitive) return v
      if (type === 'phone') return v.slice(0, 3) + '****' + v.slice(-4)
      return v.slice(0, 6) + '********' + v.slice(-4)
    },
    statusLabel(v) {
      const hit = this.ctx.statusOptions.studentStatus.find((o) => o.value === v)
      return hit ? hit.label : v
    },
    statusTone(v) {
      return { ADMITTED: 'processing', ACTIVE: 'success', SUSPENDED: 'warning', GRADUATED: 'info', DROPPED: 'default', VOIDED: 'default' }[v] || 'default'
    },
    identityLabel(v) {
      const hit = this.ctx.statusOptions.identityVerifyStatus.find((o) => o.value === v)
      return hit ? hit.label : v
    },
    bindLabel(v) {
      const hit = this.ctx.statusOptions.accountBindStatus.find((o) => o.value === v)
      return hit ? hit.label : v
    },
    riskStatusLabel(v) {
      const hit = this.ctx.statusOptions.riskTagStatus.find((o) => o.value === v)
      return hit ? hit.label : v
    },
    onToolbar(key) {
      if (key === 'back') this.$router.push('/admin/student/list')
      if (key === 'edit' && this.detail) {
        this.editDrawer = {
          visible: true,
          error: '',
          submitting: false,
          form: { name: this.detail.name, phone: this.detail.phone, counselorName: this.detail.counselorName }
        }
      }
      if (key === 'export') this.exportDialog = { visible: true, submitting: false }
    },
    async submitEdit() {
      const d = this.editDrawer
      d.submitting = true
      d.error = ''
      const res = await studentApi.updateStudent(this.detail.studentId, d.form)
      d.submitting = false
      if (res.code === 0) {
        d.visible = false
        toast.success('基础信息已更新（已留痕）')
        this.load()
      } else {
        d.error = res.message
      }
    },
    async submitExport({ reason }) {
      this.exportDialog.submitting = true
      const res = await studentApi.createExport({
        scope: 'SELECTED',
        fieldKeys: ['name', 'studentNo', 'orgPath', 'studentStatus', 'phone', 'idCard'],
        purpose: 'WORK',
        remark: reason,
        rowCount: 1
      })
      this.exportDialog.submitting = false
      if (res.code === 0) {
        this.exportDialog.visible = false
        toast.success('档案导出任务已创建：已脱敏、含水印，审计编号 ' + res.data.auditId)
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await studentApi.getStudentDetail(this.$route.params.studentId)
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

/* 档案头 */
.sd-head {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
}
.sd-head__avatar {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  background: var(--primary-50);
  color: var(--primary-700);
  border: 1px solid var(--primary-100);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  flex-shrink: 0;
}
.sd-head__main {
  flex: 1;
  min-width: 0;
}
.sd-head__name {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  flex-wrap: wrap;
}
.sd-head__sub {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.sd-head__meta {
  margin-top: var(--space-1);
  display: flex;
  gap: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  flex-wrap: wrap;
}
.sd-head__complete {
  width: 140px;
  flex-shrink: 0;
  text-align: right;
}
.sd-head__complete-num {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  font-variant-numeric: var(--font-numeric);
}
.sd-head__complete-label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.sd-head__bar {
  margin-top: var(--space-1);
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--bg-section-blue);
  overflow: hidden;
}
.sd-head__bar-fill {
  display: block;
  height: 100%;
  border-radius: var(--radius-full);
  background: var(--primary-500);
}
.sd-tabs {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-1);
  box-shadow: var(--shadow-card);
}
.sd-tab {
  border: none;
  background: none;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  cursor: pointer;
}
.sd-tab.is-active {
  background: var(--primary-50);
  color: var(--primary-700);
  font-weight: var(--font-weight-medium);
}
.sd-kv-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  column-gap: var(--space-6);
}
.sd-gap-top {
  margin-top: var(--space-3);
}
.sd-risk {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-3);
}
.sd-risk__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.sd-risk__title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}
.sd-risk__desc {
  margin: var(--space-2) 0;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.sd-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.sd-field__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.sd-field__control {
  height: 34px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  outline: none;
}
.sd-field__control:focus {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-50);
}
.sd-drawer-ops {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding-top: var(--space-2);
}
</style>
