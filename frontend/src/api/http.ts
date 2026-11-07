/**
 * =====================================================================
 * Axios 实例 + 响应适配层
 * =====================================================================
 * 【这一层解决什么问题】
 *
 * 后端 6 个模块的返回格式并不统一，是历史遗留：
 *
 *   1. {code, message, total, Data}      学生 / 就业（列表）
 *   2. {code, message, Data}              学生（单条）
 *   3. {code, message}                    删除类操作
 *   4. {msg, detail}                      成绩模块
 *   5. {total, page, size, total_pages, items}   就业分页
 *   6. {total, result}                    未就业学生
 *   7. 裸数组                              班级 / 老师 / 统计
 *
 * 如果业务代码直接处理这 7 种形状，每个页面都要写一堆 if-else，
 * 而且后端改一次格式前端就得全改一遍。
 *
 * 所以在【响应拦截器】里统一拆包，业务层永远只看到：
 *
 *      { code, message, data, total }
 *
 * 后端要改格式？只需要改这一个文件。
 * =====================================================================
 */
import axios, {
  type AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
} from 'axios'
import { ElMessage } from 'element-plus'

import type { ApiErrorBody, ApiResult, ValidationErrorItem } from '@/types/common'
import { logHttpError, logHttpRequest, logHttpResponse } from '@/utils/logger'

/** 后端地址前缀。开发环境走 Vite 代理（见 vite.config.ts），所以是 /api */
const BASE_URL = import.meta.env.VITE_API_BASE || '/api'

/** 请求超时时间（毫秒） */
const TIMEOUT = 15000

/* ---------------------------------------------------------------------
 * 错误信息中文化
 * ------------------------------------------------------------------ */

/** 后端字段名 -> 中文标签，用于把 422 的 loc 变成人能看懂的提示 */
const FIELD_LABELS: Record<string, string> = {
  stu_name: '学生姓名',
  stu_age: '年龄',
  stu_sex: '性别',
  stu_class_id: '班级',
  stu_tel: '手机号',
  stu_from: '生源地',
  stu_school: '毕业院校',
  stu_major: '专业',
  enroll_date: '入学时间',
  gra_date: '毕业时间',
  edu_bg: '学历',
  agent_name: '顾问姓名',
  agent_sex: '顾问性别',
  agent_age: '顾问年龄',
  teacher_name: '老师姓名',
  teacher_tel: '老师电话',
  teacher_job: '职位',
  class_name: '班级名称',
  start_date: '开课时间',
  company: '公司',
  salary: '薪资',
  open_date: '简历开放时间',
  offer_date: 'Offer 时间',
  stu_id: '学号',
  test_id: '考试次序',
  score: '分数',
}

/** Pydantic 的 msg 字段 -> 中文 */
function translatePydanticMsg(msg: string): string {
  /**
   * 注意：这里必须用【捕获组】取数字。
   * Pydantic 的 msg 形如 "Input should be greater than 18"，
   * 数字在句尾，所以要用 /(\d+)/ 把数字抓出来 —— 不能用 msg.replace(...)
   * 也不能假设 m[1] 一定存在（正则写错就会得到 undefined）。
   */
  const rules: [RegExp, (m: RegExpExecArray) => string][] = [
    [/^Input should be a valid integer/, () => '必须是整数'],
    [/^Input should be a valid number/, () => '必须是数字'],
    [/^Input should be a valid string/, () => '必须是字符串'],
    [/^Input should be a valid date/, () => '必须是合法日期'],
    [/^Input should be a valid email/, () => '必须是合法邮箱'],
    [/^String should have at least (\d+) characters?$/, (m) => `长度至少 ${m[1]} 个字符`],
    [/^String should have at most (\d+) characters?$/, (m) => `长度最多 ${m[1]} 个字符`],
    [/^Input should be greater than or equal to (\d+)$/, (m) => `必须大于等于 ${m[1]}`],
    [/^Input should be greater than (\d+)$/, (m) => `必须大于 ${m[1]}`],
    [/^Input should be less than or equal to (\d+)$/, (m) => `必须小于等于 ${m[1]}`],
    [/^Input should be less than (\d+)$/, (m) => `必须小于 ${m[1]}`],
    [/^String should match pattern/, () => '格式不正确'],
    [/^Field required/, () => '不能为空'],
  ]

  for (const [re, build] of rules) {
    const m = msg.match(re)
    if (m) return build(m as RegExpExecArray)
  }
  return msg
}

/**
 * 把 FastAPI 的 422 校验错误数组转成一句人话。
 *
 * 输入：
 *   [{loc: ["body", "stu_age"], msg: "Input should be greater than 18"}]
 * 输出：
 *   "年龄：必须大于 18"
 */
