import { createRouter, createWebHashHistory } from 'vue-router';
import { useAuthStore } from '../stores/auth';

const routes = [
  { path: '/login', component: () => import('../views/Login.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('../layouts/AdminLayout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'users', component: () => import('../views/Users.vue') },
    ],
  },
];

const router = createRouter({ history: createWebHashHistory(), routes });

// 全局守卫：未登录跳登录页
router.beforeEach((to) => {
  const auth = useAuthStore();
  if (!to.meta.public && !auth.isLoggedIn) return { path: '/login' };
  if (to.path === '/login' && auth.isLoggedIn) return { path: '/dashboard' };
  return true;
});

export default router;
