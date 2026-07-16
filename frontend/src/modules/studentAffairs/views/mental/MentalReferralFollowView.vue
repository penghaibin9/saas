<template>
  <AppPageShell
    title="谈话转介与回访"
    subtitle="转介 → 回访 → 关闭 的持续跟进工作台；聚焦待回访(已转介/回访中)记录，明细遮蔽、查看留痕。"
    role-name="心理老师 / 授权辅导员"
    data-scope-name="PSY_STUDENT 逐生授权范围"
    watermark-purpose="心理转介回访处理"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.risk.psyDetail.view" :loading="actioning" @click="createReferral">
        登记转介
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载转介回访工作台..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <AppSectionCard title="待回访转介（已转介 / 回访中）">
        <table class="sa-table">
          <thead>
            <tr>
              <th>学生</th>
              <th>关注等级</th>
              <th>状态</th>
              <th>事由摘要</th>
              <th>转介去向</th>
              <th>最近回访</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in openItems" :key="row.referralId">
              <td>
                <strong>{{ row.realName || '未命名学生' }}</strong>
                <small>{{ row.studentNo || row.studentId }}</small>
              </td>
              <td><AppStatusTag :type="levelKind(row.level)" :label="row.levelLabel || row.level" /></td>
              <td><AppStatusTag :type="statusKind(row.status)" :label="row.statusLabel || row.status" /></td>
              <td>{{ row.reasonSummary || '—' }}</td>
              <td>{{ row.channel || '—' }}</td>
              <td>{{ (row.lastFollowTime || '').slice(0, 16) || '尚未回访' }}</td>
              <td class="sa-actions">
                <AppPermissionButton code="studentAffairs.risk.psyDetail.view" size="sm" @click="follow(row)">
                  回访
                </AppPermissionButton>
                <AppPermissionButton code="studentAffairs.risk.psyDetail.view" size="sm" variant="secondary" @click="close(row)">
                  关闭
                </AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!openItems.length">
              <td colspan="7" class="sa-empty">暂无待回访转介</td>
            </tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 登记转介：原为「学生ID→事由摘要→去向」3 连原生弹窗。
         本页固定按重点关注（FOCUS）登记，与改造前一致，未擅自加等级选择。 -->
    <AppDrawer :visible="refDlg.visible" title="登记心理转介" @close="refDlg.visible = false">
      <div class="dr-form">
        <AppFormItem label="学生" required>
          <AppStudentPicker v-model="refDlg.studentId" :remote-search="searchStudents"
                            placeholder="按姓名 / 学号搜索" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="转介去向">
          <AppSelect v-model="refDlg.channel" :options="CHANNELS" placeholder="可空" clearable :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="转介事由摘要（≥5 字）" required>
          <AppTextarea ref="refInput" v-model="refDlg.reasonSummary" :rows="3" :maxlength="500" :disabled="actioning"
                       placeholder="客观描述观察到的表现与转介必要性" />
          <AppQuickPhrases scene-key="sa.mental.referral" @pick="onPickReferral" />
          <p class="dr-hint">仅记录客观表现与转介事由，不作诊断结论。登记后按重点关注（FOCUS）进入名单。</p>
        </AppFormItem>
        <AppInlineAlert v-if="refDlg.error" type="danger" :description="refDlg.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="refDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="actioning" @click="submitReferral">登记</AppButton>
      </template>
    </AppDrawer>

    <!-- 回访 / 关闭 -->
    <AppConfirmDialog
      v-model:visible="txtDlg.visible" :title="txtDlg.title" :type="txtDlg.type"
      :confirm-text="txtDlg.confirmText" require-reason :reason-min-length="5"
      :reason-label="txtDlg.reasonLabel" :phrase-scene-key="txtDlg.sceneKey"
      :submitting="actioning" @confirm="submitText"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog,
  AppFormItem,
  AppGlobalState,
  AppInlineAlert,
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppQuickPhrases,
  AppSectionCard,
  AppSelect,
  AppStatusTag,
  AppStudentPicker,
  AppTextarea
} from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

/** 转介去向：沿用原 prompt 提示里的四个既有选项，未自行扩充。 */
const CHANNELS = ['校内咨询', '校医院', '专业机构', '家长'].map((v) => ({ value: v, label: v }))