function formatValidationErrors(items: ValidationErrorItem[]): string {
  return items
    .map((item) => {
      // loc 形如 ["body", "stu_age"]，第一个是来源（body/query），后面才是字段名
      const fieldPath = (item.loc ?? []).slice(1).join('.')
      const label = FIELD_LABELS[fieldPath] ?? fieldPath
      const msg = translatePydanticMsg(item.msg ?? '参数不合法')
      return label ? `${label}：${msg}` : msg
    })
    .join('；')
}

/**
 * 从错误响应体里提取一句可展示给用户的中文错误信息。
 */
export function extractErrorMessage(status: number, body: unknown): string {
  const detail = (body as ApiErrorBody | undefined)?.detail

  // 422：参数校验失败，detail 是数组
  if (Array.isArray(detail)) {
    return formatValidationErrors(detail)
  }

  // 其他 HTTPException：detail 是字符串
  if (typeof detail === 'string') {
    return detail
  }

  // 兜底
  const fallback: Record<number, string> = {
    400: '请求参数有误',
    401: '未登录或登录已过期',
    403: '没有访问权限',
    404: '请求的资源不存在',
    405: '请求方法不被支持',
    409: '数据冲突（可能已存在）',
    422: '提交的数据不符合要求',
    500: '服务器内部错误',
    503: '服务暂时不可用',
  }
  return fallback[status] ?? `请求失败（HTTP ${status}）`
}

/* ---------------------------------------------------------------------
 * 响应归一化
 * ------------------------------------------------------------------ */

/**
 * 把后端的 6 种返回格式，统一成 {code, message, data, total}。
 *
 * 这是整个前端最关键的一个函数 —— 业务层只认它的输出。
 */
export function normalize<T = unknown>(body: unknown): ApiResult<T> {
  // ---- 形态 7：裸数组（班级 / 老师 / 统计）----
  if (Array.isArray(body)) {
    return {
      code: 200,
      message: '查询成功',
      data: body as T,
      total: body.length,
    }
  }

  if (body && typeof body === 'object') {
    const raw = body as Record<string, unknown>

    // ---- 形态 4：{msg, detail}（成绩模块）----
    if ('msg' in raw && !('code' in raw)) {
      return {
        code: 200,
        message: String(raw.msg ?? '操作成功'),
        data: (raw.detail ?? null) as T,
        total: 0,
      }
    }

    // ---- 形态 5.5：{total, result}（旧版未就业学生的返回形状）----
    // 后端以前返回 {"total": N, "result": [...]}，
    // 现在已经统一成 {code, message, total, Data}，这个分支留着做兼容。
    // 不特判的话会掉进最后的兜底分支，
    // 业务层拿到的 data 是整个对象而不是数组。
    if ('result' in raw && Array.isArray(raw.result)) {
      return {
        code: 200,
        message: '查询成功',
        data: raw.result as T,
        total: Number(raw.total ?? raw.result.length),
      }
    }

    // ---- 形态 5：{total, page, size, total_pages, items}（就业分页）----
    if ('items' in raw && Array.isArray(raw.items)) {
      return {
        code: 200,
        message: '查询成功',
        data: raw.items as T,
        total: Number(raw.total ?? raw.items.length),
        page: Number(raw.page ?? 1),
        size: Number(raw.size ?? raw.items.length),
        totalPages: Number(raw.total_pages ?? 1),
      }
    }

    // ---- 形态 1/2/3：{code, message, [total], [Data]}（学生 / 就业）----
    if ('code' in raw) {
      // Data 优先，其次 data，最后 null
      const data = ('Data' in raw ? raw.Data : 'data' in raw ? raw.data : null) as T
      const isList = Array.isArray(data)
      return {
        code: Number(raw.code ?? 200),
        message: String(raw.message ?? '操作成功'),
        data,
        // 有 total 用 total；列表但没 total 就用数组长度；单条对象算 1
        total: Number(raw.total ?? (isList ? data.length : data ? 1 : 0)),
      }
    }
  }

  // 兜底：空响应体等奇怪情况
  return {
    code: 200,
    message: '操作成功',
    data: body as T,
    total: 0,
  }
}

/**
 * 请求配置（在 Axios 原生配置上扩展了一个 silent 标记）。
 *
 * silent = true 时，这个请求的失败不会自动弹红色错误提示，
 * 由调用方自己决定怎么提示（比如「查不到已删除记录」这种情况不算错误）。
 */
export type RequestConfig = AxiosRequestConfig & { silent?: boolean }

