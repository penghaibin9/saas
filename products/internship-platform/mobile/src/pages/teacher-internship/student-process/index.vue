<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="学生过程事实" subtitle="轮岗部门、项目、自评与分项成绩" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack">
        <view class="card sp__head">
          <view><text class="t-lg t-bold">{{ studentName || '学生轮岗' }}</text><text class="sp__sub">当前批次 {{ batchId }} · 实习记录 {{ recordId }}</text></view>
          <button v-if="canManage" class="sp__add" @click="openCreate">新增轮岗</button>
        </view>
        <MobileInlineAlert type="info" description="每个部门单独建轮岗记录；分项成绩按批次权重合成，上一部门成绩不会被新部门覆盖。" />
        <MobileGlobalState v-if="!rows.length" state="empty" title="暂无轮岗记录" description="可由指导教师新增部门、项目与带教老师。" />

        <view v-for="item in rows" :key="item.id" class="card sp">
          <view class="row-between">
            <view class="flex-1"><text class="t-md t-bold">第{{ item.rotationSeq }}轮 · {{ item.departmentName }}</text><text class="sp__sub">{{ item.startDate }} ～ {{ item.endDate }} · {{ item.mentorName }}</text></view>
            <MobileStatusTag :label="statusLabel(item.status)" :type="item.status === 'COMPLETED' ? 'success' : item.status === 'ACTIVE' ? 'info' : 'default'" />
          </view>
          <view class="sp__facts">
            <view><text>部门负责人</text><text>{{ item.departmentManagerName || '未填写' }}</text></view>
            <view><text>学生自评</text><text>{{ item.studentSelfEvaluation ? item.studentSelfRating + '/5' : '未提交' }}</text></view>
          </view>
          <view class="sp__projects">
            <view v-for="project in item.projects" :key="project.id" class="sp__project">
              <text class="sp__project-name">{{ project.projectName }}</text>
              <text class="sp__sub">{{ project.projectContent || '暂无项目说明' }}</text>
              <text class="sp__sub">{{ project.startDate || '—' }} ～ {{ project.endDate || '—' }}</text>
            </view>
            <text v-if="!item.projects.length" class="sp__sub">尚未登记项目。</text>
          </view>
          <view v-if="item.studentSelfEvaluation" class="sp__self">
            <text class="sp__label">学生自评</text>
            <text>{{ item.studentSelfEvaluation }}</text>
          </view>
          <view class="sp__score">
            <view><text>{{ score(item.scores?.theory) }}</text><text>理论</text></view>
            <view><text>{{ score(item.scores?.skill) }}</text><text>技能</text></view>
            <view><text>{{ score(item.scores?.mentor) }}</text><text>带教</text></view>
            <view class="is-total"><text>{{ score(item.scores?.total) }}</text><text>总分</text></view>
          </view>
          <button v-if="canManage && item.studentSelfEvaluation && item.projects.length && item.status !== 'CANCELLED'"
            class="btn btn-primary" :disabled="actingId === item.id" @click="evaluate(item)">
            {{ actingId === item.id ? '提交中…' : (item.scores?.total == null ? '评定分项成绩' : '更新分项成绩') }}
          </button>
        </view>
      </view>
    </MobileGlobalState>

    <view v-if="form.visible" class="sp__mask" @click.self="closeCreate">
      <view class="sp__dialog">
        <view class="row-between"><text class="t-lg t-bold">新增轮岗安排</text><button class="sp__close" @click="closeCreate">×</button></view>
        <input v-model.trim="form.departmentName" class="sp__input" placeholder="轮岗部门，例如 生产一部" />
        <input v-model.trim="form.departmentManagerName" class="sp__input" placeholder="部门负责人（可选）" />
        <input v-model.trim="form.mentorName" class="sp__input" placeholder="带教老师 *" />
        <view class="sp__pair">
          <picker mode="date" :value="form.startDate" @change="form.startDate = $event.detail.value"><view class="sp__picker">{{ form.startDate || '开始日期' }}</view></picker>
          <picker mode="date" :value="form.endDate" @change="form.endDate = $event.detail.value"><view class="sp__picker">{{ form.endDate || '结束日期' }}</view></picker>
        </view>
        <view class="sp__projects-edit">
          <view class="row-between"><text class="sp__label">轮岗项目</text><button class="sp__tiny" @click="addProject">+ 项目</button></view>
          <view v-for="(project,index) in form.projects" :key="index" class="sp__project-edit">
            <input v-model.trim="project.projectName" class="sp__input" :placeholder="'项目'+(index+1)+'名称'" />
            <textarea v-model="project.projectContent" class="sp__textarea" maxlength="1000" placeholder="项目内容（可选）" />
            <button v-if="form.projects.length > 1" class="sp__remove" @click="form.projects.splice(index,1)">删除该项目</button>
          </view>
        </view>
        <button class="btn btn-primary" :disabled="saving" @click="createRotation">{{ saving ? '保存中…' : '保存轮岗安排' }}</button>
      </view>
    </view>
  </view>
