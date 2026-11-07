/**
 * =====================================================================
 * API 层端到端验证脚本
 * =====================================================================
 * 目的：不依赖浏览器，直接跑通【前端 API 层 -> Vite 代理 -> FastAPI 后端】
 *       的完整链路，验证每一层封装与响应归一化逻辑都是对的。
 *
 * 覆盖范围：后端 openapi.json 里全部 49 个接口
 *   · 只读接口：逐个验证 HTTP 状态 + 归一化后的 data 形状
 *   · 写接口：走「创建 -> 查询 -> 修改 -> 删除」完整生命周期，
 *     断言每一步的返回内容，最后把测试数据清理干净，不污染真实库
 *   · 错误路径：业务 404 / 参数校验 422 / 不存在的路由 404
 *
 * 用法：node scripts/verify-api.mjs
 * =====================================================================
 */

// 与前端 src/api/http.ts 的 normalize() 保持一致
function normalize(body) {
  if (Array.isArray(body)) {
    return { code: 200, message: '查询成功', data: body, total: body.length }
  }
  if (body && typeof body === 'object') {
    const raw = body
    if ('msg' in raw && !('code' in raw)) {
      return {
        code: 200,
        message: String(raw.msg ?? '操作成功'),
        data: raw.detail ?? null,
        total: 0,
      }
    }
    // 形态 5.5：{total, result}（未就业学生）
    if ('result' in raw && Array.isArray(raw.result)) {
      return {
        code: 200,
        message: '查询成功',
        data: raw.result,
        total: Number(raw.total ?? raw.result.length),
      }
    }
    if ('items' in raw && Array.isArray(raw.items)) {
      return {
        code: 200,
        message: '查询成功',
        data: raw.items,
        total: Number(raw.total ?? raw.items.length),
        page: Number(raw.page ?? 1),
        size: Number(raw.size ?? raw.items.length),
        totalPages: Number(raw.total_pages ?? 1),
      }
    }
    if ('code' in raw) {
      const data = 'Data' in raw ? raw.Data : 'data' in raw ? raw.data : null
      const isList = Array.isArray(data)
      return {
        code: Number(raw.code ?? 200),
        message: String(raw.message ?? '操作成功'),
        data,
        total: Number(raw.total ?? (isList ? data.length : data ? 1 : 0)),
      }
    }
  }
  return { code: 200, message: '操作成功', data: body, total: 0 }
}

const BASE = 'http://localhost:5173/api'

// 直接 import 前端源码里的纯映射函数做断言。
// mappers.ts 是纯函数、不依赖 Vue/axios，所以能被这个脚本原样引用
// —— 验证的就是浏览器里真正跑的那段代码。
const { toScore, toClassInfo, toClassTeacher } = await import('../src/utils/mappers.ts')

let pass = 0
let fail = 0
const failures = []

/**
 * 测试数据标记，跑完统一清理。
 *
 * 长度必须卡在后端 schema 的限制之内，不然会吃到 422 而不是业务错误：
 *   stu_name / class_teacher_name  varchar(10)  最多 10 个字
 *   class_name / agent_name        varchar(20)  最多 20 个字
 *   company                        varchar(50)  最多 50 个字
 *   stu_tel                        ^1[3-9]\d{9}$
 *   teacher_tel                    ^1\d{10}$
 *   stu_age / agent_age            > 18
 * 所以 MARK 控制在 7 个字符，后面各留 1 个字符的区分位。
 */
const MARK = 'Z' + String(Date.now()).slice(-6)
/** 本轮创建出来的测试数据 id，结束时按依赖顺序删掉 */
const created = { agent_id: null, teacher_id: null, class_teacher_id: null, class_id: null, stu_id: null }

/**
 * 跑一个请求，校验 HTTP 状态与归一化结果。
 * @param {string} name 用例名
 * @param {string} url  相对 BASE 的路径
 * @param {object} opts fetch 选项
 * @param {Function} validate (norm, status) => 错误说明|null
 * @param {number[]} okStatus 视为成功的状态码，默认 2xx
 */
async function check(name, url, opts = {}, validate, okStatus) {
  try {
    const res = await fetch(BASE + url, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
    })
    const text = await res.text()
    let raw
    try {
      raw = JSON.parse(text)
    } catch {
      raw = text
    }
    const norm = normalize(raw)
    const allowed = okStatus ?? null
    const statusOk = allowed ? allowed.includes(res.status) : res.status >= 200 && res.status < 300
    const problem = !statusOk
      ? `HTTP ${res.status}（期望 ${allowed ?? '2xx'}）${text.slice(0, 120)}`
      : validate
        ? validate(norm, res.status)
        : null
    if (problem) {
      fail++
      failures.push(`${name} -> ${problem}`)
      console.log(`  [FAIL] ${name}  ${problem}`)
      return null
    }
    pass++
    console.log(`  [OK]   ${name}  total=${norm.total} msg="${norm.message}"`)
    return norm
  } catch (e) {
    fail++
    failures.push(`${name} -> ${e.message}`)
    console.log(`  [FAIL] ${name}  ${e.message}`)
    return null
  }
}

