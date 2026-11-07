<!-- 📚📚📚 Pro-Table 文档: https://juejin.cn/post/7166068828202336263 -->

<template>
  <!-- 表格主体：筛选条 + 工具条 + 表格 + 分页，合成一张册页 -->
  <div class="card table-panel panel-ledger" :class="{ 'is-narrow': narrow }">
    <!-- 查询表单 -->
    <SearchForm
      v-show="isShowSearch"
      :search="_search"
      :reset="_reset"
      :columns="searchColumns"
      :search-param="searchParam"
      :search-col="searchCol"
    />

    <div class="table-main">
      <!-- 表格头部 操作按钮 -->
      <div class="table-header">
        <div class="header-button-lf">
          <slot
            name="tableHeader"
            :selected-list="selectedList"
            :selected-list-ids="selectedListIds"
            :is-selected="isSelected"
          />
        </div>
        <div v-if="toolButton" class="header-button-ri">
          <slot name="toolButton">
            <el-button v-if="showToolButton('refresh')" :icon="Refresh" circle @click="handleRefresh" />
            <el-button
              v-if="showToolButton('setting') && columns.length"
              :icon="Operation"
              circle
              @click="openColSetting"
            />
            <el-button
              v-if="showToolButton('search') && searchColumns?.length"
              :icon="Search"
              circle
              @click="isShowSearch = !isShowSearch"
            />
          </slot>
        </div>
      </div>
      <!-- 表格主体 -->
      <el-table
        v-loading="loading"
        v-bind="$attrs"
        :id="uuid"
        ref="tableRef"
        :data="processTableData"
        :border="border"
        :row-key="rowKey"
        :default-sort="tableDefaultSort"
        @selection-change="selectionChange"
        @sort-change="handleSortChange"
      >
        <!-- 默认插槽 -->
        <slot />
        <template v-for="(item, index) in tableColumns" :key="String(item.prop ?? item.label ?? index)">
          <!-- selection || radio || index || expand || sort -->
          <el-table-column
            v-if="item.type && columnTypes.includes(item.type)"
            v-bind="pickColumnAttrs(item)"
            :align="item.align ?? 'center'"
            :reserve-selection="item.type == 'selection'"
          >
            <template #default="scope">
              <!-- expand -->
              <template v-if="item.type == 'expand'">
                <component :is="item.render" v-bind="scope" v-if="item.render" />
                <slot v-else :name="item.type" v-bind="scope" />
              </template>
              <!-- radio -->
              <el-radio v-if="item.type == 'radio'" v-model="radio" :value="scope.row[rowKey]">
                <i></i>
              </el-radio>
              <!-- sort -->
              <el-tag v-if="item.type == 'sort'" class="move">
                <el-icon><DCaret /></el-icon>
              </el-tag>
            </template>
          </el-table-column>
          <!-- other -->
          <TableColumn v-else :column="item">
            <template v-for="slot in Object.keys($slots)" #[slot]="scope">
              <slot :name="slot" v-bind="scope" />
            </template>
          </TableColumn>
        </template>
        <!-- 插入表格最后一行之后的插槽 -->
        <template #append>
          <slot name="append" />
        </template>
        <!-- 无数据 -->
        <template #empty>
          <div class="table-empty">
            <slot name="empty">
              <img src="@/assets/images/notData.png" alt="notData" />
              <div>暂无数据</div>
            </slot>
          </div>
        </template>
      </el-table>
      <!-- 分页组件 -->
      <slot name="pagination">
        <Pagination
          v-if="pagination"
          :pageable="pageable"
          :handle-size-change="handleSizeChange"
          :handle-current-change="handleCurrentChange"
        />
      </slot>
    </div>
  </div>
  <!-- 列设置 -->
  <ColSetting v-if="toolButton" ref="colRef" v-model:col-setting="colSetting" />
</template>

<script setup lang="ts" name="ProTable">
import { Operation, Refresh, Search } from '@element-plus/icons-vue'
import Sortable from 'sortablejs'
import { computed, onMounted, provide, reactive, ref, watch } from 'vue'

import type { ColumnProps, EnumProps, ProTableProps, ProTableSort, SortOrder, TypeProps } from '@/components/ProTable/interface'
import SearchForm from '@/components/SearchForm/index.vue'
import { useSelection } from '@/hooks/useSelection'
import { useTable } from '@/hooks/useTable'
import { isRefValue, normalizeSortRules, pickColumnAttrs, sortRowsByRules } from '@/utils/proTable'
import { generateUUID, handleProp } from '@/utils/table'

import ColSetting from './components/ColSetting.vue'
import Pagination from './components/Pagination.vue'
import TableColumn from './components/TableColumn.vue'

