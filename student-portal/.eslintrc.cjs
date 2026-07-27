module.exports = {
  root: true,
  // 设计交付稿不是 Vite 生产源码；保留原文件作为参考，但不得混入 src lint/build 结论。
  ignorePatterns: ['dist/', 'node_modules/', '*.min.js', '学生PC门户设计/'],
  env: { browser: true, es2022: true, node: true },
  parserOptions: { ecmaVersion: 2022, sourceType: 'module' },
  extends: ['eslint:recommended', 'plugin:vue/vue3-essential'],
  rules: {
    'vue/multi-word-component-names': 'off',
    'no-unused-vars': 'warn'
  }
}
