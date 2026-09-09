<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="batchMode ? '批量设置过程分组' : (student ? `过程分组 · ${student.name}` : '过程分组')"
    :subtitle="batchMode ? `已选择 ${recordIds.length} 名学生 · 同一批次范围内统一写入` : (student ? `${student.studentNo} · ${student.className || '班级待确认'}` : '正在读取学生主档')"
    eyebrow="批次实施 · 过程组织"
    purpose="过程分组用于指导、检查和统计组织，不替代班级、导师、答辩组或教务主档。"
    :status-text="submitting ? '保存中' : (batchMode ? '批量办理' : '待保存')"
    status-tone="warning"
    :back-to="backTo"
    :busy="submitting"
    @blocked-back="onBlockedBack"
  >
    <template #context>
      <div class="sg-context">
        <span><b>办理对象</b>{{ batchMode ? `${recordIds.length} 名学生` : (student ? `${student.name} · ${student.studentNo}` : '正在读取') }}</span>
        <span><b>当前批次</b>{{ batchLabel }}</span>
        <span><b>当前分组</b>{{ batchMode ? '多学生批量设置' : (student?.studentGroup || '尚未分组') }}</span>
      </div>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="loadError" :description="loadError" @retry="load" />
    <form v-else class="ie-form sg-form" @submit.prevent="submit">
      <section class="sg-section ie-fld--full">
        <header>
          <span>01</span>
          <div>
            <strong>核对办理范围</strong>
            <small>{{ batchMode ? '批量操作只使用当前页面传入的学生记录 ID。' : '只修改当前学生的过程分组字段。' }}</small>
          </div>
        </header>
        <div class="sg-current">
          <div>
            <span>{{ batchMode ? '已选学生' : '学生' }}</span>
            <strong>{{ batchMode ? `${recordIds.length} 人` : student.name }}</strong>
            <small>{{ batchMode ? selectedPreview : `${student.studentNo} · ${student.topicTitle || '题目待确认'}` }}</small>
          </div>
          <div>
            <span>现有分组</span>
            <strong>{{ batchMode ? '可能包含多个分组' : (student.studentGroup || '尚未分组') }}</strong>
            <small>保存后只更新过程分组，不改班级、导师和答辩组</small>
          </div>
        </div>
      </section>

      <section class="sg-section ie-fld--full">
        <header>
          <span>02</span>
          <div>
            <strong>设置目标分组</strong>
            <small>可复用已有分组名称，也可创建本批次的新分组标签。</small>
          </div>
        </header>
        <div class="sg-section__body">
          <label class="ie-fld ie-fld--full">
            <span class="ie-lbl">目标分组名称 <i>*</i></span>
            <input
              v-model.trim="groupName"
              class="ie-in"
              list="gd-group-suggest"
              :disabled="submitting"
              placeholder="如：第1组 / A组 / 移动应用方向组"
              @input="formError = ''"
            />
            <datalist id="gd-group-suggest">
              <option v-for="group in groupOpts" :key="group" :value="group" />
            </datalist>
            <p class="ie-hint">分组名称用于当前毕业设计批次的过程组织；建议保持简短、可识别。</p>
          </label>
          <label class="ie-fld ie-fld--full">
            <span class="ie-lbl">设置说明</span>
            <textarea
              v-model.trim="reason"
              class="ie-in"
              rows="3"
              :disabled="submitting"
              :placeholder="batchMode ? '说明本次批量分组依据。' : '可填写调整分组的原因。'"
              @input="formError = ''"
            ></textarea>
          </label>
        </div>
      </section>

      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>

    <template v-if="batchMode || student" #aside>
      <section class="sg-aside-card">
        <span>保存前检查</span>
        <ul>
          <li :class="{ done: objectReady }"><b>{{ objectReady ? '✓' : '1' }}</b><div><strong>办理对象有效</strong><small>{{ batchMode ? `${recordIds.length} 个记录 ID` : student?.studentNo }}</small></div></li>
          <li :class="{ done: Boolean(groupName) }"><b>{{ groupName ? '✓' : '2' }}</b><div><strong>已填写目标分组</strong><small>必填</small></div></li>
          <li :class="{ done: Boolean(batchLabel) }"><b>{{ batchLabel ? '✓' : '3' }}</b><div><strong>批次上下文已保留</strong><small>返回时恢复原队列</small></div></li>
        </ul>
      </section>
      <section class="sg-aside-card is-next">
        <span>保存后的真实流转</span>
        <ol>
          <li>服务端按当前数据范围更新过程分组</li>
          <li>{{ batchMode ? '回执显示实际更新人数' : '重新读取学生档案确认分组' }}</li>
          <li>返回学生与进度的过程分组视图</li>
        </ol>
      </section>
      <section class="sg-warning">
        <strong>只影响过程组织</strong>
        <p>本操作不会修改行政班级、指导教师、题目、答辩组或最终毕业资格。</p>
      </section>
    </template>

    <template v-if="batchMode || student" #footer>
      <button type="button" class="mp-btn" :disabled="submitting" @click="cancel">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !objectReady || !groupName" @click="submit">
        {{ submitting ? '正在保存…' : (batchMode ? `确认批量设置 ${recordIds.length} 人` : '确认设置分组') }}
      </button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

