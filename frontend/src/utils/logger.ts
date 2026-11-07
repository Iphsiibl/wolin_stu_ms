/**
 * =====================================================================
 * 前端可观测日志（Frontend Observability Log）
 * =====================================================================
 * 【它解决什么问题】
 *
 * 系统跑起来之后，问题往往表现在「某个按钮点了没反应」「列表是空的」
 * 「接口报错了但不知道是哪一条」。以前这些线索只落在两个地方：
 *
 *   1. 浏览器的 F12 控制台 —— 刷新一次就没了，又不是每个人都会开
 *   2. 后端的 stdout —— 得 SSH 上服务器才看得到
 *
 * 所以这里把「运行痕迹」搬进前端，做成顶栏随时能翻开的「运行日志」册页。
 *
 * 【采集范围】（全部在浏览器里完成，不碰后端）
 *
 *   console  控制台的 log / info / warn / error / debug
 *   http     axios 的请求、响应、失败（方法 / URL / 状态码 / 耗时 / 业务文案）
 *   runtime  未捕获异常 window.onerror、未处理的 Promise 拒绝 unhandledrejection
 *
 * 【安全约束】
 *
 *   不记录请求体 —— 登录接口的 body 里带密码，落进日志就是明文泄露。
 *   只记录 method + url + 状态码 + 业务 code/message。
 *   参数里的值也只记「有几个」，不记「是什么」。
 *
 * 【性能约束】
 *
 *   环形缓冲，最多留 500 条，超出的从最旧的一头丢。
 *   写日志本身绝不允许抛异常 —— 一个日志系统把页面搞崩是最蠢的失败。
 * =====================================================================
 */

/* ---------------------------------------------------------------------
 * 类型
 * ------------------------------------------------------------------ */

/** 日志级别 */
export type LogLevel = 'debug' | 'info' | 'warn' | 'error' | 'http'

/** 日志来源 */
export type LogSource = 'console' | 'http' | 'runtime'

/** 一条日志 */
export interface LogEntry {
  /** 自增序号，当作 Vue 的 key */
  id: number
  /** 时间戳，形如 09:41:07.382 */
  time: string
  /** 级别 */
  level: LogLevel
  /** 来源 */
  source: LogSource
  /** 主文案 */
  message: string
  /** 补充信息（堆栈、耗时、业务文案……） */
  detail?: string
}

/** 订阅者：日志变化时被回调 */
export type LogListener = (entries: LogEntry[]) => void

/* ---------------------------------------------------------------------
 * 常量与展示文案
 * ------------------------------------------------------------------ */

/** 环形缓冲容量 */
export const MAX_LOGS = 500

/** 级别筛选条的顺序（从重到轻） */
export const LOG_LEVELS: LogLevel[] = ['error', 'warn', 'http', 'info', 'debug']

/** 级别的中文名 */
export const LEVEL_LABELS: Record<LogLevel, string> = {
  error: '错误',
  warn: '警告',
  http: '请求',
  info: '信息',
  debug: '调试',
}

/** 来源的中文名 */
export const SOURCE_LABELS: Record<LogSource, string> = {
  console: '控制台',
  http: '接口',
  runtime: '运行时',
}

/* ---------------------------------------------------------------------
 * 存储
 * ------------------------------------------------------------------ */

/** 日志缓冲，最新的在第 0 位 */
const entries: LogEntry[] = []

/** 订阅者集合 */
const listeners = new Set<LogListener>()

/** 自增序号 */
let seq = 0

/** 是否已经打过 console 补丁（防止重复安装） */
let consolePatched = false

/** 当前活跃的 http 请求数（面板上显示一个「请求中」指示） */
let pendingRequests = 0

