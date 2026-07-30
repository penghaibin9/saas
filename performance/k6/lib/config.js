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
  p500: {
    stages: [
      { duration: '2m', target: 100 },
      { duration: '3m', target: 500 },
      { duration: '5m', target: 500 },
      { duration: '2m', target: 0 },
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

const HIGH_LOAD_PROFILES = new Set(['p500', 'p1000', 'p3000']);

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

export const BASE_URL = normalizeBaseUrl(__ENV.BASE_URL);
export const PROFILE = String(__ENV.PROFILE || 'smoke').trim();
export const SCENARIO = String(__ENV.SCENARIO || 'mixed').trim();

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
  'http_req_duration{route:teacher_overview}': ['p(95)<1000', 'p(99)<2000'],
  'http_req_duration{route:teacher_todos}': ['p(95)<1000', 'p(99)<2000'],
};

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
    http_req_duration: ['p(95)<1000', 'p(99)<2000'],
    ...routeThresholds,
  },
  userAgent: 'Yueke-Capacity-Gate/1.0',
  noConnectionReuse: false,
};
