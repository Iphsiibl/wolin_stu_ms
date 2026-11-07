<!--
  ProTable 的一列。

  【为什么用 h() 而不是 Geeker 原版的 TSX】
  原版是 <script setup lang="tsx">，但 TSX 需要 @vitejs/plugin-vue-jsx 插件，
  而本项目没有装（也不允许新增依赖），
  所以这里用 Vue 的 h() 重写了同样的渲染逻辑，行为保持一致。
-->
<script lang="ts">
import { ElTableColumn, ElTag } from 'element-plus'
import { defineComponent, h, inject, ref, useSlots, type PropType, type VNode } from 'vue'

import type { ColumnProps, HeaderRenderScope, RenderScope } from '@/components/ProTable/interface'
import { filterEnum, formatValue, handleRowAccordingToProp, isRefValue, pickColumnAttrs } from '@/utils/proTable'
import { handleProp } from '@/utils/table'

/** el-tag 支持的类型 */
type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

/** el-tag 的合法 type 白名单 */
const VALID_TAG_TYPES: readonly TagType[] = ['primary', 'success', 'warning', 'info', 'danger']

export default defineComponent({
  name: 'TableColumn',
  props: {
    column: { type: Object as PropType<ColumnProps>, required: true },
  },
  setup(props) {
    const slots = useSlots()
    const enumMap = inject('enumMap', ref(new Map<string, { [key: string]: any }[]>()))

    // 列是否显示（isShow 可以写成 ref）
    const isColumnVisible = (item: ColumnProps): boolean => {
      const show = item.isShow
      if (show === undefined || show === null) return true
      if (isRefValue<boolean>(show)) return show.value !== false
      return show !== false
    }

    // 是否用 tag 展示（tag 可以写成 ref）
    const isTagEnabled = (item: ColumnProps): boolean => {
      const tag = item.tag
      if (tag === undefined || tag === null) return false
      if (isRefValue<boolean>(tag)) return tag.value === true
      return tag === true
    }

    // 渲染表格数据
    const renderCellData = (item: ColumnProps, scope: RenderScope<any>) => {
      return enumMap.value.get(item.prop!) && item.isFilterEnum
        ? filterEnum(
            handleRowAccordingToProp(scope.row, item.prop!),
            enumMap.value.get(item.prop!),
            item.fieldNames,
          )
        : formatValue(handleRowAccordingToProp(scope.row, item.prop!))
    }

    // 获取 tag 类型
    // 【注意】el-tag 的 type 有取值校验，传空串/非法值会触发 Element Plus 告警，
    // 所以这里统一做白名单过滤，取不到时回落到 primary。
    const getTagType = (item: ColumnProps, scope: RenderScope<any>): TagType => {
      const raw = filterEnum(
        handleRowAccordingToProp(scope.row, item.prop!),
        enumMap.value.get(item.prop!),
        item.fieldNames,
        'tag',
      )
      return VALID_TAG_TYPES.includes(raw as TagType) ? (raw as TagType) : 'primary'
    }

    // 自定义单元格用的插槽名：优先用 slotName，其次取 prop 的最后一段
    const getSlotName = (item: ColumnProps): string => {
      if (item.slotName) return item.slotName
      return item.prop ? handleProp(item.prop) : ''
    }

    const renderTableColumn = (item: ColumnProps): VNode => {
      const slotName = getSlotName(item)
      const attrs = pickColumnAttrs(item as Record<string, any>)
      attrs.align = item.align ?? 'center'
      attrs.showOverflowTooltip = item.showOverflowTooltip ?? item.prop !== 'operation'

      // 排序相关属性：显式透传给 el-table-column
      // （sortable 决定表头有没有排序箭头，sortMethod / sortBy 决定比较规则，
      //   sortOrders 决定点击表头时的升/降序切换顺序）
      if (item.sortable !== undefined) attrs.sortable = item.sortable
      if (item.sortMethod !== undefined) attrs.sortMethod = item.sortMethod
      if (item.sortBy !== undefined) attrs.sortBy = item.sortBy
      if (item.sortOrders !== undefined) attrs.sortOrders = item.sortOrders

      return h(ElTableColumn, attrs, {
        default: (scope: RenderScope<any>) => {
          // 多级表头
          if (item._children) return item._children.map((child) => renderTableColumn(child))
          // 自定义渲染
          if (item.render) return item.render(scope)
          // 自定义插槽
          if (slotName && slots[slotName]) return slots[slotName]!(scope)
          // 标签展示
          if (isTagEnabled(item)) {
            return h(ElTag, { type: getTagType(item, scope) }, () => renderCellData(item, scope))
          }
          return renderCellData(item, scope)
        },
        header: (scope: HeaderRenderScope<any>) => {
          if (item.headerRender) return item.headerRender(scope)
          if (slotName && slots[`${slotName}Header`]) return slots[`${slotName}Header`]!(scope)
          return item.label
        },
      })
    }

    return () => (isColumnVisible(props.column) ? renderTableColumn(props.column) : null)
  },
})
</script>
