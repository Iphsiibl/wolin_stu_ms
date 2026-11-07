/**
 * =====================================================================
 * 学生管理页
 * =====================================================================
 * 覆盖能力：分页列表、按姓名查询、按班级查询、新增、修改、删除。
 *
 * 【关于分页的一个重要细节】
 * 后端 /student/select_stu_skip 用的是 skip/limit：
 *   skip  = 跳过几条（第几页从 0 开始数）
 *   limit = 最多返回几条
 *
 * 而 Element Plus 的 el-pagination 是 1-based 的页码，
 * 所以这里要做一次转换：skip = (page - 1) * limit。
 *
 * 另外后端这个接口返回的 total 是"当前这一页的条数"而不是总条数
 *（它把 len(rows) 放进了 total），所以总数要用 后端总数 - 本页数 的方式拿不到，
 * 这里采用【一次拉全量 + 前端分页】的策略，
 * 因为学生总数只有几百条，前端分页体验更好也不会有性能问题。
 *
 * 【ProTable 改造说明】
 * 表格部分换成 ProTable：
 *   - 数据用静态 :data 传入（全量），ProTable 内部按 pageable 自动切片分页
 *   - 搜索项写在列的 search 配置里，搜索/重置由 ProTable 的 SearchForm 负责
 *   - 关键词与班级的筛选逻辑仍然是本页的（前端过滤），通过 @search/@reset 同步
 * =====================================================================
 */
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, Edit, Plus } from '@element-plus/icons-vue'

import {
  createStudent,
  deleteStudent,
  fetchAllAgents,
  fetchAllStudents,
  updateStudent,
} from '@/api/student'
import { fetchAllClasses as loadClasses } from '@/api/class'
import ProTable from '@/components/ProTable/index.vue'
import type { ColumnProps, ProTableSort } from '@/components/ProTable/interface'
import type { ClassInfo } from '@/types/models'
import type { Agent, Student, StudentCreate } from '@/types/models'
import { formatDate, sexTagClass, sexTagType } from '@/utils/format'

/* ---------------------------------------------------------------------
 * 列表数据
 * ------------------------------------------------------------------ */
const loading = ref(false)
const students = ref<Student[]>([])
const agents = ref<Agent[]>([])
const classes = ref<ClassInfo[]>([])

/** 搜索关键词 */
const keyword = ref('')
/** 按班级筛选 */
const filterClassId = ref<number | null>(null)

/** 关键词 + 班级筛选后的结果（ProTable 拿到这个数组后自己切片分页） */
const filteredStudents = computed(() => {
  let list = students.value

  if (keyword.value.trim()) {
    const kw = keyword.value.trim().toLowerCase()
    list = list.filter(
      (s) =>
        s.stu_name.toLowerCase().includes(kw) ||
        String(s.stu_id) === kw ||
        s.stu_tel.includes(kw) ||
        s.stu_school.toLowerCase().includes(kw) ||
        s.stu_major.toLowerCase().includes(kw),
    )
  }

  if (filterClassId.value !== null) {
    list = list.filter((s) => s.stu_class_id === filterClassId.value)
  }

  return list
})

/** 表格列宽拖拽后不重排的最小宽度 */
const tableMinWidth = 100

/* ---------------------------------------------------------------------
 * 排序
 * ------------------------------------------------------------------ */

/** 字符串日期 -> 时间戳（取不到返回 null） */
function toTimestamp(value: string | null | undefined): number | null {
  if (!value) return null
  // 统一按「本地时区的年月日时分秒」解析：
  // 直接 new Date('2022-09-01') 会按 UTC 解析，而 new Date('2022-09-01T00:00:00')
  // 按本地时间解析，两者混在一起会比出 8 小时的偏差。
  const matched = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?/.exec(value)
  if (!matched) return null
  const [, year, month, day, hour = '00', minute = '00', second = '00'] = matched
  const time = new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second),
  ).getTime()
  return Number.isNaN(time) ? null : time
}

/**
 * 入学时间排序比较器（升序比较器，降序由表格自动取反）。
 *
 * 原始值有两种格式：后端返回的是 ISO 字符串（'2022-09-01T00:00:00'），
 * 新增学生时表单的 date-picker 存的是 '2022-09-01'，
 * 两种格式混在一起时字典序不完全等价于时间序，所以统一按时间戳比较，
 * 取不到时间的排在最后。
 */
function compareEnrollDate(a: Record<string, any>, b: Record<string, any>): number {
  const timeA = toTimestamp(a.enroll_date)
  const timeB = toTimestamp(b.enroll_date)
  if (timeA === null && timeB === null) return 0
  if (timeA === null) return 1
  if (timeB === null) return -1
  return timeA - timeB
}

