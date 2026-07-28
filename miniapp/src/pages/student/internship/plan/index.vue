<template>
  <view class="page-wrap pl">
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack" v-if="plan">
        <view class="card">
          <text class="card-title">{{ plan.title }}</text>
          <text class="pl__status">{{ plan.ackStatusLabel }}</text>
          <view v-if="summary.total" class="pl__prog">
            <text>任务完成 {{ summary.approved }}/{{ summary.total }}（{{ summary.rate }}%）</text>
            <view class="pl__bar"><view class="pl__bar-in" :style="{ width: summary.rate + '%' }" /></view>
          </view>
        </view>
        <view class="card">
          <text class="pl__label">实习目标</text>
          <text class="pl__text">{{ plan.objectives || '—' }}</text>
          <text class="pl__label">计划正文</text>
          <text class="pl__text">{{ plan.content || '—' }}</text>
        </view>
        <view v-if="tasks.length" class="card">
          <text class="pl__label">实习任务清单</text>
          <view v-for="(t, i) in tasks" :key="t.progressId || t.sortOrder || i" class="pl__task">
            <view class="pl__task-head">
              <text class="pl__task-no">{{ t.sortOrder || i + 1 }}</text>
              <text class="pl__task-name">{{ t.name || t.taskName }}</text>
              <text class="pl__task-st">{{ t.progressStatusLabel || t.statusLabel || '未开始' }}</text>
            </view>
            <text v-if="t.requirement" class="pl__task-req">{{ t.requirement }}</text>
            <text v-if="t.deadline" class="pl__task-dl">截止：{{ formatDeadline(t.deadline) }}</text>
            <text v-if="t.reviewComment" class="pl__task-reject">退回：{{ t.reviewComment }}</text>
            <view v-if="t.evidenceFileId" class="pl__evidence">已上传任务凭证</view>
            <view v-if="canSubmit(t)" class="pl__task-act">
              <textarea v-model="t._note" class="pl__input" maxlength="500" placeholder="填写完成说明（至少5字）" />
              <view class="pl__file-row">
                <button class="btn btn-secondary btn-sm" :disabled="submitting === t.sortOrder || uploading === t.sortOrder" @click="chooseEvidence(t)">
                  {{ uploading === t.sortOrder ? '上传中…' : (t._evidenceFileId ? '重新上传凭证' : '上传完成凭证') }}
                </button>
                <text class="pl__file-name" v-if="t._evidenceFileName">{{ t._evidenceFileName }}</text>
              </view>
              <button class="btn btn-primary btn-sm pl__submit" :disabled="submitting === t.sortOrder || uploading === t.sortOrder" @click="submitTask(t)">
                {{ t.progressStatus === 'REJECTED' ? '修改后重新提交' : '提交完成情况' }}
              </button>
            </view>
          </view>
        </view>
      </view>
      <view v-else class="page-pad"><MobileGlobalState state="empty" title="暂无实习计划" description="待学院发布当前批次实习计划书" /></view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="plan && plan.ackStatus === 'PENDING'">
      <button class="btn btn-primary flex-1" :disabled="submitting !== false" @click="ack">确认已阅读当前版本计划</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import {
  studentInternshipPlan,
  studentInternshipPlanAcknowledge,
  studentInternshipPlanTasks,
  studentInternshipPlanTaskSubmit
} from '@/services/internshipApi'
import { studentApi } from '@/services/studentApi'
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      pageState: 'loading', plan: null, tasks: [],
      context: {},
      summary: { total: 0, approved: 0, rate: 0 },
      submitting: false, uploading: false
    }
  },
  onLoad() { this.load() },
  methods: {
    async load() {
      this.pageState = 'loading'
      try {
        const [plan, taskData, dashboard] = await Promise.all([
          studentInternshipPlan(),
          studentInternshipPlanTasks().catch(() => null),
          studentApi.getInternship()
        ])
        this.context = {
          batchId: dashboard?.batchId || '',
          internshipId: dashboard?.recordId || dashboard?.internshipId || ''
        }
        this.plan = plan
        const sourceTasks = (taskData && taskData.tasks) || (plan && plan.tasks) || []
        this.tasks = sourceTasks.map((t) => ({
          ...t,
          _note: t.progressStatus === 'REJECTED' ? (t.studentNote || '') : '',
          _evidenceFileId: t.evidenceFileId || '',
          _evidenceFileName: t.evidenceFileId ? '已上传凭证' : ''
        }))
        this.summary = (taskData && taskData.summary) || (plan && plan.taskSummary) || this.summary
        this.pageState = plan ? 'ready' : 'empty'
      } catch (e) {
        this.pageState = 'error'
      }
    },
    canSubmit(t) {
      if (!this.plan || this.plan.ackStatus !== 'ACKNOWLEDGED') return false
      return ['NOT_STARTED', 'REJECTED'].includes(t.progressStatus || t.status)
    },
    async ack() {
      if (this.submitting !== false || !this.plan) return
      this.submitting = 'ack'
      try {
        await studentInternshipPlanAcknowledge({
          ...this.context,
          planId: this.plan.id || this.plan.planId,
          expectedVersion: this.plan.ackVersion || 0,
          planVersion: this.plan.version || this.plan.planVersion
        })
        toast('已确认当前版本实习计划')
        await this.load()
      } catch (e) {
        toast((e && e.message) || '计划确认失败，请刷新后重试')
        if (String(e && e.code) === 'DATA_CONFLICT') await this.load()
      } finally { this.submitting = false }
    },
    async chooseEvidence(t) {
      if (this.uploading) return
      this.uploading = t.sortOrder
      try {
        const file = await chooseSingleFile()
        if (!file) return
        if (Number(file.size || 0) > 20 * 1024 * 1024) return toast('单个凭证文件不能超过20MB')
        const uploaded = await uploadBusinessFile(file, {
          bizType: 'INTERNSHIP_PLAN_TASK', bizId: t.progressId || ''
        })
        t._evidenceFileId = uploaded.fileId
        t._evidenceFileName = uploaded.fileName || file.name || '任务凭证'
        toast('凭证上传成功')
      } catch (e) {
        toast((e && e.message) || '凭证上传失败')
      } finally { this.uploading = false }
    },
    async submitTask(t) {
      if (this.submitting !== false || this.uploading) return
      const note = (t._note || '').trim()
      if (note.length < 5) return toast('完成说明至少5字')
      this.submitting = t.sortOrder
      try {
        await studentInternshipPlanTaskSubmit(t.sortOrder, {
          planId: this.plan.id || this.plan.planId,
          studentNote: note,
          evidenceFileId: t._evidenceFileId || '',
          expectedVersion: t.progressVersion ?? t.version ?? 0
        })
        toast('已提交，等待教师确认')
        await this.load()
      } catch (e) {
        toast((e && e.message) || '提交失败，请刷新后重试')
        if (String(e && e.code) === 'DATA_CONFLICT') await this.load()
      } finally { this.submitting = false }
    },
    formatDeadline(v) {
      if (!v) return '—'
      const s = String(v).replace('T', ' ').slice(0, 16)
      return s.endsWith('23:59') ? s.slice(0, 10) + ' 23:59' : s
    }
  }
}
</script>