/** 格式化成 HH:MM:SS.mmm */
function formatTime(date: Date): string {
  const pad = (n: number, width = 2) => String(n).padStart(width, '0')
  return (
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}` +
    `.${pad(date.getMilliseconds(), 3)}`
  )
}

/** 通知所有订阅者 */
function notify() {
  const snapshot = entries.slice()
  listeners.forEach((listener) => {
    try {
      listener(snapshot)
    } catch {
      // 订阅者自己出错也不能影响日志系统本身
    }
  })
}

/**
 * 把任意值转成一行可读文本。
 *
 * 对象会被 JSON 化，但一定截断 —— 一个 500KB 的响应体塞进日志面板
 * 会让整个面板卡住，日志是用来定位问题的，不是用来存数据的。
 */
export function preview(value: unknown, maxLength = 400): string {
  let text: string
  if (typeof value === 'string') {
    text = value
  } else if (value instanceof Error) {
    text = value.stack || value.message
  } else if (value === null) {
    text = 'null'
  } else if (value === undefined) {
    text = 'undefined'
  } else if (typeof value === 'object') {
    try {
      text = JSON.stringify(value)
    } catch {
      text = '[无法序列化的对象]'
    }
  } else {
    text = String(value)
  }
  if (text === undefined) text = '[未知]'
  return text.length > maxLength ? `${text.slice(0, maxLength)}…（已截断）` : text
}

/** 写一条日志 */
export function pushLog(
  level: LogLevel,
  source: LogSource,
  message: string,
  detail?: string,
): LogEntry {
  const entry: LogEntry = {
    id: ++seq,
    time: formatTime(new Date()),
    level,
    source,
    message,
  }
  if (detail) entry.detail = detail

  entries.unshift(entry)
  if (entries.length > MAX_LOGS) entries.length = MAX_LOGS
  notify()
  return entry
}

/* ---------------------------------------------------------------------
 * 对外 API
 * ------------------------------------------------------------------ */

/** 取全部日志（最新的在前） */
export function getLogs(): LogEntry[] {
  return entries.slice()
}

/** 清空日志 */
export function clearLogs() {
  entries.length = 0
  notify()
}

/** 订阅日志变化，返回取消订阅的函数 */
export function subscribeLogs(listener: LogListener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** 当前进行中的 http 请求数 */
export function getPendingCount(): number {
  return pendingRequests
}

/** 便捷方法：调试 */
export function logDebug(message: string, detail?: string) {
  return pushLog('debug', 'console', message, detail)
}

/** 便捷方法：常规信息 */
export function logInfo(message: string, detail?: string) {
  return pushLog('info', 'console', message, detail)
}

/** 便捷方法：警告 */
export function logWarn(message: string, detail?: string) {
  return pushLog('warn', 'console', message, detail)
}

/** 便捷方法：错误 */
export function logError(message: string, detail?: string) {
  return pushLog('error', 'console', message, detail)
}

/* ---------------------------------------------------------------------
 * HTTP 日志
 * ------------------------------------------------------------------ */

/** 记录一次请求 */
export function logHttpRequest(method: string, url: string) {
  pendingRequests += 1
  pushLog('http', 'http', `${method.toUpperCase()} ${url}`)
}

/**
 * 记录一次响应。
 *
 * 只记状态码、耗时和后端给的一句业务文案 ——
 * 响应体可能有几百 KB，进日志没有意义。
 */
export function logHttpResponse(
  method: string,
  url: string,
  status: number,
  duration: number,
  summary?: string,
) {
  pendingRequests = Math.max(0, pendingRequests - 1)
  const detail = [`${duration}ms`, summary].filter(Boolean).join(' · ')
  pushLog('http', 'http', `${method.toUpperCase()} ${url} → ${status}`, detail)
}

/** 记录一次失败 */
export function logHttpError(
  method: string,
  url: string,
  status: number,
  duration: number,
  message: string,
) {
  pendingRequests = Math.max(0, pendingRequests - 1)
  pushLog(
    'error',
    'http',
    `${method.toUpperCase()} ${url} → ${status || '网络异常'}`,
    `${duration}ms · ${message}`,
  )
}

/* ---------------------------------------------------------------------
 * console 拦截
 * ------------------------------------------------------------------ */

/** 原始 console 的备份，保证拦截之后浏览器控制台依然正常 */
const nativeConsole = {
  log: console.log.bind(console),
  info: console.info.bind(console),
  warn: console.warn.bind(console),
  error: console.error.bind(console),
  debug: (console.debug ?? console.log).bind(console),
}

/** 把 console 的多个参数拼成一行文本 */
function joinArgs(args: unknown[]): string {
  return args
    .map((arg) => preview(arg))
    .join(' ')
    .trim()
}

/**
 * 安装 console 拦截 + 未捕获异常监听。
 *
 * 装上之后：
 *   console.log('x')      → 浏览器控制台照常打印，同时进日志面板
 *   window.onerror        → 进日志面板（error 级）
 *   unhandledrejection    → 进日志面板（error 级）
 */
export function installConsoleLogger() {
  if (consolePatched) return
  consolePatched = true

  const patch = (
    key: 'log' | 'info' | 'warn' | 'error' | 'debug',
    level: LogLevel,
  ) => {
    const original = nativeConsole[key]
    ;(console as unknown as Record<string, unknown>)[key] = (...args: unknown[]) => {
      // 先交给浏览器原生 console，DevTools 里照常能看
      original(...args)
      try {
        pushLog(level, 'console', joinArgs(args))
      } catch {
        // 忽略：日志失败不能影响业务
      }
    }
  }

  patch('log', 'info')
  patch('info', 'info')
  patch('warn', 'warn')
  patch('error', 'error')
  patch('debug', 'debug')

  // 未捕获异常
  window.addEventListener('error', (event) => {
    const error = event.error as Error | undefined
    pushLog('error', 'runtime', event.message || '未捕获异常', error?.stack)
  })

  // 未处理的 Promise 拒绝
  window.addEventListener('unhandledrejection', (event) => {
    const reason = (event as PromiseRejectionEvent).reason
    pushLog('error', 'runtime', '未处理的 Promise 拒绝', preview(reason))
  })
}
