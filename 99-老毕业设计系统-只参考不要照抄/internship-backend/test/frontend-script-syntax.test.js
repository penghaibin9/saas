const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const webRoot = path.resolve(__dirname, '..', '..', 'web');

for (const relative of ['管理平台.html', path.join('m', 'index.html'), '演示UI.html']) {
  test(`${relative} 内联脚本语法有效`, () => {
    const html = fs.readFileSync(path.join(webRoot, relative), 'utf8');
    const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)];
    assert.ok(scripts.length > 0);
    scripts.forEach((match, index) => {
      assert.doesNotThrow(
        () => new vm.Script(match[1], { filename: `${relative}:inline-${index + 1}` }),
        `${relative} 第 ${index + 1} 段脚本应可解析`
      );
    });
  });
}
