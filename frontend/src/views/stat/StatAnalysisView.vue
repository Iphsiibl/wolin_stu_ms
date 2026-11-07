/**
 * =====================================================================
 * 统计分析页（原「数据看板」+ 原「统计分析」合并）
 * =====================================================================
 * 合并前的两个页面：
 *   数据看板 —— 学员流向尺、性别环形图、快捷入口、Top5 薪资表
 *   统计分析 —— 各类统计图表 + 两张明细表
 *
 * 两边重复的图表只保留一处（重复的都是同一批数据换了个画法）：
 *   · 各班人数 Top10 单色柱  ->  删（并入「班级人数与男女构成」堆叠柱）
 *   · 薪资 Top5 表格        ->  删（并入「薪资 Top5 明细」表，字段更全）
 *   · 册页副表               ->  合并成一条 8 格的汇总条
 *
 * 分区用 el-tabs 组织，一节一节看，不把图表堆成一坨：
 *   总览 —— 学员流向、性别构成、常用入口
 *   成绩 —— 各班平均分
 *   就业 —— 薪资榜、就业人数、去向明细
 *   班级 —— 班级人数构成、班级明细
 *
 * 所有指标均来自后端 /stat 实时统计接口，前端不做二次加工，
 * 只有「班级均人数」是在既有数据上做的除法。
 * =====================================================================
 */
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Briefcase, EditPen, Monitor, Refresh, User, School } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

import {
  fetchAllAbove80,
  fetchAvgDurationByClass,
  fetchAvgScoreByClass,
  fetchClassStatistics,
  fetchEmpDuration,
  fetchFailedTwice,
  fetchTop5Salary,
} from '@/api/stat'
import { fetchAllClasses } from '@/api/class'
import { fetchAllStudents } from '@/api/student'
import { fetchAllTeachers } from '@/api/teacher'
import type { ClassInfo } from '@/types/models'
import type {
  Above80Record,
  AvgDurationByClass,
  AvgScoreByClass,
  ClassStatistics,
  EmpDuration,
  FailedRecord,
  Top5Salary,
} from '@/types/models'
import { formatDate, formatNumber } from '@/utils/format'

// ECharts 按需注册
use([BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent, CanvasRenderer])

const router = useRouter()

// 当前分区：总览 / 成绩 / 就业 / 班级
const activeTab = ref('overview')

const loading = ref(true)
// 数据是否已经取回来了。汇总数字是从各数组算出来的，
// 数组还是空的时候算出来是 0 —— 但 0 在这里是个会误导人的值，
// 所以没加载完之前显示占位符「—」，不显示 0。
const loaded = ref(false)

const classStats = ref<ClassStatistics[]>([])
const avgScores = ref<AvgScoreByClass[]>([])
const top5 = ref<Top5Salary[]>([])
const durations = ref<EmpDuration[]>([])
const avgDurations = ref<AvgDurationByClass[]>([])
const above80 = ref<Above80Record[]>([])
const failed = ref<FailedRecord[]>([])
const classes = ref<ClassInfo[]>([])

// 在册学员总数 / 授课老师数（这两个是「人」的数，不在各班统计里）
const studentTotal = ref<number | null>(null)
const teacherTotal = ref<number | null>(null)

/** 班级 id -> 名称（有些统计接口只给 class_id） */
const classMap = computed(() => {
  const map: Record<number, string> = {}
  for (const c of classes.value) map[c.class_id] = c.class_name
  return map
})

function className(id: number): string {
  return classMap.value[id] ?? `班级${id}`
}

async function loadAll() {
  loading.value = true
  try {
    const [
      classRes,
      avgRes,
      top5Res,
      durRes,
      avgDurRes,
      aboveRes,
      failedRes,
      classListRes,
      stuRes,
      teacherRes,
    ] = await Promise.all([
      fetchClassStatistics(),
      fetchAvgScoreByClass(),
      fetchTop5Salary(),
      fetchEmpDuration(),
      fetchAvgDurationByClass(),
      fetchAllAbove80(),
      fetchFailedTwice(),
      fetchAllClasses(),
      fetchAllStudents(),
      fetchAllTeachers(),
    ])
    classStats.value = classRes.data ?? []
    avgScores.value = avgRes.data ?? []
    top5.value = top5Res.data ?? []
    durations.value = durRes.data ?? []
    avgDurations.value = avgDurRes.data ?? []
    above80.value = aboveRes.data ?? []
    failed.value = failedRes.data ?? []
    classes.value = classListRes.data ?? []
    studentTotal.value = stuRes.total ?? (stuRes.data ?? []).length
    teacherTotal.value = (teacherRes.data ?? []).length
  } finally {
    loading.value = false
    loaded.value = true
  }
}

