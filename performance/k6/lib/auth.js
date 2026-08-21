import http from 'k6/http';
import { check } from 'k6';
import encoding from 'k6/encoding';
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
 * cold = 尽量一 VU 一身份；warm = 有意复用小池，二者必须分开裁决。
 */
export const IDENTITY_MODE = String(__ENV.IDENTITY_MODE || 'cold').trim().toLowerCase();
const WARM_POOL_SIZE = Math.max(1, Number(__ENV.WARM_IDENTITY_POOL || 5));

if (!['cold', 'warm'].includes(IDENTITY_MODE)) {
  throw new Error(`Unknown IDENTITY_MODE=${IDENTITY_MODE}; allowed: cold, warm`);
}

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

function decodeJwtClaims(token) {
  const raw = String(token || '').trim();
  const parts = raw.split('.');
  if (parts.length !== 3) return {};
  try {
    return JSON.parse(encoding.b64decode(parts[1], 'rawurl', 's'));
  } catch (_error) {
    return {};
  }
}

function roleBucket(value) {
  const role = String(value || '').trim().toUpperCase();
  if (!role) return 'unknown';
  if (role.includes('COUNSELOR')) return 'counselor';
  if (role.includes('COLLEGE')) return 'college';
  if (role.includes('ADVISOR') || role === 'TEACHER') return 'advisor';
  if (role.includes('ADMIN')) return 'admin';
  return 'other';
}

function ratioMap(counts, total) {
  const keys = ['counselor', 'college', 'advisor', 'admin', 'other', 'unknown'];
  const ratios = {};
  for (const key of keys) ratios[key] = total ? Number(((counts[key] || 0) / total).toFixed(4)) : 0;
  return ratios;
}

function teacherIdentityEvidence(tokens, credentials) {
  const tokenSpan = effectivePoolSize(tokens.length);
  const credentialSpan = tokenSpan ? 0 : effectivePoolSize(credentials.length);
  const total = tokenSpan || credentialSpan;
  const roleCounts = { counselor: 0, college: 0, advisor: 0, admin: 0, other: 0, unknown: 0 };
  const contexts = new Set();

  if (tokenSpan) {
    for (let index = 0; index < tokenSpan; index += 1) {
      const claims = decodeJwtClaims(tokens[index]);
      roleCounts[roleBucket(claims.currentRoleCode || claims.roleCode || claims.role)] += 1;
      const context = String(claims.activeContextId || '').trim();
      if (context) contexts.add(context);
    }
  } else {
    for (let index = 0; index < credentialSpan; index += 1) {
      const credential = credentials[index] || {};
      roleCounts[roleBucket(credential.currentRoleCode || credential.roleCode || credential.role)] += 1;
      const context = String(credential.activeContextId || '').trim();
      if (context) contexts.add(context);
    }
  }

  return {
    uniqueTeacherContexts: contexts.size,
    teacherRoleCounts: roleCounts,
    teacherRoleRatios: ratioMap(roleCounts, total),
  };
}

/** Artifact 取证：真实池规模、cold/warm 实际身份数、教师 context/角色构成。 */
export function identityDistribution() {
  const studentTokens = studentFileTokens.length ? studentFileTokens : arrayEnv('K6_STUDENT_TOKENS_JSON');
  const teacherTokens = teacherFileTokens.length ? teacherFileTokens : arrayEnv('K6_TEACHER_TOKENS_JSON');
  const studentCredentials = arrayEnv('K6_STUDENT_CREDENTIALS_JSON');
  const teacherCredentials = arrayEnv('K6_TEACHER_CREDENTIALS_JSON');
  const teacherEvidence = teacherIdentityEvidence(teacherTokens, teacherCredentials);
  return {
    identityMode: IDENTITY_MODE,
    warmPoolSize: IDENTITY_MODE === 'warm' ? WARM_POOL_SIZE : null,
    studentTokensAvailable: studentTokens.length,
    teacherTokensAvailable: teacherTokens.length,
    studentCredentialsAvailable: studentCredentials.length,
    teacherCredentialsAvailable: teacherCredentials.length,
    uniqueStudentTokens: effectivePoolSize(studentTokens.length || studentCredentials.length),
    uniqueTeacherTokens: effectivePoolSize(teacherTokens.length || teacherCredentials.length),
    ...teacherEvidence,
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
  } catch (_error) {
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
