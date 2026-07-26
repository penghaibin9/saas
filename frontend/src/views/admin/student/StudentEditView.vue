<template>
  <ModulePageShell
    :title="isCreate ? '新增学生主档' : '编辑学生信息' + (form.name ? ' · ' + form.name : '')"
    :subtitle="isCreate ? '建档后默认「已录取 / 待核验」，进入迎新与身份核验流程' : '仅提交本次实际修改的字段，全程审计留痕'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="学生主档维护"
  >
    <template #actions>
      <AppButton variant="ghost" @click="backToList">← 返回学生列表</AppButton>
    </template>

    <div class="mp-stack">
      <EmptyState
        v-if="forbidden"
        title="当前角色无学生主档维护权限"
        :description="reason(isCreate ? 'createStudent' : 'editStudent') || '请联系学校系统管理员分配权限'"
      />
      <ErrorState v-else-if="error" :description="error" @retry="init" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!isCreate && !loaded"
        title="未找到该学生主档"
        description="记录可能不存在、已作废或超出当前数据范围；请从学生列表重新进入"
      />
      <template v-else>
        <div class="mp-card">
          <div class="mp-card__head"><div class="mp-card__title">基础信息</div></div>
          <div class="mp-card__body se-grid">
            <label class="se-field">
              <span class="se-field__label">姓名 *</span>
              <input v-model="form.name" class="se-field__control" placeholder="与身份证一致" />
            </label>
            <label class="se-field">
              <span class="se-field__label">学号 *</span>
              <input v-model="form.studentNo" class="se-field__control" :disabled="!isCreate" placeholder="全校唯一" />
            </label>
            <label class="se-field">
              <span class="se-field__label">性别</span>
              <select v-model="form.gender" class="se-field__control">
                <option value="男">男</option>
                <option value="女">女</option>
              </select>
            </label>
            <label class="se-field">
              <span class="se-field__label">班级 *</span>
              <select v-model="form.classId" class="se-field__control">
                <option value="">请选择班级</option>
                <option v-for="c in ctx.filterOptions.classes" :key="c.value" :value="c.value">{{ c.label }}</option>
              </select>
            </label>
            <label class="se-field">
              <span class="se-field__label">手机号</span>
              <input v-model="form.phone" class="se-field__control" placeholder="学生本人手机号" />
            </label>
            <label class="se-field">
              <span class="se-field__label">身份证号</span>
              <input v-model="form.idCard" class="se-field__control" placeholder="用于实名核验" />
            </label>
          </div>
        </div>

        <p v-if="formError" class="mp-form-err">{{ formError }}</p>
        <div class="se-ops">
          <AppButton variant="ghost" @click="backToList">取消</AppButton>
          <AppButton variant="primary" :disabled="submitting" @click="submit">{{ isCreate ? '确认建档' : '保存变更' }}</AppButton>
        </div>
        <p class="mp-note">提交后写入审计留痕；编辑模式仅提交实际修改的字段（避免误写脱敏展示值）。敏感字段展示与导出仍按角色权限脱敏。</p>
      </template>
    </div>
    <AppConfirmDialog
      :visible="restoreDialog.visible"
      type="danger"
      title="恢复已作废的学生主档"
      confirm-text="确认恢复"
      :submitting="restoreDialog.submitting"
      @update:visible="restoreDialog.visible = $event"
      @confirm="doRestore"
    >
      <div class="se-restore">
        <p class="se-restore__hint">{{ restoreDialog.hint }}</p>
        <p class="se-restore__note">
          恢复将<strong>复用原学生 ID 与全部历史关联</strong>（成绩、实习、毕设、审批、消息），
          不会新建第二份档案。<strong>登录账号不会一并恢复</strong>，如需该生重新登录，
          请到「系统管理 › 师生账号」单独启用并按需重置密码。本次恢复将记入审计。
        </p>
        <label class="se-restore__label">恢复原因（≥5 字，写入审计）</label>
        <textarea
          v-model="restoreDialog.reason"
          class="se-restore__input"
          rows="3"
          placeholder="例如：误作废，经与教务处核实该生仍在籍，需恢复原学籍档案"
        />
        <p v-if="restoreDialog.error" class="se-restore__error">{{ restoreDialog.error }}</p>
      </div>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 学生主档新增 / 编辑独立编辑页（2026-07-10 第二批交互改造）：
 *   新增 /admin/student/list/new；编辑 /admin/student/:studentId/edit?no=学号（可刷新、可深链）。
 * 原列表页「新增/编辑主档」抽屉字段多、多区块，按交互形态基准改独立编辑页；数据源与原抽屉一致
 * （既有列表接口按学号定位，无单条接口不造假）；编辑仅提交脏字段，防止把脱敏展示值写回主档。
 * 权限沿用 ctx.permissionActions.createStudent / editStudent（不扩大权限）。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppButton } from '@/components/ui'
import { studentApi } from '@/modules/student/api/student.api'
import { toast } from '@/utils/toast'

const EMPTY_FORM = () => ({ name: '', studentNo: '', gender: '男', classId: '', phone: '', idCard: '' })