/**
 * 顺手把某个接口的归一化结果取出来（不计入通过/失败统计）。
 * 用来先取一条"真实存在"的数据，后面再用它做断言。
 * 不能写死 stu_id=1 —— 种子数据的姓名/编号是随机生成的，
 * 而且学生/成绩都可能被软删除（is_del=1），写死会误报失败。
 */
async function fetchNorm(url, opts = {}) {
  try {
    const res = await fetch(BASE + url, { headers: { 'Content-Type': 'application/json' }, ...opts })
    const raw = await res.json()
    return { status: res.status, norm: normalize(raw), raw }
  } catch (e) {
    return { status: 0, norm: null, error: e.message }
  }
}

/** 期望某个归一化结果里的 data 是数组 */
const isArr = (label) => (r) => (!Array.isArray(r.data) ? `${label} 不是数组` : null)
/** 期望 data 是非空对象 */
const isObj = (label) => (r) => (!r.data || typeof r.data !== 'object' || Array.isArray(r.data) ? `${label} 不是对象` : null)

console.log('\n=== API 层端到端验证（前端 -> Vite代理 -> FastAPI）===\n')

/* =====================================================================
 * 一、学生模块
 * ================================================================== */
console.log('[学生模块]  后端 {code,message,total,Data}')

// 取一条真实存在的学生
const allStudents = (await fetchNorm('/student/select_stu_skip?skip=0&limit=50')).norm?.data
const sampleStu = Array.isArray(allStudents) ? allStudents[0] : null
const sampleStuId = sampleStu?.stu_id
const sampleStuName = sampleStu?.stu_name
const sampleClassId = sampleStu?.stu_class_id

await check('查询全部学生（分页接口拉全量）', '/student/select_stu_skip?skip=0&limit=5000', {}, (r) => {
  if (!Array.isArray(r.data)) return 'Data 不是数组'
  if (r.data.length < 1) return '总数为 0'
  const row = r.data[0]
  if (typeof row.stu_id !== 'number' || !row.stu_name) return `字段不对: ${JSON.stringify(row)}`
  return null
})
await check('分页查询学生', '/student/select_stu_skip?skip=0&limit=10', {}, (r) => {
  if (!Array.isArray(r.data)) return 'Data 不是数组'
  if (r.data.length > 10) return `limit=10 却返回 ${r.data.length} 条`
  return null
})
await check('按学号查询', `/student/select_stu_id?stu_id=${sampleStuId}`, {}, (r) =>
  !r.data || r.data.stu_id !== sampleStuId ? `返回的学生 id 不对（期望 ${sampleStuId}）` : null)
await check(
  '按姓名查询（存在的姓名）',
  `/student/select_stu_name?stu_name=${encodeURIComponent(sampleStuName ?? '')}`,
  {},
  (r) => (!Array.isArray(r.data) ? 'Data 不是数组' : r.data.length < 1 ? '应至少查到 1 条' : null)
)
await check('按班级查询', `/student/select_stu_class?stu_class_id=${sampleClassId}`, {}, isArr('Data'))

/* =====================================================================
 * 二、顾问模块（后端已独立成 /agent 路由）
 * ================================================================== */
console.log('\n[顾问模块]  后端已从 /student/* 拆到 /agent/*')

const allAgents = (await fetchNorm('/agent/agent')).norm?.data
const sampleAgentId = Array.isArray(allAgents) ? allAgents[0]?.agent_id : null
const sampleAgentName = Array.isArray(allAgents) ? allAgents[0]?.agent_name : null

await check('查询所有顾问', '/agent/agent', {}, (r) => {
  if (!Array.isArray(r.data)) return 'Data 不是数组'
  if (r.data.length < 1) return '应至少查到 1 条'
  const row = r.data[0]
  if (typeof row.agent_id !== 'number' || !row.agent_name) return `字段不对: ${JSON.stringify(row)}`
  return null
})
await check('按 id 查询顾问', `/agent/select_agent?agent_id=${sampleAgentId}`, {}, (r) =>
  !r.data || r.data.agent_id !== sampleAgentId ? `返回的顾问 id 不对（期望 ${sampleAgentId}）` : null)
await check(
  '按顾问查询学生',
  `/agent/select_stu_agent?agent_id=${sampleAgentId}`,
  {},
  (r) => (!Array.isArray(r.data) ? 'Data 不是数组' : null),
  // 顾问名下没有学生时后端返回 404，属于正常业务状态
  [200, 404]
)

