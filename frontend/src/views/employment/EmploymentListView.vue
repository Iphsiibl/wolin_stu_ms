/**
 * =====================================================================
 * 就业信息页
 * =====================================================================
 * 用的是后端 /employment/page 分页接口（真正的服务端分页），
 * 配合多条件筛选 /employment/search。
 *
 * 【ProTable 改造说明】
 *   - 这是唯一一个【真服务端分页】的页面，用 :request-api 模式：
 *     ProTable 把 {pageNum, pageSize, ...搜索条件} 传给 requestApi，
 *     requestApi 返回 { data: { list, total } } 即可
 *   - 后端返回的 {code, message, data, total} 用 @/utils/table 的
 *     toTableResult 转成 ProTable 期望的形状
 *   - 有筛选条件时走后端 search 接口（不分页），没有筛选条件时走 paged 接口，
 *     与原来的行为一致
 * =====================================================================
 */
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, Edit, Plus } from '@element-plus/icons-vue'

import {
  createEmployment,
  deleteEmployment,
  fetchEmploymentPage,
  fetchUnemployed,
  searchEmployment,
  updateEmployment,
} from '@/api/employment'
import ProTable from '@/components/ProTable/index.vue'
import StudentSelectField from '@/components/StudentSelectField/index.vue'
import type { ColumnProps, ProTableSort } from '@/components/ProTable/interface'
import type { Employment, EmploymentSearch, Student } from '@/types/models'
import { formatDate, formatNumber, sexTagClass, sexTagType } from '@/utils/format'
import { toTableResult } from '@/utils/table'

/** 总条数（ProTable 内部也有一份，这里给标题栏用） */
const total = ref(0)
/** 是否处于筛选模式（用 search 接口） */
const filtering = ref(false)

/* ---------------------------------------------------------------------
 * 表格列配置（ProTable）
 * ------------------------------------------------------------------ */

/** 学历下拉选项 */
const EDU_BG_OPTIONS = [
  { label: '专科', value: '专科' },
  { label: '本科', value: '本科' },
  { label: '硕士', value: '硕士' },
  { label: '博士', value: '博士' },
]

/** 性别下拉选项 */
const SEX_OPTIONS = [
  { label: '男', value: '男' },
  { label: '女', value: '女' },
]

/** 默认排序：薪资降序（高到低）→ 学号升序（同薪时按学号排） */
const defaultSort: ProTableSort[] = [
  { prop: 'salary', order: 'descending' },
  { prop: 'stu_id', order: 'ascending' },
]

/**
 * 当前的排序规则。
 *
 * 这一页是【真服务端分页】：后端一次只给一页，
 * 所以排序必须一起交给后端做 —— 只在前端排的话，
 * 排的只是当前这一页，翻到下一页顺序就断了。
 *
 * 格式与后端约定一致：'字段:方向'，多段逗号分隔。
 */
const currentSort = ref<string>(toSortParam(defaultSort))

/** 把 ProTable 的排序规则转成后端要的字符串 */
function toSortParam(rules: ProTableSort[]): string {
  return rules.map((r) => `${r.prop}:${r.order === 'descending' ? 'desc' : 'asc'}`).join(',')
}

const columns: ColumnProps[] = [
  { type: 'index', label: '#', width: 55, align: 'center', isSetting: false, className: 'num' },
  // 【列宽口径】内容列一律用 minWidth，让剩余空间按比例摊开；
  // 可排序列不低于 76（表头文字 + 排序箭头约 50px，再窄会被省略号截断）。
  // 整表列宽之和控制在 1000 以内，1366 宽的笔记本不用横向滚动。
  { prop: 'stu_id', label: '学号', minWidth: 84, align: 'center', className: 'num', sortable: true },
  {
    prop: 'stu_name',
    label: '姓名',
    minWidth: 90,
    search: { el: 'input', props: { placeholder: '学生姓名' } },
  },
  {
    prop: 'stu_sex',
    label: '性别',
    minWidth: 60,
    align: 'center',
    slotName: 'stu_sex',
    search: { el: 'select', props: { placeholder: '全部', clearable: true } },
    enum: SEX_OPTIONS,
  },
  { prop: 'class_name', label: '班级', minWidth: 110, showOverflowTooltip: true },
  {
    prop: 'company',
    label: '公司',
    minWidth: 120,
    showOverflowTooltip: true,
    search: { el: 'input', props: { placeholder: '公司名称' } },
  },
  {
    prop: 'salary',
    label: '薪资',
    minWidth: 110,
    align: 'right',
    slotName: 'salary',
    sortable: true,
    // 高到低：第一次点表头就是降序
    sortOrders: ['descending', 'ascending', null],
  },
  {
    // 最低薪资：只用于搜索，不显示在表格里
    prop: 'salary_min',
    label: '最低薪资',
    isShow: false,
    isSetting: false,
    search: { el: 'input-number', props: { controls: false, placeholder: '最低' } },
  },
  {
    // 最高薪资：只用于搜索，不显示在表格里
    prop: 'salary_max',
    label: '最高薪资',
    isShow: false,
    isSetting: false,
    search: { el: 'input-number', props: { controls: false, placeholder: '最高' } },
  },
  {
    // 学历：只用于搜索，不显示在表格里
    prop: 'edu_bg',
    label: '学历',
    isShow: false,
    isSetting: false,
    search: { el: 'select', props: { placeholder: '全部', clearable: true } },
    enum: EDU_BG_OPTIONS,
  },
  { prop: 'open_date', label: '简历开放', minWidth: 106, align: 'center', slotName: 'open_date' },
  { prop: 'offer_date', label: 'Offer 时间', minWidth: 106, align: 'center', slotName: 'offer_date' },
  {
    prop: 'operation',
    label: '操作',
    width: 170,
    align: 'center',
    fixed: 'right',
    slotName: 'operation',
    isSetting: false,
  },
]