export default {
  name: 'MentalReferralFollowView',
  components: {
    AppButton,
    AppConfirmDialog,
    AppDrawer,
    AppFormItem,
    AppGlobalState,
    AppInlineAlert,
    AppMetricCard,
    AppPageShell,
    AppPermissionButton,
    AppQuickPhrases,
    AppSectionCard,
    AppSelect,
    AppStatusTag,
    AppStudentPicker,
    AppTextarea
  },
  data() {
    return {
      loading: true, actioning: false, errorMessage: '', items: [],
      refDlg: { visible: false, studentId: '', channel: '校内咨询', reasonSummary: '', error: '' },
      txtDlg: { visible: false, kind: '', row: null, title: '', type: 'primary', confirmText: '确认', reasonLabel: '', sceneKey: '' }
    }
  },
  computed: {
    CHANNELS: () => CHANNELS,
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    openItems() {
      return this.items.filter((r) => r.status === 'REFERRED' || r.status === 'FOLLOWING')
    },
    metricCards() {
      const referred = this.items.filter((r) => r.status === 'REFERRED').length
      const following = this.items.filter((r) => r.status === 'FOLLOWING').length
      const neverFollowed = this.openItems.filter((r) => !r.lastFollowTime).length
      return [
        { key: 'open', label: '待回访', value: this.openItems.length, accent: this.openItems.length ? 'warning' : 'success' },
        { key: 'referred', label: '已转介待跟进', value: referred, accent: 'info' },
        { key: 'following', label: '回访中', value: following, accent: 'primary' },
        { key: 'never', label: '尚未回访', value: neverFollowed, accent: neverFollowed ? 'risk' : 'success' }
      ]
    }
  },
  mounted() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.errorMessage = ''
      try {
        const res = await studentAffairsApi.listMentalAttention({ page: 1, pageSize: 100 })
        this.items = res.data.items || []
      } catch (e) {
        this.errorMessage = e.message || '转介回访工作台加载失败'
      } finally {
        this.loading = false
      }
    },
    searchStudents(keyword) { return studentAffairsApi.searchStudents(keyword) },
    createReferral() {
      this.refDlg = { visible: true, studentId: '', channel: '校内咨询', reasonSummary: '', error: '' }
    },
    onPickReferral(text) {
      const el = this.$refs.refInput && this.$refs.refInput.$refs.el
      if (!el) { this.refDlg.reasonSummary += text; return }
      const r = insertAtCursor(el, this.refDlg.reasonSummary, text)
      this.refDlg.reasonSummary = r.value
      this.$nextTick(() => applyInsertion(el, r.selStart, r.selEnd))
    },
    async submitReferral() {
      const d = this.refDlg
      if (!d.studentId) { d.error = '请选择学生'; return }
      if (d.reasonSummary.trim().length < 5) { d.error = '转介事由摘要不少于 5 字'; return }
      d.error = ''
      const ok = await this.runAction(() => studentAffairsApi.createMentalReferral({
        studentId: d.studentId, level: 'FOCUS', channel: d.channel || '', reasonSummary: d.reasonSummary.trim()
      }))
      if (ok) d.visible = false
      else d.error = this.errorMessage
    },
    follow(row) {
      this.txtDlg = {
        visible: true, kind: 'follow', row, title: `登记回访 · ${row.realName || '该生'}`, type: 'primary',
        confirmText: '确认登记', reasonLabel: '本次回访记录（≥5 字）', sceneKey: 'sa.mental.followup'
      }
    },
    close(row) {
      this.txtDlg = {
        visible: true, kind: 'close', row, title: `关闭心理关注 · ${row.realName || '该生'}`, type: 'warning',
        confirmText: '确认关闭', reasonLabel: '关闭结论（≥5 字）', sceneKey: 'sa.mental.close'
      }
    },
    async submitText({ reason }) {
      const d = this.txtDlg
      const fn = d.kind === 'follow'
        ? () => studentAffairsApi.followMentalReferral(d.row.referralId, reason.trim())
        : () => studentAffairsApi.closeMentalReferral(d.row.referralId, reason.trim())
      const ok = await this.runAction(fn)
      if (ok) d.visible = false
    },
    /** @returns {boolean} 是否成功；失败时保留弹窗与已填内容。 */
    async runAction(fn) {
      this.actioning = true
      this.errorMessage = ''
      try {
        await fn()
        await this.load()
        return true
      } catch (e) {
        this.errorMessage = e.message || '操作失败'
        return false
      } finally {
        this.actioning = false
      }
    },
    levelKind(level) {
      if (level === 'CRISIS') return 'danger'
      if (level === 'FOCUS') return 'warning'
      return 'info'
    },
    statusKind(status) {
      if (status === 'CLOSED') return 'success'
      if (status === 'ESCALATED') return 'danger'
      if (status === 'FOLLOWING') return 'warning'
      return 'info'
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.sa-table {
  width: 100%;
  border-collapse: collapse;
}
.sa-table th,
.sa-table td {
  border-bottom: 1px solid var(--border-light);
  padding: var(--space-3);
  text-align: left;
  vertical-align: top;
}
.sa-table small {
  display: block;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.sa-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sa-empty {
  color: var(--text-tertiary);
  padding: var(--space-4);
  text-align: center;
}
@media (max-width: 960px) {
  .sa-grid--metrics {
    grid-template-columns: 1fr;
  }
}
.dr-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.dr-hint {
  margin: var(--space-1) 0 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}
</style>
