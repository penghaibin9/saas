import { defineStore } from 'pinia';
import axios from 'axios';

// 认证状态：登录、token/用户持久化、登出。登录直接打后端 /api/users/login。
export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    roleName: (s) => (s.user ? s.user.roleName : ''),
  },
  actions: {
    async login(username, password) {
      const res = await axios.post('/api/users/login', { username, password });
      const body = res.data;
      if (!body.success) throw new Error(body.message || '登录失败');
      this.token = body.data.token;
      this.user = body.data.user;
      localStorage.setItem('token', this.token);
      localStorage.setItem('user', JSON.stringify(this.user));
      return body.data; // 含 mustChangePassword
    },
    logout() {
      this.token = ''; this.user = null;
      localStorage.removeItem('token'); localStorage.removeItem('user');
    },
  },
});