/* =====================================================================
 * 三、成绩模块
 * ================================================================== */
console.log('\n[成绩模块]  后端 {msg,detail}，且行内字段是中文 -> 需在 api/score.ts 转英文')

// 找一个"确实有成绩"的学生
let scoreSample = null
for (const s of (Array.isArray(allStudents) ? allStudents : []).slice(0, 20)) {
  const r = await fetchNorm(`/score/stu_id/${s.stu_id}`)
  if (Array.isArray(r.norm?.data) && r.norm.data.length) {
    scoreSample = { stu: s, rows: r.norm.data }
    break
  }
}
const scoreStuId = scoreSample?.stu.stu_id
const scoreTestId = scoreSample ? toScore(scoreSample.rows[0]).test_id : undefined

await check('查学生成绩', `/score/stu_id/${scoreStuId}`, {}, (r) => {
  if (!Array.isArray(r.data)) return `detail 未映射到 data (${JSON.stringify(r.data)})`
  if (!r.data.length) return '应至少查到 1 条'
  const row = toScore(r.data[0])
  if (typeof row.stu_id !== 'number' || typeof row.test_id !== 'number' || typeof row.score !== 'number') {
    return `映射后字段类型不对: ${JSON.stringify(row)}`
  }
  if (typeof row.stu_name !== 'string') return `映射后缺 stu_name: ${JSON.stringify(row)}`
  // 学生姓名是后端 JOIN 学生表带回来的，
  // 少了它成绩列表的「学生姓名」列就会整列空白。
  if (!row.stu_name) return '学生姓名为空（后端 /score 接口应返回「学生姓名」）'
  // 班级名同理：后端 JOIN 班级表（scores -> student_info -> clazz）带回来的。
  if (typeof row.class_name !== 'string') return `映射后缺 class_name: ${JSON.stringify(row)}`
  if (!row.class_name) return '班级名为空（后端 /score 接口应返回「班级名称」）'
  if ('学生编号' in row || '考试序次' in row || '分数' in row || '学生姓名' in row || '班级名称' in row) {
    return '映射后仍残留中文 key'
  }
  return null
})
await check('查场次成绩', `/score/test_id/${scoreTestId}`, {}, (r) => {
  if (!Array.isArray(r.data)) return 'detail 未映射到 data'
  if (!r.data.length) return '应至少查到 1 条'
  const row = toScore(r.data[0])
  // 整场考试的成绩列表也要带姓名（成绩列表页按场次查时显示这一列）
  if (!row.stu_name) return `学生姓名为空: ${JSON.stringify(row)}`
  // 也要带班级名（成绩列表页的「班级」列）
  if (!row.class_name) return `班级名为空: ${JSON.stringify(row)}`
  return null
})
await check('查单条成绩', `/score/stu_id/${scoreStuId}/test_id/${scoreTestId}`, {}, (r) => {
  if (!r.data || typeof r.data !== 'object') return 'detail 未映射到 data'
  const row = toScore(r.data)
  return row.stu_id === scoreStuId && row.test_id === scoreTestId && typeof row.score === 'number'
    ? null
    : `映射结果不对: ${JSON.stringify(row)}`
})
await check('查已删除成绩（无记录时 404 属正常）', '/score/get_del', {}, () => null, [200, 404])

/* =====================================================================
 * 四、就业模块
 * ================================================================== */
console.log('\n[就业模块]  后端 {total,page,size,total_pages,items} / {total,result}')

await check('分页查询', '/employment/page?page=1&size=10', {}, (r) =>
  !Array.isArray(r.data) ? 'items 未映射到 data' : r.totalPages < 1 ? 'totalPages 缺失' : null)
// 排序交给后端做（这一页是真服务端分页，前端排只能排当前页）
await check('分页查询 + 薪资降序', '/employment/page?page=1&size=10&sort=salary:desc', {}, (r) => {
  if (!Array.isArray(r.data) || !r.data.length) return '没有数据'
  const salaries = r.data.map((x) => Number(x.salary))
  for (let i = 1; i < salaries.length; i++) {
    if (salaries[i] > salaries[i - 1]) return `第 ${i + 1} 条薪资 ${salaries[i]} 大于上一条 ${salaries[i - 1]}`
  }
  return null
})
await check('分页查询 + 学号升序', '/employment/page?page=1&size=10&sort=stu_id:asc', {}, (r) => {
  if (!Array.isArray(r.data) || !r.data.length) return '没有数据'
  const ids = r.data.map((x) => Number(x.stu_id))
  for (let i = 1; i < ids.length; i++) {
    if (ids[i] < ids[i - 1]) return `第 ${i + 1} 条学号 ${ids[i]} 小于上一条 ${ids[i - 1]}`
  }
  return null
})
// 白名单之外的字段必须被忽略（不能拼进 order_by）
await check('分页查询 + 非法排序字段被忽略', '/employment/page?page=1&size=5&sort=not_a_column:asc', {}, (r) =>
  !Array.isArray(r.data) ? 'items 未映射到 data' : null)
