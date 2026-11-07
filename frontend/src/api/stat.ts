/**
 * =====================================================================
 * 统计分析模块的接口封装
 * =====================================================================
 * 对应后端：API/stat_api.py  (router06, 前缀 /stat)
 *
 * 这个模块的接口全部返回【裸数组】，没有 code/message 包装，
 * normalize() 已经把裸数组统一成 {code, message, data, total}。
 * =====================================================================
 */
import { get } from '@/api/http'
import type {
  Above80Record,
  AvgDurationByClass,
  AvgScoreByClass,
  ClassStatistics,
  EmpDuration,
  FailedRecord,
  Student,
  Top5Salary,
} from '@/types/models'

/** 查询所有超过指定年龄的学员 */
export function fetchStudentsOverAge(age = 30) {
  return get<Student[]>('/stat/students/over_age', { age })
}

/** 统计每个班级的人数以及男生女生的人数 */
export function fetchClassStatistics() {
  return get<ClassStatistics[]>('/stat/class/statistics')
}

/** 查询每次考试成绩都在 80 分以上的学生 */
export function fetchAllAbove80() {
  return get<Above80Record[]>('/stat/score/all_above_80')
}

/** 查询有两次以上不及格的学生 */
export function fetchFailedTwice() {
  return get<FailedRecord[]>('/stat/score/failed_twice')
}

/** 统计每次考试每个班级的平均分（从高到低排序） */
export function fetchAvgScoreByClass() {
  return get<AvgScoreByClass[]>('/stat/score/avg_by_class')
}

/** 统计就业薪资最高的前五名 */
export function fetchTop5Salary() {
  return get<Top5Salary[]>('/stat/emp/top5_salary')
}

/** 统计每个学生的就业时长 */
export function fetchEmpDuration() {
  return get<EmpDuration[]>('/stat/emp/duration')
}

/** 统计每个班级的平均就业时长 */
export function fetchAvgDurationByClass() {
  return get<AvgDurationByClass[]>('/stat/emp/avg_duration_by_class')
}

/**
 * 一个省份里的去向公司（就业热力地图用）
 * ---------------------------------------------------------------------
 * company  公司名（employment 表里原样的名字）
 * city     公司所在城市
 * count    去这家公司的学员人数
 */
export interface EmpDestinationCompany {
  company: string
  city: string
  count: number
  avg_salary: number
  max_salary: number
}

/**
 * 一个省份的就业去向（就业热力地图用）
 * ---------------------------------------------------------------------
 * province    省份名，和 public/geo/china.json 里的中文名一致
 * city        该省人数最多的城市
 * count       去该省的学员人数
 * companies   去向公司清单（按人数从多到少排）
 */
export interface EmpDestination {
  province: string
  city: string
  count: number
  avg_salary: number
  max_salary: number
  companies: EmpDestinationCompany[]
}

/** 按省份统计就业去向（就业热力地图的数据源） */
export function fetchEmpDestination() {
  return get<EmpDestination[]>('/stat/emp/destination')
}
