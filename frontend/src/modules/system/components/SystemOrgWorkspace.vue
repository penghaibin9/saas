<template>
  <div class="org-workspace">
    <aside class="org-directory" aria-label="组织目录">
      <label class="org-search"
        ><Search /><input v-model="search" aria-label="搜索组织" placeholder="搜索学院、专业或班级"
      /></label>
      <button
        class="org-root"
        :disabled="submitting"
        :aria-pressed="!selected"
        @click="selectNode(null)"
      >
        <School />全校组织
      </button>
      <div class="org-tree" aria-label="组织层级">
        <div
          v-for="item in visibleNodes"
          :key="item.key"
          class="org-tree-row"
          :class="{ selected: item.key === selectedKey }"
          :style="{ paddingLeft: `${8 + item.depth * 18}px` }"
        >
          <button
            v-if="item.children?.length"
            class="org-toggle"
            :aria-label="`${expanded.has(item.key) ? '收起' : '展开'}${item.name}`"
            :aria-expanded="expanded.has(item.key)"
            @click="toggle(item.key)"
          >
            <ArrowDown v-if="expanded.has(item.key) || search" /><ArrowRight v-else />
          </button>
          <span v-else class="org-spacer" />
          <button
            class="org-node"
            :disabled="submitting"
            :aria-pressed="item.key === selectedKey"
            :title="item.trail"
            @click="selectNode(item)"
          >
            <component
              :is="
                item.type === 'CLASS' ? School : item.type === 'MAJOR' ? Reading : OfficeBuilding
              "
            /><span>{{ item.name }}</span>
          </button>
        </div>
        <p v-if="!visibleNodes.length" class="org-muted">未找到匹配组织，请换个名称或编码。</p>
      </div>
    </aside>
    <section class="org-detail" aria-label="组织详情">
      <nav class="org-breadcrumb" aria-label="组织归属">
        <button @click="selectNode(null)">全校</button
        ><template v-for="parent in ancestry" :key="parent.key"
          ><ArrowRight /><button @click="selectNode(parent)">{{ parent.name }}</button></template
        >
      </nav>
      <p v-if="refreshing" class="org-muted" role="status">正在更新组织数据…</p>
      <template v-if="!impactOpen">
        <header class="org-detail-head">
          <div>
            <h2>
              {{ selected?.name || rootTitle }}
              <small v-if="selected">{{ selected.typeLabel }}</small>
              <span
                v-if="selected"
                class="org-status"
                :class="{ disabled: selected.status === 'DISABLED' }"
                >{{ statusLabel(selected.status) }}</span
              >
            </h2>
            <p class="org-muted">
              {{
                selected
                  ? `组织编码：${selected.code || '—'} · 下级组织：${selected.children?.length ?? 0} · 成员数：${selected.memberCount ?? '—'}`
                  : '选择左侧组织查看下级，也可以直接搜索名称或编码。'
              }}
            </p>
          </div>
          <div class="org-actions">
            <AppButton
              v-if="childType && can('createOrg')"
              variant="primary"
              @click="$emit('edit', null, selected)"
              ><Plus />{{ childLabel }}</AppButton
            >
            <AppButton
              v-if="selected && can('editOrg')"
              variant="ghost"
              @click="$emit('edit', selected, null)"
              >编辑{{ selected.typeLabel }}</AppButton
            >
            <AppButton
              v-if="selected && selected.status !== 'DISABLED'"
              variant="ghost"
              @click="startImpact"
              >作废前检查</AppButton
            >
          </div>
        </header>
        <p v-if="selected?.status === 'DISABLED'" class="org-muted">
          已作废组织不能新增下级，历史归属仍可查看。
        </p>
        <div v-if="completed" class="org-result" role="status">{{ completed }}</div>
        <div class="org-list-tools">
          <label class="org-search"
            ><Search /><input
              v-model="childSearch"
              aria-label="筛选下级组织"
              placeholder="搜索当前层级名称或编码" /></label
          ><span class="org-muted">当前层级 · {{ children.length }} 项</span>
        </div>
        <div class="org-table-wrap">
          <table class="org-table">
            <thead>
              <tr>
                <th>组织名称</th>
                <th>类型</th>
                <th>编码</th>
                <th>成员数</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in pageRows" :key="item.key">
                <td>
                  <button class="org-link" @click="selectNode(item)">{{ item.name }}</button>
                </td>
                <td>{{ item.typeLabel }}</td>
                <td class="org-code">{{ item.code || '—' }}</td>
                <td>{{ item.memberCount ?? '—' }}</td>
                <td>
                  <span class="org-status" :class="{ disabled: item.status === 'DISABLED' }">{{
                    statusLabel(item.status)
                  }}</span>
                </td>
                <td><button class="org-link" @click="selectNode(item)">查看</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="!children.length" class="org-empty">
          {{
            childSearch
              ? '没有匹配的下级组织'
              : selected?.type === 'CLASS'
                ? '班级是当前组织结构的末级。可在年级与班级、任职归属中继续办理。'
                : '当前组织暂无下级'
          }}
        </p>
        <footer class="org-pagination">
          <span>共 {{ children.length }} 项 · 每页 10 项</span
          ><button :disabled="page === 1" @click="page--">上一页</button
          ><span>{{ page }} / {{ pageCount }}</span
          ><button :disabled="page >= pageCount" @click="page++">下一页</button>
        </footer>
      </template>
      <template v-else>
        <header class="org-detail-head">
          <div>
            <h2>作废前影响检查</h2>
            <p>对象：{{ selected?.name }}（{{ selected?.typeLabel }}）</p>
          </div>
          <button class="org-link" :disabled="submitting" @click="closeImpact">返回组织详情</button>
        </header>
        <ol class="org-steps" aria-label="作废办理步骤">
          <li aria-current="step">1 检查影响</li>
          <li :class="{ active: confirmOpen }">2 确认作废</li>
          <li>3 查看结果</li>
        </ol>
        <p v-if="impactLoading" role="status" class="org-empty">
          正在检查关联组织、学生和任职，不会修改数据…
        </p>
        <div v-else-if="impactError" role="alert" class="org-warning">{{ impactError }}</div>
        <template v-else-if="impact">
          <div class="org-warning" :class="{ clear: impact.canDisable }" role="status">
            <Warning />
            <div>
              <strong>{{
                impact.canDisable ? '影响检查通过，请核对后确认' : '当前不能作废'
              }}</strong>
              <p>
                {{
                  impact.canDisable
                    ? '提交时还会核对组织版本和最新关联情况。'
                    : '仍有组织、学生或任职引用，请先处理关联事项，再重新检查。'
                }}
              </p>
            </div>
          </div>
          <dl class="org-impact-counts">
            <div v-for="row in impactRows" :key="row.key">
              <dt>{{ row.label }}</dt>
              <dd>{{ row.count ?? '—' }}</dd>
            </div>
          </dl>
          <table v-if="impactRows.some((row) => row.count > 0)" class="org-table">
            <thead>
              <tr>
                <th>影响类别</th>
                <th>数量</th>
                <th>处理建议</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in impactRows.filter((row) => row.count > 0)" :key="row.key">
                <td>{{ row.label }}</td>
                <td>{{ row.count ?? '—' }}</td>
                <td>
                  {{
                    row.count > 0
                      ? row.advice
                      : row.count === 0
                        ? '此项无关联'
                        : '数量待确认，请重新检查'
                  }}
                </td>
              </tr>
            </tbody>
          </table>
        </template>
        <footer class="org-impact-footer">
          <p class="org-muted">
            检查不会修改组织或学生数据。<br />{{
              impact && expired
                ? '检查结果已过期，请重新检查。'
                : '检查结果最多 5 分钟有效；切换组织、身份或数据更新后需重新检查。'
            }}
          </p>
          <div class="org-actions">
            <AppButton
              variant="primary"
              :loading="impactLoading"
              :disabled="submitting"
              @click="startImpact"
              >重新检查</AppButton
            ><AppButton variant="danger" :disabled="!canConfirm" @click="confirmOpen = true"
              >确认作废</AppButton
            >
          </div>
        </footer>
        <p v-if="!can('deprecateOrg')" class="org-muted">
          {{
            !can('deprecateOrg')
              ? '当前身份没有作废权限。'
              : '影响未处理、检查失败或已过期时，不可提交作废。'
          }}
        </p>
      </template>
    </section>
    <AppConfirmDialog
      v-model:visible="confirmOpen"
      type="danger"
      :title="`作废组织「${selected?.name || ''}」？`"
      message="请核对组织归属。作废将停用此组织，历史归属和审计记录保留。"
      require-reason
      :initial-reason="draftReason"
      reason-label="作废原因"
      confirm-text="确认作废并留痕"
      :confirm-disabled="!canConfirm"
      :submitting="submitting"
      @confirm="deprecate"
    />
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Search,
  School,
  OfficeBuilding,
  Reading,
  ArrowDown,
  ArrowRight,
  Plus,
  Warning
} from '@element-plus/icons-vue'
import { AppButton } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { systemP1ClosureApi } from '@/modules/system/api/systemP1Closure.api'
const props = defineProps({
  tree: { type: Array, required: true },
  ctx: { type: Object, required: true },
  refreshing: { type: Boolean, default: false }
})
const emit = defineEmits(['edit', 'refresh'])
const route = useRoute(),
  router = useRouter()