// 接受父组件参数，配置默认值
const props = withDefaults(defineProps<ProTableProps>(), {
  columns: () => [],
  requestAuto: true,
  pagination: true,
  initParam: {},
  border: true,
  toolButton: true,
  rowKey: 'id',
  searchCol: () => ({ xs: 1, sm: 2, md: 2, lg: 3, xl: 4 }),
  loading: false,
})

// table 实例
const tableRef = ref<{ clearSelection: () => void }>()

// 生成组件唯一id
const uuid = ref('id-' + generateUUID())

// column 列类型
const columnTypes: TypeProps[] = ['selection', 'radio', 'index', 'expand', 'sort']

// 是否显示搜索模块
const isShowSearch = ref(true)

// 控制 ToolButton 显示
const showToolButton = (key: 'refresh' | 'setting' | 'search') => {
  return Array.isArray(props.toolButton) ? props.toolButton.includes(key) : props.toolButton
}

// 单选值
const radio = ref('')

// 表格多选 Hooks
const { selectionChange, selectedList, selectedListIds, isSelected } = useSelection(props.rowKey)

// 表格操作 Hooks
const {
  tableData,
  pageable,
  searchParam,
  searchInitParam,
  getTableList,
  search,
  reset,
  handleSizeChange,
  handleCurrentChange,
} = useTable(props.requestApi, props.initParam, props.pagination, props.dataCallback, props.requestError)

// 清空选中数据列表
const clearSelection = () => tableRef.value!.clearSelection()

// 初始化表格数据 && 拖拽排序
onMounted(() => {
  dragSort()
  if (props.requestAuto) {
    getTableList()
  }

  if (props.data) {
    pageable.value.total = props.data.length
  }
})

// 静态数据（:data）变化时同步总条数，保证分页器显示正确
watch(
  () => props.data,
  (val) => {
    if (val) pageable.value.total = val.length
  },
)

/* ---------------------------------------------------------------------
 * 排序
 * ------------------------------------------------------------------ */

// 父组件传入的默认排序规则（多条按数组顺序依次比较）
const defaultSortRules = computed(() => normalizeSortRules(props.defaultSort))

// 用户点表头后的排序规则：null = 沿用默认排序，[] = 取消排序
const userSortRules = ref<ProTableSort[] | null>(null)

// 当前生效的排序规则
const activeSortRules = computed(() => userSortRules.value ?? defaultSortRules.value)

// 传给 el-table 的 default-sort：Element Plus 一次只支持一列，取第一条作为主序
// （表头箭头落在主序列上，其余规则由 ProTable 自己比较）
const tableDefaultSort = computed(() => {
  const first = defaultSortRules.value[0]
  return first ? { prop: first.prop, order: first.order } : undefined
})

// 表头排序变化：同步 ProTable 自己的排序规则，
// 这样点表头排的是【整份数据】，翻到下一页依然是有序的
const handleSortChange = ({ prop, order }: { prop: string | null; order: SortOrder | null }) => {
  // 通知父组件（服务端分页的页面要拿这个去重新请求）
  emit('sortChange', { prop, order })

  // 第三次点击 = 取消排序
  if (!prop || !order) {
    userSortRules.value = []
    return
  }
  userSortRules.value = [{ prop, order }]
}

// 处理表格数据
const processTableData = computed(() => {
  const source = props.data ?? tableData.value
  // 先按当前排序规则排整份数据，再分页切片
  // （el-table 内置排序只作用于当前页，排完整份数据才能保证翻页后依然有序）
  const sorted = sortRowsByRules(source, activeSortRules.value, flatColumns.value)
  // 服务端分页模式：数据本身就是当前页，不再切片
  if (!props.data) return sorted
  if (!props.pagination) return sorted
  return sorted.slice(
    (pageable.value.pageNum - 1) * pageable.value.pageSize,
    pageable.value.pageSize * pageable.value.pageNum,
  )
})

// 监听页面 initParam 改化，重新获取表格数据
watch(() => props.initParam, getTableList, { deep: true })

// 接收 columns 并设置为响应式
// （这里显式转成 any 再转回来：ColumnProps 继承了 el-table-column 的全部 props，
//   Vue 的 UnwrapNestedRefs 对这么深的类型会报 TS2589，运行时行为不受影响）
const tableColumns = reactive(props.columns as any) as ColumnProps[]

// 扁平化 columns
const flatColumns = computed(() => flatColumnsFunc(tableColumns))

