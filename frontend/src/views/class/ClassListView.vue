/**
 * =====================================================================
 * 班级列表页
 * =====================================================================
 * 注意：后端 /class 模块返回的字段名是中文的，
 * 已经在 api/class.ts 里转换成 class_id / class_name / start_date 了，
 * 这个页面只跟英文字段打交道。
 *
 * 【ProTable 改造说明】
 *   - 数据用静态 :data 传入（全量），ProTable 内部自动切片分页
 *   - 关键词搜索写在列的 search 配置里（列本身不显示），
 *     筛选逻辑是本页的前端过滤：班级名称 / 班级 ID / 开课时间 /
 *     班主任姓名 / 授课老师姓名 都参与匹配
 * =====================================================================
 */
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, Edit, Plus, User } from '@element-plus/icons-vue'

import {
  createClass,
  deleteClass,
  fetchAllClasses,
  fetchAllClassTeachers,
  fetchClassStudents,
  updateClass,
} from '@/api/class'
import { fetchAllTeachers } from '@/api/teacher'
import ProTable from '@/components/ProTable/index.vue'
import type { ColumnProps } from '@/components/ProTable/interface'
import type { ClassInfo, ClassTeacher } from '@/types/models'
import type { Student, Teacher } from '@/types/models'
import { formatDate, sexTagClass, sexTagType } from '@/utils/format'

const loading = ref(false)
const classes = ref<ClassInfo[]>([])
const classTeachers = ref<ClassTeacher[]>([])
const teachers = ref<Teacher[]>([])
/** 搜索关键词 */
const keyword = ref('')

/** 班主任 id -> 姓名，供表格反查 */
const teacherMap = computed<Record<number, string>>(() => {
  const map: Record<number, string> = {}
  for (const ct of classTeachers.value) map[ct.class_teacher_id] = ct.class_teacher_name
  return map
})

/** 授课老师 id -> 姓名，供表格反查 */
const teacherNameMap = computed<Record<number, string>>(() => {
  const map: Record<number, string> = {}
  for (const t of teachers.value) map[t.teacher_id] = t.teacher_name
  return map
})

/**
 * 取班主任姓名。
 * 后端 /class 接口已经 JOIN 出姓名了，优先用它；
 * 老师被软删后又重新灌过数据时后端可能给空，再退回本地反查表。
 */
function resolveClassTeacherName(row: ClassInfo): string {
  return (
    row.class_teacher_name ||
    (row.class_teacher_id ? (teacherMap.value[row.class_teacher_id] ?? '') : '') ||
    ''
  )
}

/** 取授课老师姓名，规则同 resolveClassTeacherName */
function resolveTeacherName(row: ClassInfo): string {
  return row.teacher_name || (row.teacher_id ? (teacherNameMap.value[row.teacher_id] ?? '') : '') || ''
}

/** 关键词过滤后的班级（前端过滤，数据量小，没必要走后端） */
const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return classes.value
  return classes.value.filter((c) => {
    return (
      c.class_name.toLowerCase().includes(kw) ||
      String(c.class_id).includes(kw) ||
      c.start_date.includes(kw) ||
      resolveClassTeacherName(c).toLowerCase().includes(kw) ||
      resolveTeacherName(c).toLowerCase().includes(kw)
    )
  })
})

/* ---------------------------------------------------------------------
 * 表格列配置（ProTable）
 * ------------------------------------------------------------------ */
const columns: ColumnProps[] = [
  { type: 'index', label: '#', width: 50, align: 'center', isSetting: false, className: 'num' },
  {
    // 关键词：只用于搜索，不显示在表格里
    prop: 'keyword',
    label: '关键词',
    isShow: false,
    isSetting: false,
    search: {
      el: 'input',
      props: { placeholder: '班级名称 / ID / 班主任 / 授课老师' },
    },
  },
  // 【列宽口径】内容列一律用 minWidth，让剩余空间按比例摊开；
  // 整表列宽之和控制在 1000 以内，1366 宽的笔记本不用横向滚动。
  { prop: 'class_id', label: '班级 ID', minWidth: 92, align: 'center', className: 'num' },
  { prop: 'class_name', label: '班级名称', minWidth: 120 },
  { prop: 'start_date', label: '开课时间', minWidth: 110, align: 'center', slotName: 'start_date' },
  { prop: 'class_teacher_id', label: '班主任', minWidth: 100, align: 'center', slotName: 'class_teacher' },
  { prop: 'teacher_id', label: '授课老师', minWidth: 100, align: 'center', slotName: 'teacher' },
  {
    prop: 'operation',
    label: '操作',
    // 操作列固定在右侧，宽度要留给「学员 / 修改 / 删除」三个按钮。
    // 其它列同时收紧，保证在 1280 宽的笔记本上整表也能排开 ——
    // 否则右侧固定列会盖住「班主任 / 授课老师」两列（要横向滚动才看得到）。
    width: 220,
    align: 'center',
    fixed: 'right',
    slotName: 'operation',
    isSetting: false,
  },
]

