<script setup>
import { onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import { connectRealtime, disconnectRealtime } from '../realtime';

const auth = useAuthStore();
const router = useRouter();
const toastMsg = ref('');

const nav = [
  { path: '/dashboard', label: '工作台' },
  { path: '/users', label: '用户管理' },
  // 迁移更多页面时往这里加路由 + views 组件即可
];

onMounted(() => {
  // 站内实时通知：收到即弹出（演示 SSE 闭环）
  connectRealtime(auth.token, (n) => {
    toastMsg.value = `${n.title}：${n.content}`;
    setTimeout(() => (toastMsg.value = ''), 4000);
  });
});
onUnmounted(disconnectRealtime);

function logout() {
  disconnectRealtime();
  auth.logout();
  router.push('/login');
}
</script>

<template>
  <div class="shell">
    <aside class="side">
      <div class="brand">实习管理平台</div>
      <nav>
        <router-link v-for="n in nav" :key="n.path" :to="n.path" class="item" active-class="active">{{ n.label }}</router-link>
      </nav>
    </aside>
    <main class="main">
      <header class="top">
        <span>{{ auth.user?.realName }}（{{ auth.roleName }}）</span>
        <button class="logout" @click="logout">退出</button>
      </header>
      <section class="body"><router-view /></section>
    </main>
    <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>
  </div>
</template>

<style scoped>
.shell { display: flex; min-height: 100vh; }
.side { width: 210px; background: #0f2456; color: #fff; padding: 16px 0; }
.brand { font-weight: 700; padding: 8px 20px 18px; font-size: 16px; }
.item { display: block; padding: 11px 20px; color: #cbd5e1; text-decoration: none; }
.item.active, .item:hover { background: rgba(255,255,255,.1); color: #fff; }
.main { flex: 1; display: flex; flex-direction: column; }
.top { display: flex; justify-content: flex-end; align-items: center; gap: 14px; padding: 12px 20px; background: #fff; border-bottom: 1px solid #e8edf3; }
.logout { border: 1px solid #fca5a5; color: #dc2626; background: #fff; border-radius: 6px; padding: 5px 12px; cursor: pointer; }
.body { padding: 20px; flex: 1; }
.toast { position: fixed; right: 20px; bottom: 20px; background: #0f2456; color: #fff; padding: 12px 16px; border-radius: 10px; box-shadow: 0 6px 20px rgba(0,0,0,.2); max-width: 320px; }
</style>
