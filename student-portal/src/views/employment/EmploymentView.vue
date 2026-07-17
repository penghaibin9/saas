<template>
  <div class="sp-page">
    <nav class="sp-tabs">
      <button v-for="t in tabs" :key="t.key" class="sp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
    </nav>

    <StateBlock v-if="loading" type="loading" text="正在加载就业信息…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <!-- 我的就业 -->
      <template v-if="tab === 'overview'">
        <section class="sp-card" style="margin-bottom:16px">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap">
            <div>
              <div style="font-size:18px;font-weight:600">我的就业进度</div>
              <div class="sp-muted" style="margin-top:8px">按学校要求完成生源核对与去向登记，是顺利办理离校手续的前提。</div>
            </div>
            <span class="statepill" :class="{ warn: !isSigned }"><span class="dot" />{{ destText(my.destinationType) }}</span>
          </div>
          <FlowSteps :steps="flowSteps" style="margin-top:22px" />
        </section>
        <section class="sp-card">
          <div class="sp-panel__head">就业信息</div>
          <dl class="desc">
            <div><dt>去向类型</dt><dd>{{ destText(my.destinationType) }}</dd></div>
            <div><dt>单位</dt><dd>{{ my.companyName || '—' }}</dd></div>
            <div><dt>岗位</dt><dd>{{ my.jobTitle || '—' }}</dd></div>
            <div><dt>核验状态</dt><dd><StatusTag :text="verifyText(my.verifyStatus)" :tone="my.verifyStatus==='VERIFIED'?'success':'warn'" /></dd></div>
            <div><dt>材料状态</dt><dd><StatusTag :text="matText(my.materialStatus)" :tone="my.materialStatus==='APPROVED'?'success':'warn'" /></dd></div>
            <div><dt>帮扶级别</dt><dd>{{ helpText(my.helpLevel) }}</dd></div>
          </dl>
        </section>
        <section class="sp-card">
          <div class="sp-panel__head">就业政策与提醒</div>
          <div style="display:flex;flex-direction:column;gap:10px;font-size:13px;color:var(--t2);line-height:1.7">
            <div>· 请及时完成「生源核对」，信息将用于报到证与档案转递。</div>
            <div>· 已签约 / 已升学同学请在「去向登记」中更新状态并上传材料。</div>
            <div>· 就业去向未登记将影响离校手续办理。</div>
          </div>
        </section>
      </template>

      <!-- 生源核对 -->
      <template v-else-if="tab === 'source'">
        <section class="sp-card" style="max-width:720px">
          <div class="sp-panel__head">生源信息核对 <StatusTag :text="my.verifyStatus==='VERIFIED'?'已核对':'待核对'" :tone="my.verifyStatus==='VERIFIED'?'success':'warn'" /></div>
          <dl class="desc">
            <div><dt>姓名</dt><dd>{{ studentName }}</dd></div>
            <div><dt>就业单位</dt><dd>{{ my.companyName || '待登记' }}</dd></div>
            <div><dt>岗位</dt><dd>{{ my.jobTitle || '待登记' }}</dd></div>
            <div><dt>去向类型</dt><dd>{{ destText(my.destinationType) }}</dd></div>
          </dl>
          <p class="sp-muted" style="margin-top:14px">生源信息来自学籍档案，如有误请在「我的档案 · 申请更正联系方式」发起更正；确认无误后在「去向登记」提交去向。</p>
        </section>
      </template>

      <!-- 去向登记 -->
      <template v-else-if="tab === 'destination'">
        <section class="sp-card" style="max-width:760px">
          <div class="sp-panel__head">就业去向登记</div>
          <div class="sp-fieldlabel">去向类型</div>
          <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px">
            <button v-for="d in destTypes" :key="d.k" class="chipbtn" :class="{ on: form.destinationType === d.k }" @click="form.destinationType = d.k">{{ d.t }}</button>
          </div>
          <template v-if="form.destinationType === 'SIGNED'">
            <div class="two">
              <div><div class="sp-fieldlabel">签约单位</div><input v-model.trim="form.companyName" class="sp-inp" placeholder="就业单位" /></div>
              <div><div class="sp-fieldlabel">岗位/职务</div><input v-model.trim="form.jobTitle" class="sp-inp" placeholder="岗位" /></div>
              <div><div class="sp-fieldlabel">工作城市</div><input v-model.trim="form.city" class="sp-inp" placeholder="工作城市" /></div>
              <div><div class="sp-fieldlabel">联系电话</div><input v-model.trim="form.contact" class="sp-inp" placeholder="单位联系方式" /></div>
            </div>
          </template>
          <div class="sp-fieldlabel" style="margin-top:14px">备注</div>
          <textarea v-model.trim="form.remark" class="sp-inp" placeholder="补充说明（可选）" />
          <div style="display:flex;gap:10px;margin-top:16px">
            <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="printDoc">打印去向登记表</button>
            <button class="sp-btn" :disabled="busy || !form.destinationType" @click="submit">提交登记</button>
          </div>
        </section>
      </template>

      <!-- 签约材料 -->
      <template v-else-if="tab === 'contract'">
        <section class="sp-card" style="max-width:820px">
          <div class="sp-panel__head">签约材料</div>
          <StateBlock v-if="!(my.materials||[]).length" type="empty" text="暂无签约材料，请在去向登记时上传" />
          <AutoTable v-else :rows="my.materials" />
          <button class="sp-btn sp-btn--ghost" :disabled="busy" style="margin-top:16px" @click="printDoc">打印就业协议书</button>
        </section>
        <section class="sp-card" style="max-width:820px">
          <div class="sp-panel__head">就业回访</div>
          <AutoTable :rows="my.followUps" empty="暂无回访记录" />
        </section>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AutoTable from '../../components/AutoTable.vue'