/* ---------------------------------------------------------------------
 * 图表配置
 *   色板沿用全局设计系统，并且「一色一义」，避免同一个颜色在同页
 *   承担两种含义：
 *     靛 #2f5480   男生
 *     紫 #7b5ea6   女生
 *     赭 #a8792a   薪资
 *     青 #2c7a63   已就业 / 达标
 *     朱 #c0392b   不及格预警
 *     墨 #24313f   通用数值
 *   坐标轴统一用细灰线，标签小字灰，不做任何渐变
 * ------------------------------------------------------------------ */
const INK = '#24313f'
const INDIGO = '#2f5480'
const VIOLET = '#7b5ea6'
const OCHRE = '#a8792a'
const JADE = '#2c7a63'
const SEAL = '#c0392b'
const AXIS = '#d9e0e7'
const AXIS_TEXT = '#8a97a4'

const catAxis = {
  axisLabel: { rotate: 40, fontSize: 10, color: AXIS_TEXT },
  axisLine: { lineStyle: { color: AXIS } },
  axisTick: { show: false },
}

const valAxis = {
  axisLabel: { fontSize: 10, color: AXIS_TEXT },
  splitLine: { lineStyle: { color: AXIS } },
}

/* ---------------------------------------------------------------------
 * 学员流水尺
 *   尺子的全长 = 在册学员总数
 *   实心段     = 已就业
 *   浅色段     = 在读待就业
 *   朱砂标记   = 两科不及格落在尺上的位置
 * ------------------------------------------------------------------ */
/* 两科不及格的人数（尺子上的朱砂标记用它） */
const failedCount = computed(() => new Set(failed.value.map((r) => r.stu_id)).size)

const total = computed(() => studentTotal.value ?? 0)
const employed = computed(() => durations.value.length)
const pending = computed(() => Math.max(total.value - employed.value, 0))

/** 已就业占比（百分数，保留一位小数） */
const employedPct = computed(() => (total.value ? (employed.value / total.value) * 100 : 0))
/** 在读待就业占比 */
const pendingPct = computed(() => (total.value ? (pending.value / total.value) * 100 : 0))
/** 不及格标记在尺上的位置 */
const failedPct = computed(() => (total.value ? (failedCount.value / total.value) * 100 : 0))
/** 标记靠左时，标签改为向右展开，避免被面板裁掉 */
const failedAtLeft = computed(() => failedPct.value < 18)

/* ---------------------------------------------------------------------
 * 汇总数字
 * ------------------------------------------------------------------ */
const summary = computed(() => ({
  studentCount: total.value,
  classCount: classStats.value.length,
  teacherCount: teacherTotal.value ?? 0,
  employedCount: employed.value,
  above80Count: new Set(above80.value.map((r) => r.stu_id)).size,
  failedCount: failedCount.value,
  avgSalary: top5.value.length
    ? Math.round(top5.value.reduce((s, t) => s + t.salary, 0) / top5.value.length)
    : 0,
}))

/* 班级均人数 = 在册学员 / 有学员的班级数 */
const avgPerClass = computed(() => {
  const c = summary.value.classCount
  return c ? (summary.value.studentCount / c).toFixed(1) : '—'
})

/* 册页副表：八项汇总，横排一行（两页副表合并去重后的结果） */
const summaryCells = computed(() => {
  const s = summary.value
  const v = (n: number) => (loaded.value ? n : '—')
  return [
    { label: '学员总数', value: v(s.studentCount), unit: '人', note: '在册学员', tone: '' },
    { label: '班级数量', value: v(s.classCount), unit: '个', note: '有学员的班级', tone: '' },
    { label: '老师数量', value: v(s.teacherCount), unit: '位', note: '在册师资', tone: '' },
    { label: '班级均人数', value: loaded.value ? avgPerClass.value : '—', unit: '人/班', note: '在册 ÷ 班级', tone: '' },
    { label: '已就业人数', value: v(s.employedCount), unit: '人', note: '已确认去向', tone: 'tone-jade' },
    { label: '全优学生', value: v(s.above80Count), unit: '人', note: '各科均 80 以上', tone: 'tone-jade' },
    { label: '两科不及格', value: v(s.failedCount), unit: '人', note: '需要重点关注', tone: 'tone-seal' },
    { label: 'Top5 平均薪资', value: loaded.value ? `¥${formatNumber(s.avgSalary)}` : '—', unit: '', note: '单位：元/月', tone: 'tone-ochre' },
  ]
})

