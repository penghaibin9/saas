<template>
  <div class="sp-page">
    <section class="sp-hero">
      <div>
        <p class="sp-eyebrow">就业服务</p>
        <h1>我的就业</h1>
        <p class="sp-hero__sub">登记就业去向、维护签约材料、打印就业协议与回执。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" :disabled="loading" @click="load">刷新</button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在加载就业信息…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <section v-if="!my.hasData" class="sp-notice">
        <strong>尚未登记就业去向</strong>
        <p>{{ my.message || '毕业季开启后，你可在此登记去向、上传签约材料。' }}</p>
      </section>

      <section class="sp-kpis">
        <div class="sp-kpi"><div class="sp-kpi__label">去向类型</div><div class="sp-kpi__value" style="font-size:16px">{{ destText(my.destinationType) }}</div></div>
        <div class="sp-kpi"><div class="sp-kpi__label">单位</div><div class="sp-kpi__value" style="font-size:16px">{{ my.companyName || '—' }}</div></div>
        <div class="sp-kpi"><div class="sp-kpi__label">岗位</div><div class="sp-kpi__value" style="font-size:16px">{{ my.jobTitle || '—' }}</div></div>
        <div class="sp-kpi"><div class="sp-kpi__label">核验状态</div><div class="sp-kpi__value" style="font-size:16px"><StatusTag :text="verifyText(my.verifyStatus)" :tone="my.verifyStatus === 'VERIFIED' ? 'success' : 'warn'" /></div></div>
        <div class="sp-kpi"><div class="sp-kpi__label">材料状态</div><div class="sp-kpi__value" style="font-size:16px"><StatusTag :text="matText(my.materialStatus)" :tone="my.materialStatus === 'APPROVED' ? 'success' : 'warn'" /></div></div>
        <div class="sp-kpi"><div class="sp-kpi__label">帮扶级别</div><div class="sp-kpi__value" style="font-size:16px">{{ helpText(my.helpLevel) }}</div></div>
      </section>

      <section class="sp-actions">
        <button class="sp-btn" :disabled="busy" @click="showForm = !showForm">登记 / 更新去向</button>
        <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="printDoc">打印就业协议/回执</button>
      </section>

      <section v-if="showForm" class="sp-panel">
        <div class="sp-panel__head">就业去向登记</div>
        <div class="sp-form">
          <label>去向类型
            <select v-model="form.destinationType">
              <option value="SIGNED">已签约</option>
              <option value="FLEXIBLE">灵活就业</option>
              <option value="FURTHER">升学</option>
              <option value="MILITARY">参军</option>
              <option value="UNEMPLOYED">暂未就业</option>
            </select>
          </label>
          <label>单位名称<input v-model.trim="form.companyName" placeholder="就业单位" /></label>
          <label>岗位<input v-model.trim="form.jobTitle" placeholder="岗位名称" /></label>
          <label>联系电话<input v-model.trim="form.contact" placeholder="单位联系方式" /></label>
          <label class="sp-form__full">备注<textarea v-model.trim="form.remark" placeholder="补充说明（可选）" /></label>
          <button class="sp-btn" :disabled="busy || !form.destinationType" @click="submit">提交登记</button>
        </div>
      </section>

      <section class="sp-panel">
        <div class="sp-panel__head">签约材料</div>
        <AutoTable :rows="my.materials" empty="暂无材料记录" />
      </section>

      <section class="sp-panel">
        <div class="sp-panel__head">就业回访</div>
        <AutoTable :rows="my.followUps" empty="暂无回访记录" />
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AutoTable from '../../components/AutoTable.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const my = ref({})
const showForm = ref(false)
const form = reactive({ destinationType: 'SIGNED', companyName: '', jobTitle: '', contact: '', remark: '' })

const DEST_MAP = { SIGNED: '已签约', FLEXIBLE: '灵活就业', FURTHER: '升学', MILITARY: '参军', UNEMPLOYED: '暂未就业' }
const VERIFY_MAP = { VERIFIED: '已核验', PENDING: '待核验', REJECTED: '已退回' }
const MAT_MAP = { APPROVED: '已通过', PENDING: '待审核', REJECTED: '已退回', NONE: '未提交' }
const HELP_MAP = { NORMAL: '普通', KEY: '重点帮扶', SPECIAL: '专项帮扶' }
function destText(s) { return DEST_MAP[s] || s || '—' }
function verifyText(s) { return VERIFY_MAP[s] || s || '—' }
function matText(s) { return MAT_MAP[s] || s || '—' }
function helpText(s) { return HELP_MAP[s] || s || '—' }

async function load() {
  loading.value = true
  error.value = ''
  try { my.value = await portalApi.employmentMy() || {} }
  catch (e) { error.value = e?.message || '就业信息加载失败' }
  finally { loading.value = false }
}
async function submit() {
  busy.value = true
  try { await portalApi.employmentDestination({ ...form }); ui.notify('就业去向已登记'); showForm.value = false; load() }
  catch (e) { ui.notify(e?.message || '登记失败（演示租户为只读）') } finally { busy.value = false }
}
async function printDoc() {
  busy.value = true
  try { await portalApi.employmentDestinationPrint({}); ui.notify('已生成打印留痕') }
  catch (e) { ui.notify(e?.message || '打印失败（演示租户为只读）') } finally { busy.value = false }
}

onMounted(load)
</script>