/**
 * ProTable 的数据请求。
 * 参数是 { pageNum, pageSize, ...搜索条件 }，返回 { data: { list, total } }。
 */
async function requestApi(params: any) {
  const { pageNum, pageSize, ...filters } = params ?? {}
  const hasFilter = Object.values(filters).some((v) => v !== '' && v !== undefined && v !== null)
  filtering.value = hasFilter

  if (hasFilter) {
    // 有筛选条件时走后端 search 接口
    const res = await searchEmployment(filters as EmploymentSearch)
    total.value = res.total ?? res.data?.length ?? 0
    return toTableResult(res)
  }

  // 没筛选条件时走后端分页接口（排序也一起交给后端）
  const res = await fetchEmploymentPage({
    page: pageNum ?? 1,
    size: pageSize ?? 10,
    sort: currentSort.value,
  })
  total.value = res.total ?? 0
  return toTableResult(res)
}

/**
 * 表头排序变化：把新的排序规则翻译给后端，重新拉这一页。
 *
 * 不处理的话，点表头只会把【当前这一页】重排，
 * 翻页之后顺序就断了 —— 用户会觉得"排序坏了"。
 */
async function handleSortChange({ prop, order }: { prop: string | null; order: string | null }) {
  if (!prop || !order) {
    currentSort.value = ''
  } else {
    currentSort.value = `${prop}:${order === 'descending' ? 'desc' : 'asc'}`
  }
  await reload()
}

/** ProTable 实例（用来重新拉数据） */
const tableRef = ref()

/** 重新加载当前页数据 */
async function reload() {
  await tableRef.value?.getTableList()
}

/* ---------------- 新增 / 修改 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('新增就业信息')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)

/**
 * 【学号不能随便改】
 *
 * 原来这个表单的"学号"是一个可以直接输入数字的输入框，
 * 有两个问题：
 *
 *   1. 号码可以随便填 —— 填一个库里根本没有的学号，
 *      要到提交时后端才报错（404「学生学籍不存在」）。
 *   2. 修改的时候也能改 —— 但后端的 EmpUpdate 模型
 *      【压根不接受 stu_id 字段】，改了在后端被直接丢掉。
 *      前端看起来改成功了，其实数据一动没动，纯属误导。
 *
 * 现在：
 *   新增 -> 只能从"未就业学生"下拉里选（后端本来就有这个接口），
 *           选出来的号一定存在，而且一定还没有就业记录；
 *   修改 -> 学号锁死不可改（就业记录和学生是一对一绑定的）。
 */
const form = reactive<{
  stu_id: number | undefined
  company: string
  salary: number
  open_date: string
  offer_date: string
}>({
  stu_id: undefined,
  company: '',
  salary: 0,
  open_date: '',
  offer_date: '',
})

/** 未就业学生（新增时的学号下拉选项） */
interface SelectableStudent extends Student {
  /** /employment/unemployed 额外带的班级名 */
  class_name?: string | null
}

const selectableStudents = ref<SelectableStudent[]>([])
const loadingStudents = ref(false)

/** 编辑模式下显示的学生姓名（学号锁死时用来说明这是谁） */
const editingStudentName = ref('')

/** 拉取未就业学生，作为"学号"下拉的选项 */
async function loadSelectableStudents() {
  loadingStudents.value = true
  try {
    const res = await fetchUnemployed()
    selectableStudents.value = (res.data ?? []) as SelectableStudent[]
  } catch {
    selectableStudents.value = []
  } finally {
    loadingStudents.value = false
  }
}

const rules: FormRules = {
  stu_id: [{ required: true, message: '请选择学生', trigger: 'change' }],
  company: [
    { required: true, message: '请输入公司名称', trigger: 'blur' },
    // 后端 schema/emp_request.py：company varchar(50)，超长会 422
    { max: 50, message: '公司名称最多 50 个字', trigger: 'blur' },
  ],
  salary: [
    { required: true, message: '请输入薪资', trigger: 'blur' },
    // 后端 salary 是 gt=0（必须大于 0），放行 0 会被 422 拦下
    { type: 'number', min: 1, message: '薪资必须大于 0', trigger: 'blur' },
  ],
  open_date: [{ required: true, message: '请选择简历开放时间', trigger: 'change' }],
  // 【Offer 时间是必填的】
  // 后端 schema/emp_request.py 里 open_date / offer_date 都是必填：
  // 缺了任何一端，"就业时长"这个核心指标就统计不出来，
  // 后端会直接 422。这里必须和后端保持一致 ——
  // 之前这个字段标着"选填"且没有校验规则，
  // 用户照着界面填完一提交就是 422，白填一场。
  offer_date: [{ required: true, message: '请选择 Offer 时间', trigger: 'change' }],
}