const SAFE_PREFIX = '/admin/graduation/'

export default {
  name: 'GraduationStudentGroupView',
  components: { GraduationFormPageShell, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      student: null,
      groupName: '',
      reason: '',
      groupOpts: [],
      recordIds: [],
      loading: true,
      loadError: '',
      formError: '',
      submitting: false,
      loadToken: 0
    }
  },
  computed: {
    safeReturnTo() {
      const raw = Array.isArray(this.$route.query.returnTo) ? this.$route.query.returnTo[0] : this.$route.query.returnTo
      const value = String(raw || '').trim()
      return value.startsWith(SAFE_PREFIX) ? value : ''
    },
    backTo() {
      if (this.safeReturnTo) return this.safeReturnTo
      const panel = String(this.$route.query.returnPanel || 'grouping')
      const query = new URLSearchParams({ panel })
      for (const key of ['batchId', 'page', 'keyword', 'source']) {
        const value = this.$route.query[key]
        if (value != null && value !== '') query.set(key, String(value))
      }
      return `/admin/graduation/students?${query}`
    },
    batchMode() {
      return !this.$route.params.id && this.recordIds.length > 0
    },
    objectReady() {
      return this.batchMode ? this.recordIds.length > 0 : Boolean(this.student?.id)
    },
    batchLabel() {
      return String(this.$route.query.batchId || this.student?.batchName || this.student?.batchId || '当前批次')
    },
    selectedPreview() {
      const preview = this.recordIds.slice(0, 4).join('、')
      return this.recordIds.length > 4 ? `${preview} 等 ${this.recordIds.length} 人` : preview
    }
  },
  created() { this.load() },
  beforeUnmount() { ++this.loadToken },
  beforeRouteLeave(_to, _from, next) {
    if (this.submitting) {
      toast.info('过程分组正在保存，请等待服务器回执')
      next(false)
      return
    }
    next()
  },
  methods: {
    onBlockedBack() { toast.info('过程分组正在保存，请勿重复操作') },
    cancel() { if (!this.submitting) this.$router.push(this.backTo) },
    async load() {
      const token = ++this.loadToken
      const ids = this.$route.query.ids
      const studentId = String(this.$route.params.id || '')
      const batchId = String(this.$route.query.batchId || '')
      this.loading = true
      this.loadError = ''
      this.recordIds = ids ? String(ids).split(',').map((value) => value.trim()).filter(Boolean) : []
      try {
        const groupsPromise = gdStudentApi.getStudentGroups()
        const studentPromise = studentId ? gdStudentApi.getStudentDetail(studentId) : Promise.resolve(null)
        const [groups, studentResponse] = await Promise.all([groupsPromise, studentPromise])
        if (token !== this.loadToken) return false
        if (groups.code === 0) this.groupOpts = groups.data || []
        if (studentResponse) {
          if (studentResponse.code !== 0) {
            this.loadError = studentResponse.message || '学生信息加载失败'
            return false
          }
          const studentBatchId = String(studentResponse.data?.batchId || '')
          if (batchId && studentBatchId && batchId !== studentBatchId) {
            this.loadError = '当前批次与学生上下文不一致，请返回名单重新选择学生'
            return false
          }
          this.student = studentResponse.data
          this.groupName = studentResponse.data.studentGroup || ''
        } else if (!this.recordIds.length) {
          this.loadError = '未选择要设置分组的学生，请返回学生与进度重新选择'
          return false
        }
        return true
      } catch (error) {
        if (token === this.loadToken) this.loadError = error?.message || '过程分组页面加载失败'
        return false
      } finally {
        if (token === this.loadToken) this.loading = false
      }
    },
    async submit() {
      if (this.submitting) return
      this.formError = ''
      if (!this.objectReady) {
        this.formError = '办理对象无效，请返回重新选择学生'
        return
      }
      if (!this.groupName) {
        this.formError = '请填写目标分组名称'
        return
      }
      const target = Object.freeze({
        batchMode: this.batchMode,
        studentId: String(this.student?.id || ''),
        recordIds: Object.freeze([...this.recordIds]),
        groupName: String(this.groupName).trim(),
        reason: String(this.reason || '').trim() || (this.batchMode ? '批量设置过程分组' : '设置过程分组'),
        backTo: this.backTo
      })
      this.submitting = true
      try {
        const response = target.batchMode
          ? await gdStudentApi.batchSetStudentGroup({ recordIds: target.recordIds, groupName: target.groupName, reason: target.reason })
          : await gdStudentApi.setStudentGroup(target.studentId, { groupName: target.groupName, reason: target.reason })
        if (response.code !== 0) {
          this.formError = response.message || '过程分组保存失败'
          return
        }
        if (target.batchMode) {
          const updated = Number(response.data?.updated ?? response.data?.successCount ?? 0)
          if (updated <= 0) {
            this.formError = '批量命令已返回，但服务器未报告实际更新人数；请返回名单核对，勿重复提交。'
            return
          }
          toast.success(`过程分组已更新 ${updated} 人`)
        } else {
          const latest = await gdStudentApi.getStudentDetail(target.studentId)
          if (latest.code !== 0 || String(latest.data?.studentGroup || '') !== target.groupName) {
            this.formError = '分组命令已返回，但学生档案尚未回读到目标分组；请返回名单刷新核对，勿重复提交。'
            return
          }
          toast.success('过程分组已保存，服务器学生档案已回读')
        }
        this.$router.push(target.backTo)
      } catch (error) {
        this.formError = error?.message || '过程分组保存失败，请稍后重试'
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sg-context{display:flex;min-width:0;gap:8px}.sg-context span{display:grid;min-width:150px;gap:2px;padding:7px 10px;border:1px solid var(--border-light,#e2e8f0);border-radius:8px;background:#fff;color:var(--text-secondary);font-size:11px}.sg-context b{color:var(--text-tertiary);font-size:9px}.sg-form{gap:12px}.sg-section{overflow:hidden;border:1px solid var(--border-light);border-radius:10px;background:#fff}.sg-section>header{display:flex;align-items:center;gap:9px;padding:10px 12px;border-bottom:1px solid var(--border-light);background:var(--gray-50)}.sg-section>header>span{display:grid;width:26px;height:26px;place-items:center;border-radius:50%;background:var(--primary-50);color:var(--primary-700);font-size:10px;font-weight:700}.sg-section>header div{display:grid;gap:1px}.sg-section>header strong{font-size:12px}.sg-section>header small{color:var(--text-tertiary);font-size:10px}.sg-section__body{display:grid;gap:12px;padding:12px}.sg-current{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:12px}.sg-current>div{display:grid;gap:2px;padding:9px;border:1px solid var(--border-light);border-radius:8px;background:var(--gray-50)}.sg-current span,.sg-current small{color:var(--text-tertiary);font-size:9px}.sg-current strong{overflow:hidden;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.sg-aside-card,.sg-warning{padding:12px;border:1px solid var(--border-light);border-radius:10px;background:#fff}.sg-aside-card>span{font-size:12px;font-weight:700}.sg-aside-card ul,.sg-aside-card ol{display:grid;gap:8px;margin:9px 0 0;padding:0;list-style:none}.sg-aside-card li{display:flex;align-items:flex-start;gap:8px;font-size:10px}.sg-aside-card ul li>b{display:grid;width:22px;height:22px;flex:none;place-items:center;border-radius:50%;background:var(--gray-100);color:var(--text-tertiary);font-size:9px}.sg-aside-card ul li.done>b{background:var(--success-50);color:var(--success-700)}.sg-aside-card li div{display:grid;gap:1px}.sg-aside-card li strong{font-size:10px}.sg-aside-card li small{color:var(--text-tertiary);font-size:9px}.sg-aside-card.is-next ol{counter-reset:next}.sg-aside-card.is-next li::before{counter-increment:next;content:counter(next);display:grid;width:19px;height:19px;flex:none;place-items:center;border-radius:6px;background:var(--primary-50);color:var(--primary-700);font-size:9px;font-weight:700}.sg-warning{border-color:var(--warning-200);background:var(--warning-50)}.sg-warning strong{color:var(--warning-800);font-size:11px}.sg-warning p{margin:4px 0 0;color:var(--warning-700);font-size:10px;line-height:1.5}.mp-btn{padding:7px 16px;border:1px solid var(--line,#d9dee8);border-radius:8px;background:#fff;cursor:pointer;font-size:13px}.mp-btn--primary{border-color:var(--pri,#2563eb);background:var(--pri,#2563eb);color:#fff}.mp-btn:disabled{cursor:not-allowed;opacity:.5}@media(max-width:760px){.sg-current{grid-template-columns:1fr}}
</style>
