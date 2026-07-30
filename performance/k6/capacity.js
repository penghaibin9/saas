import http from 'k6/http';
import { check, group, sleep } from 'k6';

import { authHeaders } from './lib/auth.js';
import { BASE_URL, options as configuredOptions } from './lib/config.js';

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

function compactSummary(data) {
  const metrics = data.metrics || {};
  const duration = metrics.http_req_duration && metrics.http_req_duration.values;
  const failed = metrics.http_req_failed && metrics.http_req_failed.values;
  const checks = metrics.checks && metrics.checks.values;
  return [
    'Yueke capacity gate',
    `requests=${(metrics.http_reqs && metrics.http_reqs.values && metrics.http_reqs.values.count) || 0}`,
    `p95_ms=${duration ? duration['p(95)'] : 'n/a'}`,
    `p99_ms=${duration ? duration['p(99)'] : 'n/a'}`,
    `failed_rate=${failed ? failed.rate : 'n/a'}`,
    `check_rate=${checks ? checks.rate : 'n/a'}`,
    '',
  ].join('\n');
}

export function handleSummary(data) {
  const path = String(__ENV.SUMMARY_PATH || 'performance/results/k6-summary.json');
  return {
    stdout: compactSummary(data),
    [path]: JSON.stringify(data, null, 2),
  };
}
