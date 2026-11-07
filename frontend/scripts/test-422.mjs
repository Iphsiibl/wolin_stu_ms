/**
 * =====================================================================
 * 422 错误中文化验证（调用真实后端接口）
 * =====================================================================
 * 直接 POST 一个非法学生到后端，拿到真实的 422 明细，
 * 再用与 src/api/http.ts 完全相同的翻译逻辑处理，
 * 验证最终展示给用户的是可读中文。
 *
 * 用法：node scripts/test-422.mjs
 * =====================================================================
 */
const BASE = 'http://localhost:5173/api'

// ---- 与 src/api/http.ts 保持一致的逻辑（修复后）----
const FIELD_LABELS = {
  stu_name: '学生姓名',
  stu_age: '年龄',
  stu_sex: '性别',
  stu_class_id: '班级',
  stu_tel: '手机号',
  stu_from: '生源地',
  stu_school: '毕业院校',
  stu_major: '专业',
  enroll_date: '入学时间',
  gra_date: '毕业时间',
  edu_bg: '学历',
}

function translatePydanticMsg(msg) {
  const rules = [
    [/^Input should be a valid integer/, () => '必须是整数'],
    [/^Input should be a valid number/, () => '必须是数字'],
    [/^Input should be a valid string/, () => '必须是字符串'],
    [/^Input should be a valid date/, () => '必须是合法日期'],
    [/^Input should be a valid email/, () => '必须是合法邮箱'],
    [/^String should have at least (\d+) characters?$/, (m) => `长度至少 ${m[1]} 个字符`],
    [/^String should have at most (\d+) characters?$/, (m) => `长度最多 ${m[1]} 个字符`],
    [/^Input should be greater than or equal to (\d+)$/, (m) => `必须大于等于 ${m[1]}`],
    [/^Input should be greater than (\d+)$/, (m) => `必须大于 ${m[1]}`],
    [/^Input should be less than or equal to (\d+)$/, (m) => `必须小于等于 ${m[1]}`],
    [/^Input should be less than (\d+)$/, (m) => `必须小于 ${m[1]}`],
    [/^String should match pattern/, () => '格式不正确'],
    [/^Field required/, () => '不能为空'],
  ]
  for (const [re, build] of rules) {
    const m = msg.match(re)
    if (m) return build(m)
  }
  return msg
}

function formatValidationErrors(items) {
  return items
    .map((item) => {
      const fieldPath = (item.loc ?? []).slice(1).join('.')
      const label = FIELD_LABELS[fieldPath] ?? fieldPath
      const msg = translatePydanticMsg(item.msg ?? '参数不合法')
      return label ? `${label}：${msg}` : msg
    })
    .join('；')
}

console.log('\n=== 422 错误中文化验证（调用真实后端）===\n')

// 故意提交一个非法学生：年龄 5（<19）、手机号 123（格式错）、缺字段
const payload = {
  stu_name: '错误测试',
  stu_age: 5,
  stu_sex: '男',
  stu_class_id: 1,
  stu_tel: '123',
  stu_from: '成都',
  stu_school: '西安交通大学',
  stu_major: '软件工程',
  enroll_date: '2024-09-01',
  gra_date: '2028-06-30',
}

const res = await fetch(BASE + '/student/add_stu', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
})

const body = await res.json()

console.log(`HTTP 状态码：${res.status}`)
console.log('')
console.log('后端返回的原始明细：')
if (Array.isArray(body.detail)) {
  body.detail.forEach((d) => console.log(`  - ${JSON.stringify(d.loc)} | ${d.msg}`))
} else {
  console.log('  ' + JSON.stringify(body))
}

console.log('')
console.log('前端最终展示给用户的文案：')
if (Array.isArray(body.detail)) {
  console.log('  ' + formatValidationErrors(body.detail))
} else {
  console.log('  ' + (body.detail ?? JSON.stringify(body)))
}

// 断言：不能出现 undefined
const text = formatValidationErrors(body.detail ?? [])
console.log('')
if (text.includes('undefined')) {
  console.log('[FAIL] 文案中出现 undefined')
  process.exit(1)
} else {
  console.log('[OK] 文案无 undefined，全部为可读中文')
}