// 定义 enumMap 存储 enum 值（避免异步请求无法格式化单元格内容 || 无法填充搜索下拉选择）
const enumMap = ref(new Map<string, { [key: string]: any }[]>())
const setEnumMap = async ({ prop, enum: enumValue }: ColumnProps) => {
  if (!enumValue) return

  // 如果当前 enumMap 存在相同的值 return
  if (enumMap.value.has(prop!) && (typeof enumValue === 'function' || enumMap.value.get(prop!) === enumValue)) return

  // 当前 enum 为静态数据，则直接存储到 enumMap
  if (typeof enumValue !== 'function') {
    const list = isRefValue<EnumProps[]>(enumValue) ? enumValue.value : enumValue
    enumMap.value.set(prop!, list)
    return
  }

  // 为了防止接口执行慢，而存储慢，导致重复请求，所以预先存储为[]，接口返回后再二次存储
  enumMap.value.set(prop!, [])

  // 当前 enum 为后台数据需要请求数据，则调用该请求接口，并存储到 enumMap
  const { data } = await enumValue()
  enumMap.value.set(prop!, data)
}

// 注入 enumMap
provide('enumMap', enumMap)

// 扁平化 columns 的方法
const flatColumnsFunc = (columns: ColumnProps[], flatArr: ColumnProps[] = []) => {
  columns.forEach(async (col) => {
    if (col._children?.length) flatArr.push(...flatColumnsFunc(col._children))
    flatArr.push(col)

    // column 添加默认 isShow && isSetting && isFilterEnum 属性值
    col.isShow = col.isShow ?? true
    col.isSetting = col.isSetting ?? true
    col.isFilterEnum = col.isFilterEnum ?? true

    // 设置 enumMap
    await setEnumMap(col)
  })
  return flatArr.filter((item) => !item._children?.length)
}

// 过滤需要搜索的配置项 && 排序
const searchColumns = computed(() => {
  return flatColumns.value
    ?.filter((item) => item.search?.el || item.search?.render)
    .sort((a, b) => a.search!.order! - b.search!.order!)
})

// 设置 搜索表单默认排序 && 搜索表单项的默认值
searchColumns.value?.forEach((column, index) => {
  column.search!.order = column.search?.order ?? index + 2
  const key = column.search?.key ?? handleProp(column.prop!)
  const defaultValue = column.search?.defaultValue
  if (defaultValue !== undefined && defaultValue !== null) {
    searchParam.value[key] = defaultValue
    searchInitParam.value[key] = defaultValue
  }
})

// 列设置 ==> 需要过滤掉不需要设置的列
const colRef = ref()
const colSetting = ref<ColumnProps[]>(
  tableColumns.filter((item) => {
    const { type, prop, isSetting } = item
    return !columnTypes.includes(type!) && prop !== 'operation' && isSetting
  }),
)
const openColSetting = () => colRef.value.openColSetting()

// 定义 emit 事件
const emit = defineEmits<{
  search: []
  reset: []
  refresh: []
  dragSort: [{ newIndex?: number; oldIndex?: number }]
  /**
   * 表头排序变化。
   * 静态 data 的页面自己就排好了，父组件一般不用管；
   * 但服务端分页的页面（比如就业信息）必须知道用户点了哪一列，
   * 否则排的只是当前这一页 —— 所以这里把变化抛出去。
   */
  sortChange: [{ prop: string | null; order: SortOrder | null }]
}>()

const _search = () => {
  search()
  emit('search')
}

const _reset = () => {
  reset()
  emit('reset')
}

/**
 * 刷新按钮：
 *   - requestApi 型表格由 useTable 自己重新拉数据
 *   - 静态 data 型表格 useTable 拉不了，交给父组件通过 @refresh 重新加载
 */
const handleRefresh = () => {
  getTableList()
  emit('refresh')
}

// 表格拖拽排序
const dragSort = () => {
  const tbody = document.querySelector(`#${uuid.value} tbody`) as HTMLElement | null
  if (!tbody) return
  Sortable.create(tbody, {
    handle: '.move',
    animation: 300,
    onEnd({ newIndex, oldIndex }) {
      const [removedItem] = processTableData.value.splice(oldIndex!, 1)
      processTableData.value.splice(newIndex!, 0, removedItem)
      emit('dragSort', { newIndex, oldIndex })
    },
  })
}

// 暴露给父组件的参数和方法 (外部需要什么，都可以从这里暴露出去)
defineExpose({
  element: tableRef,
  tableData: processTableData,
  radio,
  pageable,
  searchParam,
  searchInitParam,
  isSelected,
  selectedList,
  selectedListIds,

  // 下面为 function
  getTableList,
  search,
  reset,
  handleSizeChange,
  handleCurrentChange,
  clearSelection,
  enumMap,
})
</script>