</template>

<script>
import {
  teacherInternshipCreateRotation,
  teacherInternshipEvaluateRotation,
  teacherInternshipStudentRotations
} from '@/services/internshipApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'

const emptyForm = () => ({
  visible: false, departmentName: '', departmentManagerName: '', mentorName: '',
  startDate: '', endDate: '', projects: [{ projectName: '', projectContent: '' }]
})

export default {
  data() {
    return {
      state: 'loading', error: '', recordId: '', batchId: '', studentName: '',
      rows: [], form: emptyForm(), saving: false, actingId: ''
    }
  },
  computed: {
    context() { return useInternshipContextStore() },
    canManage() { return this.context.can('internship.rotation.manage') }
  },
  onLoad(query = {}) {
    this.recordId = String(query.id || query.recordId || '')
    this.batchId = String(query.batchId || '')
    this.studentName = decodeURIComponent(String(query.name || ''))
    this.load()
  },
  methods: {
    statusLabel(status) { return ({ PLANNED: '待开始', ACTIVE: '轮岗中', COMPLETED: '已完成', CANCELLED: '已取消' })[status] || status },
    score(value) { return value == null ? '—' : Number(value).toFixed(1) },
    async load() {
      this.state = 'loading'
      try {
        if (!this.recordId || !this.batchId) throw new Error('轮岗链接缺少学生或批次信息')
        this.context.restore()
        if (!this.context.loaded) await this.context.load()
        const rows = await teacherInternshipStudentRotations(this.recordId, this.batchId)
        this.rows = Array.isArray(rows) ? rows : []
        this.state = 'ready'
      } catch (e) { this.state = 'error'; toast(e?.message || '轮岗记录加载失败') }
    },
    openCreate() { if (this.canManage) this.form = { ...emptyForm(), visible: true, projects: [{ projectName: '', projectContent: '' }] } },
    closeCreate() { if (!this.saving) this.form = emptyForm() },
    addProject() { if (this.form.projects.length < 10) this.form.projects.push({ projectName: '', projectContent: '' }) },
    async createRotation() {
      const f = this.form
      if (String(f.departmentName || '').trim().length < 2) return toast('请填写轮岗部门')
      if (String(f.mentorName || '').trim().length < 2) return toast('请填写带教老师')
      if (!f.startDate || !f.endDate || f.startDate > f.endDate) return toast('请选择正确的轮岗起止日期')
      const projects = f.projects.filter((p) => String(p.projectName || '').trim())
      if (!projects.length) return toast('至少登记一个轮岗项目')
      this.saving = true
      try {
        await teacherInternshipCreateRotation(this.recordId, this.batchId, {
          departmentName: f.departmentName,
          departmentManagerName: f.departmentManagerName,
          mentorName: f.mentorName,
          startDate: f.startDate, endDate: f.endDate,
          projects
        })
        toast('轮岗安排已创建')
        this.form = emptyForm()
        await this.load()
      } catch (e) { toast(e?.message || '轮岗安排保存失败') }
      finally { this.saving = false }
    },
    evaluate(item) {
      if (!this.canManage || this.actingId) return
      uni.showModal({
        title: '评定轮岗成绩',
        editable: true,
        placeholderText: '输入：理论,技能,带教，例如 85,90,92',
        content: '三项均为 0-100；总分由批次配置权重在服务端计算。',
        success: async (result) => {
          if (!result.confirm) return
          const parts = String(result.content || '').split(',').map(v => v.trim())
          if (parts.length !== 3 || parts.some(v => v === '' || Number.isNaN(Number(v)))) return toast('请输入三个分数，例如 85,90,92')
          if (parts.some(v => Number(v) < 0 || Number(v) > 100)) return toast('分数必须在0-100之间')
          this.actingId = item.id
          try {
            await teacherInternshipEvaluateRotation(item.id, this.batchId, {
              theoryScore: parts[0], skillScore: parts[1], mentorScore: parts[2],
              comment: '教师移动端完成轮岗分项成绩评定',
              expectedVersion: item.version
            })
            toast('轮岗成绩已评定')
            await this.load()
          } catch (e) { toast(e?.message || '轮岗成绩评定失败') }
          finally { this.actingId = '' }
        }
      })
    }
  }
}
</script>

