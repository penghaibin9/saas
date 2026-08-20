const PROFILES = {
  smoke: {
    stages: [
      { duration: '15s', target: 2 },
      { duration: '30s', target: 2 },
      { duration: '15s', target: 0 },
    ],
  },
  baseline: {
    stages: [
      { duration: '30s', target: 20 },
      { duration: '2m', target: 20 },
      { duration: '30s', target: 0 },
    ],
  },
  p300: {
    stages: [
      { duration: '1m', target: 100 },
      { duration: '2m', target: 300 },
      { duration: '4m', target: 300 },
      { duration: '1m', target: 0 },
    ],
  },
  p500: {
    stages: [
      { duration: '1m', target: 150 },
      { duration: '2m', target: 300 },
      { duration: '2m', target: 500 },
      { duration: '5m', target: 500 },
      { duration: '1m', target: 0 },
    ],
  },
  p1000: {
    stages: [
      { duration: '3m', target: 250 },
      { duration: '5m', target: 1000 },
      { duration: '8m', target: 1000 },
      { duration: '3m', target: 0 },
    ],
  },
  p3000: {
    stages: [
      { duration: '5m', target: 500 },
      { duration: '8m', target: 3000 },
      { duration: '10m', target: 3000 },
      { duration: '5m', target: 0 },
    ],
  },
};

const HIGH_LOAD_PROFILES = new Set(['p300', 'p500', 'p1000', 'p3000']);

function normalizeBaseUrl(raw) {
  const value = String(raw || '').trim().replace(/\/$/, '');
  if (!value) {
    throw new Error('BASE_URL is required');
  }
  const local = /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/i.test(value);
  if (!value.startsWith('https://') && !local) {
    throw new Error('BASE_URL must use HTTPS; only localhost may use HTTP');
  }
  return value;
}

function hostnameOf(baseUrl) {
  return String(baseUrl)
    .replace(/^https?:\/\//i, '')
    .split('/')[0]
    .split(':')[0]
    .toLowerCase();
}

function isLocalBaseUrl(baseUrl) {
  return /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/i.test(String(baseUrl));
}

export const BASE_URL = normalizeBaseUrl(__ENV.BASE_URL);
export const PROFILE = String(__ENV.PROFILE || 'smoke').trim();
export const SCENARIO = String(__ENV.SCENARIO || 'mixed').trim();
/**
 * V3 §11.5：数据规模档。10k 数据集与 10k 并发是两件事——
 * campus-10k-data 表示"上面那些并发档跑在 12k 学生数据集上"，不是 10k VU。
 */
export const DATASET = String(__ENV.DATASET || 'unknown').trim();

if (!PROFILES[PROFILE]) {
  throw new Error(`Unknown PROFILE=${PROFILE}; allowed: ${Object.keys(PROFILES).join(', ')}`);
}
if (!['student', 'teacher', 'mixed'].includes(SCENARIO)) {
  throw new Error(`Unknown SCENARIO=${SCENARIO}; allowed: student, teacher, mixed`);
}
if (HIGH_LOAD_PROFILES.has(PROFILE) && __ENV.K6_ALLOW_HIGH_LOAD !== 'true') {
  throw new Error(`${PROFILE} is locked; set K6_ALLOW_HIGH_LOAD=true after capacity review`);
}
if (
  HIGH_LOAD_PROFILES.has(PROFILE)
  && /(^|\.)api\.hnyueke\.com$/i.test(hostnameOf(BASE_URL))
  && __ENV.K6_ALLOW_PRODUCTION_HIGH_LOAD !== 'true'
) {
  throw new Error('High load against api.hnyueke.com is locked; use staging or explicitly unlock production');
}

const routeThresholds = {
  'http_req_duration{route:student_home}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:student_messages}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:student_agenda}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:student_cases}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:student_search}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:teacher_workbench}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:teacher_todos}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:teacher_risk_students}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:teacher_my_students}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:teacher_student360}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:teacher_messages}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:teacher_visit}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:teacher_employment}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:teacher_employment_verification}': ['p(95)<1000', 'p(99)<2000'],
};

export const REQUIRED_STUDENT_V3_ROUTES = [
  'student_home',
  'student_messages',
  'student_agenda',
  'student_cases',
  'student_search',
];

/** T9 Teacher V3 hard gate: legacy workbench/todo/risk plus the five newly required real paths. */
export const REQUIRED_TEACHER_V3_ROUTES = [
  'teacher_workbench',
  'teacher_todos',
  'teacher_risk_students',
  'teacher_my_students',
  'teacher_student360',
  'teacher_messages',
  'teacher_visit',
  'teacher_employment_verification',
];

const fullLatencyThresholds = {
  http_req_duration: ['p(95)<1000', 'p(99)<2000'],
  ...routeThresholds,
};

// GitHub自包含高负载把k6、FastAPI、MySQL、Redis放在同一Runner，只作为功能与稳定性诊断。
// HTTPS预发/正式环境仍执行完整延迟硬门槛，禁止用本地诊断替代真实容量验收。
export const LOCAL_HIGH_LOAD_DIAGNOSTIC =
  isLocalBaseUrl(BASE_URL) && HIGH_LOAD_PROFILES.has(PROFILE);

export const options = {
  scenarios: {
    capacity_read: {
      executor: 'ramping-vus',
      exec: SCENARIO === 'student' ? 'studentRead' : SCENARIO === 'teacher' ? 'teacherRead' : 'mixedRead',
      gracefulRampDown: '20s',
      stages: PROFILES[PROFILE].stages,
    },
  },
  thresholds: {
    checks: ['rate>0.995'],
    http_req_failed: ['rate<0.005'],
    ...(LOCAL_HIGH_LOAD_DIAGNOSTIC ? {} : fullLatencyThresholds),
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
  userAgent: 'Yueke-Capacity-Gate/1.0',
  noConnectionReuse: false,
};