/** 默认排序：学号升序 → 年龄升序 → 入学时间降序（最近入学在前） */
const defaultSort: ProTableSort[] = [
  { prop: 'stu_id', order: 'ascending' },
  { prop: 'stu_age', order: 'ascending' },
  { prop: 'enroll_date', order: 'descending' },
]

/* ---------------------------------------------------------------------
 * 表格列配置（ProTable）
 * ------------------------------------------------------------------ */

/** 班级下拉选项（搜索项用，后台数据） */
async function loadClassEnum() {
  const res = await loadClasses()
  return {
    data: (res.data ?? []).map((c) => ({ label: c.class_name, value: c.class_id })),
  }
}

const columns: ColumnProps[] = [
  { type: 'index', label: '#', width: 52, align: 'center', isSetting: false, className: 'num' },
  {
    // 关键词：只用于搜索，不显示在表格里
    prop: 'keyword',
    label: '关键词',
    isShow: false,
    isSetting: false,
    search: {
      el: 'input',
      props: { placeholder: '姓名 / 学号 / 手机号 / 院校 / 专业' },
    },
  },
  // 【列宽口径】序号和操作列用 width 固定；内容列一律用 minWidth。
  // 原因：Element Plus 把「没写 width 的列」当作弹性列，剩下的空间全分给它 ——
  // 弹性列只剩一列时，那一列会被撑到整屏宽，表格中间就出现巨大的空洞。
  // 全部内容列都写 minWidth，空间才会按比例摊开，表格既铺满又不失衡。
  // 可排序列的 minWidth 不低于 76：表头文字 + 排序箭头约 50px，再窄会被省略号截断。
  // 另外整表列宽之和要控制在 1000 以内 —— 这样 1366 宽的笔记本不用横向滚动，
  // 右侧固定的「操作」列也不会盖住「专业 / 入学时间」。
  { prop: 'stu_id', label: '学号', minWidth: 74, align: 'center', className: 'num', sortable: true },
  { prop: 'stu_name', label: '姓名', minWidth: 80, showOverflowTooltip: true },
  { prop: 'stu_age', label: '年龄', minWidth: 78, align: 'center', className: 'num', sortable: true },
  { prop: 'stu_sex', label: '性别', minWidth: 54, align: 'center', slotName: 'stu_sex' },
  {
    prop: 'stu_class_id',
    label: '班级',
    minWidth: 92,
    align: 'center',
    slotName: 'stu_class',
    search: { el: 'select', props: { placeholder: '全部班级', clearable: true } },
    enum: loadClassEnum,
  },
  { prop: 'stu_tel', label: '手机号', minWidth: 106, className: 'num' },
  { prop: 'stu_school', label: '毕业院校', minWidth: 96, showOverflowTooltip: true },
  { prop: 'stu_major', label: '专业', minWidth: 88, showOverflowTooltip: true },
  { prop: 'agent_name', label: '顾问', minWidth: 70, align: 'center', slotName: 'agent_name' },
  {
    prop: 'enroll_date',
    label: '入学时间',
    minWidth: 98,
    align: 'center',
    slotName: 'enroll_date',
    sortable: true,
    // 「最近入学在前」：第一次点表头就是降序
    sortOrders: ['descending', 'ascending', null],
    // 原始值是日期字符串（格式还不统一），用时间戳比较兜底
    sortMethod: compareEnrollDate,
  },
  {
    prop: 'operation',
    label: '操作',
    // 150 是「修改 / 删除」两个按钮并排一行所需的下限，再窄就会换行成两排
    width: 150,
    align: 'center',
    fixed: 'right',
    slotName: 'operation',
    isSetting: false,
  },
]

/** ProTable 实例（用来读搜索参数、触发刷新） */
const tableRef = ref()

/** 把 ProTable 搜索表单里的值同步到本页的筛选条件 */
function applySearchParams() {
  const params = (tableRef.value?.searchParam ?? {}) as Record<string, any>
  keyword.value = String(params.keyword ?? '')
  const classId = params.stu_class_id
  filterClassId.value =
    classId === undefined || classId === null || classId === '' ? null : Number(classId)
}

/* ---------------------------------------------------------------------
 * 加载数据
 * ------------------------------------------------------------------ */
