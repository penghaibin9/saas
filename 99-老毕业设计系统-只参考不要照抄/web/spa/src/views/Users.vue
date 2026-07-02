<script setup>
import { onMounted, ref } from 'vue';
import api from '../api/client';

// 用户管理样例页：对照 管理平台.html 同功能的迁移模板。
// 关键点：Vue 模板对 {{ }} 与属性绑定默认 HTML 转义，存储型 XSS 天然消除——
// 不再需要手写 esc()，这正是从单文件迁到 SPA 的核心收益之一。
const list = ref([]);
const total = ref(0);
const loading = ref(false);
const err = ref('');
const roleMap = { 1: '院校管理员', 2: '分院管理员', 3: '指导教师', 4: '学生', 5: '企业导师' };

async function load() {
  loading.value = true; err.value = '';
  try {
    const r = await api.get('/admin/users', { params: { page: 1, page_size: 20 } });
    list.value = r.list || [];
    total.value = r.total || 0;
  } catch (e) { err.value = e.message; }
  finally { loading.value = false; }
}
onMounted(load);
</script>

<template>
  <div>
    <h3>用户管理 <small>共 {{ total }} 人</small></h3>
    <p v-if="err" class="err">{{ err }}</p>
    <table v-else>
      <thead><tr><th>用户名</th><th>姓名</th><th>角色</th><th>学工号</th><th>状态</th></tr></thead>
      <tbody>
        <tr v-for="u in list" :key="u.id">
          <td>{{ u.username }}</td>
          <td>{{ u.realName || '-' }}</td>
          <td>{{ roleMap[u.role] || '-' }}</td>
          <td>{{ u.eeid || '—' }}</td>
          <td><span :class="u.status === 1 ? 'ok' : 'no'">{{ u.status === 1 ? '启用' : '禁用' }}</span></td>
        </tr>
      </tbody>
    </table>
    <p v-if="loading">加载中…</p>
  </div>
</template>

<style scoped>
h3 { margin: 0 0 14px; } small { color: #94a3b8; font-weight: 400; font-size: 13px; }
table { width: 100%; background: #fff; border-collapse: collapse; border-radius: 10px; overflow: hidden; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #eef2f7; font-size: 14px; }
th { background: #f8fafc; color: #5b6b82; }
.ok { color: #16a34a; } .no { color: #dc2626; }
.err { color: #dc2626; }
</style>
