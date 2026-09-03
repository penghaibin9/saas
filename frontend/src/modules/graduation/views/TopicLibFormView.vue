<template>
  <GraduationFormPageShell
    layout="inline"
    :ctx="ctx"
    :title="editing ? '编辑毕业设计题目' : applyTitle"
    :subtitle="editing ? '核对题目适用范围、指导关系与成果要求，保存后回到原工作队列。' : '把题目、指导责任和预期成果一次说明清楚，保存后可按原流程提交审核。'"
    eyebrow="题目与选题"
    :status-text="editing ? (editing.reviewStatusLabel || editing.reviewStatus || '编辑中') : '新题目申报'"
    :status-tone="topicStatusTone"
    :back-to="backTo"
    back-label="返回题目库"
    :busy="submitting"
  >
    <template #context>
      <div class="topic-context">
        <span>题目来源</span>
        <strong>{{ sourceLabel }}</strong>
      </div>
      <div class="topic-context">
        <span>关联批次</span>
        <strong>{{ form.batchId ? '已选择' : '暂未关联' }}</strong>
      </div>
      <div class="topic-context">
        <span>学生容量</span>
        <strong>{{ Number(form.capacity || 0) }} 人</strong>
      </div>
      <div class="topic-context">
        <span>材料完善度</span>
        <strong>{{ completionCount }}/5</strong>
      </div>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="loadError" :description="loadError" @retry="load" />
    <form v-else class="ie-form" @submit.prevent="submitForm">
      <section class="gd-form-section">
        <header class="gd-form-section__head">
          <div>
            <span>01 · 题目身份</span>
            <strong>让学生一眼看懂要做什么、属于哪一届</strong>
            <small>题目名称用于学生选题、过程指导、论文成果和归档，避免使用只有老师能懂的内部简称。</small>
          </div>
        </header>

        <label class="ie-fld ie-fld--full">
          <span class="ie-lbl">题目名称 <i>*</i></span>
          <input v-model.trim="form.title" class="ie-in" placeholder="2～300 字，写清对象、方法和目标" autocomplete="off" />
          <small class="ie-hint">示例：面向中职学生实习管理的风险预警系统设计与实现。</small>
        </label>
        <label class="ie-fld">
          <span class="ie-lbl">毕业设计批次</span>
          <AppGraduationDesignBatchPicker v-model="form.batchId" clearable placeholder="选择适用批次" />
          <small class="ie-hint">可暂不关联；进入正式选题前仍需由真实批次关系约束。</small>
        </label>
        <label class="ie-fld">
          <span class="ie-lbl">题目编号</span>
          <input v-model.trim="form.topicNo" class="ie-in" placeholder="按学校规则填写，可留空" autocomplete="off" />
        </label>
      </section>

      <section class="gd-form-section">
        <header class="gd-form-section__head">
          <div>
            <span>02 · 指导与适用范围</span>
            <strong>明确谁负责、适合哪些学生、最多可接收多少人</strong>
            <small>导师资格、容量和最终分配仍由服务端校验，本页不会用前端计数绕过规则。</small>
          </div>
        </header>

        <div class="ie-fld">
          <span class="ie-lbl">指导教师</span>
          <AppGraduationMentorPicker v-model="form.advisorName" placeholder="按姓名 / 工号搜索导师" />
        </div>
        <label class="ie-fld">
          <span class="ie-lbl">适用专业</span>
          <input v-model.trim="form.majorName" class="ie-in" placeholder="如 软件技术" autocomplete="off" />
        </label>
        <label class="ie-fld">
          <span class="ie-lbl">题目分类</span>
          <AppSelect v-model="form.category" :options="categoryOptions" />
        </label>
        <label class="ie-fld">
          <span class="ie-lbl">难度</span>
          <AppSelect v-model="form.difficulty" :options="GD_TOPIC_DIFFICULTY" />
        </label>
        <label v-if="form.sourceType === 'ENTERPRISE'" class="ie-fld ie-fld--full">
          <span class="ie-lbl">来源企业</span>
          <input v-model.trim="form.enterpriseName" class="ie-in" placeholder="填写真实企业名称" autocomplete="off" />
        </label>
        <label class="ie-fld">
          <span class="ie-lbl">学生容量</span>
          <input v-model.number="form.capacity" type="number" min="1" max="99" class="ie-in" inputmode="numeric" />
          <small class="ie-hint">服务端仍会结合导师容量、选题轮次和已分配人数判断。</small>
        </label>
      </section>

      <section class="gd-form-section">
        <header class="gd-form-section__head">
          <div>
            <span>03 · 完成标准</span>
            <strong>提前说明学生最终要交什么、做到什么程度</strong>
            <small>这些内容会贯穿任务书、过程指导、成果评阅和答辩，不应只写一句泛化描述。</small>
          </div>
        </header>

        <label class="ie-fld ie-fld--full">
          <span class="ie-lbl">题目要求</span>
          <textarea v-model.trim="form.requirements" class="ie-in" rows="4" placeholder="说明业务范围、主要功能、技术边界、过程要求与验收标准" />
        </label>
        <label class="ie-fld ie-fld--full">
          <span class="ie-lbl">预期成果</span>
          <textarea v-model.trim="form.outcome" class="ie-in" rows="3" placeholder="如：可运行系统、源代码、部署说明、测试报告、毕业论文" />
        </label>
        <label class="ie-fld ie-fld--full">
          <span class="ie-lbl">技能要求</span>
          <textarea v-model.trim="form.skills" class="ie-in" rows="3" placeholder="列出必要基础，不要用模糊的“能力强”作为门槛" />
          <AppTemplateChips :options="SKILL_CHIPS" @pick="appendSkill" />
        </label>
      </section>

      <section v-if="!editing" class="gd-form-section topic-submit-section">
        <header class="gd-form-section__head">
          <div>
            <span>04 · 保存方式</span>
            <strong>决定先存草稿，还是保存后进入正式审核队列</strong>
            <small>勾选后仍走原有题目审核状态机，不会直接成为可选题目。</small>
          </div>
        </header>
        <label class="topic-review-choice gd-form-section__full">
          <input v-model="form.submitReview" type="checkbox" />
          <span><strong>保存后直接提交审核</strong><small>适合信息已经齐全的题目；未勾选则保留为草稿。</small></span>
        </label>
      </section>

      <p v-if="formError" class="ie-err" role="alert">{{ formError }}</p>
    </form>

    <template #aside>
      <section class="gd-form-aside-card">
        <span>题目完整性</span>
        <strong>{{ completionCount === 5 ? '主要材料已齐全' : `建议再完善 ${5 - completionCount} 项` }}</strong>
        <ul class="gd-form-checklist">
          <li :class="{ 'is-ready': titleReady }">题目名称清楚且不少于 2 字</li>
          <li :class="{ 'is-ready': Boolean(form.advisorName) }">指导教师已经明确</li>
          <li :class="{ 'is-ready': Boolean(form.category && form.difficulty) }">分类与难度已经选择</li>
          <li :class="{ 'is-ready': Boolean(form.requirements) }">题目要求可以指导过程实施</li>
          <li :class="{ 'is-ready': Boolean(form.outcome) }">预期成果可用于最终验收</li>
        </ul>
      </section>
      <section class="gd-form-aside-card">
        <span>保存后的真实流转</span>
        <strong>{{ submitNextStep }}</strong>
        <p>审核通过后才进入选题轮次；学生选中后，任务书、开题、论文成果和归档继续绑定同一题目关系。</p>
      </section>
      <section class="gd-form-aside-card">
        <span>跨端可见性</span>
        <strong>教师 PC、学生 PC 与微信端读取同一题目事实</strong>
        <p>本页只写入题目主档，不在浏览器端伪造审核通过、容量或学生分配结果。</p>
      </section>
    </template>

    <template #footer>
      <button type="button" class="mp-btn" :disabled="submitting" @click="cancel">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || loading" @click="submitForm">
        {{ submitting ? '保存中…' : editing ? '保存题目' : form.submitReview ? '保存并提交审核' : '保存草稿' }}
      </button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { ErrorState, LoadingState } from '@/components/business'