async function loadStudents() {
  loading.value = true
  try {
    const res = await fetchAllStudents()
    students.value = res.data ?? []
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [agentRes, classRes] = await Promise.all([
    fetchAllAgents(),
    loadClasses(),
  ])
  agents.value = agentRes.data ?? []
  classes.value = classRes.data ?? []
}

/** 班级名 -> id */
function className(id: number | null | undefined): string {
  if (id === null || id === undefined) return '-'
  return classes.value.find((c) => c.class_id === id)?.class_name ?? `班级${id}`
}

/** 刷新（ProTable 右上角的刷新按钮触发） */
async function handleRefresh() {
  await loadStudents()
  ElMessage.success('已刷新')
}

/* ---------------------------------------------------------------------
 * 新增 / 修改
 * ------------------------------------------------------------------ */
const dialogVisible = ref(false)
const dialogTitle = ref('新增学生')
const submitting = ref(false)
const formRef = ref<FormInstance>()

/** 表单数据 */
const form = reactive<StudentCreate>({
  stu_name: '',
  stu_age: 19,
  stu_sex: '男',
  stu_class_id: 1,
  stu_tel: '',
  stu_from: '',
  stu_school: '',
  stu_major: '',
  enroll_date: '',
  gra_date: '',
  edu_bg: '本科',
  agent_id: undefined as number | undefined,
})

/** 正在编辑的学生 id，null 表示新增 */
const editingId = ref<number | null>(null)

const rules: FormRules = {
  stu_name: [
    { required: true, message: '请输入学生姓名', trigger: 'blur' },
    { max: 10, message: '姓名最多 10 个字', trigger: 'blur' },
  ],
  stu_age: [
    { required: true, message: '请输入年龄', trigger: 'blur' },
    { type: 'number', min: 19, message: '年龄必须大于 18', trigger: 'blur' },
  ],
  stu_sex: [{ required: true, message: '请选择性别', trigger: 'change' }],
  stu_class_id: [{ required: true, message: '请选择班级', trigger: 'change' }],
  stu_tel: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' },
  ],
  // 后端 schema/student_request.py：这三个字段都是 varchar(20)
  stu_from: [
    { required: true, message: '请输入生源地', trigger: 'blur' },
    { max: 20, message: '生源地最多 20 个字', trigger: 'blur' },
  ],
  stu_school: [
    { required: true, message: '请输入毕业院校', trigger: 'blur' },
    { max: 20, message: '毕业院校最多 20 个字', trigger: 'blur' },
  ],
  stu_major: [
    { required: true, message: '请输入专业', trigger: 'blur' },
    { max: 20, message: '专业最多 20 个字', trigger: 'blur' },
  ],
  enroll_date: [{ required: true, message: '请选择入学时间', trigger: 'change' }],
  gra_date: [{ required: true, message: '请选择毕业时间', trigger: 'change' }],
  agent_id: [{ required: true, message: '请选择负责顾问', trigger: 'change' }],
}

/** 打开新增弹窗 */
function handleCreate() {
  editingId.value = null
  dialogTitle.value = '新增学生'
  Object.assign(form, {
    stu_name: '',
    stu_age: 19,
    stu_sex: '男',
    stu_class_id: classes.value[0]?.class_id ?? 1,
    stu_tel: '',
    stu_from: '',
    stu_school: '',
    stu_major: '',
    enroll_date: '',
    gra_date: '',
    edu_bg: '本科',
    agent_id: agents.value[0]?.agent_id,
  })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

/** 打开修改弹窗 */
function handleEdit(row: Student) {
  editingId.value = row.stu_id
  dialogTitle.value = `修改学生 - ${row.stu_name}`
  Object.assign(form, {
    stu_name: row.stu_name,
    stu_age: row.stu_age,
    stu_sex: row.stu_sex,
    stu_class_id: row.stu_class_id,
    stu_tel: row.stu_tel,
    stu_from: row.stu_from,
    stu_school: row.stu_school,
    stu_major: row.stu_major,
    enroll_date: formatDate(row.enroll_date),
    gra_date: formatDate(row.gra_date),
    edu_bg: row.edu_bg,
    agent_id: row.agent_id ?? undefined,
  })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

/** 提交表单 */
async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingId.value === null) {
      await createStudent({ ...form })
      ElMessage.success('新增成功')
    } else {
      // stu_id 单独传，后端把它收在 query 上（不能塞 body）
      await updateStudent(editingId.value, { ...form })
      ElMessage.success('修改成功')
    }
    dialogVisible.value = false
    await loadStudents()
  } catch {
    // 错误提示已由 http.ts 的拦截器统一处理
  } finally {
    submitting.value = false
  }
}