/** 班级人数与男女构成（取前 12 个班） */
const genderPieOption = computed(() => {
  const top = classStats.value.slice(0, 12)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: {
      data: ['男生', '女生'],
      top: 0,
      icon: 'roundRect',
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { fontSize: 11, color: AXIS_TEXT },
    },
    grid: { left: 36, right: 12, top: 28, bottom: 66 },
    xAxis: { type: 'category', data: top.map((c) => c.class_name), ...catAxis },
    yAxis: { type: 'value', minInterval: 1, ...valAxis },
    series: [
      {
        name: '男生',
        type: 'bar',
        stack: 'total',
        barMaxWidth: 26,
        data: top.map((c) => c.male_count),
        itemStyle: { color: INDIGO },
      },
      {
        name: '女生',
        type: 'bar',
        stack: 'total',
        barMaxWidth: 26,
        data: top.map((c) => c.female_count),
        itemStyle: { color: VIOLET },
      },
    ],
  }
})

/** 男女总人数（性别构成环形图用） */
const genderTotal = computed(() => ({
  male: classStats.value.reduce((s, c) => s + c.male_count, 0),
  female: classStats.value.reduce((s, c) => s + c.female_count, 0),
}))

/** 男女比例（环形图） */
const genderOption = computed(() => {
  const { male, female } = genderTotal.value
  return {
    tooltip: { trigger: 'item', formatter: '{b}：{c} 人（{d}%）' },
    legend: { bottom: 0, icon: 'roundRect', itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 11, color: AXIS_TEXT } },
    series: [
      {
        type: 'pie',
        radius: ['52%', '74%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 3, borderColor: '#fff', borderWidth: 2 },
        label: {
          show: true,
          formatter: '{b}\n{c} 人',
          color: AXIS_TEXT,
          fontSize: 11,
          lineHeight: 15,
        },
        labelLine: { show: true, length: 8, length2: 8 },
        data: [
          { value: male, name: '男生', itemStyle: { color: INDIGO } },
          { value: female, name: '女生', itemStyle: { color: VIOLET } },
        ],
      },
    ],
  }
})

/** 各班平均分（取前 12 条） */
const avgScoreOption = computed(() => {
  const top = avgScores.value.slice(0, 12)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 44, right: 12, top: 24, bottom: 66 },
    xAxis: { type: 'category', data: top.map((c) => c.class_name), ...catAxis },
    yAxis: { type: 'value', max: 100, min: 0, ...valAxis },
    series: [
      {
        type: 'bar',
        barMaxWidth: 26,
        data: top.map((c) => c.avg_score),
        // 不及格（< 60）的班级直接标朱砂，一眼看出问题班
        itemStyle: {
          color: (params: { value: number }) => (params.value >= 60 ? INK : SEAL),
          borderRadius: [2, 2, 0, 0],
        },
        label: { show: true, position: 'top', fontSize: 10, color: AXIS_TEXT },
      },
    ],
  }
})

/** 薪资前五 */
const salaryOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 88, right: 46, top: 16, bottom: 24 },
  xAxis: {
    type: 'value',
    axisLabel: { fontSize: 10, color: AXIS_TEXT },
    splitLine: { lineStyle: { color: AXIS } },
  },
  yAxis: {
    type: 'category',
    data: top5.value.map((t) => t.stu_name).reverse(),
    axisLabel: { fontSize: 11, color: AXIS_TEXT },
    axisLine: { lineStyle: { color: AXIS } },
    axisTick: { show: false },
  },
  series: [
    {
      type: 'bar',
      barMaxWidth: 18,
      data: top5.value.map((t) => t.salary).reverse(),
      itemStyle: { color: OCHRE, borderRadius: [0, 2, 2, 0] },
      label: { show: true, position: 'right', fontSize: 10, color: AXIS_TEXT },
    },
  ],
}))

