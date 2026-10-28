import test from 'node:test'
import assert from 'node:assert/strict'
import { installStorageScope } from '../src/utils/storageScope.mjs'
import { request } from './request-module.mjs'

test('不可替换的原生接口仍能隔离登录、读取和退出的存储键', () => {
  const values=new Map([['gx_token_v1','other-system-token'],['gx_session_v1','other-session']])
  const original=globalThis.uni,scope=globalThis.__IX_H5_STORAGE_PREFIX__
  globalThis.uni=Object.freeze({getStorageSync:key=>values.get(key),setStorageSync:(key,value)=>values.set(key,value),removeStorageSync:key=>values.delete(key)})
  try {
    installStorageScope('internship')
    assert.equal(request.getToken(),'')
    request.setToken('own-token')
    assert.equal(values.get('internship:gx_token_v1'),'own-token')
    assert.equal(request.getToken(),'own-token')
    request.clearTokens()
    assert.equal(request.getToken(),'')
    assert.equal(values.get('gx_token_v1'),'other-system-token')
    assert.equal(values.get('gx_session_v1'),'other-session')
  } finally {globalThis.uni=original;globalThis.__IX_H5_STORAGE_PREFIX__=scope}
})

test('根路径安装继续读取原有存储，不丢失旧会话', () => {
  const original=globalThis.uni,scope=globalThis.__IX_H5_STORAGE_PREFIX__
  globalThis.uni=Object.freeze({getStorageSync:key=>key==='gx_token_v1'?'existing-token':null})
  try {installStorageScope('');assert.equal(request.getToken(),'existing-token')}
  finally {globalThis.uni=original;globalThis.__IX_H5_STORAGE_PREFIX__=scope}
})