import { gdTopicApi } from '@/modules/graduation/api/graduation-topic.api'
import { AppGraduationDesignBatchPicker, AppGraduationMentorPicker, AppSelect, AppTemplateChips } from '@/components/common'
import { GD_TOPIC_CATEGORY, GD_TOPIC_DIFFICULTY } from '@/modules/graduation/constants/graduation-topic.constants'
import { toast } from '@/utils/toast'

const SKILL_CHIPS = [
  '要求有一定编程基础，掌握 Java / Python / JavaScript 之一',
  '要求熟悉数据库原理，有 Web 开发基础',
  '无特殊要求，有学习热情即可'
]

const EMPTY_FORM = (sourceType = 'TEACHER') => ({
  title: '', batchId: '', topicNo: '', sourceType, advisorName: '', majorName: '',
  category: '', difficulty: '', enterpriseName: '', capacity: 1,
  requirements: '', outcome: '', skills: '', submitReview: false
})

const APPLY_TITLES = {
  TEACHER: '教师申报毕业设计题目',
  ENTERPRISE: '企业申报毕业设计题目',
  STUDENT: '学生自拟毕业设计题目'
}

const SOURCE_LABELS = {
  TEACHER: '教师申报',
  ENTERPRISE: '企业题目',
  STUDENT: '学生自拟'
}