export default {
  name: 'StudentEditView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: false,
      loaded: false,
      error: '',
      formError: '',
      submitting: false,
      form: EMPTY_FORM(),
      initial: EMPTY_FORM(),
      /* 乐观锁版本：保存时回传，服务端版本已变则 409，提示刷新 */
      loadedVersion: null,
      /* 受控恢复：复用原档案与历史关联，需原因≥5字并二次确认 */
      restoreDialog: { visible: false, reason: '', hint: '', error: '', submitting: false }
    }
  },
  computed: {
    isCreate() {
      return !this.$route.params.studentId
    },
    forbidden() {
      const key = this.isCreate ? 'createStudent' : 'editStudent'
      const pa = this.ctx.permissionActions[key]
      return !(pa && pa.visible && pa.allowed)
    }
  },
  created() {
    this.init()
  },
  methods: {
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    backToList() {
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (back && String(back).startsWith('/admin/student')) this.$router.back()
      else this.$router.push('/admin/student/list')
    },
    async init() {
      this.error = ''
      this.loaded = false
      if (this.isCreate) {
        this.form = EMPTY_FORM()
        this.initial = EMPTY_FORM()
        this.loaded = true
        return
      }
      this.loading = true
      const id = String(this.$route.params.studentId || '')
      const no = String(this.$route.query.no || '')
      try {
        let row = null
        if (no) {
          const res = await studentApi.getStudents({ keyword: no, page: 1, pageSize: 50 })
          if (res.code !== 0) throw new Error(res.message)
          row = (res.data.list || []).find((r) => r.studentId === id) || null
        }
        if (!row) {
          for (let page = 1; page <= 5 && !row; page++) {
            const res = await studentApi.getStudents({ page, pageSize: 100 })
            if (res.code !== 0) throw new Error(res.message)
            row = (res.data.list || []).find((r) => r.studentId === id) || null
            if ((res.data.list || []).length < 100) break
          }
        }
        if (row) {
          this.form = { name: row.name, studentNo: row.studentNo, gender: row.gender, classId: row.classId, phone: row.phone, idCard: row.idCard }
          this.initial = { ...this.form }
          this.loadedVersion = row.version
          this.loaded = true
        }
      } catch (e) {
        this.error = e.message || '加载失败'
      }
      this.loading = false
    },
    async submit() {
      this.formError = ''
      if (!String(this.form.name).trim()) {
        this.formError = '姓名必填'
        return
      }
      if (!String(this.form.studentNo).trim()) {
        this.formError = '学号必填'
        return
      }
      if (!this.form.classId) {
        this.formError = '请选择班级'
        return
      }
      this.submitting = true
      let res
      if (this.isCreate) {
        res = await studentApi.createStudent({ ...this.form })
      } else {
        /* 仅提交脏字段：未改动的（可能是脱敏展示值的）字段不回写 */
        const payload = {}
        for (const k of Object.keys(this.form)) {
          if (this.form[k] !== this.initial[k]) payload[k] = this.form[k]
        }
        if (!Object.keys(payload).length) {
          this.submitting = false
          toast.info('没有需要保存的变更')
          return
        }
        payload.expectedVersion = this.loadedVersion
        res = await studentApi.updateStudent(String(this.$route.params.studentId), payload)
      }
      this.submitting = false
      if (res.code === 0) {
        toast.success(this.isCreate ? '建档成功，已进入待核验队列（已留痕）' : '学生信息已更新（已留痕）')
        this.backToList()
      } else if (this.isCreate && this.isVoidedConflict(res)) {
        // 学号属于已作废档案：不静默复活，转入受控恢复（需权限 + 原因 + 二次确认）
        this.restoreDialog.visible = true
        this.restoreDialog.hint = res.message
        this.restoreDialog.reason = ''
        this.restoreDialog.error = ''
      } else {
        this.formError = res.message
      }
    },

    /** 后端用独立错误码区分「作废档案」与普通重复学号，不靠中文串匹配。 */
    isVoidedConflict(res) {
      return res?.bizCode === 'VOIDED_PROFILE_EXISTS'
        || String(res?.message || '').includes('已作废档案')
    },

    async doRestore() {
      const reason = String(this.restoreDialog.reason || '').trim()
      if (reason.length < 5) {
        this.restoreDialog.error = '恢复原因必填且不少于 5 个字'
        return
      }
      this.restoreDialog.submitting = true
      const res = await studentApi.restoreStudent({ studentNo: this.form.studentNo, reason })
      this.restoreDialog.submitting = false
      if (res.code === 0) {
        this.restoreDialog.visible = false
        toast.success(res.message || '已恢复该学生主档（登录账号未一并恢复）')
        this.backToList()
      } else {
        this.restoreDialog.error = res.message
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.se-restore { display: flex; flex-direction: column; gap: 8px; text-align: left; }
.se-restore__hint { margin: 0; color: var(--mp-text-primary, #1f2733); }
.se-restore__note { margin: 0; color: var(--mp-text-secondary, #5b6472); font-size: 13px; line-height: 1.7; }
.se-restore__label { font-size: 13px; color: var(--mp-text-secondary, #5b6472); }
.se-restore__input {
  width: 100%; border: 1px solid var(--mp-border, #d9dee7); border-radius: 6px;
  padding: 8px 10px; font: inherit; resize: vertical;
}
.se-restore__error { margin: 0; color: var(--mp-danger, #d93a3a); font-size: 13px; }
.se-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: var(--space-3);
}
.se-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.se-field__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.se-field__control {
  border: 1px solid var(--border-base, var(--border-light));
  border-radius: var(--radius-base);
  padding: var(--space-2);
  font: inherit;
  background: var(--bg-card);
}
.se-field__control:disabled {
  background: var(--bg-section-blue);
  color: var(--text-secondary);
}
.se-ops {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
</style>
