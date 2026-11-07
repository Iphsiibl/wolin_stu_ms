/**
 * =====================================================================
 * 路由配置
 * =====================================================================
 * 6 大模块对应 6 组路由，全部按需加载（懒加载），
 * 首屏只加载登录页 + 布局框架，页面切换时才拉对应的 chunk。
 *
 * 【菜单是扁平的】
 *   侧边栏不要二级菜单，所以每个页面都自己配了 meta.icon，
 *   菜单里是一排平级项：
 *     学生管理 / 顾问管理 / 学生成绩 / 就业信息
 *     / 班级列表 / 班主任 / 授课老师 / 统计分析
 *   页面级的 meta.icon 在 stores/modules/auth.ts 里被提升成顶级菜单项时使用。
 *
 * 【/dashboard 已并入 /stat/analysis】
 *   原来的「数据看板」页和「统计分析」页合并成了一页（统计分析），
 *   /dashboard 现在只是一条兼容跳转，留在路由表里是为了
 *   老的书签、老的链接不至于 404；它不占侧边栏菜单位。
 * =====================================================================
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useUserStore } from '@/store/user'

/** 主框架布局（侧边栏 + 顶栏 + 内容区） */
const Layout = () => import('@/layouts/BasicLayout.vue')

/**
 * 路由表。
 *
 * meta 里的字段：
 *   title  —— 侧边栏菜单文字 + 面包屑
 *   icon   —— Element Plus 图标组件名
 *   hidden —— true 表示不在侧边栏显示（比如详情页）
 */
export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: { title: '登录', hidden: true },
  },
  {
    path: '/',
    component: Layout,
    redirect: '/stat/analysis',
    // 首页直接跳到统计分析；children 留空数组是因为
    // vue-router 的类型要求：带 component 的路由要么有 children，要么不带 component
    children: [],
  },
  {
    /**
     * 老「数据看板」地址 —— 兼容跳转。
     *
     * 数据看板已经并入统计分析页，这个路径保留下来，
     * 免得老书签、老链接直接 404。
     * meta.hidden = true：它不占侧边栏菜单项。
     */
    path: '/dashboard',
    name: 'DashboardRedirect',
    redirect: '/stat/analysis',
    meta: { title: '统计分析', hidden: true },
  },
  {
    path: '/student',
    component: Layout,
    redirect: '/student/list',
    meta: { title: '学生管理', icon: 'User' },
    children: [
      {
        path: 'list',
        name: 'StudentList',
        component: () => import('@/views/student/StudentListView.vue'),
        meta: { title: '学生管理', icon: 'User' },
      },
      {
        path: 'agent',
        name: 'AgentList',
        component: () => import('@/views/student/AgentListView.vue'),
        meta: { title: '顾问管理', icon: 'Service' },
      },
    ],
  },
  {
    path: '/score',
    component: Layout,
    redirect: '/score/list',
    meta: { title: '成绩管理', icon: 'EditPen' },
    children: [
      {
        path: 'list',
        name: 'ScoreList',
        component: () => import('@/views/score/ScoreListView.vue'),
        meta: { title: '学生成绩', icon: 'EditPen' },
      },
    ],
  },
  {
    path: '/employment',
    component: Layout,
    redirect: '/employment/list',
    meta: { title: '就业管理', icon: 'Briefcase' },
    children: [
      {
        path: 'list',
        name: 'EmploymentList',
        component: () => import('@/views/employment/EmploymentListView.vue'),
        meta: { title: '就业信息', icon: 'Briefcase' },
      },
    ],
  },
  {
    path: '/class',
    component: Layout,
    redirect: '/class/list',
    meta: { title: '班级管理', icon: 'School' },
    children: [
      {
        path: 'list',
        name: 'ClassList',
        component: () => import('@/views/class/ClassListView.vue'),
        meta: { title: '班级列表', icon: 'School' },
      },
      {
        path: 'teacher',
        name: 'ClassTeacherList',
        component: () => import('@/views/class/ClassTeacherListView.vue'),
        meta: { title: '班主任', icon: 'Notebook' },
      },
    ],
  },
  {
    path: '/teacher',
    component: Layout,
    redirect: '/teacher/list',
    meta: { title: '授课老师', icon: 'Avatar' },
    children: [
      {
        path: 'list',
        name: 'TeacherList',
        component: () => import('@/views/teacher/TeacherListView.vue'),
        meta: { title: '授课老师', icon: 'Avatar' },
      },
    ],
  },
  {
    path: '/stat',
    component: Layout,
    redirect: '/stat/analysis',
    meta: { title: '统计分析', icon: 'TrendCharts' },
    children: [
      {
        path: 'analysis',
        name: 'StatAnalysis',
        component: () => import('@/views/stat/StatAnalysisView.vue'),
        meta: { title: '统计分析', icon: 'TrendCharts' },
      },
    ],
  },
  {
    /**
     * 数据大屏（独立路由，不套 Layout）。
     *
     * 大屏要铺满整个窗口，所以不能挂在 Layout 下面 ——
     * 侧边栏、顶栏、多页签都会挤掉大屏的展示空间。
     * meta.hidden = true 表示它不占侧边栏菜单项，
     * 入口放在「统计分析」页右上角的「进入数据大屏」按钮。
     */
    path: '/screen',
    name: 'DataScreen',
    component: () => import('@/views/screen/ScreenView.vue'),
    meta: { title: '数据大屏', hidden: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/NotFoundView.vue'),
    meta: { title: '页面不存在', hidden: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

/**
 * 路由守卫：没登录就踢回登录页。
 *
 * 因为是纯前端模拟登录，这里的判断是基于 localStorage 里有没有用户信息，
 * 不是真正的服务端鉴权。
 */
router.beforeEach((to) => {
  const userStore = useUserStore()

  // 已经登录了还去登录页 -> 直接回首页
  if (to.path === '/login' && userStore.isLoggedIn()) {
    return { path: '/stat/analysis' }
  }

  // 没登录访问任何受保护页面 -> 去登录页，并记住原本要去的地方
  if (to.path !== '/login' && !userStore.isLoggedIn()) {
    ElMessage.warning('请先登录')
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  return true
})

export default router
