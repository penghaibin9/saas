<template>
  <Teleport to="body">
    <div ref="host" class="aa-leadership-wall-host" role="region" aria-label="教务教学运行领导大屏" />
  </Teleport>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { request, currentUserFromToken } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'
import { createConnector, identityKey } from '../components/leadershipWall/aa-wall-connector.mjs'
import { mountAcademicWall } from '../components/leadershipWall/aa-wall-view.mjs'
import { createWallRuntime, routeAllowed } from '../components/leadershipWall/aa-wall-runtime.mjs'
import css from '../components/leadershipWall/aa-wall.css?raw'
import brand from '../components/leadershipWall/config/brand.json'
import campus from '../components/leadershipWall/config/campus.json'
import assetFiles from '../components/leadershipWall/config/assets.json'

// Vite resolves these assets at build time. Names may be changed in assets.json.
const assetModules = import.meta.glob('../components/leadershipWall/assets/*', {
  eager: true, query: '?url', import: 'default'
})
const assets = Object.fromEntries(Object.entries(assetFiles).map(([key,filename]) => [
  key, assetModules[`../components/leadershipWall/assets/${filename}`] || ''
]))
const props = defineProps({ ctx: { type: Object, default: null } })
const host = ref(null)
const router = useRouter(), route = useRoute()
const identity = () => identityKey(currentUserFromToken())
const can = (context,code) => context?.rbacOk !== false && Array.isArray(context?.permissionPatterns)
  && matchPermission(context.permissionPatterns,code)
let wall,connector,runtime,alive=false,appRoot,previousInert,previousOverflow,previousFocus

async function navigate(target) {
  const key = identity()
  const authorized = await connector.authorize(target)
  if(!alive || key !== identity())return
  if(!authorized) { wall.notify('当前身份无法进入该工作区，请检查权限。');return }
  const resolved = router.resolve(authorized.route)
  if(!routeAllowed(resolved,authorized.context,can)) {
    wall.notify('目标工作区未开放或权限不足。');return
  }
  wall.closeDialog()
  await router.push(authorized.route).catch(() => wall.notify('无法打开工作区，请检查当前权限。'))
}
function exit() {
  const query = { ...route.query };delete query.wall
  void router.replace({ path:route.path,query,hash:route.hash }).catch(() => wall.notify('返回工作台失败'))
}
function onVisibility(){runtime?.visibility()}
function pageHide(){runtime?.suspend()}
function pageShow(event){if(event.persisted)runtime?.invalidate()}

onMounted(() => {
  alive=true;previousFocus=document.activeElement
  appRoot=document.getElementById('app');previousInert=appRoot?.inert
  // Teleport places this wall outside #app; prevent keyboard focus on covered controls.
  if(appRoot&&!appRoot.contains(host.value))appRoot.inert=true
  previousOverflow=document.body.style.overflow;document.body.style.overflow='hidden'
  wall=mountAcademicWall(host.value,{
    css,brand,campus,assets,assetFiles,allowEditor:false,
    onNavigate:navigate,onRefresh:()=>runtime?.refresh(),onExit:exit
  })
  connector=createConnector({request,can,identity,onInvalidate:()=>wall?.reset('RESTRICTED')})
  runtime=createWallRuntime({connector,view:wall,identity,hidden:()=>document.hidden,refreshSeconds:brand.refreshSeconds})
  document.addEventListener('visibilitychange',onVisibility)
  window.addEventListener('pagehide',pageHide);window.addEventListener('pageshow',pageShow)
  runtime.start()
})
watch(() => JSON.stringify([props.ctx?.ctxKey,props.ctx?.permissionPatterns,props.ctx?.dataScope]),()=>runtime?.invalidate())
onBeforeUnmount(() => {
  alive=false;runtime?.dispose()
  document.removeEventListener('visibilitychange',onVisibility)
  window.removeEventListener('pagehide',pageHide);window.removeEventListener('pageshow',pageShow)
  if(appRoot)appRoot.inert=previousInert
  document.body.style.overflow=previousOverflow||''
  if(previousFocus?.isConnected)previousFocus.focus?.()
})
</script>

<style scoped>
.aa-leadership-wall-host { position:fixed;inset:0;z-index:10000;background:#001124;isolation:isolate; }
</style>
