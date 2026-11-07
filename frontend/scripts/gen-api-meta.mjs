/**
 * 从后端 /openapi.json 重新生成 src/types/api-meta.ts（接口速查表）。
 *
 * 用法：node scripts/gen-api-meta.mjs
 *
 * 为什么要有这个脚本：
 *   api-meta.ts 是给开发时翻的「接口清单」。后端改了路由（2026-11-03 班主任
 *   拆到 /class_teacher 就是例子），手改这份表迟早会漏。
 *   这里直接从后端实时契约生成，保证它和后端永远一致。
 */
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const BASE = process.env.VERIFY_BASE ?? 'http://127.0.0.1:8003'
const OUT = resolve('src/types/api-meta.ts')

const res = await fetch(`${BASE}/openapi.json`)
if (!res.ok) {
  console.error(`拉取 openapi 失败：HTTP ${res.status}`)
  process.exit(1)
}
const spec = await res.json()

// 按路径第一段分组
const groups = new Map()
let count = 0
for (const [p, item] of Object.entries(spec.paths)) {
  const seg = p.split('/').filter(Boolean)[0] ?? 'root'
  if (!groups.has(seg)) groups.set(seg, [])
  for (const [m, op] of Object.entries(item)) {
    if (!['get', 'post', 'put', 'delete', 'patch'].includes(m)) continue
    count++
    groups.get(seg).push({
      method: m.toUpperCase(),
      path: p,
      desc: op?.summary ?? '',
    })
  }
}

// 组内按路径排序，路径前缀短的排前面
for (const list of groups.values()) {
  list.sort((a, b) => a.path.localeCompare(b.path) || a.method.localeCompare(b.method))
}

const prefixLines = [...groups.keys()]
  .sort()
  .map((k) => `  ${k}: '/${k}',`)
  .join('\n')

const groupLines = [...groups.entries()]
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([k, list]) => {
    const items = list
      .map((e) => `    { method: '${e.method}', path: '${e.path}', desc: '${e.desc.replace(/'/g, "\\'")}' },`)
      .join('\n')
    return `  ${k}: [\n${items}\n  ],`
  })
  .join('\n')

const content = `/**
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
 * 生成时间对应的后端接口总数：${count}
 */

/** 后端服务信息 */
export const API_INFO = {
  title: '${spec.info?.title ?? '学生管理系统 API'}',
  version: '${spec.info?.version ?? '1.0.0'}',
  baseUrl: '${BASE}',
  docsUrl: '${BASE}/docs',
} as const

/** 后端的路径前缀，与 main.py 的 include_router 一一对应 */
export const API_PREFIX = {
${prefixLines}
} as const

/** 各模块的接口清单：方法 + 路径 + 说明 */
export const API_ENDPOINTS = {
${groupLines}
} as const
`

writeFileSync(OUT, content, 'utf8')
console.log(`已生成 ${OUT}`)
console.log(`  模块 ${groups.size} 个，接口 ${count} 个`)
for (const [k, v] of [...groups.entries()].sort()) console.log(`  ${k.padEnd(16)} ${v.length} 个`)
