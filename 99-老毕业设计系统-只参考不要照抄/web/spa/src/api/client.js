import axios from 'axios';
import { useAuthStore } from '../stores/auth';

// 统一 API 客户端：自动带 token，401 跳登录，统一解包 { success, data, message }
const api = axios.create({ baseURL: '/api', timeout: 30000 });

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('token');
  if (token) cfg.headers.Authorization = 'Bearer ' + token;
  return cfg;
});

api.interceptors.response.use(
  (res) => {
    const body = res.data;
    if (body && body.success === false) return Promise.reject(new Error(body.message || '请求失败'));
    return body && Object.prototype.hasOwnProperty.call(body, 'data') ? body.data : body;
  },
  (err) => {
    if (err.response && err.response.status === 401) {
      try { useAuthStore().logout(); } catch (_) {}
      if (location.hash !== '#/login') location.hash = '#/login';
    }
    const msg = err.response?.data?.message || err.message || '网络错误';
    return Promise.reject(new Error(msg));
  }
);

export default api;
