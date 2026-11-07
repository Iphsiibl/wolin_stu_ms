/**
 * =====================================================================
 * 成绩模块的接口封装
 *
 * 对应后端：API/score_api.py  (router02, 前缀 /score)
 *
 * 【这个模块的特殊之处】
 * 后端返回格式是 {msg, detail}，而且 detail 里每一行的字段名是中文的：
 *   {"msg": "查询成功", "detail": [{"学生编号": 1, "考试序次": 1, "分数": 92}]}
 *
 * 来源在 API/score_api.py 的 _score_to_dict()，
 * 那里硬编码了中文 key（和 class 模块一样是老代码留下的约定）。
 *
 * 注意：请求体反而是英文的 —— Score 模型是 {stu_id, test_id, score}，
 * 所以只有【响应】需要转换，【请求】不用动。
 *
 * 解决办法：在这个文件里把中文 key 转成英文，
 * 视图层统一用 stu_id / test_id / score，
 * 不让中文 key 扩散到界面代码里（和 api/class.ts 是同一套路）。
 * =====================================================================
 */
import { del, get, post, put } from '@/api/http'
import type { Score, ScoreCreate } from '@/types/models'
import { toScore, type RawScore } from '@/utils/mappers'

export type { RawScore }

/* ---------------------------------------------------------------------
 * 成绩
 * ------------------------------------------------------------------ */

/** 录入成绩 */
export function createScore(payload: ScoreCreate) {
  return post<Score>('/score/score', payload)
}

/** 查某个学生的所有场次成绩 */
export async function fetchScoresByStudent(stu_id: number) {
  const res = await get<RawScore[]>('/score/stu_id/' + stu_id)
  return { ...res, data: (res.data ?? []).map(toScore) }
}

/** 查某场考试所有学生的成绩 */
export async function fetchScoresByTest(test_id: number) {
  const res = await get<RawScore[]>('/score/test_id/' + test_id)
  return { ...res, data: (res.data ?? []).map(toScore) }
}

/** 查某个学生某一场考试的成绩 */
export async function fetchScore(stu_id: number, test_id: number) {
  const res = await get<RawScore>(`/score/stu_id/${stu_id}/test_id/${test_id}`)
  return { ...res, data: toScore(res.data ?? {}) }
}

/** 修改成绩（学号和考试次序放在请求体里） */
export function updateScore(payload: ScoreCreate) {
  return put<Score>('/score/put', payload)
}

/** 删除成绩（软删除） */
export function deleteScore(stu_id: number, test_id: number) {
  return del<null>(`/score/del/stu_id/${stu_id}/test_id/${test_id}`)
}

/**
 * 查询已软删除的成绩。
 *
 * 注意：后端在「一条都没有」时会返回 404（detail: '未找到当前信息'），
 * 不是空数组。所以这里把 404 也当成「没有已删除记录」处理，
 * 免得弹一个红色报错框。
 */
export async function fetchDeletedScores() {
  try {
    const res = await get<RawScore[]>('/score/get_del', undefined, { silent: true })
    return { ...res, data: (res.data ?? []).map(toScore) }
  } catch {
    return { code: 200, message: '没有已删除的成绩', data: [] as Score[], total: 0 }
  }
}
