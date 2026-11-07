// 校验：前端 src/api/*.ts 里写的每个接口路径，是否都存在于后端当前 openapi 契约里。
// 用法：node scripts/check-api-paths.mjs
import { readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const API_DIR = resolve('src/api')
const BASE = process.env.VERIFY_BASE ?? 'http://127.0.0.1:8003'

const res = await fetch(`${BASE}/openapi.json`)
const spec = await res.json()

// 把 openapi 里的路径归一化成「方法 + 路径模板」
const contract = new Map() // 'GET /student/xxx' -> true
for (const [p, item] of Object.entries(spec.paths)) {
  for (const [m, op] of Object.entries(item)) {
    if (!['get', 'post', 'put', 'delete', 'patch'].includes(m)) continue
    contract.set(`${m.toUpperCase()} ${p}`, op?.summary ?? '')
  }
}

/** 把 '/class/get_class/' + id 这种拼接，统一成 '/class/get_class/{id}' */
function normalizeTemplate(raw) {
  return raw
    .replace(/\$\{[^}]+\}/g, '{p}')      // 模板字符串里的变量
    .replace(/\/\s*\+\s*[A-Za-z_$][\w$]*/g, '/{p}') // 字符串 + 变量
    .replace(/\/\s*\+\s*`[^`]*`/g, '/{p}')
    .replace(/\?.*$/, '')                 // 去掉 query
}

/** 从源码里抠出所有 http 调用：get/post/put/del('path' ...) */
const CALL_RE = /\b(?:get|post|put|del|patch)\s*(?:<[^>]*>)?\s*\(\s*(`[^`]*`|'[^']*')/g

const files = readdirSync(API_DIR).filter((f) => f.endsWith('.ts'))
const problems = []
let total = 0

for (const f of files) {
  const code = readFileSync(join(API_DIR, f), 'utf8')
  for (const m of code.matchAll(CALL_RE)) {
    const raw = m[1].slice(1, -1)
    if (!raw.startsWith('/')) continue
    total++
    const tmpl = normalizeTemplate(raw)
    // m[0] 形如 "put<ClassInfo>('/class/update_class/' + id" —— 方法名就在开头
    // 注意：前端封装里的 del 对应 HTTP 的 DELETE
    const methodMatch = m[0].match(/^\s*(get|post|put|del|patch)\b/)
    const rawMethod = methodMatch ? methodMatch[1] : 'get'
    const method = rawMethod === 'del' ? 'DELETE' : rawMethod.toUpperCase()

    // 把 {p} 换成 openapi 里的任意路径参数名做匹配
    const found = [...contract.keys()].some((key) => {
      const [m2, path] = key.split(' ')
      if (m2 !== method) return false
      if (tmpl === path) return true
      const a = tmpl.replace(/\{p\}/g, '').split('/')
      const b = path.replace(/\{[^}]+\}/g, '').split('/')
      if (a.length !== b.length) return false
      return a.every((seg, i) => seg === b[i] || /\{/.test(path.split('/')[i]) || seg === '')
    })

    if (!found) {
      problems.push({ file: f, raw, tmpl, method })
    }
  }
}

console.log(`前端共 ${total} 个接口调用，契约里共 ${contract.size} 个接口`)
if (!problems.length) {
  console.log('✅ 前端所有接口路径都能在后端契约里找到')
} else {
  console.log(`\n❌ 有 ${problems.length} 个前端路径在后端契约里找不到：\n`)
  for (const p of problems) {
    console.log(`  ${p.method.padEnd(6)} ${p.raw.padEnd(46)} ${p.file}`)
    // 给出后端里最接近的
    const hint = [...contract.keys()].filter((k) => k.split(' ')[1].includes(p.tmpl.split('/')[1] ?? ''))
    if (hint.length) console.log(`         后端相近的: ${hint.slice(0, 4).join('  |  ')}`)
  }
}