<style scoped>
.pl__status { display:block;margin-top:6px;font-size:var(--font-size-sm);color:var(--warning-600); }
.pl__prog { margin-top:10px;font-size:var(--font-size-sm);color:var(--text-secondary); }
.pl__bar { height:6px;background:#e2e8f0;border-radius:3px;margin-top:6px;overflow:hidden; }
.pl__bar-in { height:100%;background:var(--primary-500,#2563eb);border-radius:3px; }
.pl__label { display:block;font-size:var(--font-size-sm);font-weight:var(--font-weight-medium);margin:10px 0 4px; }
.pl__text { display:block;font-size:var(--font-size-sm);color:var(--text-secondary);line-height:1.6;white-space:pre-wrap; }
.pl__task { margin-top:10px;padding:10px;background:var(--bg-subtle,#f8fafc);border-radius:8px; }
.pl__task-head { display:flex;align-items:center;gap:8px;flex-wrap:wrap; }
.pl__task-no { width:22px;height:22px;line-height:22px;text-align:center;border-radius:50%;background:var(--primary-100,#dbeafe);color:var(--primary-700,#1d4ed8);font-size:12px;font-weight:600; }
.pl__task-name { flex:1;font-size:var(--font-size-sm);font-weight:var(--font-weight-medium); }
.pl__task-st { font-size:11px;color:var(--warning-700,#b45309); }
.pl__task-req,.pl__task-dl,.pl__task-reject { display:block;margin-top:6px;font-size:var(--font-size-xs);line-height:1.5; }
.pl__task-req { color:var(--text-secondary); }
.pl__task-dl { color:var(--warning-700,#b45309); }
.pl__task-reject { color:var(--danger-600,#dc2626); }
.pl__evidence { margin-top:6px;font-size:var(--font-size-xs);color:var(--success-600); }
.pl__task-act { margin-top:8px; }
.pl__input { width:100%;min-height:72px;padding:8px;border:1px solid #e2e8f0;border-radius:6px;font-size:13px;margin-bottom:8px;box-sizing:border-box; }
.pl__file-row { display:flex;align-items:center;gap:8px;margin-bottom:8px; }
.pl__file-name { flex:1;font-size:11px;color:var(--text-tertiary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap; }
.pl__submit { width:100%; }
</style>
