/**
 * =====================================================================
 * 菜单与面包屑
 * ---------------------------------------------------------------------
 * 对应 Geeker-Admin 的 stores/modules/auth.ts。
 * 区别：Geeker 的菜单来自后端接口，本项目的菜单直接从路由表推导 ——
 *       路由表是唯一真相来源，加一个页面只要改路由表，
 *       菜单和面包屑会自动跟着变。
 *
 * ★ 扁平化规则
 *   本项目【不要二级菜单】——不管一个模块下面有几个页面，
 *   都把子页面直接提升成顶级菜单项。
 *   例如「学生管理 → 学生管理 / 顾问管理」会拆成两个平级菜单：
 *        学生管理、顾问管理（各自有自己的图标）。
 *   所以侧边栏是一排平级项，不会有可展开的箭头。
 *   父级路径只负责 URL 前缀（/student/list），不再出现在菜单和面包屑里。
 * =====================================================================
 */
import { defineStore } from 'pinia'
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { Component } from 'vue'

import type { MenuMeta, MenuOptions } from '@/stores/interface'
import { resolveIcon } from '@/utils/icons'

export const useAuthStore = defineStore('app-auth', () => {
  const router = useRouter()

  /**
   * 被"提升"的父级路径集合。
   * 这些父级只有一个子页面，子页面被提升成顶级菜单后，
   * 面包屑里就不该再出现这一层（否则会出现两个同名节点）。
   */
  const promotedParentPaths = new Set<string>()

  /** 路由表 -> 菜单树 */
  const showMenuListGet = computed<MenuOptions[]>(() => {
    const routes = router.getRoutes()

    // 顶层路由：路径只有一段（/dashboard、/student、/score ...）
    const topLevel = routes.filter((r) => {
      if (!r.meta?.title || r.meta.hidden) return false
      if (!r.path.startsWith('/') || r.path === '/') return false
      return r.path.split('/').filter(Boolean).length === 1
    })

    const result: MenuOptions[] = []

    for (const r of topLevel) {
      const parentIcon = resolveIcon(String(r.meta!.icon ?? ''))
      const parentMeta: MenuMeta = {
        title: String(r.meta!.title),
        icon: parentIcon,
        activeMenu: r.meta?.activeMenu ? String(r.meta.activeMenu) : undefined,
      }

      const children = r.children
        ?.filter((c) => c.meta?.title)
        .map((c) => ({
          path: (c.path.startsWith('/') ? c.path : r.path + '/' + c.path).replace(/\/+/g, '/'),
          name: c.name ? String(c.name) : undefined,
          meta: {
            title: String(c.meta!.title),
            // 子页面没单独配图标时留空，渲染时不占位
            icon: c.meta!.icon ? resolveIcon(String(c.meta!.icon)) : undefined,
          } as MenuMeta,
        }))

      // 没有子页面：本身就是顶级菜单项
      if (!children?.length) {
        result.push({
          path: r.path,
          name: r.name ? String(r.name) : undefined,
          meta: parentMeta,
        })
        continue
      }

      // ★ 有子页面：全部提升为顶级菜单项（本项目不要二级菜单）
      //   父级这一层不再出现在菜单里，面包屑里也要跳过（见 promotedParentPaths）
      if (children.length) {
        promotedParentPaths.add(r.path)
        for (const child of children) {
          result.push({
            path: child.path,
            name: child.name,
            meta: {
              ...child.meta,
              // 子页面没单独配图标时回退到父级图标，避免出现默认的文档图标
              icon: child.meta.icon ?? parentIcon,
            },
          })
        }
        continue
      }
    }

    return result
  })

  /** 扁平化后的叶子菜单（菜单搜索用） */
  const flatMenuListGet = computed<MenuOptions[]>(() => {
    const result: MenuOptions[] = []

    const walk = (items: MenuOptions[]) => {
      for (const item of items) {
        if (item.children?.length) {
          walk(item.children)
        } else {
          result.push(item)
        }
      }
    }

    walk(showMenuListGet.value)
    return result
  })

  /**
   * 面包屑：key 是叶子路由的完整路径，value 是从父级到叶子的菜单链。
   * （Geeker 用后端下发的面包屑数据，本项目从路由 matched 链推导）
   */
  const breadcrumbListGet = computed<Record<string, MenuOptions[]>>(() => {
    const result: Record<string, MenuOptions[]> = {}
    const menuByPath = new Map<string, MenuOptions>()

    const collect = (items: MenuOptions[]) => {
      for (const item of items) {
        menuByPath.set(item.path, item)
        if (item.children?.length) collect(item.children)
      }
    }
    collect(showMenuListGet.value)

    for (const route of router.getRoutes()) {
      if (!route.meta?.title) continue

      const chain: MenuOptions[] = []
      // matched 从外到内：Layout -> 模块 -> 页面
      for (const record of router.resolve(route.path).matched) {
        const path = record.path.replace(/\/+$/, '') || '/'

        // 该父级的唯一子页面已被提升为顶级菜单，这一层不再出现在面包屑里
        if (promotedParentPaths.has(path)) continue

        const menu = menuByPath.get(path)
        if (menu) {
          chain.push(menu)
        } else if (record.meta?.title) {
          chain.push({
            path,
            name: record.name ? String(record.name) : undefined,
            meta: { title: String(record.meta.title) },
          })
        }
      }

      if (chain.length) {
        result[route.path] = chain
      }
    }

    return result
  })

  /** 按路径找菜单项 */
  function findMenu(path: string): MenuOptions | undefined {
    let hit: MenuOptions | undefined
    const walk = (items: MenuOptions[]) => {
      for (const item of items) {
        if (item.path === path) hit = item
        if (item.children?.length) walk(item.children)
      }
    }
    walk(showMenuListGet.value)
    return hit
  }

  /**
   * 取某个路由的图标（页签用）。
   * 页面本身没配图标时，回退到所属模块的图标。
   */
  function getRouteIcon(path: string): Component | undefined {
    const menu = findMenu(path)
    if (menu?.meta.icon) return menu.meta.icon as Component

    // 页面被提升成顶级菜单时菜单树里能找到；找不到就沿父级链回退
    const resolved = router.resolve(path)
    for (let i = resolved.matched.length - 2; i >= 0; i--) {
      const parentPath = resolved.matched[i].path.replace(/\/+$/, '') || '/'
      const parent = findMenu(parentPath)
      if (parent?.meta.icon) return parent.meta.icon as Component
    }

    return undefined
  }

  return {
    showMenuListGet,
    flatMenuListGet,
    breadcrumbListGet,
    getRouteIcon,
  }
})
