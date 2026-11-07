/**
 * =====================================================================
 * 就业模块的接口封装
 * =====================================================================
 * 对应后端：API/emp_api.py  (router03, 前缀 /employment)
 * =====================================================================
 */
import { del, get, post, put } from '@/api/http'
import type {
  Employment,
  EmploymentCreate,
  EmploymentSearch,
  EmploymentUpdate,
  Student,
} from '@/types/models'

/**
 * 新增就业信息。
 *
 * 后端这个接口的请求体里不含 stu_name 等学生基本信息 ——
 * 它用 stu_id 去关联学生表，前端只需要传这几项。
 */
export function createEmployment(payload: EmploymentCreate) {
  return post<Employment>('/employment/create', payload)
}

/**
 * 按条件查询就业信息。
 *
 * 注意：查不到时后端返回的是空数组 []（正常状态，不是错误），
 * 所以这里不需要特殊处理。
 */
export function searchEmployment(params: EmploymentSearch) {
  // 把值为 undefined / 空字符串的参数去掉，避免后端收到 "stu_name=" 这种空条件
  const clean: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      clean[key] = value
    }
  }
  return get<Employment[]>('/employment/search', clean)
}

/**
 * 分页查询就业信息。
 *
 * 后端分页返回的是 {total, page, size, total_pages, items}，
 * normalize() 已经把它拆好了，items 变成 data。
 *
 * sort：可选，格式 '字段:方向'，多段逗号分隔，如 'salary:desc,stu_id:asc'。
 * 这一页是【真服务端分页】，所以排序也必须交给后端做 ——
 * 只在前端排的话，排的只是当前这一页，翻页之后顺序就断了。
 */
export function fetchEmploymentPage(params: { page: number; size: number; sort?: string }) {
  return get<Employment[]>('/employment/page', params)
}

/**
 * 查询当前未就业的学生。
 *
 * 后端 Dao/emp_dao.py 的 get_unemployed_students() 返回的是标准形状：
 *   {"code": 200, "message": "查询成功", "total": N, "Data": [...]}
 * 适配层（http.ts 的 normalize）已经统一拆过包，
 * 所以这里拿到的 res.data 就是学生数组，res.total 是人数。
 *
 * 附带信息：Data 里的每一行还多带 class_name / agent_name 两个字段
 * （学生表接口没有这两个），做看板时可以直接用，
 * 新增就业信息时的"学号"下拉也用它。
 */
export function fetchUnemployed() {
  return get<Student[]>('/employment/unemployed')
}

/** 修改就业信息 */
export function updateEmployment(stu_id: number, payload: EmploymentUpdate) {
  return put<Employment>(`/employment/put/${stu_id}`, payload)
}

/** 删除就业信息（软删除） */
export function deleteEmployment(stu_id: number) {
  return del<null>(`/employment/delete/${stu_id}`)
}