<style scoped>
.sp__head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:14px}.sp__sub{display:block;margin-top:4px;font-size:11px;color:var(--text-tertiary);line-height:1.55}.sp__add,.sp__tiny,.sp__remove{margin:0;padding:3px 6px;min-height:0;border:0;background:transparent;color:var(--teacher-700);font-size:12px}.sp__add::after,.sp__tiny::after,.sp__remove::after{border:none}.sp{display:flex;flex-direction:column;gap:11px;padding:14px}.sp__facts{display:grid;grid-template-columns:1fr 1fr;gap:6px}.sp__facts view{padding:8px;border-radius:7px;background:var(--gray-50)}.sp__facts text{display:block}.sp__facts text:first-child{font-size:9px;color:var(--text-tertiary)}.sp__facts text:last-child{margin-top:3px;font-size:12px}.sp__projects{display:flex;flex-direction:column;gap:7px}.sp__project{padding:9px;border-radius:8px;background:var(--gray-50)}.sp__project-name,.sp__label{display:block;font-size:12px;font-weight:600}.sp__self{padding:10px;border-radius:8px;background:var(--primary-50);font-size:12px;line-height:1.7}.sp__self>text:last-child{display:block;margin-top:4px}.sp__score{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;padding:9px;border-radius:8px;background:var(--gray-50)}.sp__score view{display:flex;flex-direction:column;align-items:center;gap:3px}.sp__score text:first-child{font-size:17px;font-weight:700}.sp__score text:last-child{font-size:9px;color:var(--text-tertiary)}.sp__score .is-total text:first-child{color:var(--teacher-700)}.sp__mask{position:fixed;inset:0;z-index:999;display:flex;align-items:flex-end;background:rgba(15,23,42,.48)}.sp__dialog{box-sizing:border-box;width:100%;max-height:90vh;overflow:auto;padding:18px;border-radius:18px 18px 0 0;background:#fff;display:flex;flex-direction:column;gap:9px}.sp__close{margin:0;padding:0 6px;min-height:0;border:0;background:transparent;font-size:24px}.sp__close::after{border:none}.sp__input,.sp__textarea,.sp__picker{box-sizing:border-box;width:100%;border:1px solid var(--border-base);border-radius:8px;padding:10px 12px;background:#fff;font-size:13px}.sp__textarea{min-height:70px}.sp__pair{display:grid;grid-template-columns:1fr 1fr;gap:8px}.sp__projects-edit{display:flex;flex-direction:column;gap:8px}.sp__project-edit{padding:8px;border-radius:8px;background:var(--gray-50);display:flex;flex-direction:column;gap:6px}.sp__remove{align-self:flex-end;color:var(--danger-600)}
</style>
