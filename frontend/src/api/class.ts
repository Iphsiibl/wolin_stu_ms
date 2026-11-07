/**
 * =====================================================================
 * 班级 + 班主任模块的接口封装
 * =====================================================================
 * 对应后端：API/class_api.py        (router04, 前缀 /class)
 *           API/class_teacher_api.py (router08, 前缀 /class_teacher)
 *
 * 【这个模块的特殊之处】
 * 后端返回的字段名是中文的：
 *   {"班级id": 1, "班级名字": "软件工程1班", "开课时间": "2022-09-01", ...}
 *
 * 其他 5 个模块都是英文 key，只有这个模块是中文 ——
 * 后端 class_api.py 的注释里也写了"这里保持原样，不改成别的模块那种格式"。
 *
 * 解决办法：在这个文件里把中文 key 转成英文，
 * 视图层统一用 class_id / class_name / start_date，
 * 不让中文 key 扩散到界面代码里。
 *
 * 【班主任的接口在 2026-11-03 换了路由】
 * 原来班主任是挂在 /class 下面的（/class/all_class_teacher 等），
 * 后端把它们拆到了独立的 router08，前缀变成 /class_teacher：
 *   GET    /class_teacher/all_class_teacher
 *   GET    /class_teacher/get_class_teacher/{id}
 *   POST   /class_teacher/class_teacher
 *   PUT    /class_teacher/update_class_teacher/{id}
 *   DELETE /class_teacher/delete_class_teacher/{id}
 * 旧的 /class/* 那几条已经 404，别再用了。
 * 返回字段名没变（还是「班主任id / 班主任名字 / 班主任性别」），
 * 所以下面的 toClassTeacher 映射不用动。
 * =====================================================================
 */
import { del, get, post, put } from '@/api/http'
import type { ClassInfo, ClassTeacher, Student } from '@/types/models'
import { toClassInfo, toClassTeacher, type RawClass, type RawClassTeacher } from '@/utils/mappers'

export type { ClassInfo, ClassTeacher, RawClass, RawClassTeacher }

/* ---------------------------------------------------------------------
 * 班级
 * ------------------------------------------------------------------ */

/** 查询所有班级 */
export async function fetchAllClasses() {
  const res = await get<RawClass[]>('/class/all_class')
  return {
    ...res,
    data: (res.data ?? []).map(toClassInfo),
  }
}

/** 按 id 查询单个班级 */
export async function fetchClass(stu_class_id: number) {
  const res = await get<RawClass>('/class/get_class/' + stu_class_id)
  return { ...res, data: toClassInfo(res.data ?? {}) }
}

/** 新建班级 */
export function createClass(payload: {
  class_name: string
  start_date: string
  class_teacher_id: number
  teacher_id: number
}) {
  return post<ClassInfo>('/class/', payload)
}

/** 修改班级 */
export function updateClass(stu_class_id: number, payload: Record<string, unknown>) {
  return put<ClassInfo>('/class/update_class/' + stu_class_id, payload)
}

/** 删除班级（连带软删除班级下的学员） */
export function deleteClass(stu_class_id: number) {
  return del<null>('/class/delete_class/' + stu_class_id)
}

/* ---------------------------------------------------------------------
 * 班主任（后端 2026-11-03 拆到独立路由 /class_teacher）
 * ------------------------------------------------------------------ */

/** 查询所有班主任 */
export async function fetchAllClassTeachers() {
  const res = await get<RawClassTeacher[]>('/class_teacher/all_class_teacher')
  return {
    ...res,
    data: (res.data ?? []).map(toClassTeacher),
  }
}

/** 按 id 查询单个班主任 */
export async function fetchClassTeacher(class_teacher_id: number) {
  const res = await get<RawClassTeacher>('/class_teacher/get_class_teacher/' + class_teacher_id)
  return { ...res, data: toClassTeacher(res.data ?? {}) }
}

/** 新增班主任 */
export function createClassTeacher(payload: {
  class_teacher_name: string
  class_teacher_sex?: string
  stu_class_id?: number
}) {
  return post<ClassTeacher>('/class_teacher/class_teacher', payload)
}

/** 修改班主任 */
export function updateClassTeacher(
  class_teacher_id: number,
  payload: Record<string, unknown>,
) {
  return put<ClassTeacher>('/class_teacher/update_class_teacher/' + class_teacher_id, payload)
}

/** 删除班主任 */
export function deleteClassTeacher(class_teacher_id: number) {
  return del<null>('/class_teacher/delete_class_teacher/' + class_teacher_id)
}

/* ---------------------------------------------------------------------
 * 班级学员（后端 2026-11-03 新增）
 * ------------------------------------------------------------------ */

/**
 * 查询某个班级下的全部学员。
 *
 * 这个接口是后端新加的（2026-11-03），返回的 key 是英文的
 * （和别的模块一样），不用做中文转换，直接透传。
 * 注意 agent_name 可能为 null —— 不是每个学员都有顾问。
 */
export async function fetchClassStudents(stu_class_id: number) {
  const res = await get<Student[]>('/class/get_class/' + stu_class_id + '/students')
  return { ...res, data: res.data ?? [] }
}
