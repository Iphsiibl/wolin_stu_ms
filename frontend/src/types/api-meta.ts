/**
 * =====================================================================
 * 后端接口元数据（由 scripts/gen-api-meta.mjs 从 /openapi.json 生成）
 * =====================================================================
 * 这份文件是【自动生成】的索引，不要手改 ——
 * 后端改了路由就重新跑一次：node scripts/gen-api-meta.mjs
 *
 * 它的作用是：开发时想知道某个接口的路径/方法/参数，不用去翻后端代码。
 *
 * 真正的请求体类型在 types/models.ts 里手写维护 —— 因为后端有多种
 * 返回格式，openapi 生成的类型反而不如手写直观。
 *
 * 生成时间对应的后端接口总数：51
 */

/** 后端服务信息 */
export const API_INFO = {
  title: '学生管理系统 API',
  version: '1.0.0',
  baseUrl: 'http://127.0.0.1:8003',
  docsUrl: 'http://127.0.0.1:8003/docs',
} as const

/** 后端的路径前缀，与 main.py 的 include_router 一一对应 */
export const API_PREFIX = {
  agent: '/agent',
  class: '/class',
  class_teacher: '/class_teacher',
  employment: '/employment',
  score: '/score',
  stat: '/stat',
  student: '/student',
  teacher: '/teacher',
} as const

/** 各模块的接口清单：方法 + 路径 + 说明 */
export const API_ENDPOINTS = {
  agent: [
    { method: 'POST', path: '/agent/add_agent', desc: '新增顾问' },
    { method: 'GET', path: '/agent/agent', desc: '查询所有顾问' },
    { method: 'DELETE', path: '/agent/delete_agent', desc: '删除顾问' },
    { method: 'GET', path: '/agent/select_agent', desc: '按id查询单个顾问' },
    { method: 'GET', path: '/agent/select_stu_agent', desc: '按顾问查询学生' },
    { method: 'PUT', path: '/agent/update_agent', desc: '修改顾问' },
  ],
  class: [
    { method: 'POST', path: '/class/', desc: '新建班级' },
    { method: 'GET', path: '/class/all_class', desc: '查询所有班级信息' },
    { method: 'DELETE', path: '/class/delete_class/{stu_class_id}', desc: '删除班级以及班级学员' },
    { method: 'GET', path: '/class/get_class/{stu_class_id}', desc: '查询班级信息' },
    { method: 'GET', path: '/class/get_class/{stu_class_id}/students', desc: '查询班级所有学生信息' },
    { method: 'PUT', path: '/class/update_class/{stu_class_id}', desc: '修改班级信息' },
  ],
  class_teacher: [
    { method: 'GET', path: '/class_teacher/all_class_teacher', desc: '查询所有班主任信息' },
    { method: 'POST', path: '/class_teacher/class_teacher', desc: '新增班主任' },
    { method: 'DELETE', path: '/class_teacher/delete_class_teacher/{class_teacher_id}', desc: '删除班主任' },
    { method: 'GET', path: '/class_teacher/get_class_teacher/{class_teacher_id}', desc: '查询班主任信息' },
    { method: 'PUT', path: '/class_teacher/update_class_teacher/{class_teacher_id}', desc: '修改班主任信息' },
  ],
  employment: [
    { method: 'POST', path: '/employment/create', desc: '添加一条学生的就业信息' },
    { method: 'DELETE', path: '/employment/delete/{stu_id}', desc: '删除用户信息' },
    { method: 'GET', path: '/employment/page', desc: '分页查询就业信息' },
    { method: 'PUT', path: '/employment/put/{stu_id}', desc: '根据学号修改学生的就业信息' },
    { method: 'GET', path: '/employment/search', desc: '依据条件查询就业信息' },
    { method: 'GET', path: '/employment/unemployed', desc: '查询当前未就业的学生信息' },
  ],
  score: [
    { method: 'DELETE', path: '/score/del/stu_id/{stu_id}/test_id/{test_id}', desc: '删除学生的考试成绩' },
    { method: 'GET', path: '/score/get_del', desc: '查询已删除的学生成绩' },
    { method: 'PUT', path: '/score/put', desc: '修改学生考试成绩' },
    { method: 'POST', path: '/score/score', desc: '录入成绩' },
    { method: 'GET', path: '/score/stu_id/{stu_id}', desc: '查询单个学生的考试成绩' },
    { method: 'GET', path: '/score/stu_id/{stu_id}/test_id/{test_id}', desc: '查询单个学生的单一考试序次的考试成绩' },
    { method: 'GET', path: '/score/test_id/{test_id}', desc: '查询单次考试次序的学生成绩' },
    { method: 'GET', path: '/score/test_id1/{test_id}', desc: '查询单次考试次序的学生成绩' },
  ],
  stat: [
    { method: 'GET', path: '/stat/class/statistics', desc: '统计每个班级的人数以及男生女生的人数' },
    { method: 'GET', path: '/stat/emp/avg_duration_by_class', desc: '统计每个班级的平均就业时长（只统计进入就业阶段的学生，也就是有就业开放时间）' },
    { method: 'GET', path: '/stat/emp/duration', desc: '统计每个学生的就业时长（offer下发时间-就业开放时间）' },
    { method: 'GET', path: '/stat/emp/top5_salary', desc: '统计就业薪资最高的前五名学生的姓名，班级和就业时间，就业公司' },
    { method: 'GET', path: '/stat/score/all_above_80', desc: '查询每次考试成绩都在80分以上的学生的编号，姓名和成绩' },
    { method: 'GET', path: '/stat/score/avg_by_class', desc: '统计每次考试每个班级的平均分，按照从高到低排序' },
    { method: 'GET', path: '/stat/score/failed_twice', desc: '查询有两次以上不及格的学生的姓名，班级和不及格成绩' },
    { method: 'GET', path: '/stat/students/over_age', desc: '查询所有超过指定年龄的学员的信息' },
  ],
  student: [
    { method: 'POST', path: '/student/add_stu', desc: '新增学生' },
    { method: 'DELETE', path: '/student/delete_stu', desc: '删除学生' },
    { method: 'GET', path: '/student/select_stu_class', desc: '按班级查询学生' },
    { method: 'GET', path: '/student/select_stu_id', desc: '按照学生id查询' },
    { method: 'GET', path: '/student/select_stu_name', desc: '按姓名查询学生' },
    { method: 'GET', path: '/student/select_stu_skip', desc: '分页查询学生列表' },
    { method: 'PUT', path: '/student/update_stu_class', desc: '更改学生信息' },
  ],
  teacher: [
    { method: 'GET', path: '/teacher/', desc: '查询所有老师' },
    { method: 'POST', path: '/teacher/', desc: '新增老师' },
    { method: 'DELETE', path: '/teacher/{teacher_id}', desc: '删除老师' },
    { method: 'GET', path: '/teacher/{teacher_id}', desc: '根据ID查询单个老师' },
    { method: 'PUT', path: '/teacher/{teacher_id}', desc: '修改老师信息' },
  ],
} as const