await check('条件查询', '/employment/search', {}, isArr('Data'))
await check('查询未就业学生（{total,result} 形态）', '/employment/unemployed', {}, (r) => {
  if (!Array.isArray(r.data)) return `result 未映射到 data，实际是 ${JSON.stringify(r.data).slice(0, 80)}`
  if (typeof r.total !== 'number') return 'total 缺失'
  return null
})

/* =====================================================================
 * 五、班级模块
 * ================================================================== */
console.log('\n[班级模块]  后端中文字段 -> 需在 api/class.ts 转英文')

await check('查询所有班级', '/class/all_class', {}, (r) => {
  if (!Array.isArray(r.data)) return '不是数组'
  if (!r.data.length) return '应至少查到 1 条'
  const row = toClassInfo(r.data[0])
  if (typeof row.class_id !== 'number' || !row.class_name) return `映射后字段不对: ${JSON.stringify(row)}`
  if ('班级id' in row || '班级名字' in row || '开课时间' in row) return '映射后仍残留中文 key'
  return null
})
await check('按 id 查询班级', '/class/get_class/1', {}, (r) => {
  if (!r.data || typeof r.data !== 'object') return '不是对象'
  const row = toClassInfo(r.data)
  if (typeof row.class_id !== 'number' || !row.class_name) return `映射结果不对: ${JSON.stringify(row)}`
  // 2026-11-03：后端 JOIN 了班主任表和老师表，会带姓名回来。
  // 少了这两个字段，班级列表的「班主任 / 授课老师」两列就会全变成 -。
  if (!row.class_teacher_name) return '班主任姓名丢失（后端 /class 接口应返回「班主任姓名」）'
  if (!row.teacher_name) return '授课老师姓名丢失（后端 /class 接口应返回「授课老师姓名」）'
  if (!row.teacher_id) return '授课老师 id 丢失'
  return null
})
// 2026-11-03 后端新增：查某个班级的全部学员。返回的是英文 key，不用转换。
await check('查询班级学员', '/class/get_class/1/students', {}, (r) => {
  if (!Array.isArray(r.data)) return '不是数组'
  if (!r.data.length) return '应至少查到 1 条'
  const row = r.data[0]
  if (typeof row.stu_id !== 'number' || !row.stu_name) return `字段不对: ${JSON.stringify(row)}`
  // agent_name 允许为 null（不是每个学员都有顾问），但 agent_id 必须存在
  if (!('agent_id' in row)) return 'agent_id 字段丢失'
  return null
})
await check('查询所有班主任', '/class_teacher/all_class_teacher', {}, (r) => {
  if (!Array.isArray(r.data)) return '不是数组'
  if (!r.data.length) return '应至少查到 1 条'
  const row = toClassTeacher(r.data[0])
  if (typeof row.class_teacher_id !== 'number' || !row.class_teacher_name) {
    return `映射后字段不对: ${JSON.stringify(row)}`
  }
  // 性别必须透传，否则「修改班主任」会把女班主任的性别改掉
  if (!row.class_teacher_sex) return '性别字段丢失'
  if ('班主任名字' in row || '班主任性别' in row) return '映射后仍残留中文 key'
  return null
})
await check('按 id 查询班主任', '/class_teacher/get_class_teacher/1', {}, (r) => {
  if (!r.data || typeof r.data !== 'object') return '不是对象'
  const row = toClassTeacher(r.data)
  return typeof row.class_teacher_id === 'number' ? null : `映射结果不对: ${JSON.stringify(row)}`
})

/* =====================================================================
 * 六、老师模块
 * ================================================================== */
console.log('\n[老师模块]  后端裸数组')

const allTeachers = (await fetchNorm('/teacher/')).norm?.data
const sampleTeacherId = Array.isArray(allTeachers) ? allTeachers[0]?.teacher_id : null

await check('查询所有老师', '/teacher/', {}, isArr('data'))
await check('按 id 查询老师', `/teacher/${sampleTeacherId}`, {}, (r) =>
  !r.data || r.data.teacher_id !== sampleTeacherId ? '返回的老师不对' : null)

/* =====================================================================
 * 七、统计模块
 * ================================================================== */
console.log('\n[统计模块]  后端裸数组')

