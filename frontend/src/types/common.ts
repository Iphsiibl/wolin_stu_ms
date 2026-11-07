/**
 * =====================================================================
 * 统一响应类型
 * =====================================================================
 * 后端一共有 6 种不同的返回格式（这是历史原因，不是设计）。
 * 本文件定义前端【统一之后】的形状 —— 所有业务代码只认这一种。
 */

/** 归一化之后的统一响应体 */
export interface ApiResult<T = unknown> {
  /** 业务状态码。后端统一用 200 表示成功 */
  code: number
  /** 提示文案，可直接展示给用户 */
  message: string
  /** 真正的业务数据 */
  data: T
  /** 总条数（列表接口才有） */
  total: number
  /** 当前页码（分页接口才有） */
  page?: number
  /** 每页条数（分页接口才有） */
  size?: number
  /** 总页数（分页接口才有） */
  totalPages?: number
}

/** 后端 HTTPException 的错误体：{"detail": "..."} */
export interface ApiErrorBody {
  detail?: string | ValidationErrorItem[]
}

/** FastAPI 422 参数校验错误的明细 */
export interface ValidationErrorItem {
  type?: string
  loc?: (string | number)[]
  msg?: string
  input?: unknown
}