/** 删除 */
async function handleDelete(row: Student) {
  try {
    await ElMessageBox.confirm(
      `确定要删除学生「${row.stu_name}」吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteStudent(row.stu_id)
    ElMessage.success('删除成功')
    await loadStudents()
  } catch {
    // 用户取消 或 接口报错（提示已统一处理）
  }
}

onMounted(async () => {
  await Promise.all([loadStudents(), loadOptions()])
})
</script>

<template>
  <div class="page-container">
    <!-- 标题栏 -->
    <div class="page-header">
      <div class="page-heading">
        <span class="page-eyebrow">Student Roster</span>
        <div class="page-title">学生管理</div>
        <p class="page-subtitle">
          共 <span class="num">{{ students.length }}</span> 名学生，当前筛选出
          <span class="num">{{ filteredStudents.length }}</span> 条
        </p>
      </div>
    </div>

    <!-- 表格 -->
    <ProTable
      ref="tableRef"
      :columns="columns"
      :data="filteredStudents"
      :default-sort="defaultSort"
      :loading="loading"
      :min-width="tableMinWidth"
      row-key="stu_id"
      border
      stripe
      @search="applySearchParams"
      @reset="applySearchParams"
      @refresh="handleRefresh"
    >
      <!-- 工具栏按钮 -->
      <template #tableHeader>
        <el-button type="primary" :icon="Plus" @click="handleCreate">新增学生</el-button>
      </template>

      <!-- 自定义单元格 -->
      <template #stu_sex="{ row }">
        <el-tag :type="sexTagType(row.stu_sex)" :class="sexTagClass(row.stu_sex)" size="small" effect="light">
          {{ row.stu_sex }}
        </el-tag>
      </template>

      <template #stu_class="{ row }">
        {{ className(row.stu_class_id) }}
      </template>

      <template #agent_name="{ row }">
        {{ row.agent_name ?? '-' }}
      </template>

      <template #enroll_date="{ row }">
        <span class="num">{{ formatDate(row.enroll_date) }}</span>
      </template>

      <template #operation="{ row }">
        <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">修改</el-button>
        <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
      </template>

      <template #empty>
        <div class="empty-hint">没有符合条件的学生</div>
      </template>
    </ProTable>

    <!-- 新增 / 修改弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="680px"
      destroy-on-close
      @closed="formRef?.clearValidate()"
    >
      <div class="card">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="姓名" prop="stu_name">
                <el-input v-model="form.stu_name" placeholder="请输入姓名" maxlength="10" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="年龄" prop="stu_age">
                <el-input-number
                  v-model="form.stu_age"
                  :min="19"
                  :max="100"
                  style="width: 100%"
                  controls-position="right"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="性别" prop="stu_sex">
                <el-radio-group v-model="form.stu_sex">
                  <el-radio value="男">男</el-radio>
                  <el-radio value="女">女</el-radio>
                </el-radio-group>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="班级" prop="stu_class_id">
                <el-select v-model="form.stu_class_id" placeholder="请选择班级" style="width: 100%">
                  <el-option
                    v-for="c in classes"
                    :key="c.class_id"
                    :label="c.class_name"
                    :value="c.class_id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="手机号" prop="stu_tel">
                <el-input v-model="form.stu_tel" placeholder="11 位手机号" maxlength="11" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="生源地" prop="stu_from">
                <el-input v-model="form.stu_from" placeholder="如：成都" maxlength="20" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="毕业院校" prop="stu_school">
                <el-input v-model="form.stu_school" placeholder="如：西安交通大学" maxlength="20" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="专业" prop="stu_major">
                <el-input v-model="form.stu_major" placeholder="如：软件工程1" maxlength="20" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="入学时间" prop="enroll_date">
                <el-date-picker
                  v-model="form.enroll_date"
                  type="date"
                  value-format="YYYY-MM-DD"
                  placeholder="选择日期"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="毕业时间" prop="gra_date">
                <el-date-picker
                  v-model="form.gra_date"
                  type="date"
                  value-format="YYYY-MM-DD"
                  placeholder="选择日期"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="负责顾问" prop="agent_id">
            <el-select
              v-model="form.agent_id"
              placeholder="请选择负责顾问"
              filterable
              style="width: 100%"
            >
              <el-option
                v-for="a in agents"
                :key="a.agent_id"
                :label="a.agent_name"
                :value="a.agent_id"
              >
                <span>{{ a.agent_name }}</span>
                <span style="float: right; color: #909399; font-size: 12px">
                  {{ a.agent_sex }} · {{ a.agent_age }}岁
                </span>
              </el-option>
            </el-select>
          </el-form-item>

          <el-form-item label="学历">
            <el-select v-model="form.edu_bg" placeholder="请选择学历" style="width: 200px">
              <el-option label="专科" value="专科" />
              <el-option label="本科" value="本科" />
              <el-option label="硕士" value="硕士" />
              <el-option label="博士" value="博士" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