await check('班级人数统计', '/stat/class/statistics', {}, (r) => {
  if (!Array.isArray(r.data)) return '不是数组'
  if (!r.data.length) return '应至少查到 1 条'
  const row = r.data[0]
  for (const k of ['class_id', 'class_name', 'total', 'male_count', 'female_count']) {
    if (row[k] === undefined) return `缺少字段 ${k}`
  }
  // 男生数 + 女生数 应等于总人数（后端修过一个把 '男'/'女' 当 int 比较的 bug）
  if (row.male_count + row.female_count !== row.total) {
    return `男女之和 ${row.male_count}+${row.female_count} != 总数 ${row.total}`
  }
  return null
})
await check('各班平均分', '/stat/score/avg_by_class', {}, isArr('data'))
await check('薪资前五', '/stat/emp/top5_salary', {}, (r) => {
  if (!Array.isArray(r.data)) return '不是数组'
  if (r.data.length > 5) return '超过 5 条'
  return null
})
await check('就业时长', '/stat/emp/duration', {}, isArr('data'))
await check('各班平均就业时长', '/stat/emp/avg_duration_by_class', {}, isArr('data'))
await check('全优学生', '/stat/score/all_above_80', {}, isArr('data'))
await check('两科不及格', '/stat/score/failed_twice?pass_score=60', {}, isArr('data'))
await check('超龄学员', '/stat/students/over_age?age=30', {}, isArr('data'))
await check('就业去向（热力地图数据源）', '/stat/emp/destination', {}, (r) => {
  if (!Array.isArray(r.data)) return '不是数组'
  if (!r.data.length) return '应至少查到 1 条'
  const row = r.data[0]
  for (const k of ['province', 'count', 'avg_salary']) {
    if (row[k] === undefined) return `缺少字段 ${k}`
  }
  // 省份名必须是中文，且不能为空串（前端要拿它去匹配地图上的省）
  if (typeof row.province !== 'string' || !row.province.trim()) return '省份名不合法'
  return null
})

/* =====================================================================
 * 八、写接口生命周期（创建 -> 查 -> 改 -> 删），最后清理
 * ================================================================== */
console.log('\n[写接口生命周期]  创建 -> 查询 -> 修改 -> 删除（结束后清理测试数据）')

const json = (body) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

// ---- 顾问 ----
{
  const created1 = await check(
    '新增顾问',
    '/agent/add_agent',
    json({ agent_name: MARK, agent_sex: '男', agent_age: 30 }),
    (r) => (r.code !== 200 ? `code=${r.code}` : null),
    [200, 201]
  )
  const aid = created1?.data?.Data?.agent_id ?? created1?.data?.agent_id ?? created1?.data?.data?.agent_id
  if (aid) {
    created.agent_id = aid
    await check('查询新建的顾问', `/agent/select_agent?agent_id=${aid}`, {}, (r) =>
      r.data?.agent_id !== aid ? 'id 不匹配' : r.data?.agent_name !== MARK ? '姓名不匹配' : null)
    await check(
      '修改顾问（agent_id 走 query）',
      `/agent/update_agent?agent_id=${aid}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_age: 31 }),
      },
      (r) => (r.code !== 200 ? `code=${r.code}` : null)
    )
    await check(
      '修改后复读顾问',
      `/agent/select_agent?agent_id=${aid}`,
      {},
      (r) => (r.data?.agent_age !== 31 ? `年龄应为 31，实际 ${r.data?.agent_age}` : null)
    )
  } else {
    console.log('  [SKIP] 顾问的后续步骤：新增接口没返回 agent_id')
  }
}

// ---- 老师 ----
{
  const created1 = await check(
    '新增老师',
    '/teacher/',
    json({ teacher_name: MARK + 'T', teacher_tel: '13000000000', teacher_job: '讲师' }),
    (r) => (r.code !== 200 ? `code=${r.code}` : null),
    [200, 201]
  )
  const tid = created1?.data?.teacher_id ?? created1?.data?.Data?.teacher_id ?? created1?.data?.data?.teacher_id
  if (tid) {
    created.teacher_id = tid
    await check('查询新建的老师', `/teacher/${tid}`, {}, (r) =>
      r.data?.teacher_id !== tid ? 'id 不匹配' : r.data?.teacher_name !== MARK + 'T' ? '姓名不匹配' : null)
    await check(
      '修改老师',
      `/teacher/${tid}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ teacher_job: '高级讲师' }),
      },
      (r) => (r.code !== 200 ? `code=${r.code}` : null)
    )
    await check('修改后复读老师', `/teacher/${tid}`, {}, (r) =>
      r.data?.teacher_job !== '高级讲师' ? `职位应为 高级讲师，实际 ${r.data?.teacher_job}` : null)
  } else {
    console.log('  [SKIP] 老师的后续步骤：新增接口没返回 teacher_id')
  }
}

