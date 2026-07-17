<template>
  <GraduationFormPageShell
    layout="inline"
    :ctx="ctx"
    :title="editing ? '编辑题目' : applyTitle"
    :subtitle="editing ? '修改题目信息后保存' : '填写题目信息，保存后可提交审核'"
    :back-to="backTo"
  >
    <form class="ie-form" @submit.prevent="submitForm">
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">题目名称 <i>*</i></span>
        <input v-model.trim="form.title" class="ie-in" placeholder="2~300字" />
      </label>
      <label class="ie-fld"><span class="ie-lbl">毕设批次</span>
        <select v-model="form.batchId" class="ie-in">
          <option value="">不关联批次</option>
          <option v-for="b in batchOpts" :key="b.id" :value="b.id">{{ b.batchName }}</option>
        </select>
      </label>
      <label class="ie-fld"><span class="ie-lbl">题目编号</span><input v-model.trim="form.topicNo" class="ie-in" /></label>
      <div class="ie-fld"><span class="ie-lbl">指导教师</span>
        <AppMentorPicker v-model="form.advisorName" :remote-search="searchMentors" placeholder="按姓名 / 工号搜索导师" />
      </div>
      <label class="ie-fld"><span class="ie-lbl">专业</span><input v-model.trim="form.majorName" class="ie-in" /></label>
      <label class="ie-fld"><span class="ie-lbl">分类</span>
        <select v-model="form.category" class="ie-in">
          <option value="">请选择</option>
          <option v-for="c in GD_TOPIC_CATEGORY" :key="c" :value="c">{{ c }}</option>
        </select>
      </label>
      <label class="ie-fld"><span class="ie-lbl">难度</span>
        <select v-model="form.difficulty" class="ie-in">
          <option value="">请选择</option>
          <option v-for="d in GD_TOPIC_DIFFICULTY" :key="d.value" :value="d.value">{{ d.label }}</option>
        </select>
      </label>
      <label v-if="form.sourceType === 'ENTERPRISE'" class="ie-fld ie-fld--full">
        <span class="ie-lbl">企业名称</span><input v-model.trim="form.enterpriseName" class="ie-in" />
      </label>
      <label class="ie-fld"><span class="ie-lbl">容量</span>
        <input v-model.number="form.capacity" type="number" min="1" max="99" class="ie-in" />
      </label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">题目要求</span>
        <textarea v-model.trim="form.requirements" class="ie-in" rows="3" />
      </label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">预期成果</span>
        <textarea v-model.trim="form.outcome" class="ie-in" rows="2" />
      </label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">技能要求</span>
        <textarea v-model.trim="form.skills" class="ie-in" rows="2" placeholder="专业基础、技能要求…" />
        <AppTemplateChips :options="SKILL_CHIPS" @pick="(t) => (form.skills = form.skills ? form.skills + '\n' + t : t)" />
      </label>
      <label v-if="!editing" class="ie-fld ie-fld--full">
        <input v-model="form.submitReview" type="checkbox" /> 保存后直接提交审核
      </label>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template #footer>
      <button type="button" class="mp-btn" @click="$router.push(backTo)">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submitForm">保存</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { gdTopicApi } from '@/modules/graduation/api/graduation-topic.api'
import { graduationMentorApi } from '@/modules/graduation/api/graduation-mentor.api'
import { AppMentorPicker, AppTemplateChips } from '@/components/common'
import { GD_TOPIC_CATEGORY, GD_TOPIC_DIFFICULTY } from '@/modules/graduation/constants/graduation-topic.constants'
import { toast } from '@/utils/toast'

const SKILL_CHIPS = [
  '要求有一定编程基础，掌握Java/Python/JavaScript之一',
  '要求熟悉数据库原理，有Web开发基础',
  '无特殊要求，有学习热情即可'
]

const EMPTY_FORM = (sourceType = 'TEACHER') => ({
  title: '', batchId: '', topicNo: '', sourceType, advisorName: '', majorName: '',
  category: '', difficulty: '', enterpriseName: '', capacity: 1,
  requirements: '', outcome: '', skills: '', submitReview: false
})

const APPLY_TITLES = {
  TEACHER: '教师申报题目',
  ENTERPRISE: '企业题目申报',
  STUDENT: '学生自拟题目'
}

export default {
  name: 'TopicLibFormView',
  components: { GraduationFormPageShell, AppMentorPicker, AppTemplateChips },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      GD_TOPIC_CATEGORY, GD_TOPIC_DIFFICULTY, SKILL_CHIPS,
      submitting: false, editing: null, form: EMPTY_FORM(), formError: '',
      batchOpts: []
    }
  },
  computed: {
    backTo() {
      const panel = this.$route.query.returnPanel || 'list'
      return `/admin/graduation/topic-lib?panel=${panel}`
    },
    applyTitle() {
      return APPLY_TITLES[this.form.sourceType] || '申报题目'
    }
  },
  async created() {
    const b = await gdTopicApi.getBatchOptions()
    if (b.code === 0) this.batchOpts = b.data
    const id = this.$route.params.id
    if (id) {
      const d = await gdTopicApi.getTopicDetail(id)
      if (d.code !== 0) { toast.error(d.message); return }
      this.editing = d.data
      const row = d.data
      this.form = {
        title: row.title, batchId: row.batchId || '', topicNo: row.topicNo || '',
        sourceType: row.sourceType, advisorName: row.advisorName || '', majorName: row.majorName || '',
        category: row.category || '', difficulty: row.difficulty || '', enterpriseName: row.enterpriseName || '',
        capacity: row.capacity, requirements: row.requirements || '', outcome: row.outcome || '',
        skills: row.skills || '', submitReview: false
      }
    } else {
      const sourceType = this.$route.query.sourceType || 'TEACHER'
      this.form = EMPTY_FORM(sourceType)
    }
  },
  methods: {
    /** 导师远程搜索（导师库真实接口，按姓名/工号） */
    async searchMentors(keyword) {
      const res = await graduationMentorApi.getMentors({ keyword, pageSize: 20 })
      if (res.code !== 0) throw new Error(res.message || "搜索失败")
      return res.data.list.map((m) => ({ label: m.teacherName + "（" + (m.capacityText || m.collegeName || "教师") + "）", value: m.teacherName }))
    },
    async submitForm() {
      if (!this.form.title || this.form.title.length < 2) { this.formError = '题目名称至少2字'; return }
      this.submitting = true
      this.formError = ''
      const body = { ...this.form, batchId: this.form.batchId || null }
      const r = this.editing
        ? await gdTopicApi.updateTopic(this.editing.id, body)
        : await gdTopicApi.createTopic(body)
      this.submitting = false
      if (r.code !== 0) { this.formError = r.message; return }
      toast.success(this.editing ? '已保存' : '已创建')
      this.$router.push(this.backTo)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
