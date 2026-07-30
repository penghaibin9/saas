import http from 'k6/http';
import { check } from 'k6';

const cache = { student: null, teacher: null };

function parseJsonEnv(name, fallback) {
  const raw = String(__ENV[name] || '').trim();
  if (!raw) return fallback;
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(`${name} must be valid JSON: ${error.message}`);
  }
}

function arrayEnv(name) {
  const value = parseJsonEnv(name, []);
  if (!Array.isArray(value)) {
    throw new Error(`${name} must be a JSON array`);
  }
  return value;
}

function selectByVu(items, label) {
  if (!items.length) return null;
  const index = Math.max(0, (__VU - 1) % items.length);
  const selected = items[index];
  if (!selected) throw new Error(`${label} contains an empty item at index ${index}`);
  return selected;
}

function extractAccessToken(payload) {
  const data = payload && payload.data ? payload.data : payload;
  return data && (data.accessToken || data.token || data.access_token);
}

function loginWithCredential(role, credential, baseUrl) {
  if (!credential || !credential.loginName || !credential.password) {
    throw new Error(`${role} credential requires loginName and password`);
  }
  const body = JSON.stringify({
    tenantCode: credential.tenantCode || undefined,
    loginName: credential.loginName,
    password: credential.password,
    clientType: role === 'student' ? 'STUDENT_MINI' : 'TEACHER_MINI',
  });
  const response = http.post(`${baseUrl}/api/v1/auth/login`, body, {
    headers: { 'Content-Type': 'application/json' },
    tags: { route: `${role}_login`, role },
  });
  const ok = check(response, {
    [`${role} login status=200`]: (res) => res.status === 200,
  });
  if (!ok) {
    throw new Error(`${role} login failed with HTTP ${response.status}`);
  }
  let payload;
  try {
    payload = response.json();
  } catch (error) {
    throw new Error(`${role} login returned non-JSON response`);
  }
  if (payload && payload.code !== undefined && Number(payload.code) !== 0) {
    throw new Error(`${role} login business code=${payload.code}`);
  }
  const token = extractAccessToken(payload);
  if (!token) throw new Error(`${role} login response does not contain accessToken`);
  return token;
}

export function bearerFor(role, baseUrl) {
  if (!['student', 'teacher'].includes(role)) throw new Error(`Unsupported role=${role}`);
  if (cache[role]) return cache[role];

  const tokenName = role === 'student' ? 'K6_STUDENT_TOKENS_JSON' : 'K6_TEACHER_TOKENS_JSON';
  const credentialName = role === 'student'
    ? 'K6_STUDENT_CREDENTIALS_JSON'
    : 'K6_TEACHER_CREDENTIALS_JSON';

  const token = selectByVu(arrayEnv(tokenName), tokenName);
  if (typeof token === 'string' && token.trim()) {
    cache[role] = token.trim();
    return cache[role];
  }

  const credential = selectByVu(arrayEnv(credentialName), credentialName);
  if (!credential) {
    throw new Error(`No ${role} token or credential pool configured`);
  }
  if (['p300', 'p500', 'p1000', 'p3000'].includes(String(__ENV.PROFILE || 'smoke'))) {
    throw new Error(`High-load profiles require pre-issued ${role} token pools; credential login is intentionally blocked`);
  }
  cache[role] = loginWithCredential(role, credential, baseUrl);
  return cache[role];
}

export function authHeaders(role, baseUrl) {
  return {
    Authorization: `Bearer ${bearerFor(role, baseUrl)}`,
    Accept: 'application/json',
  };
}
