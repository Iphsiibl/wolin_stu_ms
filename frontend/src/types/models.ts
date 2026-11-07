/**
 * =====================================================================
 * 业务数据模型（对应后端 model/ 与 schema/）
 * =====================================================================
 * 字段名与后端返回保持一致（除 /class 模块，
 * 那个模块后端返回的是中文 key，我在 api/class.ts 里做了转换）。
 */

/** 性别 */
export type Sex = '男' | '女'

/* ---------------------------------------------------------------------
 * 学生
 * ------------------------------------------------------------------ */

/** 学生信息（后端 _stu_to_dict 的输出） */
export interface Student {
  stu_id: number
  stu_name: string
  stu_age: number
  stu_sex: Sex
  stu_tel: string
  stu_class_id: number
  agent_id: number | null
  agent_name: string | null
  stu_from: string
  stu_school: string
  stu_major: string
  enroll_date: string
  gra_date: string
  edu_bg: string
}

/**
 * 新增学生的请求体（对应 Student_request）
 *
 * 注意 agent_id：后端业务规则要求"每个学生都必须有顾问"，是必填字段。
 * 表单阶段允许为空（用户还没选），提交前由表单校验拦截。
 */
export interface StudentCreate {
  stu_name: string
  stu_age: number
  stu_sex: Sex
  stu_class_id: number
  stu_tel: string
  stu_from: string
  stu_school: string
  stu_major: string
  enroll_date: string
  gra_date: string
  edu_bg?: string
  /** 顾问 id —— 必填，但表单阶段允许 undefined */
  agent_id?: number
}

/** 修改学生的请求体（对应 UpdateStudent，字段全部可选） */
export type StudentUpdate = Partial<StudentCreate>

/* ---------------------------------------------------------------------
 * 顾问
 * ------------------------------------------------------------------ */

export interface Agent {
  agent_id: number
  agent_name: string
  agent_sex: Sex
  agent_age: number
}

export interface AgentCreate {
  agent_name: string
  agent_sex: Sex
  agent_age: number
}

export type AgentUpdate = Partial<AgentCreate>

/* ---------------------------------------------------------------------
 * 成绩
 * ------------------------------------------------------------------ */

/**
 * 单条成绩（后端 _score_to_dict 的输出）
 *
 * stu_name：后端返回的中文 key 是「学生姓名」，
 * 在 utils/mappers.ts 的 toScore 里转成英文字段。
 * 后端 /score/stu_id/* 和 /score/test_id/* 都会带上它，
 * 所以成绩列表不用再查一遍学生表。
 *
 * class_name：班级名，同理由后端 JOIN 班级表带出，
 * 中文 key 是「班级名称」。学生没分班时是空串。
 */
export interface Score {
  stu_id: number
  /** 学生姓名（后端返回，可能为空字符串） */
  stu_name: string
  /** 班级名称（后端返回，可能为空字符串） */
  class_name: string
  test_id: number
  score: number
}

/** 录入成绩的请求体（对应 Score） */
export interface ScoreCreate {
  stu_id: number
  test_id: number
  score: number
}

/* ---------------------------------------------------------------------
 * 就业
 * ------------------------------------------------------------------ */

/** 就业信息 */
export interface Employment {
  stu_id: number
  stu_name: string
  company: string
  salary: number
  open_date: string
  offer_date: string | null
  class_name: string
  stu_major: string
  stu_school: string
  gra_date: string
  edu_bg: string
  stu_sex: Sex
}

/** 就业查询条件（对应 EmpSearch） */
export interface EmploymentSearch {
  stu_id?: number
  stu_name?: string
  company?: string
  salary_min?: number
  salary_max?: number
  stu_class_id?: number
  edu_bg?: string
  stu_major?: string
  stu_sex?: Sex
}

/** 新增就业信息 */
export interface EmploymentCreate {
  stu_id: number
  company: string
  salary: number
  open_date: string
  offer_date?: string | null
}

export type EmploymentUpdate = Partial<EmploymentCreate>

/* ---------------------------------------------------------------------
 * 班级
 * ------------------------------------------------------------------ */

/**
 * 班级信息。
 * 注意：后端 /class/all_class 返回的是中文字段名，
 * 已在 api/class.ts 里转成这里的英文字段。
 *
 * 2026-11-03 起后端会连带返回班主任 / 授课老师的姓名，
 * 有这两个字段时直接显示，不用再拿 id 去老师表反查。
 */
export interface ClassInfo {
  class_id: number
  class_name: string
  start_date: string
  class_teacher_id: number | null
  /** 班主任姓名（后端 /class 接口直接给的，可能为空） */
  class_teacher_name?: string | null
  teacher_id: number | null
  /** 授课老师姓名（后端 /class 接口直接给的，可能为空） */
  teacher_name?: string | null
}

/** 班主任 */
export interface ClassTeacher {
  class_teacher_id: number
  class_teacher_name: string
  /** 性别。后端返回中文 key「班主任性别」，在 api/class.ts 里转过来 */
  class_teacher_sex?: string
  class_teacher_tel?: string
  stu_class_id?: number
}

/** 授课老师（后端 /class/all_class_teacher 的字段） */
export interface ClassTeacherRef {
  class_teacher_id: number
  class_teacher_name: string
  stu_class_id: number
}

/* ---------------------------------------------------------------------
 * 老师
 * ------------------------------------------------------------------ */

/** 老师信息（对应 Teacher_Out） */
export interface Teacher {
  teacher_id: number
  teacher_name: string
  teacher_tel: string
  teacher_job: string
  stu_class_ids: number[]
}

export interface TeacherCreate {
  teacher_name: string
  teacher_tel: string
  teacher_job: string
}

export type TeacherUpdate = Partial<TeacherCreate>

/* ---------------------------------------------------------------------
 * 统计
 * ------------------------------------------------------------------ */

/** 班级人数统计 */
export interface ClassStatistics {
  class_id: number
  class_name: string
  total: number
  male_count: number
  female_count: number
}

/** 每次考试各班平均分 */
export interface AvgScoreByClass {
  test_id: number
  class_id: number
  class_name: string
  avg_score: number
}

/** 薪资前五（后端返回 class_id，不是 class_name） */
export interface Top5Salary {
  stu_id: number
  stu_name: string
  class_id: number
  company: string
  salary: number
  offer_date: string
}

/** 就业时长（后端直接返回格式化好的文案） */
export interface EmpDuration {
  stu_id: number
  stu_name: string
  class_id: number
  open_date: string
  offer_date: string
  /** 后端算好的时长文案，如 "26个月0天" */
  duration_text: string
}

/** 各班平均就业时长 */
export interface AvgDurationByClass {
  class_id: number
  student_count: number
  duration_text: string
}

/** 单条「80 分以上」成绩记录 */
export interface Above80Record {
  stu_id: number
  stu_name: string
  test_id: number
  score: number
}

/** 单条「不及格」成绩记录 */
export interface FailedRecord {
  stu_id: number
  stu_name: string
  class_id: number
  test_id: number
  score: number
}
