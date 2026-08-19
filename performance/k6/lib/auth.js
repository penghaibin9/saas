import http from 'k6/http';
import { check } from 'k6';
import { SharedArray } from 'k6/data';

const cache = { student: null, teacher: null };

function parseJson(raw, label, fallback) {
  const value = String(raw || '').trim();
  if (!value) return fallback;
  try {
    return JSON.parse(value);
  } catch (error) {
    throw new Error(`${label} must be valid JSON: ${error.message}`);
  }
}

function arrayEnv(name) {
  const value = parseJson(__ENV[name], name, []);
  if (!Array.isArray(value)) {
    throw new Error(`${name} must be a JSON array`);
  }
  return value;
}

function fileArray(envName, label) {
  const path = String(__ENV[envName] || '').trim();
  if (!path) return [];
  const value = parseJson(open(path), label, []);
  if (!Array.isArray(value)) {
    throw new Error(`${label} must contain a JSON array`);
  }
  return value;
}

const studentFileTokens = new SharedArray('student capacity token pool', () =>
  fileArray('K6_STUDENT_TOKENS_FILE', 'K6_STUDENT_TOKENS_FILE'),
);
const teacherFileTokens = new SharedArray('teacher capacity token pool', () =>
  fileArray('K6_TEACHER_TOKENS_FILE', 'K6_TEACHER_TOKENS_FILE'),
);

/**
 * V3 §11.6 身份分布（深审 P0-08）。
 *
 * 高并发若复用少量 token，请求会集中命中同一份 Redis 缓存与同一个 scope，
 * 压出来的是"热缓存容量"，不是真实容量。因此分两档：
 *
 *   cold  —— 每个 VU 尽量拿到不同身份，覆盖冷启动与真实数据库成本（默认）；
 *   warm  —— 故意只用少量身份重复访问，单独评价缓存本身的稳定性。
 *
 * 两档都必须把实际使用到的 unique token 数写进 Artifact，否则无法判断这次
 * 压测到底压的是数据库还是缓存。
 */
export const IDENTITY_MODE = String(__ENV.IDENTITY_MODE || 'cold').trim().toLowerCase();
const WARM_POOL_SIZE = Math.max(1, Number(__ENV.WARM_IDENTITY_POOL || 5));

if (!['cold', 'warm'].includes(IDENTITY_MODE)) {
  throw new Error(`Unknown IDENTITY_MODE=${IDENTITY_MODE}; allowed: cold, warm`);
}

/** 本次运行实际会用到多少个不同身份——直接决定 Artifact 里的 uniqueTokens。 */
export function effectivePoolSize(total) {
  if (!total) return 0;
  return IDENTITY_MODE === 'warm' ? Math.min(total, WARM_POOL_SIZE) : total;
}

function selectByVu(items, label) {
  if (!items.length) return null;
  const span = effectivePoolSize(items.length);
  const index = Math.max(0, (__VU - 1) % span);
  const selected = items[index];
  if (!selected) throw new Error(`${label} contains an empty item at index ${index}`);
  return selected;
}

/** 供 Artifact 记录：各端 token 池规模与本次实际使用的身份数。 */
export function identityDistribution() {
  const studentTotal = studentFileTokens.length || arrayEnv('K6_STUDENT_TOKENS_JSON').length;
  const teacherTotal = teacherFileTokens.length || arrayEnv('K6_TEACHER_TOKENS_JSON').length;
  return {
    identityMode: IDENTITY_MODE,
    warmPoolSize: IDENTITY_MODE === 'warm' ? WARM_POOL_SIZE : null,
    studentTokensAvailable: studentTotal,
    teacherTokensAvailable: teacherTotal,
    uniqueStudentTokens: effectivePoolSize(studentTotal),
    uniqueTeacherTokens: effectivePoolSize(teacherTotal),
  };
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

function tokenPool(role) {
  const filePool = role === 'student' ? studentFileTokens : teacherFileTokens;
  if (filePool.length) return filePool;
  const tokenName = role === 'student' ? 'K6_STUDENT_TOKENS_JSON' : 'K6_TEACHER_TOKENS_JSON';
  return arrayEnv(tokenName);
}

export function bearerFor(role, baseUrl) {
  if (!['student', 'teacher'].includes(role)) throw new Error(`Unsupported role=${role}`);
  if (cache[role]) return cache[role];

  const tokenName = role === 'student' ? 'K6_STUDENT_TOKENS_JSON' : 'K6_TEACHER_TOKENS_JSON';
  const credentialName = role === 'student'
    ? 'K6_STUDENT_CREDENTIALS_JSON'
    : 'K6_TEACHER_CREDENTIALS_JSON';

  const token = selectByVu(tokenPool(role), `${tokenName}/file`);
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