// ---- 班主任 ----
// 注意：后端 POST /class_teacher/class_teacher 只返回 {"message": "新增班主任成功"}，
// 不带 id，所以这里新增之后从列表里按名字反查一次。
{
  const ctName = MARK + 'C'
  await check(
    '新增班主任',
    '/class_teacher/class_teacher',
    json({ class_teacher_name: ctName, class_teacher_sex: '女' }),
    (r) => (r.code !== 200 ? `code=${r.code}` : null),
    [200, 201]
  )
  const ctList = (await fetchNorm('/class_teacher/all_class_teacher')).norm?.data
  const ctRow = Array.isArray(ctList)
    ? ctList.map(toClassTeacher).find((x) => x.class_teacher_name === ctName)
    : null
  if (ctRow) {
    created.class_teacher_id = ctRow.class_teacher_id
    await check('查询新建的班主任', `/class_teacher/get_class_teacher/${ctRow.class_teacher_id}`, {}, (r) => {
      const row = toClassTeacher(r.data ?? {})
      return row.class_teacher_id !== ctRow.class_teacher_id
        ? 'id 不匹配'
        : row.class_teacher_name !== ctName
          ? '姓名不匹配'
          : null
    })
    await check(
      '修改班主任',
      `/class_teacher/update_class_teacher/${ctRow.class_teacher_id}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ class_teacher_name: MARK + 'C2', class_teacher_sex: '女' }),
      },
      (r) => (r.code !== 200 ? `code=${r.code}` : null)
    )
    await check('修改后复读班主任', `/class_teacher/get_class_teacher/${ctRow.class_teacher_id}`, {}, (r) => {
      const row = toClassTeacher(r.data ?? {})
      return row.class_teacher_name !== MARK + 'C2' ? `姓名应改为 ${MARK}C2，实际 ${row.class_teacher_name}` : null
    })
  } else {
    console.log('  [SKIP] 班主任的后续步骤：列表里没找到新建的班主任')
  }
}

// ---- 班级 ----
// 同样：POST /class/ 只返回 {"message": "创建成功"}，不带 id，新增后从列表反查。
{
  const clsName = MARK + 'K'
  await check(
    '新建班级',
    '/class/',
    json({
      class_name: clsName,
      start_date: '2026-01-01',
      class_teacher_id: created.class_teacher_id || 1,
      teacher_id: created.teacher_id || 1,
    }),
    (r) => (r.code !== 200 ? `code=${r.code}` : null),
    [200, 201]
  )
  const clsList = (await fetchNorm('/class/all_class')).norm?.data
  const clsRow = Array.isArray(clsList)
    ? clsList.map(toClassInfo).find((x) => x.class_name === clsName)
    : null
  if (clsRow) {
    created.class_id = clsRow.class_id
    await check('查询新建的班级', `/class/get_class/${clsRow.class_id}`, {}, (r) => {
      const row = toClassInfo(r.data ?? {})
      return row.class_id !== clsRow.class_id
        ? 'id 不匹配'
        : row.class_name !== clsName
          ? '班级名不匹配'
          : null
    })
    await check(
      '修改班级',
      `/class/update_class/${clsRow.class_id}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          class_name: MARK + 'K2',
          start_date: '2026-01-01',
          class_teacher_id: created.class_teacher_id || 1,
          teacher_id: created.teacher_id || 1,
        }),
      },
      (r) => (r.code !== 200 ? `code=${r.code}` : null)
    )
    await check('修改后复读班级', `/class/get_class/${clsRow.class_id}`, {}, (r) => {
      const row = toClassInfo(r.data ?? {})
      return row.class_name !== MARK + 'K2' ? `班级名应改为 ${MARK}K2，实际 ${row.class_name}` : null
    })
  } else {
    console.log('  [SKIP] 班级的后续步骤：列表里没找到新建的班级')
  }
}