/**
 * 带计时的请求配置。
 *
 * 请求发出时记下时间戳，响应回来时算差值 —— 面板上就能看到
 * 「哪个接口慢」。这个字段只活在内存里，不进请求体。
 */
type TimedConfig = AxiosRequestConfig & { __stuStartedAt?: number }

/** 把 baseURL 和 url 拼成一条人能读的完整路径 */
function buildUrl(config?: AxiosRequestConfig): string {
  if (!config) return ''
  const base = config.baseURL ?? ''
  const url = config.url ?? ''
  if (base && url.startsWith(base)) return url
  return `${base}${url}`
}

/** 取请求方法 */
function buildMethod(config?: AxiosRequestConfig): string {
  return (config?.method ?? 'get').toUpperCase()
}

/* ---------------------------------------------------------------------
 * Axios 实例
 * ------------------------------------------------------------------ */

const http: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: TIMEOUT,
  headers: { 'Content-Type': 'application/json' },
})

/* 请求拦截器：预留鉴权头位。
   当前后端没有鉴权接口，所以这里什么都不加。
   将来后端加了 token 认证，只要在这里加一行 Authorization 即可，
   业务代码一行都不用改。
   顺带在这里打一个请求日志（含计时起点），面板上能看到接口流水。 */
http.interceptors.request.use((config) => {
  const timed = config as TimedConfig
  timed.__stuStartedAt = Date.now()
  logHttpRequest(buildMethod(config), buildUrl(config))
  return config
})

/* 响应拦截器：成功时归一化，失败时统一弹提示 */
http.interceptors.response.use(
  (response) => {
    // 用适配后的结构替换原始 body，这样调用方拿到的直接就是统一形状
    response.data = normalize(response.data)

    // 记录耗时与后端给的一句业务文案（不记录响应体本身）
    const timed = response.config as TimedConfig | undefined
    const duration = timed?.__stuStartedAt ? Date.now() - timed.__stuStartedAt : 0
    const normalized = response.data as ApiResult<unknown>
    const summary = normalized?.code ? `${normalized.code} ${normalized.message ?? ''}`.trim() : ''
    logHttpResponse(
      buildMethod(response.config),
      buildUrl(response.config),
      response.status,
      duration,
      summary,
    )

    return response
  },
  (error: AxiosError) => {
    const status = error.response?.status ?? 0
    const body = error.response?.data
    const message = extractErrorMessage(status, body)

    // 失败也要进日志：错误码和文案在这里落一句，面板上一眼能看到
    const timed = error.config as TimedConfig | undefined
    const duration = timed?.__stuStartedAt ? Date.now() - timed.__stuStartedAt : 0
    logHttpError(buildMethod(error.config), buildUrl(error.config), status, duration, message)

    // 业务错误统一在这里提示，页面里就不用重复写 try/catch + ElMessage
    // 静默标记：需要页面自己处理错误的请求可以加 { silent: true }
    const silent = (error.config as (AxiosRequestConfig & { silent?: boolean }) | undefined)?.silent
    if (!silent) {
      ElMessage.error(message)
    }

    // 抛一个带 message 的 Error，方便页面 catch 后还能拿到文案
    const wrapped = new Error(message) as Error & { status?: number; body?: unknown }
    wrapped.status = status
    wrapped.body = body
    return Promise.reject(wrapped)
  },
)

/* ---------------------------------------------------------------------
 * 对外的调用封装
 * ------------------------------------------------------------------ */

/**
 * 发一个 GET 请求，返回归一化后的结果。
 *
 * 用法：
 *   const res = await request.get<Student[]>('/student/select_stu_skip?skip=0&limit=100')
 *   res.data  // Student[]
 *   res.total // 总条数
 */
export async function get<T = unknown>(
  url: string,
  params?: Record<string, unknown>,
  config?: RequestConfig,
): Promise<ApiResult<T>> {
  const res = await http.get<ApiResult<T>>(url, { params, ...config })
  return res.data
}

/** 发一个 POST 请求 */
export async function post<T = unknown>(
  url: string,
  data?: unknown,
  config?: RequestConfig,
): Promise<ApiResult<T>> {
  const res = await http.post<ApiResult<T>>(url, data, config)
  return res.data
}

/** 发一个 PUT 请求 */
export async function put<T = unknown>(
  url: string,
  data?: unknown,
  config?: RequestConfig,
): Promise<ApiResult<T>> {
  const res = await http.put<ApiResult<T>>(url, data, config)
  return res.data
}

/** 发一个 DELETE 请求 */
export async function del<T = unknown>(
  url: string,
  config?: RequestConfig,
): Promise<ApiResult<T>> {
  const res = await http.delete<ApiResult<T>>(url, config)
  return res.data
}

export default http
