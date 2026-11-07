/**
 * =====================================================================
 * 各页面实机截图（docs/screenshots/）
 * ---------------------------------------------------------------------
 * 为什么不用「打开页面 → 手工截图」：
 *   文档里的截图要能复现、固定 1920x1080、并且跟真实后端数据一致。
 *   所以这里用系统自带的 Edge 无头模式 + CDP 驱动，
 *   自动登录（演示模式，前端模拟登录）→ 逐页导航 → 截图落盘。
 *
 * 用法：
 *   node scripts/capture-screenshots.mjs            # 全部
 *   node scripts/capture-screenshots.mjs stat     # 只截名字里含 stat 的
 *
 * 前置条件：前端 dev server 已启动（默认 http://localhost:5173），
 *           后端已启动（默认 http://127.0.0.1:8003）。
 * =====================================================================
 */
import { spawn } from 'node:child_process'
import { mkdir, writeFile, rm } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const BASE = process.env.CAPTURE_BASE ?? 'http://localhost:5173'
const OUT_DIR = path.resolve('docs/screenshots')
const PORT = Number(process.env.CAPTURE_PORT ?? 9333)
const VIEWPORT = {
  width: Number(process.env.CAPTURE_WIDTH ?? 1920),
  height: Number(process.env.CAPTURE_HEIGHT ?? 1080),
}
const PROFILE_DIR = path.resolve('.runtime/edge-shot-profile')

const EDGE_CANDIDATES = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
]

/**
 * 截图清单。
 *   url   相对 BASE 的路径
 *   ready 截图前必须满足的页面状态（轮询到 true 才截）
 *   wait  状态就绪后再多等一会儿，让入场动画 / 图表动画收尾
 */
const TABLE_READY = `(() => {
  const rows = document.querySelectorAll('.el-table__body tr');
  if (!rows.length) return false;
  const mask = document.querySelector('.el-loading-mask');
  if (mask && getComputedStyle(mask).display !== 'none') return false;
  return true;
})()`

/**
 * 图表就绪：至少有一个已经画上东西的 canvas。
 *
 * 【为什么不能写死 canvas 数量】
 *   合并看板以后，统计分析页每个分区的图表数量变了（总览只剩 1 张环形图），
 *   写死「>= 4」会一直等到超时，白白多花 20 秒还拍不到。
 *   改成「有一张画布且宽高不为 0」，哪个页面都成立。
 */
const CANVAS_READY = `(() => {
  const c = document.querySelector('canvas');
  return !!c && c.width > 0 && c.height > 0;
})()`

const SHOTS = [
  { file: '01-登录页.png', url: '/login', ready: `!!document.querySelector('.login-btn')`, wait: 900 },
  { file: '02-学生管理.png', url: '/student/list', ready: TABLE_READY, wait: 900 },
  { file: '03-顾问管理.png', url: '/student/agent', ready: TABLE_READY, wait: 900 },
  { file: '04-学生成绩.png', url: '/score/list', ready: TABLE_READY, wait: 900 },
  { file: '05-就业信息.png', url: '/employment/list', ready: TABLE_READY, wait: 900 },
  { file: '06-班级列表.png', url: '/class/list', ready: TABLE_READY, wait: 900 },
  { file: '07-班主任.png', url: '/class/teacher', ready: TABLE_READY, wait: 900 },
  { file: '08-授课老师.png', url: '/teacher/list', ready: TABLE_READY, wait: 900 },
  { file: '09-统计分析.png', url: '/stat/analysis', ready: CANVAS_READY, wait: 1800 },
  { file: '10-数据大屏.png', url: '/screen', ready: CANVAS_READY, wait: 1800 },
  {
    file: '11-运行日志.png',
    url: '/employment/list',
    ready: TABLE_READY,
    wait: 900,
    logPanel: true,
  },
  { file: '12-404-页面不存在.png', url: '/this-route-does-not-exist', ready: `!!document.querySelector('.page-title, .nf-code, h1')`, wait: 700 },
  { file: '13-退出登录确认.png', url: '/stat/analysis', ready: CANVAS_READY, wait: 900, logout: true },
]

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/** 找到可用的浏览器可执行文件 */
function findBrowser() {
  for (const p of EDGE_CANDIDATES) {
    if (existsSync(p)) return p
  }
  return null
}

/** 极简 CDP 客户端（Node 22+ 自带全局 WebSocket，不需要装依赖） */
async function connect(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl)
    let seq = 0
    const pending = new Map()
    const handlers = []

    ws.addEventListener('open', () =>
      resolve({
        send(method, params = {}) {
          const id = ++seq
          return new Promise((res, rej) => {
            pending.set(id, { res, rej, method })
            ws.send(JSON.stringify({ id, method, params }))
          })
        },
        on(fn) {
          handlers.push(fn)
        },
        close() {
          ws.close()
        },
      }),
    )
    ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.id && pending.has(msg.id)) {
        const { res, rej, method } = pending.get(msg.id)
        pending.delete(msg.id)
        if (msg.error) rej(new Error(`${msg.error.message} (${method})`))
        else res(msg.result)
      } else {
        for (const fn of handlers) fn(msg)
      }
    })
    ws.addEventListener('error', () => reject(new Error('CDP WebSocket 连接失败')))
    ws.addEventListener('close', () => {
      for (const { rej } of pending.values()) rej(new Error('CDP 连接已关闭'))
      pending.clear()
    })
  })
}

/** 等待某个 CDP 事件，返回一个 promise（带超时） */
function waitEvent(client, method, timeout = 20000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`等待 ${method} 超时`)), timeout)
    client.on((msg) => {
      if (msg.method === method) {
        clearTimeout(timer)
        resolve(msg.params)
      }
    })
  })
}

