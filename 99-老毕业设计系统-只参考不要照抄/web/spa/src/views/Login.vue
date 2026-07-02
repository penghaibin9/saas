<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';

const username = ref('');
const password = ref('');
const err = ref('');
const loading = ref(false);
const auth = useAuthStore();
const router = useRouter();

async function submit() {
  err.value = '';
  loading.value = true;
  try {
    const r = await auth.login(username.value, password.value);
    if (r.mustChangePassword) alert('首次登录，请尽快修改初始密码');
    router.push('/dashboard');
  } catch (e) {
    err.value = e.message;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="wrap">
    <form class="card" @submit.prevent="submit">
      <h2>实习管理平台 · 管理端</h2>
      <input v-model="username" placeholder="用户名" autocomplete="username" />
      <input v-model="password" type="password" placeholder="密码" autocomplete="current-password" />
      <p v-if="err" class="err">{{ err }}</p>
      <button :disabled="loading">{{ loading ? '登录中…' : '登 录' }}</button>
    </form>
  </div>
</template>

<style scoped>
.wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.card { background: #fff; padding: 32px; border-radius: 14px; box-shadow: 0 8px 30px rgba(0,0,0,.08); width: 320px; display: flex; flex-direction: column; gap: 12px; }
h2 { margin: 0 0 8px; font-size: 18px; color: #0f2456; }
input { border: 1px solid #cbd5e1; border-radius: 8px; padding: 11px; font-size: 15px; }
button { background: #0ea5e9; color: #fff; border: none; border-radius: 8px; padding: 12px; font-size: 16px; cursor: pointer; }
button:disabled { opacity: .6; }
.err { color: #dc2626; font-size: 13px; margin: 0; }
</style>
