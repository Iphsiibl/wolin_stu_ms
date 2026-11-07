/**
 * =====================================================================
 * 登录态管理（Pinia）
 * =====================================================================
 * 【重要说明：这是纯前端模拟登录】
 *
 * 你的后端目前【没有任何登录/鉴权接口】
 * （已确认：无 OAuth、无 token 依赖、无 Authorization 处理），
 * 所以这里不做真正的身份验证 —— 它只负责：
 *
 *   1. 记住"当前用户"（存在 localStorage）
 *   2. 路由守卫判断"登录了没"，没登录就跳登录页
 *
 * 也就是说，它挡的是"没登录的用户直接敲 URL 进主界面"，
 * 挡不住"直接调后端接口"。真正的鉴权必须后端来做。
 *
 * 将来后端加了 token 认证，改造点只有两个：
 *   - 这里 login() 改成调后端接口、存 token
 *   - api/http.ts 的请求拦截器里加 Authorization 头
 * 业务代码一行都不用动。
 * =====================================================================
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

/** 模拟登录的用户信息 */
export interface LoginUser {
  username: string
  displayName: string
  role: string
  /** 登录时间戳 */
  loginAt: number
}

/** localStorage 的键名 */
const STORAGE_KEY = 'stu_ms_user'

/** 默认的模拟账号（随便填都能登录） */
const DEFAULT_USER: LoginUser = {
  username: 'admin',
  displayName: '系统管理员',
  role: '管理员',
  loginAt: 0,
}

export const useUserStore = defineStore('user', () => {
  /** 当前登录用户，null 表示未登录 */
  const user = ref<LoginUser | null>(readFromStorage())

  /** 侧边栏是否折叠 */
  const sidebarCollapsed = ref(false)

  /** 从 localStorage 读回登录态 */
  function readFromStorage(): LoginUser | null {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return null
      return JSON.parse(raw) as LoginUser
    } catch {
      // localStorage 里的数据坏了就当没登录，重新登录即可
      return null
    }
  }

  /** 是否已登录 */
  function isLoggedIn(): boolean {
    return user.value !== null
  }

  /**
   * 模拟登录。
   *
   * 因为后端没有鉴权接口，这里【不做任何密码校验】，
   * 任何用户名密码都能进。这是"演示模式"的已知限制，
   * 等后端补上登录接口后，替换这个函数即可。
   */
  function login(username: string, password: string) {
    if (!username || !password) {
      throw new Error('请输入用户名和密码')
    }
    const next: LoginUser = {
      username,
      displayName: username === 'admin' ? DEFAULT_USER.displayName : username,
      role: username === 'admin' ? DEFAULT_USER.role : '普通用户',
      loginAt: Date.now(),
    }
    user.value = next
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    return next
  }

  /** 退出登录 */
  function logout() {
    user.value = null
    localStorage.removeItem(STORAGE_KEY)
  }

  /** 切换侧边栏折叠状态 */
  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  return {
    user,
    sidebarCollapsed,
    isLoggedIn,
    login,
    logout,
    toggleSidebar,
  }
})
