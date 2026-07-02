/**
 * 前端类型生成：OpenAPI 组件 schema → TypeScript 接口
 * ───────────────────────────────────────────────────────────
 * 以 openapi/spec.js（与 zod 契约一致）为单一事实源，生成 web/spa 可用的强类型，
 * 实现前后端契约对齐。运行：npm run gen:types
 * 输出：web/spa/src/types/api.ts
 */
const fs = require('fs');
const path = require('path');

const spec = require('../openapi/spec')('');
const schemas = (spec.components && spec.components.schemas) || {};

const refName = (ref) => ref.split('/').pop();

function tsType(s, depth = 0) {
  if (!s) return 'any';
  if (s.$ref) return refName(s.$ref);
  if (s.enum) return s.enum.map((v) => (typeof v === 'string' ? `'${v}'` : v)).join(' | ');
  switch (s.type) {
    case 'string': return 'string';
    case 'integer':
    case 'number': return 'number';
    case 'boolean': return 'boolean';
    case 'array': return `${tsType(s.items, depth)}[]`;
    case 'object': {
      if (!s.properties) return 'Record<string, any>';
      const req = new Set(s.required || []);
      const pad = '  '.repeat(depth + 1);
      const fields = Object.entries(s.properties).map(([k, v]) => {
        const opt = req.has(k) ? '' : '?';
        const nul = v.nullable ? ' | null' : '';
        return `${pad}${k}${opt}: ${tsType(v, depth + 1)}${nul};`;
      }).join('\n');
      return `{\n${fields}\n${'  '.repeat(depth)}}`;
    }
    default: return 'any';
  }
}

let out = `// 本文件由 openapi/spec.js 自动生成，请勿手改。生成：npm run gen:types\n`;
out += `// 与后端 zod 契约一致，用于前端强类型对齐。\n\n`;
out += `export interface ApiResp<T = any> { success: boolean; message?: string; code?: string; data: T; }\n\n`;

for (const [name, s] of Object.entries(schemas)) {
  if (s.enum) { out += `export type ${name} = ${tsType(s)};\n\n`; continue; }
  if (s.type === 'object' || s.properties) { out += `export interface ${name} ${tsType(s)}\n\n`; continue; }
  out += `export type ${name} = ${tsType(s)};\n\n`;
}

const dest = path.join(__dirname, '..', '..', 'web', 'spa', 'src', 'types');
fs.mkdirSync(dest, { recursive: true });
const file = path.join(dest, 'api.ts');
fs.writeFileSync(file, out, 'utf8');
console.log(`✅ 已生成前端类型：${file}（${Object.keys(schemas).length} 个 schema）`);