import FlowSteps from '../../components/FlowSteps.vue'
import { portalApi } from '../../services/portalApi'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const session = useSessionStore()
const tabs = [
  { key: 'overview', label: '我的就业' }, { key: 'source', label: '生源核对' },
  { key: 'destination', label: '去向登记' }, { key: 'contract', label: '签约材料' }
]
const tab = ref('overview')
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const my = ref({})
const form = reactive({ destinationType: 'SIGNED', companyName: '', jobTitle: '', city: '', contact: '', remark: '' })
const destTypes = [
  { k: 'SIGNED', t: '签约就业' }, { k: 'FLEXIBLE', t: '灵活就业' }, { k: 'FURTHER', t: '升学' },
  { k: 'MILITARY', t: '参军' }, { k: 'UNEMPLOYED', t: '暂未就业' }
]
const studentName = computed(() => session.user?.realName || '同学')
const isSigned = computed(() => my.value.destinationType === 'SIGNED')
const DEST = { SIGNED: '已签约', FLEXIBLE: '灵活就业', FURTHER: '升学', MILITARY: '参军', UNEMPLOYED: '暂未就业' }
const VERIFY = { VERIFIED: '已核验', PENDING: '待核验', REJECTED: '已退回' }
const MAT = { APPROVED: '已通过', PENDING: '待审核', REJECTED: '已退回', NONE: '未提交' }
const HELP = { NORMAL: '普通', KEY: '重点帮扶', SPECIAL: '专项帮扶' }
function destText(s) { return DEST[s] || s || '待登记' }
function verifyText(s) { return VERIFY[s] || s || '—' }
function matText(s) { return MAT[s] || s || '—' }
function helpText(s) { return HELP[s] || s || '—' }

const flowSteps = computed(() => {
  const order = ['生源核对', '去向登记', '签约材料', '离校归档']
  let cur = 0
  if (my.value.verifyStatus === 'VERIFIED') cur = 1
  if (my.value.destinationType && my.value.destinationType !== 'UNSET') cur = 2
  if (my.value.materialStatus === 'APPROVED') cur = 3
  return order.map((name, i) => ({ name, state: i < cur ? 'done' : i === cur ? 'current' : 'todo' }))
})

async function load() {
  loading.value = true; error.value = ''
  try { my.value = await portalApi.employmentMy() || {} }
  catch (e) { error.value = e?.message || '就业信息加载失败' } finally { loading.value = false }
}
async function submit() {
  busy.value = true
  try { await portalApi.employmentDestination({ ...form }); ui.notify('就业去向已登记'); tab.value = 'overview'; load() }
  catch (e) { ui.notify(e?.message || '登记失败（演示租户为只读）') } finally { busy.value = false }
}
async function printDoc() {
  busy.value = true
  try { await portalApi.employmentDestinationPrint({}); ui.notify('已生成打印留痕') }
  catch (e) { ui.notify(e?.message || '打印失败（演示租户为只读）') } finally { busy.value = false }
}
onMounted(load)
</script>

<style scoped>
.statepill { display: inline-flex; align-items: center; gap: 7px; padding: 8px 13px; background: var(--pri-50); border-radius: 9px; color: var(--pri); font-weight: 600; font-size: 13.5px; }
.statepill.warn { background: var(--warn-bg); color: var(--warn-fg); }
.statepill .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.desc { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px 24px; margin: 0; }
.desc dt { font-size: 12px; color: var(--t3); margin-bottom: 5px; }
.desc dd { margin: 0; font-size: 14px; color: var(--t1); }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.chipbtn { all: unset; box-sizing: border-box; cursor: pointer; padding: 9px 16px; border-radius: 9px; font-size: 13px; font-weight: 500; background: #fff; color: var(--t1); border: 1px solid var(--line); }
.chipbtn.on { background: var(--pri-50); color: var(--pri); border-color: var(--pri); font-weight: 600; }
@media (max-width: 900px) { .desc { grid-template-columns: 1fr 1fr; } .two { grid-template-columns: 1fr; } }
</style>
