<template>
  <div class="profile-page">
    <div class="profile-page__topbar">
      <div>
        <p>岗位实习中心</p>
        <h1>实习档案</h1>
      </div>
      <button type="button" @click="router.push('/internship/selection')">返回实习选岗</button>
    </div>

    <div v-if="loading" class="page-state">正在加载实习档案…</div>
    <div v-else-if="error" class="page-state page-state--error">
      <strong>实习档案加载失败</strong>
      <span>{{ error }}</span>
      <button type="button" @click="load">重新加载</button>
    </div>
    <InternshipProfileEditor
      v-else
      :profile="profile"
      :completeness="completeness"
      :items="items"
      :busy="busy"
      @save="saveProfile"
      @add-item="addItem"
      @delete-item="deleteItem"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import InternshipProfileEditor from '../../components/recruitment/InternshipProfileEditor.vue'
import {
  normalizeInternshipProfile,
  normalizeProfileCompleteness,
  normalizeProfileItems
} from '../../modules/internshipRecruitment/profileModel'
import { internshipSelectionApi } from '../../services/internshipSelectionApi'

const router = useRouter()
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const profile = ref(normalizeInternshipProfile())
const completeness = ref(normalizeProfileCompleteness())
const items = ref([])
let requestSeq = 0

async function load() {
  const requestId = ++requestSeq
  loading.value = true
  error.value = ''
  try {
    const [profileData, completenessData, itemData] = await Promise.all([
      internshipSelectionApi.profile(),
      internshipSelectionApi.profileCompleteness(),
      internshipSelectionApi.profileItems()
    ])
    if (requestId !== requestSeq) return
    profile.value = normalizeInternshipProfile(profileData || {})
    completeness.value = normalizeProfileCompleteness(completenessData || {})
    items.value = normalizeProfileItems(itemData || [])
  } catch (err) {
    if (requestId !== requestSeq) return
    error.value = err?.message || '请稍后重试'
  } finally {
    if (requestId === requestSeq) loading.value = false
  }
}

async function refreshAfterWrite() {
  const [profileData, completenessData, itemData] = await Promise.all([
    internshipSelectionApi.profile(),
    internshipSelectionApi.profileCompleteness(),
    internshipSelectionApi.profileItems()
  ])
  profile.value = normalizeInternshipProfile(profileData || {})
  completeness.value = normalizeProfileCompleteness(completenessData || {})
  items.value = normalizeProfileItems(itemData || [])
}

async function saveProfile(payload) {
  busy.value = true
  try {
    await internshipSelectionApi.updateProfile(payload)
    await refreshAfterWrite()
  } catch (err) {
    error.value = err?.message || '实习档案保存失败'
  } finally {
    busy.value = false
  }
}

async function addItem(payload) {
  busy.value = true
  try {
    await internshipSelectionApi.createProfileItem(payload)
    await refreshAfterWrite()
  } catch (err) {
    error.value = err?.message || '材料条目添加失败'
  } finally {
    busy.value = false
  }
}

async function deleteItem(item) {
  if (!item?.id) return
  busy.value = true
  try {
    await internshipSelectionApi.deleteProfileItem(item.id)
    await refreshAfterWrite()
  } catch (err) {
    error.value = err?.message || '材料条目删除失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.profile-page { min-height:100%; padding:20px; background:#f7f8fa; }
.profile-page__topbar { display:flex; align-items:flex-end; justify-content:space-between; gap:16px; margin-bottom:14px; }
.profile-page__topbar p { margin:0 0 4px; color:#2f6bff; font-size:12px; font-weight:600; }
.profile-page__topbar h1 { margin:0; color:#1a1a1a; font-size:24px; }
.profile-page__topbar button { border:1px solid #d9d9d9; border-radius:7px; padding:8px 12px; background:#fff; color:#2f6bff; cursor:pointer; }
.page-state { display:flex; align-items:center; justify-content:center; gap:10px; min-height:220px; padding:20px; border:1px solid #eef0f3; border-radius:12px; background:#fff; color:#8c8c8c; }
.page-state--error { flex-direction:column; border-color:#ffccc7; background:#fff2f0; color:#a8071a; }
.page-state button { border:0; border-radius:6px; padding:7px 12px; background:#2f6bff; color:#fff; cursor:pointer; }
@media (max-width:899px) { .profile-page { padding:12px; } }
</style>
