module.exports = {
  root: true,
  ignorePatterns: ['dist/', 'node_modules/'],
  env: { browser: true, es2022: true, node: true },
  parserOptions: { ecmaVersion: 2022, sourceType: 'module' },
  extends: ['eslint:recommended', 'plugin:vue/vue3-essential'],
  rules: {
    'no-alert': 'error',
    'vue/multi-word-component-names': 'off',
    'no-unused-vars': 'warn'
  }
}
