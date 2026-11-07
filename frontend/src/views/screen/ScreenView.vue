/**
 * =====================================================================
 * 数据大屏（独立路由 /screen）
 * ---------------------------------------------------------------------
 * 布局参考经典「驾驶舱」大屏的三列结构：
 *   左列：核心大数 + 环形构成 + 滚动明细表
 *   中列：标题 + KPI 条 + 主视觉排行 + 薪资榜
 *   右列：学历构成 + 薪资区间 + 成绩趋势
 *
 * 【配色说明】
 *   整屏用【墨色深底】而不是常见的科技蓝 —— 大屏是同一套「教务墨册」
 *   系统在暗环境下的延伸，所以沿用同一套颜色逻辑，并且严格照搬
 *   styles/theme.css 里各颜色的「职责分工」：
 *     靛蓝 #5b8ac4  通用数据（面板 / 排行 / 柱线图）—— 大屏主色
 *     赭黄 #d4a04a  就业 / 薪资 / 排行榜前三名
 *     青绿 #4fb99a  达标 / 已就业 / 全优学员
 *     紫   #9b7fd4  分类构成里的「另一类」（女生 / 大专）
 *     朱砂 #e0574a  只用于预警（两科不及格）和标题匾额的上下勾边
 *   底色 #0b1119，文字 #e9eef4。
 *   —— 朱砂不再大面积铺数据，跟后台「朱只出现在激活/预警/删除」的规矩一致。
 *
 * 【自适应】
 *   画布固定 1920×1080，用 transform: scale() 等比缩放到窗口，
 *   这样布局在任意分辨率下都保持设计稿的比例，不会错位。
 *
 * 【数据来源】全部走前端 api 层，不直接调后端；
 *   后端接口形状变了，只需要改 src/api/**，这个页面不用动。
 * =====================================================================
 */
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { graphic, registerMap, use } from 'echarts/core'
import { BarChart, GaugeChart, HeatmapChart, LineChart, MapChart, PieChart } from 'echarts/charts'
import {
  GeoComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import screenfull from 'screenfull'

import { fetchAllClasses, fetchAllClassTeachers } from '@/api/class'
import { fetchEmploymentPage, fetchUnemployed } from '@/api/employment'
import {
  fetchAllAbove80,
  fetchAvgScoreByClass,
  fetchClassStatistics,
  fetchEmpDestination,
  fetchEmpDuration,
  fetchFailedTwice,
  fetchTop5Salary,
  type EmpDestination,
} from '@/api/stat'
import { fetchAllAgents, fetchAllStudents } from '@/api/student'
import { fetchAllTeachers } from '@/api/teacher'
import type { AvgScoreByClass, ClassStatistics, Top5Salary } from '@/types/models'

use([
  BarChart,
  LineChart,
  PieChart,
  GaugeChart,
  // 就业热力中国地图要用：地图系列 + 热力系列 + geo 坐标系 + visualMap 色阶
  MapChart,
  HeatmapChart,
  GeoComponent,
  VisualMapComponent,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
])

/* ---------------------------------------------------------------------
 * 大屏色板 —— 与 styles/theme.css「教务墨册」同源。
 *
 * 主题里每个颜色都有固定职责，这里一一对应，不混用：
 *   靛蓝 indigo  通用数据    —— 面板、排行、柱状图、折线图
 *   赭黄 ochre   就业 / 薪资 —— 薪资区间、薪资榜、排行榜前三
 *   青绿 jade    达标 / 全优 —— 已就业人数、全优学员
 *   朱砂 seal    预警 / 强调 —— 两科不及格、屏幕印章
 * ------------------------------------------------------------------ */
const SEAL = '#e0574a'
const INDIGO = '#5b8ac4'
const OCHRE = '#d4a04a'
const JADE = '#4fb99a'
const VIOLET = '#9b7fd4'
const TEXT = '#e9eef4'
const TEXT_SUB = '#8d9bad'

/** 靛蓝的 rgba 变体，样式表里也用同一组数值 */
const INDIGO_RGB = '91, 138, 196'
const OCHRE_RGB = '212, 160, 74'
const JADE_RGB = '79, 185, 154'
const SEAL_RGB = '224, 87, 74'

/**
 * 把色板注入成 CSS 变量，样式表里写 var(--indigo) 就能取到值。
 * 这样 JS（ECharts）和 CSS（样式表）共用同一份真值，
 * 以后换配色只改上面这几个常量，不用两边对改。
 */
const paletteVars = {
  '--seal': SEAL,
  '--indigo': INDIGO,
  '--ochre': OCHRE,
  '--jade': JADE,
  '--violet': VIOLET,
  '--seal-rgb': SEAL_RGB,
  '--indigo-rgb': INDIGO_RGB,
  '--ochre-rgb': OCHRE_RGB,
  '--jade-rgb': JADE_RGB,
} as Record<string, string>

const router = useRouter()

/* ---------------------------------------------------------------------
 * 画布缩放
 * ------------------------------------------------------------------ */
const DESIGN_W = 1920
const DESIGN_H = 1080
const scale = ref(1)

function updateScale() {
  const s = Math.min(window.innerWidth / DESIGN_W, window.innerHeight / DESIGN_H)
  scale.value = s
}

/* ---------------------------------------------------------------------
 * 顶部时钟
 * ------------------------------------------------------------------ */
const now = ref(new Date())
let clockTimer: number | undefined

const WEEK = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const clockTime = computed(() => {
  const d = now.value
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
})
const clockDate = computed(() => {
  const d = now.value
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} ${WEEK[d.getDay()]}`
})
const clockTimeParts = computed(() => clockTime.value.split(':'))

/* ---------------------------------------------------------------------
 * 数据
 * ------------------------------------------------------------------ */
const loading = ref(true)
const loadError = ref('')
const updatedAt = ref('')

const students = ref<any[]>([])
const classStats = ref<ClassStatistics[]>([])
const top5 = ref<Top5Salary[]>([])
const avgScores = ref<AvgScoreByClass[]>([])
const unemployed = ref<any[]>([])
const employments = ref<any[]>([])
const empDurations = ref<any[]>([])
const classCount = ref(0)
const teacherCount = ref(0)
const classTeacherCount = ref(0)
const agentCount = ref(0)
const above80Count = ref(0)
const failedCount = ref(0)

/* ---------------------------------------------------------------------
 * 就业去向热力中国地图
 * ------------------------------------------------------------------ */
const destinations = ref<EmpDestination[]>([])
/** 省份中心点：省名 -> [经度, 纬度]（从 china.json 的 properties.cp 里取） */
const provinceCenters = ref<Record<string, [number, number]>>({})
/** china.json 原始数据，注册给 echarts 用 */
const chinaGeo = ref<unknown>(null)
/** 地图加载失败的原因（空字符串 = 没失败） */
const mapError = ref('')
/** 当前选中的省份（点地图上的省份切换） */
const selectedProvince = ref('')

/** 地图准备好了没有 —— 没准备好就不渲染图表，只画占位提示 */
const mapReady = computed(() => !!chinaGeo.value && !mapError.value)

/**
 * 加载中国地图底图。
 *
 * 走运行时 fetch 而不是打包 import，是为了让 geoJSON 单独缓存，
 * 也为了兼容子路径部署（BASE_URL 可能是 /xxx/）。
 * 加载失败不抛错，只记下原因 —— 面板里显示「地图数据加载失败」，
 * 大屏其它面板照常工作。
 */
async function loadChinaMap() {
  mapError.value = ''
  try {
    const url = `${import.meta.env.BASE_URL}geo/china.json`
    const res = await fetch(url)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const json = await res.json()
    if (!json || !Array.isArray(json.features) || !json.features.length) {
      throw new Error('geoJSON 数据异常')
    }

    // 每个省的中心点（[经度, 纬度]）——热力点靠它摆到省份位置上
    const centers: Record<string, [number, number]> = {}
    for (const f of json.features) {
      const name = f?.properties?.name
      const cp = f?.properties?.cp
      if (name && Array.isArray(cp) && cp.length >= 2) {
        centers[name] = [Number(cp[0]), Number(cp[1])]
      }
    }

    provinceCenters.value = centers
    chinaGeo.value = json
    registerMap('china', json)
  } catch (e) {
    mapError.value = e instanceof Error ? e.message : '未知错误'
    chinaGeo.value = null
  }
}

/**
 * 拉就业去向数据。
 *
 * 单独一个函数自己兜底：这个接口挂了也不该把整屏拖下水，
 * 只是地图上没有热力点而已。
 */
async function loadDestination() {
  try {
    const res = await fetchEmpDestination()
    destinations.value = res.data ?? []
  } catch {
    destinations.value = []
  }
}

/** 能上图的省份（归不到省份的「其他」不上图） */
const provinceList = computed(() => destinations.value.filter((d) => d.province !== '其他'))

/** 当前选中的省份那一行 */
const selectedRow = computed(
  () => provinceList.value.find((p) => p.province === selectedProvince.value) ?? null,
)

/** 榜单条目：默认显示去向最多的省份，选中省份后显示该省的去向公司 */
interface MapListItem {
  name: string
  sub: string
  count: number
  value: string
}

const mapList = computed<MapListItem[]>(() => {
  const sel = selectedRow.value
  if (sel) {
    return sel.companies.slice(0, 5).map((c) => ({
      name: c.company,
      sub: c.city,
      count: c.count,
      value: `均 ¥${Number(c.avg_salary).toLocaleString('zh-CN')}`,
    }))
  }
  return provinceList.value.slice(0, 5).map((p) => ({
    name: p.province,
    sub: p.city,
    count: p.count,
    value: `均 ¥${Number(p.avg_salary).toLocaleString('zh-CN')}`,
  }))
})

/** 榜单抬头 */
const mapListTitle = computed(() =>
  selectedRow.value ? `${selectedRow.value.province} · 去向公司 TOP 5` : '去向省份 TOP 5',
)

/** 榜单右侧的说明 */
const mapListNote = computed(() =>
  selectedRow.value
    ? `${selectedRow.value.count} 人 · 均 ¥${Number(selectedRow.value.avg_salary).toLocaleString('zh-CN')}`
    : '点击地图省份查看去向公司',
)

/** 地图配置：visualMap + heatmap（坐标系用 geo） */
const mapOption = computed(() => {
  // 只取地图上有的省份（中心点对不上的就不画点）
  const points = provinceList.value
    .filter((p) => provinceCenters.value[p.province])
    .map((p) => {
      const [lng, lat] = provinceCenters.value[p.province]
      return { name: p.province, value: [lng, lat, p.count] }
    })

  const maxCount = points.length ? Math.max(...points.map((p) => p.value[2])) : 1

  return {
    tooltip: {
      trigger: 'item',
      ...tooltipStyle,
      formatter: (params: any) => {
        const row = provinceList.value.find((p) => p.province === params.name)
        if (!row) return String(params.name ?? '')
        const top = row.companies
          .slice(0, 3)
          .map((c) => `${c.company}（${c.count} 人）`)
          .join('、')
        return (
          `<div style="min-width:170px">` +
          `<div style="font-size:14px;font-weight:600">${row.province} · ${row.city}</div>` +
          `<div style="margin-top:4px">就业人数：${row.count} 人</div>` +
          `<div>平均薪资：¥${Number(row.avg_salary).toLocaleString('zh-CN')}/月</div>` +
          `<div>最高薪资：¥${Number(row.max_salary).toLocaleString('zh-CN')}/月</div>` +
          `<div style="margin-top:4px;color:#8d9bad">主要去向：${top || '—'}</div>` +
          `</div>`
        )
      },
    },
    visualMap: {
      min: 0,
      max: maxCount,
      dimension: 2,
      left: 10,
      bottom: 10,
      calculable: true,
      itemWidth: 10,
      itemHeight: 92,
      text: ['多', '少'],
      textStyle: { color: TEXT_SUB, fontSize: 11 },
      /* 色阶沿用大屏的赭黄 / 青绿 / 朱砂体系：人少偏靛，人多偏朱砂 */
      inRange: {
        color: ['rgba(91, 138, 196, 0.45)', '#4fb99a', '#d4a04a', '#e0574a'],
      },
    },
    geo: {
      map: 'china',
      roam: false,
      layoutCenter: ['50%', '50%'],
      layoutSize: '92%',
      itemStyle: {
        areaColor: 'rgba(91, 138, 196, 0.1)',
        borderColor: 'rgba(91, 138, 196, 0.45)',
        borderWidth: 1,
      },
      emphasis: {
        itemStyle: { areaColor: 'rgba(212, 160, 74, 0.22)' },
        label: { show: false },
      },
      /* 选中的省份描一道赭黄边 */
      regions: selectedRow.value
        ? [
            {
              name: selectedRow.value.province,
              itemStyle: {
                areaColor: 'rgba(212, 160, 74, 0.25)',
                borderColor: '#d4a04a',
                borderWidth: 1.5,
              },
            },
          ]
        : [],
    },
    series: [
      {
        type: 'heatmap',
        coordinateSystem: 'geo',
        data: points,
        /* pointSize 必须是【数字】：ECharts 内部拿它算热力笔刷画布的边长
           （(pointSize + blurSize) * 2），写成回调会算出 NaN，
           画布就变成 0 宽 0 高，热力点一个都画不出来。
           人数的大小交给 visualMap 的色阶表达。 */
        pointSize: Math.max(12, Math.min(26, Math.round(maxCount / 4))),
        blurSize: 16,
        itemStyle: {
          borderColor: 'rgba(11, 17, 25, 0.55)',
          borderWidth: 1,
        },
        emphasis: {
          itemStyle: { borderColor: SEAL, borderWidth: 2 },
        },
      },
    ],
  }
})

/** 点地图上的省份 —— 切换下方的去向公司榜单 */
function onMapClick(params: any) {
  const name = params?.name
  if (!name) return
  const hit = provinceList.value.find((p) => p.province === name)
  if (!hit) return
  selectedProvince.value = hit.province
}

/**
 * 就业信息分页拉全量。
 * 后端 /employment/page 的 size 上限是 100，总量 149 条，
 * 所以得分页循环拉，不能只要第一页。
 */
async function fetchAllEmployment(): Promise<any[]> {
  const first = await fetchEmploymentPage({ page: 1, size: 100 })
  const all = [...(first.data ?? [])]
  const pages = Math.ceil((first.total || all.length) / 100)
  for (let p = 2; p <= pages; p++) {
    const r = await fetchEmploymentPage({ page: p, size: 100 })
    all.push(...(r.data ?? []))
  }
  return all
}

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    const [stuRes, classRes, top5Res, durRes, avgRes, aboveRes, failedRes, unempRes, empList, clsRes, ctRes, teacherRes, agentRes] =
      await Promise.all([
        fetchAllStudents(),
        fetchClassStatistics(),
        fetchTop5Salary(),
        fetchEmpDuration(),
        fetchAvgScoreByClass(),
        fetchAllAbove80(),
        fetchFailedTwice(),
        fetchUnemployed(),
        fetchAllEmployment(),
        fetchAllClasses(),
        fetchAllClassTeachers(),
        fetchAllTeachers(),
        fetchAllAgents(),
      ])

    students.value = stuRes.data ?? []
    classStats.value = classRes.data ?? []
    top5.value = top5Res.data ?? []
    avgScores.value = avgRes.data ?? []
    unemployed.value = unempRes.data ?? []
    employments.value = empList
    empDurations.value = durRes.data ?? []
    classCount.value = (clsRes.data ?? []).length
    classTeacherCount.value = (ctRes.data ?? []).length
    teacherCount.value = (teacherRes.data ?? []).length
    agentCount.value = (agentRes.data ?? []).length
    above80Count.value = new Set((aboveRes.data ?? []).map((r: any) => r.stu_id)).size
    failedCount.value = new Set((failedRes.data ?? []).map((r: any) => r.stu_id)).size
    updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    /* 就业去向单独拉：它挂了也不该把整屏拖下水 */
    await loadDestination()
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '数据加载失败'
  } finally {
    loading.value = false
  }
}

/* ---------------------------------------------------------------------
 * 派生指标
 * ------------------------------------------------------------------ */
const studentTotal = computed(() => students.value.length)
const employedTotal = computed(() => employments.value.length)
const unemployedTotal = computed(() => unemployed.value.length)
const employRate = computed(() =>
  studentTotal.value ? employedTotal.value / studentTotal.value : 0,
)

const maleCount = computed(() => students.value.filter((s) => s.stu_sex === '男').length)
const femaleCount = computed(() => students.value.filter((s) => s.stu_sex === '女').length)

const avgSalary = computed(() => {
  const list = employments.value.filter((e) => Number(e.salary) > 0)
  if (!list.length) return 0
  return Math.round(list.reduce((s, e) => s + Number(e.salary), 0) / list.length)
})

/**
 * 平均就业周期（天）。
 *
 * 后端 /stat/emp/duration 返回的 duration_text 是格式化好的文案，
 * 但要做平均需要原始天数，所以这里按 open_date / offer_date 自己算。
 */
const avgEmployDays = computed(() => {
  const days = empDurations.value
    .map((d: any) => {
      const open = new Date(d.open_date).getTime()
      const offer = new Date(d.offer_date).getTime()
      if (!open || !offer || Number.isNaN(open) || Number.isNaN(offer)) return null
      return Math.max(0, Math.round((offer - open) / 86400000))
    })
    .filter((v): v is number => v !== null)
  if (!days.length) return 0
  return Math.round(days.reduce((s, v) => s + v, 0) / days.length)
})

/** 平均就业周期的中文文案 */
const avgEmployText = computed(() => {
  const d = avgEmployDays.value
  if (!d) return '-'
  const months = Math.floor(d / 30)
  const rest = d % 30
  if (months <= 0) return `${rest} 天`
  return rest ? `${months} 个月 ${rest} 天` : `${months} 个月`
})

/* 学历构成 */
const eduDist = computed(() => {
  const map = new Map<string, number>()
  for (const s of students.value) {
    const key = s.edu_bg && s.edu_bg !== 'string' ? s.edu_bg : '其他'
    map.set(key, (map.get(key) ?? 0) + 1)
  }
  return [...map.entries()].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value)
})

/* 年龄段构成 */
const ageDist = computed(() => {
  const buckets = [
    { name: '19-21岁', min: 18, max: 21 },
    { name: '22-24岁', min: 22, max: 24 },
    { name: '25-27岁', min: 25, max: 99 },
  ]
  return buckets.map((b) => ({
    name: b.name,
    value: students.value.filter((s) => s.stu_age >= b.min && s.stu_age <= b.max).length,
  }))
})

/* 薪资区间分布 */
const salaryDist = computed(() => {
  const buckets = [
    { name: '8K以下', min: 0, max: 7999 },
    { name: '8-12K', min: 8000, max: 11999 },
    { name: '12-18K', min: 12000, max: 17999 },
    { name: '18-25K', min: 18000, max: 24999 },
    { name: '25K以上', min: 25000, max: 999999 },
  ]
  return buckets.map((b) => ({
    name: b.name,
    value: employments.value.filter((e) => {
      const v = Number(e.salary)
      return v >= b.min && v <= b.max
    }).length,
  }))
})

/* 班级人数 Top10 */
const topClasses = computed(() =>
  [...classStats.value].sort((a, b) => b.total - a.total).slice(0, 10),
)

/* 每次考试的班级平均分（取每场考试的全局平均，做成趋势线） */
const scoreTrend = computed(() => {
  const byTest = new Map<number, number[]>()
  for (const r of avgScores.value) {
    if (r.avg_score === null || r.avg_score === undefined) continue
    const arr = byTest.get(r.test_id) ?? []
    arr.push(Number(r.avg_score))
    byTest.set(r.test_id, arr)
  }
  const points = [...byTest.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([testId, arr]) => ({
      testId,
      avg: arr.reduce((s, v) => s + v, 0) / arr.length,
    }))
  return points
})

/* 待就业学员滚动表（取前 14 条，复制一份做无缝循环） */
const scrollRows = computed(() => {
  const rows = unemployed.value.slice(0, 14)
  return rows.length ? [...rows, ...rows] : []
})

/* ---------------------------------------------------------------------
 * ECharts 配置
 * ------------------------------------------------------------------ */
const axisLabelColor = TEXT_SUB
const splitLineColor = `rgba(${INDIGO_RGB}, 0.16)`

const tooltipStyle = {
  backgroundColor: 'rgba(20, 28, 38, 0.92)',
  borderColor: `rgba(${INDIGO_RGB}, 0.45)`,
  textStyle: { color: TEXT, fontSize: 12 },
}

/**
 * 生成「图例自带数值 + 环心总数字」的环形图配置。
 *
 * 之前用外侧文字标签（label + labelLine），学历构成有 4 个扇区时
 * 标签会挤成一团互相压字。改成：
 *   · 外侧标签关掉，改由图例直接写「本科 153人」
 *   · 环心总数字用 HTML 覆盖层写（见模板里的 .donut-center），
 *     比用第二个「零半径饼图」可靠 —— 那种写法在 ECharts 6 下
 *     富文本的两行会叠在一起（数字压住文字）。
 */
function donutOption(
  data: { name: string; value: number }[],
  colors: string[],
  colorMap?: Record<string, string>,
) {
  return {
    tooltip: { trigger: 'item', ...tooltipStyle, formatter: '{b}: {c} 人 ({d}%)' },
    legend: {
      bottom: 0,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: TEXT_SUB, fontSize: 12 },
      formatter: (name: string) => {
        const hit = data.find((d) => d.name === name)
        return hit ? `${name}  ${hit.value}人` : name
      },
    },
    series: [
      {
        type: 'pie',
        radius: ['52%', '74%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: { borderColor: '#121a24', borderWidth: 3, borderRadius: 6 },
        data: data.map((d, i) => ({
          ...d,
          /* 有色表就按名字取色 —— 分类的先后顺序会变，颜色不该跟着乱跳 */
          itemStyle: { color: colorMap?.[d.name] ?? colors[i % colors.length] },
        })),
      },
    ],
  }
}

/** 性别环形图 */
const genderOption = computed(() =>
  donutOption(
    [
      { name: '男生', value: maleCount.value },
      { name: '女生', value: femaleCount.value },
    ],
    [INDIGO, VIOLET],
  ),
)

/** 学历环形图：颜色跟学历本身绑定，不跟排序绑定 */
const EDU_COLOR_MAP: Record<string, string> = {
  本科: INDIGO,
  硕士: JADE,
  大专: VIOLET,
  其他: '#6b7a89',
}

const eduOption = computed(() =>
  donutOption(eduDist.value, [INDIGO, JADE, VIOLET, '#6b7a89'], EDU_COLOR_MAP),
)

/** 年龄段柱状图 */
const ageOption = computed(() => ({
  tooltip: { trigger: 'axis', ...tooltipStyle },
  grid: { left: 38, right: 14, top: 24, bottom: 26 },
  xAxis: {
    type: 'category',
    data: ageDist.value.map((d) => d.name),
    axisLabel: { color: axisLabelColor, fontSize: 11 },
    axisLine: { lineStyle: { color: splitLineColor } },
    axisTick: { show: false },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    axisLabel: { color: axisLabelColor, fontSize: 11 },
    splitLine: { lineStyle: { color: splitLineColor } },
  },
  series: [
    {
      type: 'bar',
      data: ageDist.value.map((d) => d.value),
      barMaxWidth: 26,
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: new graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: INDIGO },
          { offset: 1, color: `rgba(${INDIGO_RGB}, 0.15)` },
        ]),
      },
    },
  ],
}))

/** 薪资区间柱状图（赭黄 = 就业 / 薪资） */
const salaryOption = computed(() => ({
  tooltip: { trigger: 'axis', ...tooltipStyle },
  grid: { left: 40, right: 14, top: 24, bottom: 26 },
  xAxis: {
    type: 'category',
    data: salaryDist.value.map((d) => d.name),
    axisLabel: { color: axisLabelColor, fontSize: 11, interval: 0 },
    axisLine: { lineStyle: { color: splitLineColor } },
    axisTick: { show: false },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    axisLabel: { color: axisLabelColor, fontSize: 11 },
    splitLine: { lineStyle: { color: splitLineColor } },
  },
  series: [
    {
      type: 'bar',
      data: salaryDist.value.map((d) => d.value),
      barMaxWidth: 26,
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: new graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: OCHRE },
          { offset: 1, color: `rgba(${OCHRE_RGB}, 0.12)` },
        ]),
      },
    },
  ],
}))

/** 成绩趋势折线图 */
const scoreOption = computed(() => ({
  tooltip: { trigger: 'axis', ...tooltipStyle },
  grid: { left: 42, right: 16, top: 26, bottom: 28 },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: scoreTrend.value.map((p) => `第${p.testId}次`),
    axisLabel: { color: axisLabelColor, fontSize: 11 },
    axisLine: { lineStyle: { color: splitLineColor } },
    axisTick: { show: false },
  },
  yAxis: {
    type: 'value',
    min: 40,
    max: 100,
    axisLabel: { color: axisLabelColor, fontSize: 11 },
    splitLine: { lineStyle: { color: splitLineColor } },
  },
  series: [
    {
      type: 'line',
      smooth: true,
      symbolSize: 7,
      data: scoreTrend.value.map((p) => Number(p.avg.toFixed(1))),
      lineStyle: { width: 2.5, color: INDIGO },
      itemStyle: { color: INDIGO, borderColor: '#121a24', borderWidth: 2 },
      areaStyle: {
        color: new graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: `rgba(${INDIGO_RGB}, 0.38)` },
          { offset: 1, color: `rgba(${INDIGO_RGB}, 0)` },
        ]),
      },
    },
  ],
}))

/** 就业率仪表盘 */
const gaugeOption = computed(() => ({
  series: [
    {
      type: 'gauge',
      startAngle: 210,
      endAngle: -30,
      min: 0,
      max: 100,
      radius: '92%',
      center: ['50%', '62%'],
      progress: { show: true, width: 12, roundCap: true, itemStyle: { color: OCHRE } },
      axisLine: { lineStyle: { width: 12, color: [[1, `rgba(${OCHRE_RGB}, 0.18)`]] } },
      pointer: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      anchor: { show: false },
      title: { show: true, offsetCenter: [0, '32%'], color: TEXT_SUB, fontSize: 13 },
      detail: {
        valueAnimation: true,
        offsetCenter: [0, '2%'],
        formatter: '{value}%',
        color: OCHRE,
        fontSize: 34,
        fontWeight: 600,
      },
      data: [{ value: Number((employRate.value * 100).toFixed(1)), name: '就业率' }],
    },
  ],
}))

/* ---------------------------------------------------------------------
 * 交互
 * ------------------------------------------------------------------ */
const isFullscreen = ref(false)

async function toggleFullscreen() {
  try {
    if (!screenfull.isEnabled) return
    await screenfull.toggle()
  } catch {
    /* 用户拒绝全屏请求时忽略 */
  }
}

function onFullscreenChange() {
  isFullscreen.value = screenfull.isFullscreen
  updateScale()
}

function goBack() {
  router.push('/stat/analysis')
}

onMounted(() => {
  updateScale()
  window.addEventListener('resize', updateScale)
  clockTimer = window.setInterval(() => (now.value = new Date()), 1000)
  document.addEventListener('fullscreenchange', onFullscreenChange)
  /* 地图底图和统计数据并行拉，谁先回来谁先上屏 */
  loadChinaMap()
  loadAll()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateScale)
  window.clearInterval(clockTimer)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})
</script>

<template>
  <div class="screen-root" :style="paletteVars">
    <div
      class="screen-stage"
      :style="{ transform: `scale(${scale})`, width: `${DESIGN_W}px`, height: `${DESIGN_H}px` }"
    >
      <!-- ===================== 顶部标题栏 ===================== -->
      <header class="screen-header">
        <div class="hd-left">
          <div class="clock">
            <span v-for="(part, i) in clockTimeParts" :key="i" class="clock-part">
              {{ part }}<i v-if="i < 2">:</i>
            </span>
          </div>
          <div class="clock-date">{{ clockDate }}</div>
        </div>

        <h1 class="hd-title">
          <span class="hd-title-text">学生管理系统 · 数据驾驶舱</span>
        </h1>

        <div class="hd-right">
          <div class="hd-meta">
            <span class="hd-meta-label">数据更新</span>
            <span class="hd-meta-value">{{ updatedAt || '--:--:--' }}</span>
          </div>
          <button class="hd-btn" type="button" @click="toggleFullscreen">
            {{ isFullscreen ? '退出全屏' : '全屏显示' }}
          </button>
          <button class="hd-btn hd-btn-primary" type="button" @click="goBack">返回后台</button>
        </div>
      </header>

      <!-- ===================== 主体三列 ===================== -->
      <div class="screen-body">
        <!-- ---------- 左列 ---------- -->
        <section class="col col-left">
          <!-- 核心大数 -->
          <div class="panel panel-hero">
            <div class="panel-bar"></div>
            <div class="hero-label">在读学员总数</div>
            <div class="hero-value">{{ studentTotal.toLocaleString('zh-CN') }}</div>
            <div class="hero-sub">
              <span class="hero-sub-item">
                已就业 <b class="c-jade">{{ employedTotal }}</b>
              </span>
              <span class="hero-divider">|</span>
              <span class="hero-sub-item">
                待就业 <b class="c-ochre">{{ unemployedTotal }}</b>
              </span>
            </div>
          </div>

          <!-- 性别构成 -->
          <div class="panel panel-chart">
            <div class="panel-title">学员性别构成</div>
            <div class="donut-wrap">
              <div class="donut-box">
                <v-chart :option="genderOption" style="height: 190px" autoresize />
                <div class="donut-center">
                  <div class="donut-center-num">{{ studentTotal.toLocaleString('zh-CN') }}</div>
                  <div class="donut-center-sub">学员总数</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 待就业滚动表 -->
          <div class="panel panel-table">
            <div class="panel-title">待就业学员实时名录</div>
            <div class="mini-table">
              <div class="mini-head">
                <span>姓名</span>
                <span>班级</span>
                <span>顾问</span>
                <span>电话</span>
              </div>
              <div class="mini-viewport">
                <div class="mini-body">
                  <div v-for="(row, i) in scrollRows" :key="`${row.stu_id}-${i}`" class="mini-row">
                    <span class="c-text">{{ row.stu_name }}</span>
                    <span class="c-text">{{ row.class_name || '-' }}</span>
                    <span class="c-text">{{ row.agent_name || '-' }}</span>
                    <span class="c-sub">{{ row.stu_tel || '-' }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- ---------- 中列 ---------- -->
        <section class="col col-center">
          <!-- KPI 条 -->
          <div class="kpi-row">
            <!-- 口径提示：
                 这里的「班级总数」取自 /class/all_class —— 全部在册班级（72），
                 含暂时没有学员的空班；
                 而下面的「班级在读人数排行」来自 /stat/class/statistics ——
                 只有 59 个班有学员（浅色看板的「班级数量」也是这个口径）。
                 悬浮提示写清楚，避免两个页面数字看着打架。 -->
            <div class="kpi" title="全部在册班级（含暂无学员的班级）；下方排行只统计有学员的班级">
              <div class="kpi-value">{{ classCount }}</div>
              <div class="kpi-label">班级总数</div>
            </div>
            <div class="kpi" title="在册授课老师人数">
              <div class="kpi-value">{{ teacherCount }}</div>
              <div class="kpi-label">授课老师</div>
            </div>
            <div class="kpi" title="在册班主任人数">
              <div class="kpi-value">{{ classTeacherCount }}</div>
              <div class="kpi-label">班主任</div>
            </div>
            <div class="kpi" title="在册招生顾问人数">
              <div class="kpi-value">{{ agentCount }}</div>
              <div class="kpi-label">招生顾问</div>
            </div>
            <div class="kpi" title="有两次及以上考试不及格的学员数">
              <div class="kpi-value c-seal">{{ failedCount }}</div>
              <div class="kpi-label">两科不及格</div>
            </div>
            <div class="kpi" title="每场考试平均分都在 80 分以上的学员数">
              <div class="kpi-value c-jade">{{ above80Count }}</div>
              <div class="kpi-label">全优学员</div>
            </div>
          </div>

          <!-- 中段：班级人数排行 + 就业去向热力中国地图 -->
          <div class="center-mid">
            <!-- 主视觉：班级人数排行 -->
            <div class="panel panel-rank">
              <div class="panel-title">班级在读人数排行 TOP 10</div>
              <div class="rank-list">
                <div v-for="(c, i) in topClasses" :key="c.class_id" class="rank-item">
                  <span class="rank-no" :class="{ 'rank-no-top': i < 3 }">NO.{{ i + 1 }}</span>
                  <span class="rank-name" :title="c.class_name">{{ c.class_name }}</span>
                  <div class="rank-bar-wrap">
                    <div
                      class="rank-bar"
                      :style="{
                        width: topClasses[0]?.total ? (c.total / topClasses[0].total) * 100 + '%' : '0%',
                      }"
                    ></div>
                  </div>
                  <span class="rank-value">{{ c.total }} 人</span>
                </div>
              </div>
            </div>

            <!-- 就业去向热力中国地图 -->
            <div class="panel panel-map">
              <div class="panel-title">就业去向热力中国地图</div>

              <div class="map-chart">
                <v-chart
                  v-if="mapReady"
                  :option="mapOption"
                  style="height: 100%"
                  autoresize
                  @click="onMapClick"
                />
                <!-- 地图没加载出来时的占位：不影响大屏其它面板 -->
                <div v-else class="map-fallback">
                  <span class="map-fallback-text">
                    {{ mapError ? '地图数据加载失败' : '地图加载中…' }}
                  </span>
                  <span v-if="mapError" class="map-fallback-sub">{{ mapError }}</span>
                </div>
              </div>

              <!-- 榜单：默认是去向省份 Top5，点地图上的省份后切成该省的去向公司 -->
              <div class="map-list">
                <div class="map-list-head">
                  <span class="map-list-title">{{ mapListTitle }}</span>
                  <span class="map-list-note">{{ mapListNote }}</span>
                </div>
                <div class="map-list-body">
                  <div v-for="(item, i) in mapList" :key="item.name" class="map-list-row">
                    <span class="rank-no" :class="{ 'rank-no-top': i < 3 }">NO.{{ i + 1 }}</span>
                    <span class="map-list-name" :title="item.name">{{ item.name }}</span>
                    <span class="map-list-sub">{{ item.sub }}</span>
                    <span class="map-list-count">{{ item.count }} 人</span>
                    <span class="map-list-value">{{ item.value }}</span>
                  </div>
                  <div v-if="!mapList.length" class="map-list-empty">暂无就业去向数据</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 底部：就业率仪表 + 薪资榜 -->
          <div class="center-bottom">
            <div class="panel panel-gauge">
              <div class="panel-title">整体就业率</div>
              <v-chart :option="gaugeOption" style="height: 190px" autoresize />
              <div class="gauge-extra">
                平均薪资 <b class="c-ochre">¥{{ avgSalary.toLocaleString('zh-CN') }}</b>
              </div>
              <div class="gauge-extra">
                平均就业周期 <b class="c-ochre">{{ avgEmployText }}</b>
              </div>
            </div>

            <div class="panel panel-salary">
              <div class="panel-title">就业薪资 TOP 5</div>
              <div class="salary-list">
                <div v-for="(t, i) in top5" :key="t.stu_id" class="salary-item">
                  <span class="rank-no" :class="{ 'rank-no-top': i < 3 }">NO.{{ i + 1 }}</span>
                  <div class="salary-main">
                    <div class="salary-name">
                      {{ t.stu_name }}
                      <span class="salary-company">{{ t.company }}</span>
                    </div>
                    <div class="salary-meta">学号 {{ t.stu_id }} · 班级 {{ t.class_id }}</div>
                  </div>
                  <div class="salary-value">¥{{ Number(t.salary).toLocaleString('zh-CN') }}</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- ---------- 右列 ---------- -->
        <section class="col col-right">
          <div class="panel panel-chart">
            <div class="panel-title">学员学历构成</div>
            <div class="donut-wrap">
              <div class="donut-box">
                <v-chart :option="eduOption" style="height: 190px" autoresize />
                <div class="donut-center">
                  <div class="donut-center-num">{{ studentTotal.toLocaleString('zh-CN') }}</div>
                  <div class="donut-center-sub">学员总数</div>
                </div>
              </div>
            </div>
          </div>

          <div class="panel panel-chart">
            <div class="panel-title">就业薪资区间分布</div>
            <v-chart :option="salaryOption" style="height: 190px" autoresize />
          </div>

          <div class="panel panel-chart">
            <div class="panel-title">各场考试平均分趋势</div>
            <v-chart :option="scoreOption" style="height: 190px" autoresize />
          </div>

          <div class="panel panel-chart panel-age">
            <div class="panel-title">学员年龄段分布</div>
            <v-chart :option="ageOption" style="height: 150px" autoresize />
          </div>
        </section>
      </div>

      <!-- 加载 / 错误遮罩 -->
      <div v-if="loading" class="screen-mask">
        <div class="mask-text">数据加载中…</div>
      </div>
      <div v-else-if="loadError" class="screen-mask screen-mask-error">
        <div class="mask-text">加载失败：{{ loadError }}</div>
        <button class="hd-btn hd-btn-primary" type="button" @click="loadAll">重新加载</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* =====================================================================
 * 大屏根容器：墨绿深色底 + 中心光晕
 * ================================================================== */
.screen-root {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background:
    radial-gradient(ellipse 70% 55% at 50% 8%, rgba(var(--indigo-rgb), 0.22), transparent 70%),
    radial-gradient(ellipse 50% 40% at 12% 92%, rgba(var(--indigo-rgb), 0.12), transparent 70%),
    #0b1119;
  color: #e9eef4;
  font-family: var(--font-body);
}

/* 大屏里的数字也用等宽，和后台各页的台账数字保持一致 */
.clock,
.hero-value,
.kpi-value,
.rank-value,
.salary-value,
.gauge-extra {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

/* 细网格纹理，增加大屏质感 */
.screen-root::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(var(--indigo-rgb), 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(var(--indigo-rgb), 0.05) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
}

.screen-stage {
  position: relative;
  flex-shrink: 0;
  transform-origin: center center;
  display: flex;
  flex-direction: column;
  padding: 14px 18px 16px;
  box-sizing: border-box;
}

/* =====================================================================
 * 顶部标题栏
 * ================================================================== */
.screen-header {
  position: relative;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  height: 84px;
  flex-shrink: 0;
}

.hd-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.clock {
  display: flex;
  align-items: baseline;
  font-size: 30px;
  font-weight: 700;
  color: #9dc0e8;
  letter-spacing: 1px;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 14px rgba(var(--indigo-rgb), 0.55);
}

.clock-part i {
  font-style: normal;
  margin: 0 2px;
  opacity: 0.6;
}

.clock-date {
  font-size: 13px;
  color: #8d9bad;
  letter-spacing: 1px;
}

/* 中央标题：梯形匾额。
   匾身走靛蓝深底，只有上下两道朱砂勾边 —— 对应后台侧栏那块朱砂印章，
   是整个大屏的「落款」；但不让朱砂整块铺开，
   这样屏幕上唯一的朱砂仍然是「两科不及格」那个预警数字。 */
.hd-title {
  position: relative;
  margin: 0;
  padding: 0 70px;
  height: 56px;
  display: flex;
  align-items: center;
  background: linear-gradient(180deg, rgba(var(--indigo-rgb), 0.3), rgba(var(--indigo-rgb), 0.05));
  clip-path: polygon(14% 0, 86% 0, 100% 50%, 86% 100%, 14% 100%, 0 50%);
  border-top: 1px solid rgba(var(--seal-rgb), 0.45);
  border-bottom: 1px solid rgba(var(--seal-rgb), 0.45);
}

.hd-title-text {
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 400;
  letter-spacing: 8px;
  color: #ffffff;
  text-shadow:
    0 0 10px rgba(var(--indigo-rgb), 0.75),
    0 0 28px rgba(var(--indigo-rgb), 0.5);
}

.hd-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}

.hd-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  line-height: 1.35;
  margin-right: 6px;
}

.hd-meta-label {
  font-size: 11px;
  color: #5d6a7a;
}

.hd-meta-value {
  font-size: 14px;
  color: #8d9bad;
  font-variant-numeric: tabular-nums;
}

.hd-btn {
  padding: 7px 16px;
  font-size: 13px;
  color: #8d9bad;
  background: rgba(var(--indigo-rgb), 0.12);
  border: 1px solid rgba(var(--indigo-rgb), 0.45);
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
}

.hd-btn:hover {
  color: #ffffff;
  background: rgba(var(--indigo-rgb), 0.28);
  border-color: #7fa9dc;
  box-shadow: 0 0 12px rgba(var(--indigo-rgb), 0.35);
}

/* 出口按钮：暗底上用近白实心最清楚。
   刻意不用朱砂 —— 朱砂在这套系统里只表示「预警」。 */
.hd-btn-primary {
  color: #0b1119;
  background: #e9eef4;
  border-color: #e9eef4;
  font-weight: 600;
}

.hd-btn-primary:hover {
  color: #0b1119;
  background: #ffffff;
  border-color: #ffffff;
}

/* =====================================================================
 * 主体三列
 * ================================================================== */
.screen-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 440px 1fr 440px;
  gap: 16px;
  padding-top: 12px;
}

.col {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
}

.col-center {
  gap: 14px;
}

/* =====================================================================
 * 面板
 * ================================================================== */
.panel {
  position: relative;
  background: linear-gradient(180deg, rgba(var(--indigo-rgb), 0.1), rgba(var(--indigo-rgb), 0.02));
  border: 1px solid rgba(var(--indigo-rgb), 0.28);
  padding: 12px 14px 14px;
  box-sizing: border-box;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* 四角装饰 */
.panel::before,
.panel::after {
  content: '';
  position: absolute;
  width: 12px;
  height: 12px;
  border-color: var(--indigo);
  border-style: solid;
  pointer-events: none;
}

.panel::before {
  top: -1px;
  left: -1px;
  border-width: 2px 0 0 2px;
}

.panel::after {
  bottom: -1px;
  right: -1px;
  border-width: 0 2px 2px 0;
}

.panel-title {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #e9eef4;
  letter-spacing: 1px;
  padding-left: 10px;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.panel-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 14px;
  background: var(--indigo);
  box-shadow: 0 0 8px rgba(var(--indigo-rgb), 0.9);
}

.panel-title::after {
  content: '';
  position: absolute;
  left: 10px;
  right: 0;
  bottom: -5px;
  height: 1px;
  background: linear-gradient(90deg, rgba(var(--indigo-rgb), 0.5), transparent 75%);
}

/* =====================================================================
 * 左列：核心大数
 * ================================================================== */
.panel-hero {
  flex-shrink: 0;
  padding: 16px 18px 14px;
  overflow: hidden;
}

.panel-bar {
  position: absolute;
  inset: 0 0 auto 0;
  height: 3px;
  background: linear-gradient(90deg, transparent, var(--indigo), transparent);
  box-shadow: 0 0 16px rgba(var(--indigo-rgb), 0.7);
}

.hero-label {
  font-size: 14px;
  color: #8d9bad;
  letter-spacing: 3px;
}

.hero-value {
  font-size: 62px;
  font-weight: 700;
  line-height: 1.08;
  color: #ffffff;
  font-variant-numeric: tabular-nums;
  text-shadow:
    0 0 14px rgba(var(--indigo-rgb), 0.65),
    0 0 40px rgba(var(--indigo-rgb), 0.45);
  margin: 6px 0 8px;
}

.hero-sub {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 13px;
  color: #8d9bad;
}

.hero-sub-item b {
  font-size: 17px;
  margin-left: 4px;
  font-variant-numeric: tabular-nums;
}

.hero-divider {
  color: rgba(var(--indigo-rgb), 0.6);
}

/* =====================================================================
 * 左列：滚动表
 * ================================================================== */
.panel-table {
  flex: 1;
  min-height: 0;
}

.mini-table {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.mini-head,
.mini-row {
  display: grid;
  grid-template-columns: 1fr 1.3fr 1fr 1.5fr;
  gap: 6px;
  align-items: center;
}

.mini-head {
  padding: 6px 8px;
  font-size: 12px;
  color: #9dc0e8;
  background: rgba(var(--indigo-rgb), 0.16);
  border-bottom: 1px solid rgba(var(--indigo-rgb), 0.28);
  flex-shrink: 0;
}

.mini-head span:nth-child(3),
.mini-head span:nth-child(4) {
  text-align: right;
}

.mini-viewport {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  position: relative;
}

/* 上下渐隐：滚动到边界时不会硬切。
   不用 mask-image —— Chromium 下 mask 会把子元素提到独立合成层，
   跟 .mini-body 的 transform 动画叠加后文字会发暗发灰。 */
.mini-viewport::before,
.mini-viewport::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  height: 14px;
  pointer-events: none;
  z-index: 2;
}

.mini-viewport::before {
  top: 0;
  background: linear-gradient(180deg, rgba(20, 28, 38, 0.85), rgba(20, 28, 38, 0));
}

.mini-viewport::after {
  bottom: 0;
  background: linear-gradient(0deg, rgba(20, 28, 38, 0.85), rgba(20, 28, 38, 0));
}

.mini-body {
  animation: scrollLoop 26s linear infinite;
}

.mini-row {
  padding: 7px 8px;
  font-size: 12.5px;
  border-bottom: 1px dashed rgba(var(--indigo-rgb), 0.18);
}

.mini-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mini-row span:nth-child(3),
.mini-row span:nth-child(4) {
  text-align: right;
}

@keyframes scrollLoop {
  from {
    transform: translateY(0);
  }
  to {
    transform: translateY(-50%);
  }
}

/* =====================================================================
 * 中列：KPI 条
 * ================================================================== */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  flex-shrink: 0;
}

.kpi {
  position: relative;
  padding: 12px 8px 10px;
  text-align: center;
  background: linear-gradient(180deg, rgba(var(--indigo-rgb), 0.16), rgba(var(--indigo-rgb), 0.03));
  border: 1px solid rgba(var(--indigo-rgb), 0.3);
  border-radius: 2px;
  overflow: hidden;
}

.kpi::after {
  content: '';
  position: absolute;
  inset: auto 0 0 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--indigo), transparent);
}

.kpi-value {
  font-size: 30px;
  font-weight: 700;
  line-height: 1.15;
  color: #ffffff;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 12px rgba(var(--indigo-rgb), 0.4);
}

.kpi-label {
  margin-top: 4px;
  font-size: 12.5px;
  color: #8d9bad;
  letter-spacing: 1px;
}

/* =====================================================================
 * 中列：排行榜
 * ================================================================== */
.panel-rank {
  flex: 1;
  min-height: 0;
}

/* 中段：左边班级排行，右边就业热力地图。
   地图是宽幅主视觉，所以这一段按 400px + 剩余宽度切，
   剩下的都给地图（中间列本来就比两侧宽）。 */
.center-mid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 400px 1fr;
  gap: 14px;
}

.rank-list {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
  gap: 4px;
  overflow: hidden;
}

.rank-item {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 34px;
}

.rank-no {
  flex-shrink: 0;
  width: 52px;
  font-size: 14px;
  font-weight: 700;
  color: #8d9bad;
  letter-spacing: 0.5px;
}

.rank-no-top {
  color: var(--ochre);
  text-shadow: 0 0 10px rgba(var(--ochre-rgb), 0.6);
}

.rank-name {
  flex-shrink: 0;
  width: 150px;
  font-size: 14px;
  color: #e9eef4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-bar-wrap {
  flex: 1;
  min-width: 0;
  height: 14px;
  background: rgba(var(--indigo-rgb), 0.12);
  border-radius: 2px;
  overflow: hidden;
}

.rank-bar {
  height: 100%;
  background: linear-gradient(90deg, rgba(var(--indigo-rgb), 0.85), var(--indigo));
  box-shadow: 0 0 14px rgba(var(--indigo-rgb), 0.55);
  border-radius: 2px;
  transition: width 0.8s ease;
}

.rank-value {
  flex-shrink: 0;
  width: 62px;
  text-align: right;
  font-size: 13px;
  color: #9dc0e8;
  font-variant-numeric: tabular-nums;
}

/* =====================================================================
 * 中列：就业去向热力中国地图
 * ================================================================== */
.panel-map {
  min-width: 0;
}

/* 地图区：撑满面板里剩下的高度 */
.map-chart {
  position: relative;
  flex: 1;
  min-height: 0;
}

/* 地图没加载出来时的占位提示。
   底图拉不到（网络失败 / geoJSON 异常）时，
   这一块显示占位文字，大屏其它面板照常工作，不会白屏。 */
.map-fallback {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-align: center;
}

.map-fallback-text {
  font-size: 15px;
  letter-spacing: 2px;
  color: var(--ochre);
}

.map-fallback-sub {
  font-size: 12px;
  color: #5d6a7a;
}

/* 下方榜单：默认是去向省份 Top5，点地图上的省份后变成该省的去向公司 */
.map-list {
  flex-shrink: 0;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(var(--indigo-rgb), 0.22);
}

.map-list-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.map-list-title {
  font-size: 13px;
  font-weight: 600;
  color: #e9eef4;
  letter-spacing: 1px;
}

.map-list-note {
  font-size: 11.5px;
  color: #8d9bad;
  font-variant-numeric: tabular-nums;
}

.map-list-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.map-list-row {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 19px;
  font-size: 12.5px;
}

.map-list-row .rank-no {
  width: 44px;
  font-size: 12px;
}

.map-list-name {
  flex: 1;
  min-width: 0;
  color: #e9eef4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.map-list-sub {
  width: 56px;
  color: #5d6a7a;
  text-align: right;
}

.map-list-count {
  width: 52px;
  color: #9dc0e8;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.map-list-value {
  width: 104px;
  color: var(--ochre);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.map-list-empty {
  padding: 6px 0;
  font-size: 12.5px;
  color: #5d6a7a;
}

/* =====================================================================
 * 中列：底部（仪表 + 薪资榜）
 * ================================================================== */
.center-bottom {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 14px;
  height: 268px;
  flex-shrink: 0;
}

.panel-gauge {
  align-items: stretch;
}

.gauge-extra {
  text-align: center;
  font-size: 13px;
  color: #8d9bad;
  margin-top: -6px;
}

.gauge-extra b {
  font-size: 18px;
  margin-left: 6px;
  font-variant-numeric: tabular-nums;
}

.panel-salary {
  min-width: 0;
}

.salary-list {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
  gap: 4px;
  overflow: hidden;
}

.salary-item {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 38px;
  padding: 0 10px;
  background: rgba(var(--ochre-rgb), 0.06);
  border-left: 2px solid rgba(var(--ochre-rgb), 0.45);
}

.salary-main {
  flex: 1;
  min-width: 0;
}

.salary-name {
  font-size: 14px;
  color: #e9eef4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.salary-company {
  font-size: 12px;
  color: #8d9bad;
  margin-left: 8px;
}

.salary-meta {
  font-size: 11.5px;
  color: #5d6a7a;
}

.salary-value {
  flex-shrink: 0;
  font-size: 19px;
  font-weight: 700;
  color: var(--ochre);
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 12px rgba(var(--ochre-rgb), 0.45);
}

/* =====================================================================
 * 右列
 * ================================================================== */
.panel-chart {
  flex: 1;
  min-height: 0;
}

.panel-age {
  flex: 0 0 auto;
}

/* =====================================================================
 * 环形图：环心总数字
 * ---------------------------------------------------------------------
 * 用 HTML 覆盖层写环心文字，而不是在 ECharts 里再叠一个「零半径饼图」。
 * 那种写法在 ECharts 6 下富文本的两行会叠在一起（数字压住文字），
 * HTML 覆盖层位置跟着 .donut-box 走，稳定可控。
 *
 * 【为什么定位基准必须是 .donut-box，而不是外层的 .donut-wrap】
 *   饼图的 center: ['50%', '44%'] 是相对【图表自身 190px 高度】算的，
 *   而 .donut-wrap 在面板里是 flex:1，会被面板拉高到 220px 以上。
 *   两个基准不一样，覆盖层就会比圆心偏低（数字压到圆环下沿）。
 *   所以这里让 .donut-box 固定 190px —— 它就是图表的盒子，
 *   覆盖层的 top:44% 和饼图圆心用的是同一个基准，必然对齐。
 * ================================================================== */
.donut-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
}

.donut-box {
  position: relative;
  height: 190px;
}

.donut-center {
  position: absolute;
  left: 0;
  right: 0;
  /* 和 ECharts 里 pie 的 center: ['50%', '44%'] 对齐（基准 = 图表高度 190px） */
  top: 44%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  pointer-events: none;
}

.donut-center-num {
  font-family: var(--font-mono);
  font-size: 26px;
  font-weight: 700;
  line-height: 1.1;
  color: #ffffff;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 14px rgba(var(--indigo-rgb), 0.55);
}

.donut-center-sub {
  font-size: 11px;
  color: #8d9bad;
  letter-spacing: 1px;
}

/* =====================================================================
 * 遮罩
 * ================================================================== */
.screen-mask {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  /* 半透明而不是全黑：加载期间也能看到面板骨架，不至于整屏黑一下 */
  background: rgba(11, 17, 25, 0.55);
  z-index: 20;
  backdrop-filter: blur(1px);
}

.mask-text {
  font-size: 17px;
  letter-spacing: 2px;
  color: #9dc0e8;
}

.screen-mask-error .mask-text {
  color: var(--seal);
}

/* =====================================================================
 * 语义色工具类
 * ---------------------------------------------------------------------
 * 放在最后是有原因的：这些 class 和 .kpi-value / .mini-row 等
 * 同为单类选择器（特异性相同），CSS 同特异性下后写的赢。
 * 早先写在前面时，.kpi-value 的 color 会把 .c-ochre / .c-jade 覆盖掉，
 * 导致「两科不及格」「全优学员」两个 KPI 的数字显示成普通白色。
 *
 * 命名跟 styles/theme.css 的 token 对齐，一眼能看出这个颜色归谁：
 *   .c-seal   朱砂 —— 预警
 *   .c-ochre  赭黄 —— 就业 / 薪资
 *   .c-jade   青绿 —— 达标 / 全优
 *   .c-indigo 靛蓝 —— 通用数据
 * ================================================================== */
.c-seal {
  color: var(--seal);
}

.c-ochre {
  color: var(--ochre);
}

.c-jade {
  color: var(--jade);
}

.c-indigo {
  color: var(--indigo);
}

.c-text {
  color: #e9eef4;
}

.c-sub {
  color: #8d9bad;
}
</style>