async function main() {
  const filter = process.argv[2]
  const shots = filter ? SHOTS.filter((s) => s.file.includes(filter) || s.url.includes(filter)) : SHOTS
  if (!shots.length) {
    console.error(`没有匹配 "${filter}" 的截图项`)
    process.exit(1)
  }

  const browser = findBrowser()
  if (!browser) {
    console.error('找不到 Edge / Chrome 可执行文件')
    process.exit(1)
  }

  await mkdir(OUT_DIR, { recursive: true })
  await rm(PROFILE_DIR, { recursive: true, force: true })

  const proc = spawn(
    browser,
    [
      '--headless=new',
      `--remote-debugging-port=${PORT}`,
      `--user-data-dir=${PROFILE_DIR}`,
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-gpu',
      'about:blank',
    ],
    { stdio: ['ignore', 'pipe', 'pipe'] },
  )

  let stderr = ''
  proc.stderr.on('data', (d) => {
    stderr += d.toString()
  })
  proc.on('exit', (code) => {
    if (code) console.error(`浏览器进程退出，code=${code}\n${stderr.slice(0, 800)}`)
  })

  const cleanup = () => {
    try {
      proc.kill()
    } catch {
      /* ignore */
    }
  }
  process.on('exit', cleanup)

  // 等 CDP 端点就绪
  let target = null
  for (let i = 0; i < 80; i++) {
    await sleep(300)
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`)
      const list = await res.json()
      target = list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl)
      if (target) break
    } catch (err) {
      if (i % 10 === 0) console.error(`  等待 CDP ... ${err.message}`)
    }
  }
  if (!target?.webSocketDebuggerUrl) {
    console.error('CDP 未就绪')
    console.error(stderr.slice(0, 1500))
    cleanup()
    process.exit(1)
  }

  const client = await connect(target.webSocketDebuggerUrl)
  await client.send('Page.enable')
  await client.send('Runtime.enable')
  await client.send('Emulation.setDeviceMetricsOverride', {
    width: VIEWPORT.width,
    height: VIEWPORT.height,
    deviceScaleFactor: 1,
    mobile: false,
  })

  const evaluate = async (expression) => {
    const r = await client.send('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
    })
    return r?.result?.value
  }

  const navigate = async (url) => {
    const loaded = waitEvent(client, 'Page.loadEventFired')
    await client.send('Page.navigate', { url })
    await loaded
    // 文档截图里不出现小管家：它浮在右下角，会盖住分页器和最后两行操作按钮。
    // 每次导航都要重新注入（换页以后 style 节点就没了）。
    await evaluate(`
      (() => {
        const style = document.createElement('style');
        style.textContent = '.kb-assistant{display:none !important}';
        (document.head || document.documentElement).appendChild(style);
        return true;
      })()
    `)
  }

  const capture = async (file) => {
    const { data } = await client.send('Page.captureScreenshot', {
      format: 'png',
      captureBeyondViewport: false,
    })
    const out = path.join(OUT_DIR, file)
    await writeFile(out, Buffer.from(data, 'base64'))
    console.log(`✓ ${file}`)
  }

  /** 轮询直到页面状态就绪，避免「盲等固定毫秒」拍到半成品 */
  const waitReady = async (expr, timeout = 20000) => {
    const deadline = Date.now() + timeout
    while (Date.now() < deadline) {
      if (await evaluate(expr)) return true
      await sleep(250)
    }
    console.warn(`  ! 等待超时：${expr}`)
    return false
  }

  // 1) 登录页：必须先截，否则写入登录态后 /login 会被守卫弹回首页
  const loginShot = shots.find((s) => s.file === '01-登录页.png')
  if (loginShot) {
    await navigate(BASE + loginShot.url)
    await waitReady(loginShot.ready)
    await sleep(loginShot.wait)
    await capture(loginShot.file)
  }

  // 2) 写入演示登录态（前端模拟登录：localStorage 里放用户信息即可）
  //    用带 query 的地址，避开「导航到同一 URL 不触发 load」的情况
  await navigate(BASE + '/login?seed=1')
  await evaluate(`
    localStorage.setItem('stu_ms_user', JSON.stringify({
      username: 'admin',
      displayName: '系统管理员',
      role: '管理员',
      loginAt: Date.now(),
    }));
    localStorage.setItem('stu_ms_global_state', JSON.stringify({
      isCollapse: false, accordion: true, breadcrumb: true,
      breadcrumbIcon: true, tabs: true, tabsIcon: true, footer: true,
    }));
    true;
  `)

  for (const shot of shots) {
    if (shot.file === '01-登录页.png') continue
    await navigate(BASE + shot.url)
    await waitReady(shot.ready)
    await sleep(shot.wait)

    if (shot.logout) {
      // 打开右上角头像菜单 -> 点「退出登录」-> 截二次确认弹窗
      await evaluate(`document.querySelector('.header-avatar')?.click(); true`)
      await sleep(700)
      await evaluate(`
        (() => {
          const items = [...document.querySelectorAll('.el-dropdown-menu__item')];
          const hit = items.find((el) => (el.textContent || '').includes('退出登录'));
          if (hit) { hit.click(); return true; }
          return false;
        })()
      `)
      await sleep(900)
    }

    if (shot.logPanel) {
      // 点顶栏的「运行日志」图标 -> 截抽屉式日志面板
      await evaluate(`document.querySelector('.log-trigger')?.click(); true`)
      await sleep(1200)
    }

    await capture(shot.file)
  }

  client.close()
  cleanup()
  await sleep(800)
  await rm(PROFILE_DIR, { recursive: true, force: true }).catch(() => {})
  console.log(`\n完成：${shots.length} 张 -> ${OUT_DIR}`)
}

main().catch((err) => {
  console.error('截图失败：', err.message)
  process.exit(1)
})
