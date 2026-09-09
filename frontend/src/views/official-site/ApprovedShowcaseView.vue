<template>
  <!-- Trusted repository-authored markup. Never replace with API/user-provided HTML. -->
  <div ref="host" v-html="markup" />
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import markup from '../../components/official-site/showcase/approved-home.html?raw'
import { mountShowcase } from '../../components/official-site/showcase/runtime.js'
import { OFFICIAL_SITE_CONTACT } from '../../config/officialSalesPages.js'
import { TEACHER_LOGIN_URL, STUDENT_LOGIN_URL, ENTERPRISE_LOGIN_URL, PRIVACY_URL, TERMS_URL } from '../../config/portalConfig.js'
import '../../components/official-site/showcase/showcase.css'
import { refreshOfficialHomeShare } from '../../services/officialWechatRuntime.js'

const host = ref(null)
const router = useRouter()
const route = useRoute()
let instance = null
let previousBodyMarker
let previousTitle
const ownedHead = []
const title = '跃科｜服务学生成长，成就教师发展'
const description = '跃科高校师生全生命周期解决方案：学生管理与高校人事两条产品线，教务、学工、岗位实习、毕业设计 PC 各十页，教师与学生微信小程序各十页，预约完整产品讲解。'
function metadata(selector, attributes, value) {
  let node = document.head.querySelector(selector)
  const previous = node?.getAttribute('content')
  const created = !node
  if (!node) { node = document.createElement('meta'); Object.entries(attributes).forEach(([key, content]) => node.setAttribute(key, content)); document.head.appendChild(node) }
  node.setAttribute('content', value)
  ownedHead.push(() => { if (node.getAttribute('content') !== value) return; if (created) node.remove(); else if (previous === null) node.removeAttribute('content'); else node.setAttribute('content', previous) })
}
onMounted(() => {
  previousTitle = document.title
  document.title = title
  previousBodyMarker = document.body.getAttribute('data-yueke-showcase')
  document.body.setAttribute('data-yueke-showcase', 'active')
  metadata('meta[name="description"]', { name: 'description' }, description)
  metadata('meta[property="og:title"]', { property: 'og:title' }, title)
  metadata('meta[property="og:description"]', { property: 'og:description' }, description)
  metadata('meta[property="og:image"]', { property: 'og:image' }, `${OFFICIAL_SITE_CONTACT.canonicalOrigin}/official-site/showcase-20260909/scenes/overview.webp`)
  void refreshOfficialHomeShare()
  instance = mountShowcase(host.value.querySelector('#ykw-site'), {
    contact: { ...OFFICIAL_SITE_CONTACT, tel: OFFICIAL_SITE_CONTACT.phoneHref.replace(/^tel:/, '') },
    links: { teacher: TEACHER_LOGIN_URL, student: STUDENT_LOGIN_URL, enterprise: ENTERPRISE_LOGIN_URL, privacy: PRIVACY_URL, terms: TERMS_URL },
    navigate: to => router.push(to)
  })
})
watch(() => route.hash, hash => instance?.navigateHash(hash))
onBeforeUnmount(() => {
  instance?.destroy()
  instance = null
  if (document.body.getAttribute('data-yueke-showcase') === 'active') {
    if (previousBodyMarker === null) document.body.removeAttribute('data-yueke-showcase')
    else document.body.setAttribute('data-yueke-showcase', previousBodyMarker)
  }
  if (document.title === title) document.title = previousTitle
  ownedHead.splice(0).forEach(restore => restore())
})
</script>
