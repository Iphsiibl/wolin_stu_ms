/**
 * =====================================================================
 * 学生 + 顾问模块的接口封装
 * =====================================================================
 * 对应后端：
 *   API/stu_info_api.py  router01 -> 前缀 /student
 *   API/stu_info_api.py  router07 -> 前缀 /agent   （顾问已独立成模块）
 *
 * 【后端 2026-11 调整过的三处，务必注意】
 *
 * 1. 顾问模块被拆出去了
 *    原来顾问的接口挂在 /student/* 下面，现在换成了 /agent/*：
 *        /student/agent        ->  /agent/agent
 *        /student/select_agent ->  /agent/select_agent
 *        /student/add_agent    ->  /agent/add_agent
 *        /student/update_agent ->  /agent/update_agent
 *        /student/delete_agent ->  /agent/delete_agent
 *        /student/select_stu_agent -> /agent/select_stu_agent
 *
 * 2. agent_id 改成了【query 参数】
 *    后端签名是 def update_agent_api(agent_id: int, agent_data: UpdateAgent)
 *    —— agent_id 没有 Body() 标注，FastAPI 就当成 query 参数收，
 *    放在 body 里会直接 422。
 *
 * 3. /student/select_all 被删了
 *    现在只有 /student/select_stu_skip（skip/limit 分页）。
 *    所以「查全部学生」= skip=0 + limit 给个大数。
 *
 * 另外：update_stu_class 的 stu_id 同样是 query 参数
 *    （def update_stu_info_api(stu_id: int, stu_info: UpdateStudent)），
 *    放在 body 里会 422：{"detail":[{"loc":["query","stu_id"], ...}]}
 * =====================================================================
 */
import { del, get, post, put } from '@/api/http'
import type {
  Agent,
  AgentCreate,
  AgentUpdate,
  Student,
  StudentCreate,
  StudentUpdate,
} from '@/types/models'

/** 一次拉取全部学生时用的 limit（后端 limit 没有上限，学生量级远小于这个数） */
const ALL_STUDENTS_LIMIT = 5000

/* ---------------------------------------------------------------------
 * 学生
 * ------------------------------------------------------------------ */

/**
 * 查询全部学生。
 *
 * 后端原本的 /student/select_all 已经删掉了，现在只能走分页接口
 * /student/select_stu_skip（skip=0 表示从头取）。
 * 注意这个接口返回的 total 是【本页条数】，不是总人数 ——
 * 总人数要自己拿 data.length。
 */
export async function fetchAllStudents() {
  const res = await get<Student[]>('/student/select_stu_skip', {
    skip: 0,
    limit: ALL_STUDENTS_LIMIT,
  })
  const list = res.data ?? []
  return { ...res, data: list, total: list.length }
}

/**
 * 分页查询学生。
 *
 * 注意后端用的是 skip/limit，不是 page/size：
 *   skip  = 跳过几条（第几页从 0 开始数）
 *   limit = 最多返回几条
 */
export function fetchStudentPage(params: { skip: number; limit: number }) {
  return get<Student[]>('/student/select_stu_skip', params)
}

/** 按学号查询单个学生 */
export function fetchStudentById(stu_id: number) {
  return get<Student>('/student/select_stu_id', { stu_id })
}

/**
 * 按姓名查询学生（可能返回多个）。
 *
 * 查不到时后端返回 404「没有匹配学生姓名」——
 * 这是正常业务状态（不是系统错误），所以加 silent 免得弹红色报错。
 */
export async function fetchStudentsByName(stu_name: string) {
  const res = await get<Student[]>('/student/select_stu_name', { stu_name }, { silent: true })
  return { ...res, data: res.data ?? [], total: res.data?.length ?? 0 }
}

/** 按班级查询学生 */
export function fetchStudentsByClass(stu_class_id: number) {
  return get<Student[]>('/student/select_stu_class', { stu_class_id })
}

/**
 * 按顾问查询学生。
 *
 * 这个接口后端也挪到了 /agent 路由下（router07）。
 * 顾问名下没有学生时后端返回 404，同样按正常业务状态处理。
 */
export async function fetchStudentsByAgent(agent_id: number) {
  const res = await get<Student[]>('/agent/select_stu_agent', { agent_id }, { silent: true })
  return { ...res, data: res.data ?? [], total: res.data?.length ?? 0 }
}

/** 新增学生 */
export function createStudent(payload: StudentCreate) {
  return post<Student>('/student/add_stu', payload)
}

/**
 * 修改学生信息。
 *
 * 【重要】stu_id 要放在 query 上，不能塞在 body 里。
 * 后端签名：def update_stu_info_api(stu_id: int, stu_info: UpdateStudent)
 * stu_id 没标 Body()，FastAPI 收的是 query 参数。
 *
 * body 用 UpdateStudent（所有字段可选），配合 exclude_unset
 * 实现「只改传了的字段」。
 */
export function updateStudent(stu_id: number, payload: StudentUpdate) {
  return put<Student>('/student/update_stu_class', payload, { params: { stu_id } })
}

/** 删除学生（后端是软删除，is_del 置 1） */
export function deleteStudent(stu_id: number) {
  return del<null>('/student/delete_stu', { params: { stu_id } })
}

/* ---------------------------------------------------------------------
 * 顾问（后端独立成 /agent 路由）
 * ------------------------------------------------------------------ */

/** 查询所有顾问 */
export function fetchAllAgents() {
  return get<Agent[]>('/agent/agent')
}

/** 按 id 查询单个顾问 */
export function fetchAgentById(agent_id: number) {
  return get<Agent>('/agent/select_agent', { agent_id })
}

/** 新增顾问 */
export function createAgent(payload: AgentCreate) {
  return post<Agent>('/agent/add_agent', payload)
}

/**
 * 修改顾问。
 *
 * agent_id 走 query 参数（见文件头说明 2）。
 */
export function updateAgent(agent_id: number, payload: AgentUpdate) {
  return put<Agent>('/agent/update_agent', payload, { params: { agent_id } })
}

/**
 * 删除顾问。
 *
 * agent_id 同样走 query 参数。
 */
export function deleteAgent(agent_id: number) {
  return del<null>('/agent/delete_agent', { params: { agent_id } })
}