// ---- 学生 ----
{
  const created1 = await check(
    '新增学生',
    '/student/add_stu',
    json({
      stu_name: MARK + 'S',
      stu_age: 22,
      stu_sex: '男',
      stu_class_id: created.class_id || sampleClassId || 1,
      stu_tel: '13900000000',
      stu_from: '河北',
      stu_school: '测试大学',
      stu_major: '计算机',
      enroll_date: '2024-09-01',
      gra_date: '2026-06-30',
      edu_bg: '本科',
      agent_id: created.agent_id || sampleAgentId || 1,
    }),
    (r) => (r.code !== 200 ? `code=${r.code}` : null),
    [200, 201]
  )
  const sid = created1?.data?.Data?.stu_id ?? created1?.data?.stu_id ?? created1?.data?.data?.stu_id
  if (sid) {
    created.stu_id = sid
    await check('查询新建的学生', `/student/select_stu_id?stu_id=${sid}`, {}, (r) =>
      r.data?.stu_id !== sid ? 'id 不匹配' : r.data?.stu_name !== MARK + 'S' ? '姓名不匹配' : null)
    await check(
      '修改学生（stu_id 走 query，不是 body）',
      `/student/update_stu_class?stu_id=${sid}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stu_age: 23 }),
      },
      (r) => (r.code !== 200 ? `code=${r.code}` : null)
    )
    await check('修改后复读学生', `/student/select_stu_id?stu_id=${sid}`, {}, (r) =>
      r.data?.stu_age !== 23 ? `年龄应为 23，实际 ${r.data?.stu_age}` : null)
  } else {
    console.log('  [SKIP] 学生的后续步骤：新增接口没返回 stu_id')
  }
}

// ---- 就业 ----
if (created.stu_id) {
  await check(
    '新增就业信息',
    '/employment/create',
    json({
      stu_id: created.stu_id,
      company: MARK + 'CO',
      salary: 18000,
      open_date: '2026-01-15',
      offer_date: '2026-03-20',
    }),
    (r) => (r.code !== 200 ? `code=${r.code}` : null),
    [200, 201]
  )
  await check('条件查询就业信息', `/employment/search?company=${encodeURIComponent(MARK)}`, {}, (r) =>
    !Array.isArray(r.data) ? 'Data 不是数组' : r.data.length < 1 ? '应查到刚建的记录' : null)
  await check(
    '修改就业信息',
    `/employment/put/${created.stu_id}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ salary: 20000 }),
    },
    (r) => (r.code !== 200 ? `code=${r.code}` : null)
  )
}

// ---- 成绩 ----
/**
 * 后端 DELETE /score/del 一旦 500，这条测试成绩就会留在库里
 * （学生删除是软删除，不级联成绩表），所以要记下来，
 * 在收尾时明确告诉使用者怎么手动清 —— 别让残留悄悄堆进正式数据。
 */
let scoreResidue = null
if (created.stu_id) {
  await check(
    '录入成绩',
    '/score/score',
    json({ stu_id: created.stu_id, test_id: 99, score: 88 }),
    () => null,
    [200, 201]
  )
  await check('查询刚录入的成绩', `/score/stu_id/${created.stu_id}/test_id/99`, {}, (r) => {
    const row = toScore(r.data ?? {})
    return row.score === 88 ? null : `分数应为 88，实际 ${row.score}`
  })
  await check(
    '修改成绩',
    '/score/put',
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stu_id: created.stu_id, test_id: 99, score: 95 }),
    },
    () => null
  )
  // 删除成绩这里没用 check()：需要额外拿到 HTTP 状态码，
  // 才能判断「删掉了」还是「接口挂了、成绩留在库里」。
  {
    const res = await fetch(`${BASE}/score/del/stu_id/${created.stu_id}/test_id/99`, { method: 'DELETE' })
    const text = await res.text()
    if (res.status >= 200 && res.status < 300) {
      pass++
      console.log('  [OK]   删除成绩  total=0 msg="删除成功"')
    } else {
      fail++
      failures.push(`删除成绩 -> HTTP ${res.status}（期望 2xx）${text.slice(0, 120)}`)
      console.log(`  [FAIL] 删除成绩  HTTP ${res.status}（期望 2xx）${text.slice(0, 120)}`)
      scoreResidue = { stu_id: created.stu_id }
    }
  }
  await check('删除后查已删除成绩（应能查到刚才那条）', '/score/get_del', {}, (r) => {
    if (!Array.isArray(r.data)) return 'detail 未映射到 data'
    const hit = r.data.map(toScore).find((x) => x.stu_id === created.stu_id && x.test_id === 99)
    return hit ? null : '刚删的成绩没出现在已删除列表里'
  })
}

/* =====================================================================
 * 九、错误路径
 * ================================================================== */
console.log('\n[错误处理]  后端业务异常应保留可读文案')

try {
  const errRes = await fetch(BASE + '/student/select_stu_id?stu_id=999999')
  const errBody = await errRes.json()
  if (errRes.status === 404 && typeof errBody.detail === 'string' && errBody.detail.length > 0) {
    pass++
    console.log(`  [OK]   404 业务异常 -> detail="${errBody.detail}"`)
  } else {
    fail++
    failures.push('404 业务异常文案异常')
    console.log(`  [FAIL] 404 业务异常 -> status=${errRes.status} body=${JSON.stringify(errBody)}`)
  }
} catch (e) {
  fail++
  failures.push('404 业务异常 -> ' + e.message)
  console.log(`  [FAIL] 404 业务异常 -> ${e.message}`)
}