/** ProTable 实例（用来读搜索参数） */
const tableRef = ref()

/** 把 ProTable 搜索表单里的值同步到本页的筛选条件 */
function applySearchParams() {
  const params = (tableRef.value?.searchParam ?? {}) as Record<string, any>
  keyword.value = String(params.keyword ?? '')
}

async function loadAll() {
  loading.value = true
  try {
    const [classRes, ctRes, teacherRes] = await Promise.all([
      fetchAllClasses(),
      fetchAllClassTeachers(),
      fetchAllTeachers(),
    ])
    classes.value = classRes.data ?? []
    classTeachers.value = ctRes.data ?? []
    teachers.value = teacherRes.data ?? []
  } finally {
    loading.value = false
  }
}

/** 刷新（ProTable 右上角的刷新按钮触发） */
async function handleRefresh() {
  await loadAll()
  ElMessage.success('已刷新')
}

/* ---------------- 新增 / 修改 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('新建班级')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)

const form = reactive({
  class_name: '',
  start_date: '',
  class_teacher_id: null as number | null,
  teacher_id: null as number | null,
})

const rules: FormRules = {
  class_name: [
    { required: true, message: '请输入班级名称', trigger: 'blur' },
    // 后端 schema/class_schema.py：class_name varchar(20)，超长会 422
    { max: 20, message: '班级名称最多 20 个字', trigger: 'blur' },
  ],
  start_date: [{ required: true, message: '请选择开课时间', trigger: 'change' }],
  class_teacher_id: [{ required: true, message: '请选择班主任', trigger: 'change' }],
  teacher_id: [{ required: true, message: '请选择授课老师', trigger: 'change' }],
}

function handleCreate() {
  editingId.value = null
  dialogTitle.value = '新建班级'
  Object.assign(form, {
    class_name: '',
    start_date: '',
    class_teacher_id: null,
    teacher_id: null,
  })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

function handleEdit(row: ClassInfo) {
  editingId.value = row.class_id
  dialogTitle.value = `修改班级 - ${row.class_name}`
  Object.assign(form, {
    class_name: row.class_name,
    start_date: formatDate(row.start_date),
    class_teacher_id: row.class_teacher_id,
    teacher_id: row.teacher_id,
  })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload = {
      class_name: form.class_name,
      start_date: form.start_date,
      class_teacher_id: form.class_teacher_id!,
      teacher_id: form.teacher_id!,
    }
    if (editingId.value === null) {
      await createClass(payload)
      ElMessage.success('新建成功')
    } else {
      await updateClass(editingId.value, payload)
      ElMessage.success('修改成功')
    }
    dialogVisible.value = false
    await loadAll()
  } catch {
    // 提示已由拦截器统一处理
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: ClassInfo) {
  try {
    await ElMessageBox.confirm(
      `确定要删除班级「${row.class_name}」吗？该班级下的学员也会被一并删除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteClass(row.class_id)
    ElMessage.success('删除成功')
    await loadAll()
  } catch {
    // 用户取消
  }
}

/* ---------------- 班级学员抽屉 ----------------
 * 后端 2026-11-03 新增了 GET /class/get_class/{id}/students，
 * 这里把它用起来：点某行的「学员」，拉出这个班的学员名单。
 * 之前班级页只能看到班主任和授课老师，看不到班里到底有哪些人。
 * ------------------------------------------------ */
const studentDrawerVisible = ref(false)
const studentLoading = ref(false)
const currentClass = ref<ClassInfo | null>(null)
const classStudents = ref<Student[]>([])