const SAFE_PREFIX = '/admin/graduation/'
const freezeSnapshot = (value) => Object.freeze({ ...value })

export default {
  name: 'TopicLibFormView',
  components: {
    GraduationFormPageShell,
    ErrorState,
    LoadingState,
    AppGraduationDesignBatchPicker,
    AppGraduationMentorPicker,
    AppSelect,
    AppTemplateChips
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      GD_TOPIC_CATEGORY,
      GD_TOPIC_DIFFICULTY,
      SKILL_CHIPS,
      submitting: false,
      loading: false,
      loadError: '',
      editing: null,
      form: EMPTY_FORM(),
      formError: '',
      commandSnapshot: null
    }
  },
  computed: {
    categoryOptions() {
      return this.GD_TOPIC_CATEGORY.map((value) => ({ value, label: value }))
    },
    backTo() {
      const panel = String(this.$route.query.returnPanel || this.$route.query.panel || 'list')
      return this.$router.resolve({
        name: 'graduation-topic-lib',
        query: {
          ...this.$route.query,
          panel,
          returnPanel: undefined,
          sourceType: undefined,
          returnTo: undefined
        }
      }).fullPath
    },
    safeExitTarget() {
      const raw = Array.isArray(this.$route.query.returnTo)
        ? this.$route.query.returnTo[0]
        : this.$route.query.returnTo
      const value = String(raw || '').trim()
      return value.startsWith(SAFE_PREFIX) ? value : this.backTo
    },
    applyTitle() {
      return APPLY_TITLES[this.form.sourceType] || '申报毕业设计题目'
    },
    sourceLabel() {
      return SOURCE_LABELS[this.form.sourceType] || '题目申报'
    },
    titleReady() {
      return Boolean(this.form.title && this.form.title.length >= 2)
    },
    capacityReady() {
      const value = Number(this.form.capacity)
      return Number.isFinite(value) && value >= 1 && value <= 99
    },
    completionCount() {
      return [
        this.titleReady,
        Boolean(this.form.advisorName),
        Boolean(this.form.category && this.form.difficulty),
        Boolean(this.form.requirements),
        Boolean(this.form.outcome)
      ].filter(Boolean).length
    },
    submitNextStep() {
      if (this.editing) return '保存后回到题目库，继续查看审核状态或选题关系'
      return this.form.submitReview ? '保存后进入题目审核队列' : '先保存草稿，完善后再提交审核'
    },
    topicStatusTone() {
      const status = String(this.editing?.reviewStatus || this.editing?.status || '').toUpperCase()
      if (status === 'APPROVED') return 'success'
      if (status === 'REJECTED' || status === 'ARCHIVED') return 'danger'
      if (status === 'PENDING_REVIEW') return 'warning'
      return 'info'
    }
  },
  created() {
    this.load()
  },
  beforeRouteLeave(to, from, next) {
    if (this.submitting) {
      toast.info('题目正在保存，请等待服务器回执后再离开')
      next(false)
      return
    }
    next()
  },
  methods: {
    appendSkill(text) {
      this.form.skills = this.form.skills ? `${this.form.skills}\n${text}` : text
    },
    cancel() {
      if (!this.submitting) this.$router.push(this.safeExitTarget)
    },
    async load() {
      const id = this.$route.params.id
      if (!id) {
        const sourceType = String(this.$route.query.sourceType || 'TEACHER').toUpperCase()
        this.form = EMPTY_FORM(Object.prototype.hasOwnProperty.call(APPLY_TITLES, sourceType) ? sourceType : 'TEACHER')
        return
      }
      this.loading = true
      this.loadError = ''
      try {
        const response = await gdTopicApi.getTopicDetail(id)
        if (response.code !== 0) {
          this.loadError = response.message || '题目详情加载失败'
          return
        }
        this.editing = response.data
        const row = response.data || {}
        this.form = {
          title: row.title || '',
          batchId: row.batchId || '',
          topicNo: row.topicNo || '',
          sourceType: row.sourceType || 'TEACHER',
          advisorName: row.advisorName || '',
          majorName: row.majorName || '',
          category: row.category || '',
          difficulty: row.difficulty || '',
          enterpriseName: row.enterpriseName || '',
          capacity: Number(row.capacity || 1),
          requirements: row.requirements || '',
          outcome: row.outcome || '',
          skills: row.skills || '',
          submitReview: false
        }
      } catch (error) {
        this.loadError = error?.message || '题目详情加载失败'
      } finally {
        this.loading = false
      }
    },
    validate() {
      if (!this.titleReady) return '题目名称至少 2 字'
      if (!this.capacityReady) return '学生容量必须在 1～99 之间'
      if (this.form.sourceType === 'ENTERPRISE' && !this.form.enterpriseName) return '企业题目需要填写来源企业'
      return ''
    },
    async submitForm() {
      if (this.submitting) return
      this.formError = this.validate()
      if (this.formError) return

      const body = freezeSnapshot({ ...this.form, batchId: this.form.batchId || null })
      const snapshot = freezeSnapshot({
        editing: Boolean(this.editing),
        id: this.editing?.id || null,
        body,
        returnTo: this.safeExitTarget
      })
      this.commandSnapshot = snapshot
      this.submitting = true
      let saved = false
      try {
        const response = snapshot.editing
          ? await gdTopicApi.updateTopic(snapshot.id, snapshot.body)
          : await gdTopicApi.createTopic(snapshot.body)
        if (response.code !== 0) {
          this.formError = response.message || '题目保存失败'
          return
        }
        saved = true
        toast.success(snapshot.editing
          ? '题目已保存，审核与选题状态以服务器最新结果为准'
          : this.form.submitReview ? '题目已创建并进入审核队列' : '题目草稿已创建')
      } catch (error) {
        this.formError = error?.message || '题目保存失败'
      } finally {
        this.submitting = false
        this.commandSnapshot = null
      }
      if (saved) await this.$router.push(snapshot.returnTo)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.topic-context {
  display: grid;
  flex: 0 0 auto;
  min-width: 128px;
  gap: 2px;
  padding: 7px 10px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 8px;
  background: var(--bg-card, #fff);
}

.topic-context span {
  color: var(--text-tertiary, #64748b);
  font-size: 10px;
}

.topic-context strong {
  overflow: hidden;
  color: var(--text-primary, #0f172a);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topic-review-choice {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--primary-100, #dbeafe);
  border-radius: 9px;
  background: var(--primary-50, #eff6ff);
  cursor: pointer;
}

.topic-review-choice input {
  width: 16px;
  height: 16px;
  margin-top: 2px;
}

.topic-review-choice span {
  display: grid;
  gap: 2px;
}

.topic-review-choice strong {
  color: var(--text-primary, #0f172a);
  font-size: 12px;
}

.topic-review-choice small {
  color: var(--text-secondary, #64748b);
  font-size: 11px;
  line-height: 1.5;
}

.mp-btn {
  min-height: 36px;
  padding: 0 16px;
  border: 1px solid var(--border-base, #d9dee8);
  border-radius: 8px;
  background: var(--bg-card, #fff);
  color: var(--text-primary, #0f172a);
  cursor: pointer;
  font-size: 13px;
}

.mp-btn--primary {
  border-color: var(--primary-600, #2563eb);
  background: var(--primary-600, #2563eb);
  color: #fff;
}

.mp-btn:disabled {
  cursor: not-allowed;
  opacity: .5;
}
</style>
