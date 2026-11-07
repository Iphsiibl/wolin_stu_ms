/**
 * =====================================================================
 * 授课老师页
 * =====================================================================
 * 列表用 ProTable 展示：
 *   - 数据用静态 :data 传入（全量），ProTable 内部自动切片分页
 *   - 关键词筛选写在列的 search 配置里，筛选逻辑仍然是本页的前端过滤
 * =====================================================================
 */
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, Edit, Plus } from '@element-plus/icons-vue'

import {
  createTeacher,
  deleteTeacher,
  fetchAllTeachers,
  updateTeacher,
} from '@/api/teacher'
import { fetchAllClasses } from '@/api/class'
import ProTable from '@/components/ProTable/index.vue'
import type { ColumnProps, ProTableSort } from '@/components/ProTable/interface'
import type { ClassInfo } from '@/types/models'
import type { Teacher, TeacherCreate } from '@/types/models'

const loading = ref(false)
const teachers = ref<Teacher[]>([])
const classes = ref<ClassInfo[]>([])
const keyword = ref('')

const filtered = computed(() => {
  if (!keyword.value.trim()) return teachers.value
  const kw = keyword.value.trim().toLowerCase()
  return teachers.value.filter(
    (t) =>
      t.teacher_name.toLowerCase().includes(kw) ||
      t.teacher_tel.includes(kw) ||
      t.teacher_job.toLowerCase().includes(kw),
  )
})

/** 班级 id -> 名称 */
const classMap = computed(() => {
  const map: Record<number, string> = {}
  for (const c of classes.value) map[c.class_id] = c.class_name
  return map
})

/* ---------------------------------------------------------------------
 * 表格列配置（ProTable）
 * ------------------------------------------------------------------ */

/**
 * 默认排序：编号升序 → 姓名升序。
 *
 * 选编号做主序是因为它唯一且稳定（跟花名册一个道理），
 * 姓名做次序只会在编号相同时兜底，实际用得很少，但比再挂一个
 * 「职位 / 联系电话 / 任教班级」更克制（任教班级是数组，原始值没法直接比较）。
 */
const defaultSort: ProTableSort[] = [
  { prop: 'teacher_id', order: 'ascending' },
  { prop: 'teacher_name', order: 'ascending' },
]

const columns: ColumnProps[] = [
  { type: 'index', label: '#', width: 55, align: 'center', isSetting: false },
  {
    // 关键词：只用于搜索，不显示在表格里
    prop: 'keyword',
    label: '关键词',
    isShow: false,
    isSetting: false,
    search: {
      el: 'input',
      props: { placeholder: '姓名 / 电话 / 职位' },
    },
  },
  // 【列宽口径】内容列一律用 minWidth，让剩余空间按比例摊开；
  // 可排序列不低于 76（表头文字 + 排序箭头约 50px，再窄会被省略号截断）。
  { prop: 'teacher_id', label: '编号', minWidth: 86, align: 'center', className: 'num', sortable: true },
  { prop: 'teacher_name', label: '姓名', minWidth: 120, sortable: true },
  { prop: 'teacher_tel', label: '联系电话', minWidth: 130, className: 'num' },
  { prop: 'teacher_job', label: '职位', minWidth: 110, align: 'center', slotName: 'teacher_job' },
  { prop: 'stu_class_ids', label: '任教班级', minWidth: 240, slotName: 'stu_class_ids' },
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

/** ProTable 实例（用来读搜索参数、触发刷新） */
const tableRef = ref()

/** 把 ProTable 搜索表单里的值同步到本页的筛选条件 */
function applySearchParams() {
  const params = (tableRef.value?.searchParam ?? {}) as Record<string, any>
  keyword.value = String(params.keyword ?? '')
}

async function loadAll() {
  loading.value = true
  try {
    const [teacherRes, classRes] = await Promise.all([
      fetchAllTeachers(),
      fetchAllClasses(),
    ])
    teachers.value = teacherRes.data ?? []
    classes.value = classRes.data ?? []
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
const dialogTitle = ref('新增老师')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)

const form = reactive<TeacherCreate>({
  teacher_name: '',
  teacher_tel: '',
  teacher_job: '',
})

const rules: FormRules = {
  teacher_name: [{ required: true, message: '请输入老师姓名', trigger: 'blur' }],
  teacher_tel: [
    { required: true, message: '请输入联系电话', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' },
  ],
  teacher_job: [{ required: true, message: '请输入职位', trigger: 'blur' }],
}

function handleCreate() {
  editingId.value = null
  dialogTitle.value = '新增老师'
  Object.assign(form, { teacher_name: '', teacher_tel: '', teacher_job: '' })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

function handleEdit(row: Teacher) {
  editingId.value = row.teacher_id
  dialogTitle.value = `修改老师 - ${row.teacher_name}`
  Object.assign(form, {
    teacher_name: row.teacher_name,
    teacher_tel: row.teacher_tel,
    teacher_job: row.teacher_job,
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
      await createTeacher({ ...form })
      ElMessage.success('新增成功')
    } else {
      await updateTeacher(editingId.value, { ...form })
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

async function handleDelete(row: Teacher) {
  try {
    await ElMessageBox.confirm(
      `确定要删除老师「${row.teacher_name}」吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteTeacher(row.teacher_id)
    ElMessage.success('删除成功')
    await loadAll()
  } catch {
    // 用户取消
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div class="page-heading">
        <span class="page-eyebrow">Faculty</span>
        <div class="page-title">授课老师</div>
        <p class="page-subtitle">共 <span class="num">{{ teachers.length }}</span> 位老师</p>
      </div>
    </div>

    <ProTable
      ref="tableRef"
      :columns="columns"
      :data="filtered"
      :default-sort="defaultSort"
      :loading="loading"
      row-key="teacher_id"
      border
      stripe
      @search="applySearchParams"
      @reset="applySearchParams"
      @refresh="handleRefresh"
    >
      <template #tableHeader>
        <el-button type="primary" :icon="Plus" @click="handleCreate">新增老师</el-button>
      </template>

      <template #teacher_job="{ row }">
        <el-tag size="small" effect="plain">{{ row.teacher_job }}</el-tag>
      </template>

      <template #stu_class_ids="{ row }">
        <el-tag
          v-for="cid in row.stu_class_ids"
          :key="cid"
          size="small"
          type="info"
          effect="plain"
          style="margin: 2px 4px 2px 0"
        >
          {{ classMap[cid] ?? `班级${cid}` }}
        </el-tag>
        <span v-if="!row.stu_class_ids?.length" style="color: #c0c4cc">-</span>
      </template>

      <template #operation="{ row }">
        <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">修改</el-button>
        <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
      </template>

      <template #empty>
        <div class="empty-hint">暂无老师数据</div>
      </template>
    </ProTable>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="480px" destroy-on-close>
      <div class="card">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
          <el-form-item label="姓名" prop="teacher_name">
            <el-input v-model="form.teacher_name" placeholder="请输入老师姓名" />
          </el-form-item>
          <el-form-item label="联系电话" prop="teacher_tel">
            <el-input v-model="form.teacher_tel" placeholder="11 位手机号" maxlength="11" />
          </el-form-item>
          <el-form-item label="职位" prop="teacher_job">
            <el-input v-model="form.teacher_job" placeholder="如：高级讲师" />
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
