import http from 'k6/http';
import { check, group, sleep } from 'k6';

import { authHeaders, identityDistribution } from './lib/auth.js';
import {
  BASE_URL, DATASET, PROFILE, REQUIRED_STUDENT_V3_ROUTES, SCENARIO,
  options as configuredOptions,
} from './lib/config.js';

export const options = configuredOptions;

function getJson(role, route, path) {
  const response = http.get(`${BASE_URL}${path}`, {
    headers: authHeaders(role, BASE_URL),
    tags: { route, role },
    timeout: '15s',
  });
  const transportOk = check(response, {
    [`${route} HTTP 200`]: (res) => res.status === 200,
  });
  if (!transportOk) return response;

  check(response, {
    [`${route} business code 0`]: (res) => {
      try {
        const body = res.json();
        return body && Number(body.code) === 0;
      } catch (_error) {
        return false;
      }
    },
  });
  return response;
}

function jitter() {
  sleep(0.2 + Math.random() * 0.8);
}

const SEARCH_KEYWORD = String(__ENV.SEARCH_KEYWORD || '通知').trim();

export function studentRead() {
  group('student-core-read', () => {
    getJson('student', 'student_home', '/api/v1/mobile/home');
    jitter();
    getJson('student', 'student_todos', '/api/v1/student-mini/todos?status=PENDING&page=1&pageSize=20');
    jitter();
    getJson(
      'student',
      'student_messages',
      '/api/v1/mobile/performance/student/messages-page?tab=notice&page=1&pageSize=20',
    );
    jitter();
    getJson('student', 'student_profile', '/api/v1/mobile/me/profile');
    jitter();
    // ── V3 新增 P0 链路（§11.6 / 深审 P0-07）──
    getJson('student', 'student_agenda', '/api/v1/mobile/student/agenda?days=7&pageSize=20');
    jitter();
    getJson('student', 'student_cases', '/api/v1/mobile/student/cases?statusGroup=all&pageSize=20');
    jitter();
    // 搜索用固定关键词，保证不同 VU 的扫描成本可比；关键词长度必须 ≥2 才会真正查询。
    getJson('student', 'student_search', `/api/v1/mobile/student/search?q=${encodeURIComponent(SEARCH_KEYWORD)}&pageSize=20`);
  });
  jitter();
}

export function teacherRead() {
  group('teacher-core-read', () => {
    getJson(
      'teacher',
      'teacher_workbench',
      '/api/v1/mobile/performance/teacher/workbench?pageSize=8',
    );
    jitter();
    getJson(
      'teacher',
      'teacher_todos',
      '/api/v1/mobile/performance/teacher/todos-page?group=all&page=1&pageSize=20',
    );
    jitter();
    getJson('teacher', 'teacher_classes', '/api/v1/mobile/teacher/my-classes');
    jitter();
    getJson(
      'teacher',
      'teacher_risk_students',
      '/api/v1/mobile/performance/teacher/risk-students-page?level=all&page=1&pageSize=20',
    );
  });
  jitter();
}

export function mixedRead() {
  const studentShare = Math.min(100, Math.max(0, Number(__ENV.STUDENT_SHARE_PERCENT || 75)));
  const selector = (__VU * 31 + __ITER * 17) % 100;
  if (selector < studentShare) studentRead();
  else teacherRead();
}

/** 每条路由的 p95/p99 单独取出，供 Artifact 逐路由判定，而不是只看全局分位。 */
function routeLatencies(metrics) {
  const rows = {};
  for (const [name, metric] of Object.entries(metrics || {})) {
    const match = /^http_req_duration\{route:([^}]+)\}$/.exec(name);
    if (!match || !metric || !metric.values) continue;
    rows[match[1]] = {
      p95: metric.values['p(95)'],
      p99: metric.values['p(99)'],
      count: metric.values.count,
    };
  }
  return rows;
}

function compactSummary(data) {
  const metrics = data.metrics || {};
  const duration = metrics.http_req_duration && metrics.http_req_duration.values;
  const failed = metrics.http_req_failed && metrics.http_req_failed.values;
  const checks = metrics.checks && metrics.checks.values;
  const identity = identityDistribution();
  const routes = routeLatencies(metrics);
  const missing = REQUIRED_STUDENT_V3_ROUTES.filter((route) => !routes[route]);
  return [
    'Yueke capacity gate',
    `profile=${PROFILE} scenario=${SCENARIO} dataset=${DATASET}`,
    `identityMode=${identity.identityMode} uniqueStudentTokens=${identity.uniqueStudentTokens} uniqueTeacherTokens=${identity.uniqueTeacherTokens}`,
    `requests=${(metrics.http_reqs && metrics.http_reqs.values && metrics.http_reqs.values.count) || 0}`,
    `p95_ms=${duration ? duration['p(95)'] : 'n/a'}`,
    `p99_ms=${duration ? duration['p(99)'] : 'n/a'}`,
    `failed_rate=${failed ? failed.rate : 'n/a'}`,
    `check_rate=${checks ? checks.rate : 'n/a'}`,
    missing.length
      ? `MISSING_V3_ROUTES=${missing.join(',')}（本次未覆盖 V3 新增链路，不能作为容量证据）`
      : 'v3_routes=covered',
    '',
  ].join('\n');
}

export function handleSummary(data) {
  const path = String(__ENV.SUMMARY_PATH || 'performance/results/k6-summary.json');
  const metrics = data.metrics || {};
  const routes = routeLatencies(metrics);
  const identity = identityDistribution();
  // V3 §11.6：Artifact 自带 VU、身份分布、逐路由分位与覆盖结论，
  // 否则事后无法判断这份数据压的是数据库还是热缓存、有没有覆盖新链路。
  //
  // 注意：SUMMARY_PATH 必须继续是**原始 k6 summary**——
  // performance/tools/evaluate_capacity_result.py 直接读它的 metrics 字段做裁决。
  // V3 的附加信息写到同目录的 sibling 文件，不改既有契约。
  const artifact = {
    schema: 'yueke-capacity-artifact/1',
    profile: PROFILE,
    scenario: SCENARIO,
    dataset: DATASET,
    baseUrl: BASE_URL,
    identity,
    routes,
    requiredStudentV3Routes: REQUIRED_STUDENT_V3_ROUTES,
    missingStudentV3Routes: REQUIRED_STUDENT_V3_ROUTES.filter((route) => !routes[route]),
    totals: {
      requests: (metrics.http_reqs && metrics.http_reqs.values && metrics.http_reqs.values.count) || 0,
      failedRate: metrics.http_req_failed && metrics.http_req_failed.values.rate,
      checkRate: metrics.checks && metrics.checks.values.rate,
    },
  };
  const artifactPath = path.replace(/\.json$/, '') + '-v3.json';
  return {
    stdout: compactSummary(data),
    // 原始 summary：既有裁决工具的输入，形状不变。
    [path]: JSON.stringify(data, null, 2),
    // V3 附加取证：身份分布 + 逐路由分位 + 新链路覆盖结论。
    [artifactPath]: JSON.stringify(artifact, null, 2),
  };
}
