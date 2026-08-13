#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const root = process.cwd();
const required = [
  'backend/scripts/seed_internship_capacity.py',
  'backend/tests/test_internship_capacity_seed_contract.py',
  'performance/k6/internship.js',
  'performance/tools/seed_internship_capacity_env.py',
  '.github/workflows/internship-capacity-fixture.yml',
];
const failures = [];
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
for (const file of required) {
  if (!fs.existsSync(path.join(root, file))) failures.push(`missing ${file}`);
}

if (failures.length === 0) {
  const seed = read(required[0]);
  const test = read(required[1]);
  const k6 = read(required[2]);
  const tokens = read(required[3]);
  const workflow = read(required[4]);

  for (const contract of [
    'default=20_000',
    'default=8_000',
    'default=5',
    'default=180',
    'default=26',
    'default=10',
    'default=12',
    'default=0.03',
    'settings.is_prod',
    'engine.dialect.name != "mysql"',
    '--cleanup',
    '--replace',
    'seedDurationSeconds',
    'capacity tenant already exists; use --replace or --cleanup',
    '"current_stage": "INTERN" if active else "ENROLLED"',
  ]) {
    if (!seed.includes(contract)) failures.push(`fixture generator missing contract ${contract}`);
  }
  for (const model of [
    'StudentProfile', 'InternshipBatch', 'InternshipRecord', 'InternshipCheckin',
    'WeeklyReport', 'InternshipGuidance', 'InternshipBatchPlan',
    'InternshipPlanTaskProgress', 'InternshipProcessReport', 'RiskRecord',
    'AttendanceException',
  ]) {
    if (!seed.includes(model)) failures.push(`fixture generator missing scale table ${model}`);
  }
  if (!test.includes('1_440_000') || !test.includes('208_000') || !test.includes('48_000')) {
    failures.push('seed contract test must lock D20K/D8K row-plan magnitudes');
  }

  for (const endpoint of [
    '/api/v1/internship/dashboard',
    '/api/v1/internship/intern-students',
    '/api/v1/internship/reports',
    '/api/v1/internship/guidances',
    '/api/v1/internship/risks',
    '/api/v1/mobile/teacher/internship/context',
    '/api/v1/mobile/internship/context/my',
    '/api/v1/mobile/internship/context/plan/tasks',
  ]) {
    if (!k6.includes(endpoint)) failures.push(`internship workload missing endpoint ${endpoint}`);
  }
  if (!k6.includes('INTERNSHIP_BATCH_ID is required')) failures.push('internship workload must fail closed without batch id');
  if (!k6.includes("domain: 'internship'")) failures.push('internship workload requests must be explicitly tagged');
  if (!k6.includes('LOCAL_HIGH_LOAD_DIAGNOSTIC')) failures.push('internship workload must preserve local diagnostic latency semantics');
  for (const forbidden of [/\/upload/i, /\/download/i, /file-center/i, /attachments?/i, /\bcos\b/i]) {
    if (forbidden.test(k6)) failures.push(`internship k6 must not exercise file traffic: ${forbidden}`);
  }

  if (!tokens.includes('CAP-INT-{index:05d}') && !tokens.includes('CAP-INT-${index')) {
    failures.push('student capacity tokens must map to unique generated student numbers');
  }
  if (!tokens.includes('min(active, 3000)')) failures.push('token issuer must cap pool to fixture population and p3000');
  if (/print\([^\n]*(token|Bearer)/i.test(tokens)) failures.push('token issuer must not print token material');

  for (const workflowContract of [
    'mysql:8.0',
    'redis:7-alpine',
    'alembic upgrade head',
    'seed_internship_capacity.py',
    '--students 500',
    '--active-interns 200',
    'seed_internship_capacity_env.py',
    'grafana/k6:0.54.0',
    'performance/k6/internship.js',
    'internship-fixture-smoke-${{ github.run_id }}',
  ]) {
    if (!workflow.includes(workflowContract)) failures.push(`workflow missing contract ${workflowContract}`);
  }
}

if (failures.length) {
  console.error('Internship capacity fixture contract failed:');
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}
console.log('Internship capacity fixture contract passed');