const search = ref(''),
  childSearch = ref(''),
  selectedKey = ref(''),
  expanded = ref(new Set()),
  page = ref(1)
const impactOpen = ref(false),
  impactLoading = ref(false),
  impact = ref(null),
  impactError = ref(''),
  confirmOpen = ref(false),
  submitting = ref(false),
  expiresAt = ref(0),
  now = ref(Date.now()),
  completed = ref(''),
  draftReason = ref('')
let sequence = 0
const timer = setInterval(() => {
  now.value = Date.now()
}, 1000)
onBeforeUnmount(() => {
  clearInterval(timer)
  sequence++
})
const statusLabel = (status) =>
  ({ ENABLED: '正常', ACTIVE: '正常', DISABLED: '已作废' })[status] || '状态待确认'
const keyOf = (node) => `${node.type}:${String(node.id)}`
const nodes = computed(() => {
  const result = []
  function walk(items, parents = []) {
    for (const node of items) {
      const item = {
        ...node,
        key: keyOf(node),
        parents: parents.map((p) => p.key),
        depth: parents.length,
        trail: [...parents.map((p) => p.name), node.name].join(' / ')
      }
      result.push(item)
      walk(node.children || [], [...parents, item])
    }
  }
  walk(props.tree)
  return result
})
const selected = computed(() => nodes.value.find((n) => n.key === selectedKey.value) || null)
const ancestry = computed(() =>
  selected.value
    ? [...selected.value.parents, selected.value.key]
        .map((k) => nodes.value.find((n) => n.key === k))
        .filter(Boolean)
    : []
)
const visibleNodes = computed(() => {
  const q = search.value.trim().toLocaleLowerCase()
  if (q) {
    const keys = new Set()
    for (const n of nodes.value)
      if (`${n.name} ${n.code}`.toLocaleLowerCase().includes(q)) {
        keys.add(n.key)
        n.parents.forEach((k) => keys.add(k))
      }
    return nodes.value.filter((n) => keys.has(n.key))
  }
  return nodes.value.filter((n) => n.parents.every((k) => expanded.value.has(k)))
})
const categoryType = computed(
  () => ({ major: 'MAJOR', class: 'CLASS', college: 'COLLEGE' })[route.query.tab] || ''
)
const rootTitle = computed(
  () =>
    ({ MAJOR: '全校专业', CLASS: '全校班级', COLLEGE: '学院与部门' })[categoryType.value] ||
    '全校组织'
)
const children = computed(() =>
  nodes.value
    .filter((n) =>
      selected.value
        ? n.parents.at(-1) === selected.value.key
        : categoryType.value
          ? n.type === categoryType.value
          : !n.parents.length
    )
    .filter((n) =>
      `${n.name} ${n.code}`
        .toLocaleLowerCase()
        .includes(childSearch.value.trim().toLocaleLowerCase())
    )
)
const pageCount = computed(() => Math.max(1, Math.ceil(children.value.length / 10)))
const pageRows = computed(() => children.value.slice((page.value - 1) * 10, page.value * 10))
const childType = computed(() =>
  selected.value?.status === 'DISABLED'
    ? ''
    : !selected.value
      ? !categoryType.value || categoryType.value === 'COLLEGE'
        ? 'COLLEGE'
        : ''
      : selected.value.type === 'COLLEGE'
        ? 'MAJOR'
        : selected.value.type === 'MAJOR'
          ? 'CLASS'
          : ''
)
const childLabel = computed(
  () => ({ COLLEGE: '新增学院', MAJOR: '新增专业', CLASS: '新增班级' })[childType.value]
)
const can = (key) =>
  Boolean(
    props.ctx?.permissionActions?.[key]?.visible && props.ctx?.permissionActions?.[key]?.allowed
  )