/** 就业人数与平均时长（取前 12 个班） */
const durationOption = computed(() => {
  const top = avgDurations.value.slice(0, 12)
  return {
    tooltip: { trigger: 'axis' },
    /* 单系列折线不需要图例，把底部空间全留给旋转的班级名 */
    grid: { left: 36, right: 12, top: 20, bottom: 66 },
    xAxis: { type: 'category', data: top.map((c) => className(c.class_id)), ...catAxis },
    yAxis: { type: 'value', minInterval: 1, ...valAxis },
    series: [
      {
        name: '就业人数',
        type: 'line',
        smooth: true,
        symbolSize: 6,
        data: top.map((c) => c.student_count),
        lineStyle: { width: 2, color: JADE },
        itemStyle: { color: JADE },
        areaStyle: { color: JADE, opacity: 0.08 },
      },
    ],
  }
})

/* 常用入口（图标用组件而不是字符串，模板里直接 <component :is>） */
const shortcuts = [
  { title: '学生管理', desc: '学员信息增删改查', path: '/student/list', icon: User, color: INK },
  { title: '学生成绩', desc: '各场次成绩录入查询', path: '/score/list', icon: EditPen, color: INDIGO },
  { title: '就业信息', desc: '就业信息与薪资', path: '/employment/list', icon: Briefcase, color: OCHRE },
  { title: '班级列表', desc: '班级编制与任课老师', path: '/class/list', icon: School, color: JADE },
]