function handleCreate() {
  editingId.value = null
  editingStudentName.value = ''
  dialogTitle.value = '新增就业信息'
  Object.assign(form, {
    stu_id: undefined,
    company: '',
    salary: 0,
    open_date: '',
    offer_date: '',
  })
  dialogVisible.value = true
  formRef.value?.clearValidate()
  // 打开弹窗的同时把"可选项"拉出来
  loadSelectableStudents()
}

function handleEdit(row: Employment) {
  editingId.value = row.stu_id
  editingStudentName.value = row.stu_name
  dialogTitle.value = `修改就业信息 - ${row.stu_name}`
  Object.assign(form, {
    stu_id: row.stu_id,
    company: row.company,
    salary: row.salary,
    open_date: formatDate(row.open_date),
    offer_date: row.offer_date ? formatDate(row.offer_date) : '',
  })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingId.value === null) {
      await createEmployment({
        stu_id: form.stu_id!,
        company: form.company,
        salary: form.salary,
        open_date: form.open_date,
        offer_date: form.offer_date,
      })
      ElMessage.success('新增成功')
    } else {
      // 【修改时不传 stu_id】
      // 就业记录和学生是一对一绑定的，编号不能改；
      // 后端的 EmpUpdate 也不接受这个字段，传了也是被丢掉。
      await updateEmployment(editingId.value, {
        company: form.company,
        salary: form.salary,
        open_date: form.open_date,
        offer_date: form.offer_date,
      })
      ElMessage.success('修改成功')
    }
    dialogVisible.value = false
    await reload()
  } catch {
    // 提示已由拦截器统一处理
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: Employment) {
  try {
    await ElMessageBox.confirm(
      `确定要删除「${row.stu_name}」的就业信息吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteEmployment(row.stu_id)
    ElMessage.success('删除成功')
    await reload()
  } catch {
    // 用户取消
  }
}
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div class="page-heading">
        <span class="page-eyebrow">Employment</span>
        <div class="page-title">就业信息</div>
        <p class="page-subtitle">
          共 <span class="num">{{ total }}</span> 条就业记录
          <template v-if="filtering">（当前为筛选结果）</template>
        </p>
      </div>
    </div>

    <ProTable
      ref="tableRef"
      :columns="columns"
      :request-api="requestApi"
      :default-sort="defaultSort"
      row-key="stu_id"
      border
      stripe
      @sort-change="handleSortChange"
    >
      <template #tableHeader>
        <el-button type="primary" :icon="Plus" @click="handleCreate">新增就业信息</el-button>
      </template>

      <template #stu_sex="{ row }">
        <el-tag :type="sexTagType(row.stu_sex)" :class="sexTagClass(row.stu_sex)" size="small" effect="light">
          {{ row.stu_sex }}
        </el-tag>
      </template>

      <template #salary="{ row }">
        <span class="num tone-ochre" style="font-weight: 600">¥{{ formatNumber(row.salary) }}</span>
      </template>

      <template #open_date="{ row }">
        <span class="num">{{ formatDate(row.open_date) }}</span>
      </template>

      <template #offer_date="{ row }">
        <span class="num">{{ row.offer_date ? formatDate(row.offer_date) : '-' }}</span>
      </template>

      <template #operation="{ row }">
        <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">修改</el-button>
        <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
      </template>

      <template #empty>
        <div class="empty-hint">暂无就业数据</div>
      </template>
    </ProTable>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="560px" destroy-on-close>
      <div class="card">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
          <el-form-item label="学号" prop="stu_id">
            <!--
              新增选人 / 修改锁号这四种状态都收在组件里，
              列表页本身不写业务分支。
            -->
            <StudentSelectField
              v-model="form.stu_id"
              :options="selectableStudents"
              :loading="loadingStudents"
              :locked="editingId !== null"
              :locked-label="`${form.stu_id} · ${editingStudentName}`"
              empty-text="当前没有未就业的学生 —— 所有学生都已有就业记录"
            />
          </el-form-item>
          <el-form-item label="公司" prop="company">
            <el-input v-model="form.company" placeholder="请输入公司名称" maxlength="50" />
          </el-form-item>
          <el-form-item label="薪资" prop="salary">
            <el-input-number
              v-model="form.salary"
              :min="1"
              :step="500"
              style="width: 100%"
              controls-position="right"
            />
          </el-form-item>
          <el-form-item label="简历开放时间" prop="open_date">
            <el-date-picker
              v-model="form.open_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="Offer 时间" prop="offer_date">
            <el-date-picker
              v-model="form.offer_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="请选择日期"
              style="width: 100%"
            />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
