import http from 'k6/http';
import { check, group, sleep } from 'k6';

import { authHeaders } from './lib/auth.js';
import {
  BASE_URL,
  LOCAL_HIGH_LOAD_DIAGNOSTIC,
  options as configuredOptions,
} from './lib/config.js';

const BATCH_ID = String(__ENV.INTERNSHIP_BATCH_ID || '').trim();
if (!BATCH_ID) throw new Error('INTERNSHIP_BATCH_ID is required for internship capacity workload');

const internshipRouteThresholds = {
  'http_req_duration{route:internship_dashboard}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:internship_students}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:internship_reports}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:internship_teacher_context}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:internship_student_context}': ['p(95)<1000', 'p(99)<2000'],
};

export const options = {
  ...configuredOptions,
  thresholds: {
    ...configuredOptions.thresholds,
    ...(LOCAL_HIGH_LOAD_DIAGNOSTIC ? {} : internshipRouteThresholds),
  },
};

function getJson(role, route, path) {
  const response = http.get(`${BASE_URL}${path}`, {
    headers: authHeaders(role, BASE_URL),
    tags: { route, role, domain: 'internship' },
    timeout: '15s',
  });
  const transportOk = check(response, {
    [`${route} HTTP 200`]: (res) => res.status === 200,
  });
  if (!transportOk) return response;
  check(response, {
    [`${route} business code 0`]: (res) => {
      try {
        return Number((res.json() || {}).code) === 0;
      } catch (_error) {
        return false;
      }
    },
  });
  return response;
}

function jitter() {
  sleep(0.15 + Math.random() * 0.55);
}

export function studentRead() {
  group('internship-student-read', () => {
    getJson(
      'student',
      'internship_student_context',
      `/api/v1/mobile/internship/context/my?batchId=${encodeURIComponent(BATCH_ID)}`,
    );
    jitter();
    getJson('student', 'internship_student_plan', '/api/v1/mobile/internship/context/plan');
    jitter();
    getJson('student', 'internship_student_plan_tasks', '/api/v1/mobile/internship/context/plan/tasks');
  });
  jitter();
}

export function teacherRead() {
  group('internship-teacher-read', () => {
    getJson(
      'teacher',
      'internship_dashboard',
      `/api/v1/internship/dashboard?batchId=${encodeURIComponent(BATCH_ID)}`,
    );
    jitter();
    getJson(
      'teacher',
      'internship_students',
      `/api/v1/internship/intern-students?page=1&pageSize=20&batchId=${encodeURIComponent(BATCH_ID)}`,
    );
    jitter();
    getJson(
      'teacher',
      'internship_reports',
      `/api/v1/internship/reports?page=1&pageSize=20&batchId=${encodeURIComponent(BATCH_ID)}`,
    );
    jitter();
    getJson(
      'teacher',
      'internship_guidances',
      `/api/v1/internship/guidances?page=1&pageSize=20&batchId=${encodeURIComponent(BATCH_ID)}`,
    );
    jitter();
    getJson(
      'teacher',
      'internship_risks',
      `/api/v1/internship/risks?page=1&pageSize=20&batchId=${encodeURIComponent(BATCH_ID)}`,
    );
    jitter();
    getJson(
      'teacher',
      'internship_teacher_context',
      '/api/v1/mobile/teacher/internship/context',
    );
    jitter();
    getJson(
      'teacher',
      'internship_teacher_plan_tasks',
      `/api/v1/mobile/teacher/internship/context/plan-tasks?batchId=${encodeURIComponent(BATCH_ID)}&page=1&pageSize=20`,
    );
  });
  jitter();
}

export function mixedRead() {
  const studentShare = Math.min(100, Math.max(0, Number(__ENV.STUDENT_SHARE_PERCENT || 65)));
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
    'Yueke internship capacity workload',
    `batch_id=${BATCH_ID}`,
    `requests=${(metrics.http_reqs && metrics.http_reqs.values && metrics.http_reqs.values.count) || 0}`,
    `p95_ms=${duration ? duration['p(95)'] : 'n/a'}`,
    `p99_ms=${duration ? duration['p(99)'] : 'n/a'}`,
    `failed_rate=${failed ? failed.rate : 'n/a'}`,
    `check_rate=${checks ? checks.rate : 'n/a'}`,
    '',
  ].join('\n');
}

export function handleSummary(data) {
  const path = String(__ENV.SUMMARY_PATH || 'performance/results/internship-k6-summary.json');
  return {
    stdout: compactSummary(data),
    [path]: JSON.stringify(data, null, 2),
  };
}
