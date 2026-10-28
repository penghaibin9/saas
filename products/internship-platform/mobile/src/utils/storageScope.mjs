// uni-app 会静态转换 API 调用，因此隔离存储键，不替换运行时 API 对象。
export function installStorageScope(scope) {
  globalThis.__IX_H5_STORAGE_PREFIX__ = scope ? `${scope}:` : ''
}

installStorageScope(import.meta.env?.VITE_STORAGE_SCOPE || '')
