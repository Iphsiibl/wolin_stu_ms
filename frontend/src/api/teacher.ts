/**
 * =====================================================================
 * 老师模块的接口封装
 * =====================================================================
 * 对应后端：API/teacher_api.py  (router05, 前缀 /teacher)
 *
 * 注意：列表接口的后端路径是 /teacher/ （带斜杠），
 * 而查询单个是 /teacher/{id} —— 不带斜杠会被 FastAPI 路由到 {id} 上当成 id="teacher"。
 * =====================================================================
 */
import { del, get, post, put } from '@/api/http'
import type { Teacher, TeacherCreate, TeacherUpdate } from '@/types/models'

/** 查询所有老师 */
export function fetchAllTeachers() {
  return get<Teacher[]>('/teacher/')
}

/** 按 id 查询单个老师 */
export function fetchTeacher(teacher_id: number) {
  return get<Teacher>('/teacher/' + teacher_id)
}

/** 新增老师 */
export function createTeacher(payload: TeacherCreate) {
  return post<Teacher>('/teacher/', payload)
}

/** 修改老师 */
export function updateTeacher(teacher_id: number, payload: TeacherUpdate) {
  return put<Teacher>('/teacher/' + teacher_id, payload)
}

/** 删除老师（软删除） */
export function deleteTeacher(teacher_id: number) {
  return del<null>('/teacher/' + teacher_id)
}