console.log('\n[错误处理]  422 参数校验错误应转成可读中文')
try {
  const vRes = await fetch(BASE + '/student/add_stu', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stu_name: '测试' }), // 缺 age/class_id/tel 等必填字段
  })
  const vBody = await vRes.json()
  if (vRes.status === 422 && Array.isArray(vBody.detail)) {
    pass++
    console.log(`  [OK]   422 校验错误 -> ${vBody.detail.length} 条明细，前端会转成"字段名：提示"`)
  } else {
    fail++
    failures.push('422 校验错误格式异常')
    console.log(`  [FAIL] 422 校验错误 -> status=${vRes.status} body=${JSON.stringify(vBody)}`)
  }
} catch (e) {
  fail++
  failures.push('422 校验错误 -> ' + e.message)
  console.log(`  [FAIL] 422 校验错误 -> ${e.message}`)
}

console.log('\n[错误处理]  后端已删除的旧路径应返回 404（确认前端不再调用）')
for (const dead of [
  '/student/select_all',
  '/student/agent',
  '/student/select_agent',
  '/student/add_agent',
  '/student/update_agent?agent_id=1',
  '/student/delete_agent?agent_id=1',
  '/student/select_stu_agent?agent_id=1',
  // 2026-11-03：班主任拆到独立路由 /class_teacher 后，旧的 /class/* 全部下线
  '/class/all_class_teacher',
  '/class/get_class_teacher/1',
  '/class/class_teacher',
  '/class/update_class_teacher/1',
  '/class/delete_class_teacher/1',
]) {
  const r = await fetch(BASE + dead)
  if (r.status === 404) {
    pass++
    console.log(`  [OK]   旧路径已下线 -> ${dead}`)
  } else {
    fail++
    failures.push(`旧路径 ${dead} 仍返回 ${r.status}，前端可能还在用它`)
    console.log(`  [FAIL] 旧路径仍存在 -> ${dead} -> ${r.status}`)
  }
}

/* =====================================================================
 * 十、清理测试数据
 * ================================================================== */
console.log('\n[清理]  删除本轮创建的测试数据')

async function cleanup(name, url, method = 'DELETE') {
  if (!url) return
  const r = await fetch(BASE + url, { method, headers: { 'Content-Type': 'application/json' } })
  if (r.ok) {
    pass++
    console.log(`  [OK]   已清理 ${name}`)
  } else {
    console.log(`  [WARN] 清理 ${name} 失败 -> HTTP ${r.status}`)
  }
}

// 成绩的「删除」是软删（is_del=1），后端没有物理删除接口，
// 所以这行测试数据一定会以「已删除」状态留在库里 —— 它不影响任何列表查询，
// 但每跑一轮就多一行。这里把话说明白，并给出精确的清理 SQL，
// 免得测试数据悄悄堆进正式数据。
if (created.stu_id) {
  console.log('  [WARN] 成绩是软删（is_del=1），后端无物理删除接口，本轮测试行会留在库里：')
  console.log(`         DELETE FROM scores WHERE stu_id=${created.stu_id} AND test_id=99;`)
}
if (scoreResidue) {
  console.log('  [WARN] 成绩删除接口本身异常（不是软删残留），请一并手动清理：')
  console.log(`         DELETE FROM scores WHERE stu_id=${scoreResidue.stu_id};`)
}
if (created.stu_id) await cleanup('就业信息', `/employment/delete/${created.stu_id}`)
if (created.stu_id) await cleanup('学生', `/student/delete_stu?stu_id=${created.stu_id}`)
if (created.class_id) await cleanup('班级', `/class/delete_class/${created.class_id}`)
if (created.class_teacher_id) await cleanup('班主任', `/class_teacher/delete_class_teacher/${created.class_teacher_id}`)
if (created.agent_id) await cleanup('顾问', `/agent/delete_agent?agent_id=${created.agent_id}`)
if (created.teacher_id) await cleanup('老师', `/teacher/${created.teacher_id}`)

/* =====================================================================
 * 十一、代理链路
 * ================================================================== */
console.log('\n[跨域验证]  浏览器直连后端会被 CORS 拦截，代理链路则不会')
try {
  const direct = await fetch('http://127.0.0.1:8003/student/select_stu_skip?skip=0&limit=1')
  console.log(`  直连后端 status=${direct.status}（浏览器中会被 CORS 拦截，正是用代理的原因）`)
} catch (e) {
  console.log(`  直连后端失败: ${e.message}`)
}
try {
  const viaProxy = await fetch(BASE + '/student/select_stu_skip?skip=0&limit=1')
  console.log(`  经代理 status=${viaProxy.status}（同源，无跨域问题）`)
} catch (e) {
  console.log(`  经代理失败: ${e.message}`)
}

console.log(`\n=== 结果：通过 ${pass} 项，失败 ${fail} 项 ===`)
if (failures.length) {
  console.log('\n失败明细：')
  failures.forEach((f) => console.log('  - ' + f))
  process.exit(1)
}
console.log('全部通过\n')
