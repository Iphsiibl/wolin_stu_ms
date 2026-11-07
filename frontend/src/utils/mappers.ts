/**
 * =====================================================================
 * 后端返回格式 -> 前端类型 的纯映射函数
 *
 * 【为什么要单独抽一个文件】
 * 后端有 2 个模块的【响应】字段名是中文的：
 *   成绩模块（API/score_api.py 的 _score_to_dict）
 *     学生编号 / 考试序次 / 分数
 *   班级模块（API/class_api.py）
 *     班级id / 班级名字 / 开课时间 / 班主任id / 授课老师
 *     班主任id / 班主任名字 / 班主任性别
 *
 * 这两个模块的【请求体】反而是英文的，所以只需要转换响应。
 * 转换逻辑放在 api/score.ts 和 api/class.ts 里，
 * 视图层就只会看到 stu_id / test_id / score、class_id / class_name 这些英文 key，
 * 中文 key 不会扩散到界面代码里。
 *
 * 【为什么单独一个文件】
 * 这些函数是纯函数（不依赖 Vue、axios、路由），
 * 所以 scripts/verify-api.mjs 能直接 import 进来做断言，
 * 避免「表格空白」这种问题再次发生却没被验证脚本发现。
 *
 * 纯函数 + 无运行时依赖 = 可以在 Node 里直接跑。
 * =====================================================================
 */
import type { ClassInfo, ClassTeacher, Score } from '../types/models'

/* ---------------------------------------------------------------------
 * 成绩模块
 * ------------------------------------------------------------------ */

/** 后端返回的中文字段形状 */
export interface RawScore {
  学生编号?: number
  考试序次?: number
  /** 学生姓名 —— 后端 _score_to_dict 里是硬编码的中文 key */
  学生姓名?: string | null
  /** 班级名称 —— 后端 JOIN 班级表带回来的 */
  班级名称?: string | null
  分数?: number
}

/** 中文字段 -> 英文字段 */
export function toScore(raw: RawScore): Score {
  return {
    stu_id: Number(raw.学生编号 ?? 0),
    // 后端查成绩时 JOIN 了学生表，姓名是白送的，
    // 不用前端再查一遍学生表反查学号。
    stu_name: String(raw.学生姓名 ?? ''),
    // 班级名同理：后端 JOIN 了班级表（scores -> student_info -> clazz）。
    // 查不到班级时后端给空串，这里保持空串，页面显示「-」。
    class_name: String(raw.班级名称 ?? ''),
    test_id: Number(raw.考试序次 ?? 0),
    score: Number(raw.分数 ?? 0),
  }
}

/* ---------------------------------------------------------------------
 * 班级模块
 * ------------------------------------------------------------------ */

/**
 * 后端返回的中文字段形状（班级）
 *
 * 【2026-11-03 后端改过字段名】
 * 原来只有「授课老师」（一个 id），现在后端 JOIN 了班主任表和老师表，
 * 拆成了「授课老师id」+「授课老师姓名」，另外多给了「班主任姓名」。
 * 旧的「授课老师」字段保留在类型里做兼容，新旧两种都能解析。
 */
export interface RawClass {
  message?: string
  班级id?: number
  班级名字?: string
  开课时间?: string
  班主任id?: number | null
  班主任姓名?: string | null
  授课老师id?: number | null
  授课老师姓名?: string | null
  /** 旧字段：只有一个 id，没有姓名 */
  授课老师?: number | null
}

/** 后端返回的中文字段形状（班主任） */
export interface RawClassTeacher {
  message?: string
  班主任id?: number
  班主任名字?: string
  班主任性别?: string
  stu_class_id?: number
}

/** 中文字段 -> 英文字段（班级） */
export function toClassInfo(raw: RawClass): ClassInfo {
  return {
    class_id: Number(raw.班级id ?? 0),
    class_name: String(raw.班级名字 ?? ''),
    start_date: String(raw.开课时间 ?? ''),
    class_teacher_id: raw.班主任id ?? null,
    // 后端直接给了姓名的话优先用，省得前端再查一遍老师表反查
    class_teacher_name: raw.班主任姓名 ?? null,
    teacher_id: raw.授课老师id ?? raw.授课老师 ?? null,
    teacher_name: raw.授课老师姓名 ?? null,
  }
}

/** 中文字段 -> 英文字段（班主任） */
export function toClassTeacher(raw: RawClassTeacher): ClassTeacher {
  return {
    class_teacher_id: Number(raw.班主任id ?? 0),
    class_teacher_name: String(raw.班主任名字 ?? ''),
    class_teacher_sex: String(raw.班主任性别 ?? ''),
    stu_class_id: raw.stu_class_id,
  }
}