const expired = computed(() => now.value >= expiresAt.value)
const canConfirm = computed(
  () =>
    can('deprecateOrg') &&
    impact.value?.canDisable === true &&
    Boolean(impact.value?.previewToken) &&
    impact.value?.nodeVersion != null &&
    !expired.value &&
    !impactLoading.value &&
    !submitting.value &&
    !props.refreshing &&
    selected.value?.status !== 'DISABLED'
)
const impactRows = computed(() =>
  [
    { key: 'affectedMajors', label: '受影响专业', advice: '先调整或停用关联专业' },
    { key: 'affectedClasses', label: '受影响班级', advice: '在左侧展开组织，逐一核对下属班级' },
    { key: 'affectedStudents', label: '受影响学生', advice: '在年级与班级中处理学生归属' },
    {
      key: 'affectedAssignments',
      label: '在任任职',
      advice: '在教职工任职归属查询中核对并调整任职'
    }
  ].map((r) => ({ ...r, count: impact.value?.[r.key] }))
)
function invalidate() {
  sequence++
  impact.value = null
  expiresAt.value = 0
  confirmOpen.value = false
  impactLoading.value = false
}
function closeImpact() {
  invalidate()
  impactOpen.value = false
  impactError.value = ''
}
function toggle(key) {
  const next = new Set(expanded.value)
  next.has(key) ? next.delete(key) : next.add(key)
  expanded.value = next
}
function selectNode(node) {
  if (submitting.value) return
  closeImpact()
  draftReason.value = ''
  selectedKey.value = node?.key || ''
  childSearch.value = ''
  page.value = 1
  if (node) expanded.value = new Set([...expanded.value, ...node.parents, node.key])
  const query = { ...route.query }
  if (node) query.org = node.key
  else delete query.org
  router.push({ query })
}
watch(
  () => route.query.org,
  (value) => {
    closeImpact()
    selectedKey.value = String(value || '')
    page.value = 1
    const n = selected.value
    if (n) expanded.value = new Set([...expanded.value, ...n.parents, n.key])
  },
  { immediate: true }
)
watch(childSearch, () => {
  page.value = 1
})
watch(
  () => route.query.tab,
  () => {
    closeImpact()
    childSearch.value = ''
    page.value = 1
  }
)
watch(
  () => props.refreshing,
  (value) => {
    if (value) invalidate()
  }
)
watch(
  () => can('deprecateOrg'),
  () => closeImpact()
)
watch(
  () => props.tree,
  () => {
    invalidate()
    if (selectedKey.value && !selected.value) selectedKey.value = ''
    const n = selected.value
    if (n) expanded.value = new Set([...expanded.value, ...n.parents])
    page.value = Math.min(page.value, pageCount.value)
  }
)
watch(
  () => [
    props.ctx,
    props.ctx?.ctxKey,
    props.ctx?.currentRole?.roleCode,
    props.ctx?.dataScope?.scopeName
  ],
  () => {
    closeImpact()
    selectedKey.value = ''
    search.value = ''
    completed.value = ''
  }
)
async function startImpact() {
  if (!selected.value || submitting.value || props.refreshing) return
  invalidate()
  const request = sequence
  const node = selected.value
  impactOpen.value = true
  impactLoading.value = true
  impactError.value = ''
  try {
    const response = await systemApi.getOrgNodeImpact(node.type, node.id)
    if (request !== sequence) return
    if (response.code !== 0) throw new Error(response.message)
    if (
      typeof response.data?.canDisable !== 'boolean' ||
      !response.data.previewToken ||
      response.data.nodeVersion == null
    ) {
      throw new Error('影响检查未返回完整凭证，请重新检查；仍失败时联系管理员。')
    }
    impact.value = response.data
    expiresAt.value =
      Date.now() + Math.min(300, Math.max(0, Number(response.data.previewExpiresIn ?? 300))) * 1000
    now.value = Date.now()
  } catch (error) {
    if (request === sequence) impactError.value = error.message || '影响检查失败，请重新检查'
  } finally {
    if (request === sequence) impactLoading.value = false
  }
}
async function deprecate({ reason }) {
  if (!canConfirm.value) return
  draftReason.value = reason
  const node = selected.value,
    receipt = impact.value,
    request = sequence
  submitting.value = true
  impactError.value = ''
  // One signed preview is consumed once; never retry a write with a fresh version automatically.
  impact.value = null
  expiresAt.value = 0
  try {
    const result = await systemP1ClosureApi.deprecateOrgNodeWithPreview(node.id, {
      type: node.type,
      reason,
      previewToken: receipt.previewToken,
      expectedVersion: receipt.nodeVersion
    })
    if (request !== sequence) return
    if (result?.status !== 'DISABLED' || String(result.id) !== String(node.id))
      throw new Error('提交结果未确认，请回读组织状态后重新检查')
    confirmOpen.value = false
    impactOpen.value = false
    selectedKey.value = ''
    draftReason.value = ''
    completed.value = `「${node.name}」已作废，历史归属和审计记录保留。`
    const query = { ...route.query }
    delete query.org
    await router.replace({ query })
    emit('refresh')
  } catch (error) {
    if (request === sequence) {
      confirmOpen.value = false
      impactError.value = error.message || '作废结果未确认，请回读组织状态后重新检查'
      emit('refresh')
    }
  } finally {
    submitting.value = false
  }
}
</script>
<style scoped>
.org-status {
  font-size: 12px;
  border-radius: 12px;
  padding: 4px 8px;
  background: #edf8f2;
  color: #246440;
  white-space: nowrap;
}
.org-status.disabled {
  background: #f1f3f7;
  color: #586d89;
}
.org-workspace {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
  color: var(--t1, #203450);
  font-size: 14px;
}
.org-directory,
.org-detail {
  background: var(--surface, #fff);
  border: 1px solid var(--line, #dce5f3);
  border-radius: 10px;
  min-width: 0;
}
.org-directory {
  padding: 16px 10px;
  position: sticky;
  top: 12px;
}
.org-detail {
  padding: 22px;
  min-height: 610px;
}
.org-search {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--line, #dce5f3);
  border-radius: 7px;
  padding: 10px 12px;
  background: var(--surface, #fff);
}
.org-workspace .org-search input {
  width: 100%;
  min-width: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  outline: none;
  min-height: 20px;
  border-radius: 0;
  font-size: 14px;
}
.org-search:focus-within {
  outline: 2px solid var(--pri, #285bb5);
  outline-offset: 2px;
}
.org-workspace svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}
.org-workspace button {
  font: inherit;
  cursor: pointer;
}
.org-workspace button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
.org-root,
.org-node,
.org-toggle {
  display: flex;
  align-items: center;
  background: none;
  border: 0;
  color: inherit;
}
.org-root {
  gap: 10px;
  padding: 16px 10px;
}
.org-tree {
  max-height: 58vh;
  overflow: auto;
}
.org-tree-row {
  display: flex;
  align-items: center;
  border-radius: 6px;
  min-height: 40px;
}
.org-tree-row.selected {
  background: var(--pri-50, #e5edfc);
  color: var(--pri, #285bb5);
  font-weight: 600;
}
.org-tree-row:hover {
  background: var(--bg-hover, #edf3fc);
}
.org-node {
  gap: 8px;
  text-align: left;
  flex: 1;
  padding: 8px 4px;
  min-width: 0;
}
.org-node span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.org-toggle {
  padding: 2px;
}
.org-toggle svg {
  width: 14px;
}
.org-spacer {
  width: 18px;
  flex-shrink: 0;
}
.org-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--t3, #586d89);
  margin-bottom: 12px;
}
.org-breadcrumb button,
.org-link {
  padding: 0;
  background: none;
  border: 0;
  color: var(--pri, #285bb5);
  text-align: left;
}
.org-breadcrumb svg {
  width: 12px;
}
.org-detail-head {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.org-detail-head p {
  margin: 0;
  line-height: 1.6;
}
.org-detail h2 {
  font-size: 24px;
  line-height: 1.5;
  margin: 0 0 10px;
}
.org-detail h2 small {
  font-size: 13px;
  background: var(--pri-50, #e5edfc);
  color: var(--pri, #285bb5);
  border-radius: 12px;
  padding: 4px 10px;
  vertical-align: middle;
}
.org-muted {
  color: var(--t3, #586d89);
  line-height: 1.7;
  font-size: 13px;
}
.org-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.org-list-tools {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin: 20px 0 16px;
}
.org-list-tools .org-search {
  max-width: 340px;
}
.org-table-wrap {
  overflow: auto;
}
.org-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}
.org-table th {
  background: var(--bg-page, #f4f7fc);
  color: var(--t3, #586d89);
  font-weight: 600;
}
.org-table td,
.org-table th {
  padding: 15px 12px;
  border-bottom: 1px solid var(--line, #dce5f3);
}
.org-code {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.org-pagination {
  display: flex;
  justify-content: flex-end;
  gap: 14px;
  align-items: center;
  margin-top: 24px;
  color: var(--t3, #586d89);
}
.org-pagination button {
  border: 1px solid var(--line, #dce5f3);
  border-radius: 5px;
  padding: 6px 10px;
  background: var(--surface, #fff);
  color: inherit;
}
.org-pagination > span:first-child {
  margin-right: auto;
}
.org-empty {
  padding: 36px 12px;
  text-align: center;
  color: var(--t3, #586d89);
}
.org-steps {
  display: flex;
  gap: 24px;
  justify-content: space-around;
  list-style: none;
  padding: 8px 0;
  margin: 0 0 14px;
  color: var(--t3, #586d89);
}
.org-steps [aria-current],
.org-steps .active {
  color: var(--pri, #285bb5);
  font-weight: 600;
}
.org-warning {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 12px 16px;
  background: #fff7e8;
  border: 1px solid #f1d4a4;
  border-radius: 8px;
  color: #8d4a09;
  line-height: 1.7;
}
.org-warning svg {
  width: 24px;
  height: 24px;
}
.org-warning p {
  margin: 4px 0 0;
}
.org-warning.clear,
.org-result {
  background: #edf8f2;
  border-color: #a9d7bf;
  color: #246440;
}
.org-result {
  padding: 16px;
  line-height: 1.6;
}
.org-impact-counts {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  padding: 12px 0;
  border-block: 1px solid var(--line, #dce5f3);
  margin: 16px 0;
}
.org-impact-counts div {
  padding: 0 18px;
  border-right: 1px solid var(--line, #dce5f3);
}
.org-impact-counts div:last-child {
  border: 0;
}
.org-impact-counts dt {
  color: var(--t3, #586d89);
  font-size: 13px;
}
.org-impact-counts dd {
  margin: 6px 0 0;
  font-size: 26px;
  color: var(--pri, #285bb5);
  font-weight: 650;
}
.org-impact-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 18px;
}
.org-workspace button:focus-visible {
  outline: 2px solid var(--pri, #285bb5);
  outline-offset: 2px;
}
@media (max-width: 1150px) {
  .org-workspace {
    grid-template-columns: 220px minmax(0, 1fr);
  }
  .org-detail {
    padding: 16px;
  }
  .org-impact-counts {
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
  }
}
@media (max-width: 800px) {
  .org-workspace {
    grid-template-columns: 1fr;
  }
  .org-directory {
    position: static;
  }
  .org-tree {
    max-height: 240px;
  }
  .org-list-tools {
    align-items: stretch;
    flex-direction: column;
  }
  .org-steps {
    gap: 8px;
    font-size: 12px;
  }
  .org-table th,
  .org-table td {
    padding: 12px 6px;
  }
  .org-detail {
    min-height: 0;
  }
}
</style>
