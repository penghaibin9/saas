<template>
  <ModulePageShell
    title="学籍档案"
    :subtitle="detail ? `${detail.realName} · 学号 ${detail.studentNo}` : '学籍档案详情'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.back()">返回</button>
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else-if="detail">
        <AppSectionCard title="基础信息">
          <AppDescriptionList :items="baseItems" :columns="3" />
        </AppSectionCard>

        <AppSectionCard title="证件与联系">
          <div class="aa-sensitive-row">
            <span class="aa-sensitive-label">身份证号</span>
            <span class="aa-mask">{{ revealed ? revealedIdCard : detail.idCardMasked || '—' }}</span>
            <button v-if="!revealed" class="mp-link" @click="revealVisible = true">查看完整</button>
            <button v-else class="mp-link" @click="hideRevealed">隐藏</button>
          </div>
          <p class="mp-note">查看完整证件号需填写理由，系统将记录本次查看审计。</p>
        </AppSectionCard>

        <AppSectionCard title="学籍状态历史">
          <EmptyState v-if="!detail.statusHistory.length" title="暂无学籍状态变更记录" />
          <AppTimeline v-else :items="historyItems" />
        </AppSectionCard>

        <AppSectionCard title="快捷入口">
          <div class="aa-quick-actions">
            <button class="mp-btn" :disabled="!detail.enrolled" @click="goChange">发起学籍异动</button>
            <button class="mp-btn" @click="goCorrection">发起学籍信息更正</button>
            <button class="mp-btn" @click="goTranscript">查看成绩单</button>
            <button class="mp-btn" @click="goChanges">查看该生全部异动记录</button>
          </div>
        </AppSectionCard>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="revealVisible"
      title="查看完整证件号"
      message="查看学生完整身份证号将写入敏感数据查看审计，请填写查看理由。"
      type="warning"
      confirm-text="确认查看"
      require-reason
      reason-label="查看理由"
      reason-placeholder="如：核对身份证材料真实性（不少于 5 个字，将写入审计日志）"
      :submitting="revealing"
      @confirm="doReveal"
    />
  </ModulePageShell>
</template>

<script>
/** 学籍档案详情（/admin/academic-affairs/roster/:studentId）：GET /academic-affairs/roster/{id}（数据范围收敛，越权 403）。
 * 证件号查看走 POST /roster/{id}/reveal（理由必填≥5字，服务层二次鉴权+SUCCESS/DENY 双向审计）。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppTimeline, AppConfirmDialog } from '@/components/common'
import AppDescriptionList from '@/components/common/display/AppDescriptionList.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const STATUS_LABEL = {
  NORMAL: '正常', MERGED: '已合并', RECYCLED: '已回收', PENDING_REGISTER: '待注册',
  REGISTERED: '在籍注册', UNREGISTERED: '未注册', SUSPENDED: '休学', RETAINED: '留级',
  WITHDRAWN: '退学', TRANSFER_SCHOOL: '转学', GRADUATED: '毕业', COMPLETED: '结业', INCOMPLETE: '肄业'
}
const CHANGE_TYPE_LABEL = {
  ENROLL_REGISTER: '入学注册', ANNUAL_REGISTER: '学年注册', SEMESTER_REGISTER: '学期注册',
  SUSPEND: '休学', WITHDRAW: '退学', RESUME: '复学', RETAIN: '留级', TRANSFER_MAJOR: '转专业'
}

export default {
  name: 'AaRosterDetailView',
  components: {
    ModulePageShell, AppSectionCard, LoadingState, ErrorState, EmptyState,
    AppTimeline, AppDescriptionList, AppConfirmDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', detail: null,
      revealVisible: false, revealing: false, revealed: false, revealedIdCard: ''
    }
  },
  computed: {
    studentId() {
      return this.$route.params.studentId
    },
    baseItems() {
      const d = this.detail
      if (!d) return []
      return [
        { label: '学号', value: d.studentNo },
        { label: '姓名', value: d.realName },
        { label: '性别', value: d.gender || '—' },
        { label: '学院', value: d.collegeName || '—' },
        { label: '专业', value: d.majorName || '—' },
        { label: '班级', value: d.className || '—' },
        { label: '年级', value: d.grade || '—' },
        { label: '学籍状态', value: STATUS_LABEL[d.studentStatus] || d.studentStatus },
        { label: '是否在籍', value: d.enrolled ? '在籍' : '非在籍' },
        { label: '当前阶段', value: d.currentStage || '—' },
        { label: '入学日期', value: d.enrollDate || '—' },
        { label: '备注', value: d.remark || '—' }
      ]
    },
    historyItems() {
      return (this.detail?.statusHistory || []).map((h) => ({
        id: h.changeId,
        title: `${CHANGE_TYPE_LABEL[h.changeType] || h.changeType}：${h.fromStatus || '—'} → ${h.toStatus || '—'}`,
        time: h.effectiveDate || '',
        status: h.status,
        description: h.reason || '',
        type: h.status === 'EFFECTIVE' ? 'success' : h.status === 'REJECTED' ? 'danger' : 'default'
      }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getRosterDetail(this.studentId)
      if (res.code === 0) {
        this.detail = res.data
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    hideRevealed() {
      this.revealed = false
      this.revealedIdCard = ''
    },
    async doReveal({ reason }) {
      this.revealing = true
      const res = await academicAffairsApi.revealRosterSensitive(this.studentId, reason)
      this.revealing = false
      if (res.code === 0) {
        this.revealed = true
        this.revealedIdCard = res.data.idCard || ''
        this.revealVisible = false
        toast.success('已记录本次查看审计')
      } else {
        toast.error(res.message || '查看失败')
      }
    },
    goChange() {
      this.$router.push({ path: '/admin/academic-affairs/status-changes/new', query: { studentId: this.studentId, name: this.detail?.realName } })
    },
    goCorrection() {
      this.$router.push({ path: '/admin/academic-affairs/roster/corrections', query: { studentId: this.studentId, name: this.detail?.realName } })
    },
    goTranscript() {
      this.$router.push(`/admin/academic-affairs/transcript?studentId=${this.studentId}`)
    },
    goChanges() {
      this.$router.push({ path: '/admin/academic-affairs/roster/changes', query: { studentId: this.studentId } })
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-sensitive-row { display: flex; align-items: center; gap: var(--space-3); }
.aa-sensitive-label { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.aa-mask { font-family: var(--font-mono, monospace); color: var(--text-900, #1f2329); }
.aa-quick-actions { display: flex; gap: var(--space-3); flex-wrap: wrap; }
</style>