async function handleViewStudents(row: ClassInfo) {
  currentClass.value = row
  classStudents.value = []
  studentDrawerVisible.value = true
  studentLoading.value = true
  try {
    const res = await fetchClassStudents(row.class_id)
    classStudents.value = res.data ?? []
  } catch {
    // 提示已由拦截器统一处理
    classStudents.value = []
  } finally {
    studentLoading.value = false
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div class="page-heading">
        <span class="page-eyebrow">Classes</span>
        <div class="page-title">班级列表</div>
        <p class="page-subtitle">
          共 <span class="num">{{ filtered.length }}</span> 个班级<template
            v-if="keyword.trim()"
          >（全部 {{ classes.length }} 个）</template>
        </p>
      </div>
    </div>

    <ProTable
      ref="tableRef"
      :columns="columns"
      :data="filtered"
      :loading="loading"
      row-key="class_id"
      border
      stripe
      @search="applySearchParams"
      @reset="applySearchParams"
      @refresh="handleRefresh"
    >
      <template #tableHeader>
        <el-button type="primary" :icon="Plus" @click="handleCreate">新建班级</el-button>
      </template>

      <template #start_date="{ row }">
        <span class="num">{{ formatDate(row.start_date) }}</span>
      </template>

      <!-- 姓名优先用后端 /class 接口直接返回的；
           后端没给（比如老师被软删后重新灌过数据）再退回本地反查表 -->
      <template #class_teacher="{ row }">
        {{ resolveClassTeacherName(row) || '-' }}
      </template>

      <template #teacher="{ row }">
        {{ resolveTeacherName(row) || '-' }}
      </template>

      <template #operation="{ row }">
        <el-button type="primary" link :icon="User" @click="handleViewStudents(row)">学员</el-button>
        <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">修改</el-button>
        <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
      </template>

      <template #empty>
        <div class="empty-hint">暂无班级数据</div>
      </template>
    </ProTable>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" destroy-on-close>
      <div class="card">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
          <el-form-item label="班级名称" prop="class_name">
            <el-input v-model="form.class_name" placeholder="如：软件工程1班" maxlength="20" />
          </el-form-item>
          <el-form-item label="开课时间" prop="start_date">
            <el-date-picker
              v-model="form.start_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="班主任" prop="class_teacher_id">
            <el-select
              v-model="form.class_teacher_id"
              placeholder="请选择班主任"
              style="width: 100%"
            >
              <el-option
                v-for="ct in classTeachers"
                :key="ct.class_teacher_id"
                :label="ct.class_teacher_name"
                :value="ct.class_teacher_id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="授课老师" prop="teacher_id">
            <el-select v-model="form.teacher_id" placeholder="请选择授课老师" style="width: 100%">
              <el-option
                v-for="t in teachers"
                :key="t.teacher_id"
                :label="t.teacher_name"
                :value="t.teacher_id"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 班级学员抽屉：数据来自后端新增的 GET /class/get_class/{id}/students -->
    <el-drawer
      v-model="studentDrawerVisible"
      :title="`${currentClass?.class_name ?? ''} · 学员名单`"
      direction="rtl"
      size="min(780px, 94vw)"
      destroy-on-close
    >
      <div class="class-students">
        <div class="class-students-head">
          <span class="class-students-count">
            共 <span class="num">{{ classStudents.length }}</span> 名学员
          </span>
          <span class="class-students-tip">
            班主任：{{ currentClass ? resolveClassTeacherName(currentClass) : '-' }}
            · 授课老师：{{ currentClass ? resolveTeacherName(currentClass) : '-' }}
          </span>
        </div>

        <el-table
          v-loading="studentLoading"
          :data="classStudents"
          border
          stripe
          row-key="stu_id"
          height="100%"
        >
          <el-table-column prop="stu_id" label="学号" width="80" align="center" class-name="num" />
          <el-table-column prop="stu_name" label="姓名" width="92" show-overflow-tooltip />
          <el-table-column prop="stu_sex" label="性别" width="62" align="center">
            <template #default="{ row }">
              <el-tag :type="sexTagType(row.stu_sex)" :class="sexTagClass(row.stu_sex)" size="small" effect="light">
                {{ row.stu_sex }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="stu_age" label="年龄" width="60" align="center" class-name="num" />
          <el-table-column prop="stu_tel" label="电话" width="120" class-name="num" />
          <el-table-column prop="agent_name" label="顾问" width="92">
            <template #default="{ row }">{{ row.agent_name || '-' }}</template>
          </el-table-column>
          <el-table-column prop="stu_from" label="生源地" width="96" show-overflow-tooltip />
          <el-table-column prop="stu_school" label="院校" min-width="120" show-overflow-tooltip />
          <el-table-column prop="stu_major" label="专业" min-width="110" show-overflow-tooltip />
          <el-table-column prop="edu_bg" label="学历" width="80" align="center" />
          <template #empty>
            <div class="empty-hint">这个班还没有学员</div>
          </template>
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
.class-students {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.class-students-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.class-students-count {
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.class-students-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