onMounted(loadAll)
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <div class="page-heading">
        <span class="page-eyebrow">Statistics</span>
        <div class="page-title">统计分析</div>
        <p class="page-subtitle">
          在册学员 <span class="num">{{ studentTotal ?? '—' }}</span> 人 · 班级
          <span class="num">{{ loaded ? summary.classCount : '—' }}</span> 个 · 老师
          <span class="num">{{ teacherTotal ?? '—' }}</span> 位
        </p>
      </div>
      <div class="page-actions">
        <!-- 大屏入口：从原数据看板页挪过来，放在抬头右上角最显眼的位置 -->
        <el-button type="primary" :icon="Monitor" @click="router.push('/screen')">进入数据大屏</el-button>
        <el-button :icon="Refresh" @click="loadAll">刷新数据</el-button>
      </div>
    </div>

    <!-- 册页副表（两页副表合并去重后的 8 格汇总，整页常驻） -->
    <section class="card ledger-strip">
      <div v-for="c in summaryCells" :key="c.label" class="ledger-cell">
        <div class="ledger-label">{{ c.label }}</div>
        <div class="ledger-value" :class="c.tone">
          <span class="num">{{ c.value }}</span>
          <small>{{ c.unit }}</small>
        </div>
        <div class="ledger-note">{{ c.note }}</div>
      </div>
    </section>

    <!-- 分区导航：总览 / 成绩 / 就业 / 班级 -->
    <el-tabs v-model="activeTab" class="stat-tabs">
      <!-- ================= 总览 ================= -->
      <!-- lazy：页签内容第一次切到时才渲染。
           不这么做的话，没激活的页签是 display:none，
           里面的 ECharts 会拿 0 宽 0 高初始化，图表就成了空白。 -->
      <el-tab-pane label="总览" name="overview" lazy>
        <div class="tab-body">
          <!-- 学员流水尺 -->
          <section class="card panel-ledger flow-panel">
            <div class="panel-head">
              <div class="panel-title">学员流向</div>
              <span class="panel-note">全长 {{ total }} 人 · 数据源 /stat 实时接口</span>
            </div>

            <div class="ruler">
              <!-- 尺身 -->
              <div class="ruler-bar">
                <div class="ruler-seg ruler-seg--done" :style="{ width: employedPct + '%' }">
                  <span class="ruler-num num">{{ employed }}</span>
                  <span class="ruler-tag">已就业</span>
                </div>
                <div class="ruler-seg ruler-seg--open" :style="{ width: pendingPct + '%' }">
                  <span class="ruler-num num">{{ pending }}</span>
                  <span class="ruler-tag">在读待就业</span>
                </div>
              </div>

              <!-- 刻度 -->
              <div class="ruler-ticks">
                <i v-for="n in 5" :key="n" />
              </div>

              <!-- 异常标记：不及格的人落在尺上的位置 -->
              <div
                class="ruler-flag"
                :class="{ 'is-left': failedAtLeft }"
                :style="{ left: failedPct + '%' }"
              >
                <span class="ruler-flag-pin" />
                <span class="ruler-flag-label">
                  两科不及格 <b class="num">{{ failedCount || '—' }}</b> 人
                  <em class="num">{{ failedPct.toFixed(1) }}%</em>
                </span>
              </div>
            </div>
          </section>

          <el-row :gutter="16">
            <!-- 性别构成（环形图） -->
            <el-col :xs="24" :lg="10">
              <div class="card">
                <div class="panel-head">
                  <div class="panel-title">学员性别构成</div>
                  <span class="panel-note">单位：人</span>
                </div>
                <v-chart :option="genderOption" style="height: 300px" autoresize />
              </div>
            </el-col>

            <!-- 常用入口：竖着排，和左边图表一样高，卡片下面不留空洞 -->
            <el-col :xs="24" :lg="14">
              <div class="card card--fill">
                <div class="panel-head">
                  <div class="panel-title">常用入口</div>
                  <span class="panel-note">学员 · 成绩 · 就业 · 班级</span>
                </div>
                <div class="shortcut-list">
                  <div
                    v-for="item in shortcuts"
                    :key="item.path"
                    class="shortcut"
                    @click="router.push(item.path)"
                  >
                    <div class="shortcut-icon" :style="{ color: item.color }">
                      <el-icon :size="17"><component :is="item.icon" /></el-icon>
                    </div>
                    <div>
                      <div class="shortcut-title">{{ item.title }}</div>
                      <div class="shortcut-desc">{{ item.desc }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <!-- ================= 成绩 ================= -->
      <el-tab-pane label="成绩" name="score" lazy>
        <div class="tab-body">
          <div class="card">
            <div class="panel-head">
              <div class="panel-title">各班平均分</div>
              <span class="panel-note">Top 12 · 60 分及格线 · 单位：分</span>
            </div>
            <v-chart :option="avgScoreOption" style="height: 340px" autoresize />
          </div>
        </div>
      </el-tab-pane>

      <!-- ================= 就业 ================= -->
      <el-tab-pane label="就业" name="employment" lazy>
        <div class="tab-body">
          <el-row :gutter="16">
            <el-col :xs="24" :lg="12">
              <div class="card">
                <div class="panel-head">
                  <div class="panel-title">就业薪资 Top 5</div>
                  <span class="panel-note">单位：元/月</span>
                </div>
                <v-chart :option="salaryOption" style="height: 300px" autoresize />
              </div>
            </el-col>
            <el-col :xs="24" :lg="12">
              <div class="card">
                <div class="panel-head">
                  <div class="panel-title">各班就业人数</div>
                  <span class="panel-note">Top 12 · 单位：人</span>
                </div>
                <v-chart :option="durationOption" style="height: 300px" autoresize />
              </div>
            </el-col>
          </el-row>

          <!-- 明细表格 -->
          <div class="card">
            <div class="panel-head">
              <div class="panel-title">薪资 Top 5 明细</div>
              <span class="panel-note">单位：元/月</span>
            </div>
            <el-table :data="top5" stripe>
              <el-table-column type="index" label="排名" width="70" align="center">
                <template #default="{ $index }">
                  <span class="num rank" :class="{ 'rank--top': $index < 3 }">{{ $index + 1 }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="stu_name" label="姓名" min-width="120" />
              <el-table-column label="班级" min-width="140">
                <template #default="{ row }">{{ className(row.class_id) }}</template>
              </el-table-column>
              <el-table-column prop="company" label="公司" min-width="140" />
              <el-table-column label="薪资" width="130" align="right">
                <template #default="{ row }">
                  <span class="num tone-ochre" style="font-weight: 600">¥{{ formatNumber(row.salary) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="Offer 时间" width="130" align="center">
                <template #default="{ row }">
                  <span class="num">{{ formatDate(row.offer_date) }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-tab-pane>

      <!-- ================= 班级 ================= -->
      <el-tab-pane label="班级" name="class" lazy>
        <div class="tab-body">
          <div class="card">
            <div class="panel-head">
              <div class="panel-title">班级人数与男女构成</div>
              <span class="panel-note">Top 12 · 单位：人</span>
            </div>
            <v-chart :option="genderPieOption" style="height: 320px" autoresize />
          </div>

          <div class="card">
            <div class="panel-head">
              <div class="panel-title">班级人数统计明细</div>
              <span class="panel-note">单位：人</span>
            </div>
            <el-table :data="classStats" stripe max-height="420">
              <el-table-column prop="class_id" label="班级 ID" width="100" align="center">
                <template #default="{ row }">
                  <span class="num">{{ row.class_id }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="class_name" label="班级名称" min-width="160" />
              <el-table-column prop="total" label="总人数" width="100" align="center">
                <template #default="{ row }">
                  <span class="num">{{ row.total }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="male_count" label="男生" width="90" align="center">
                <template #default="{ row }">
                  <span class="num tone-indigo">{{ row.male_count }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="female_count" label="女生" width="90" align="center">
                <template #default="{ row }">
                  <span class="num tone-violet">{{ row.female_count }}</span>
                </template>
              </el-table-column>
              <el-table-column label="男女比" min-width="160">
                <template #default="{ row }">
                  <el-progress
                    :percentage="row.total ? Math.round((row.male_count / row.total) * 100) : 0"
                    :stroke-width="14"
                    text-inside
                  />
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
/* ---------------------------------------------------------------------
 * 分区导航：页签做成「册页签」的样子 —— 墨色下划线，其余只有一条细灰线
 * ------------------------------------------------------------------ */
.stat-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}

.stat-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background-color: var(--rule);
}

.stat-tabs :deep(.el-tabs__item) {
  height: 40px;
  padding: 0 18px;
  font-family: var(--font-display);
  font-size: 15px;
  letter-spacing: 2px;
  color: var(--text-sub);
}

.stat-tabs :deep(.el-tabs__item.is-active) {
  color: var(--text-ink);
  font-weight: 600;
}

.stat-tabs :deep(.el-tabs__active-bar) {
  height: 2px;
  background-color: var(--seal);
}

/* 每个分区内部的纵向排版 */
.tab-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 和旁边的图表卡并排时，矮的那张也撑到同样的高度，
   免得右边空出一大块白 */
.card--fill {
  height: 100%;
  box-sizing: border-box;
}

/* ---------------------------------------------------------------------
 * 学员流水尺
 * ------------------------------------------------------------------ */
.flow-panel {
  padding-bottom: 26px;
}

.ruler {
  position: relative;
  padding-top: 4px;
  /* 给下方的朱砂标记留出位置，避免溢出面板 */
  padding-bottom: 26px;
}

/* 尺身：两段相加等于在册总数 */
.ruler-bar {
  display: flex;
  height: 56px;
  overflow: hidden;
  border-radius: 2px;
}

.ruler-seg {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  min-width: 0;
  transition: width 0.3s ease;
}

.ruler-seg--done {
  background-color: var(--ink-700);
}

.ruler-seg--open {
  background-color: var(--rule);
}

.ruler-num {
  font-size: 19px;
  font-weight: 600;
  line-height: 1.1;
  color: #fff;
}

.ruler-seg--open .ruler-num {
  color: var(--text-ink);
}

.ruler-tag {
  font-size: 11.5px;
  line-height: 1.3;
  color: rgb(255 255 255 / 68%);
  white-space: nowrap;
}

.ruler-seg--open .ruler-tag {
  color: var(--text-sub);
}

/* 刻度：像尺子上的分度 */
.ruler-ticks {
  display: flex;
  justify-content: space-between;
  height: 6px;
  padding-top: 4px;
}

.ruler-ticks i {
  width: 1px;
  height: 5px;
  background-color: var(--rule-strong);
}

/* 异常标记：朱砂游标，标出不及格的人落在尺上的位置 */
.ruler-flag {
  position: absolute;
  top: 0;
  transform: translateX(-50%);
}

.ruler-flag-pin {
  display: block;
  width: 2px;
  height: 56px;
  background-color: var(--seal);
}

.ruler-flag-label {
  position: absolute;
  top: 60px;
  left: 50%;
  display: block;
  padding: 2px 7px;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--seal);
  white-space: nowrap;
  background-color: var(--seal-soft);
  border-radius: 2px;
  transform: translateX(-50%);
}

.ruler-flag-label em {
  margin-left: 4px;
  font-style: normal;
  opacity: 0.75;
}

/* 靠左时标签向右展开，避免被裁掉 */
.ruler-flag.is-left {
  transform: translateX(0);

  .ruler-flag-label {
    left: 0;
    transform: none;
  }
}

/* ---------------------------------------------------------------------
 * 册页副表：八格一行（样式见 styles/theme.css 的 .ledger-strip）
 * ------------------------------------------------------------------ */

/* 排名：前三是朱砂，其余是墨色 */
.rank {
  font-weight: 600;
  color: var(--text-sub);
}

.rank--top {
  color: var(--seal);
}
</style>
