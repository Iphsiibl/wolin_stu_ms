/**
 * =====================================================================
 * 班主任管理页
 * =====================================================================
 * 列表用 ProTable 展示：
 *   - 数据用静态 :data 传入（全量），ProTable 内部自动切片分页
 *   - 关键词搜索写在列的 search 配置里（列本身不显示），
 *     筛选逻辑是本页的前端过滤：姓名 / 编号 / 性别 都参与匹配
 *   - 中文字段映射仍然由 @/utils/mappers 的 toClassTeacher 负责
 * =====================================================================
 */
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, Edit, Plus } from '@element-plus/icons-vue'

import {
  createClassTeacher,
  deleteClassTeacher,
  fetchAllClassTeachers,
  updateClassTeacher,
} from '@/api/class'
import ProTable from '@/components/ProTable/index.vue'
import type { ColumnProps } from '@/components/ProTable/interface'
import type { ClassTeacher } from '@/types/models'
import { sexTagClass, sexTagType } from '@/utils/format'

const loading = ref(false)
const rows = ref<ClassTeacher[]>([])
/** 搜索关键词 */
const keyword = ref('')

/** 关键词过滤后的班主任（前端过滤，数据量小，没必要走后端） */
const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return rows.value
  return rows.value.filter(
    (ct) =>
      ct.class_teacher_name.toLowerCase().includes(kw) ||
      String(ct.class_teacher_id).includes(kw) ||
      (ct.class_teacher_sex ?? '').toLowerCase().includes(kw),
  )
})

/* ---------------------------------------------------------------------
 * 表格列配置（ProTable）
 * ------------------------------------------------------------------ */
const columns: ColumnProps[] = [
  { type: 'index', label: '#', width: 55, align: 'center', isSetting: false, className: 'num' },
  {
    // 关键词：只用于搜索，不显示在表格里
    prop: 'keyword',
    label: '关键词',
    isShow: false,
    isSetting: false,
    search: {
      el: 'input',
      props: { placeholder: '姓名 / 编号 / 性别' },
    },
  },
  // 【列宽口径】内容列一律用 minWidth，让剩余空间按比例摊开。
  { prop: 'class_teacher_id', label: '编号', minWidth: 110, align: 'center', className: 'num' },
  { prop: 'class_teacher_name', label: '姓名', minWidth: 160 },
  { prop: 'class_teacher_sex', label: '性别', minWidth: 90, align: 'center', slotName: 'class_teacher_sex' },
  {
    prop: 'operation',
    label: '操作',
    width: 170,
    align: 'center',
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

async function load() {
  loading.value = true
  try {
    const res = await fetchAllClassTeachers()
    rows.value = res.data ?? []
  } finally {
    loading.value = false
  }
}

/** 刷新（ProTable 右上角的刷新按钮触发） */
async function handleRefresh() {
  await load()
  ElMessage.success('已刷新')
}

/* ---------------- 新增 / 修改 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('新增班主任')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)

const form = reactive({
  class_teacher_name: '',
  class_teacher_sex: '男',
  stu_class_id: undefined as number | undefined,
})

const rules: FormRules = {
  class_teacher_name: [
    { required: true, message: '请输入班主任姓名', trigger: 'blur' },
    // 后端 schema/class_schema.py：class_teacher_name varchar(10)，超长会 422
    { max: 10, message: '班主任姓名最多 10 个字', trigger: 'blur' },
  ],
  class_teacher_sex: [{ required: true, message: '请选择性别', trigger: 'change' }],
}

function handleCreate() {
  editingId.value = null
  dialogTitle.value = '新增班主任'
  Object.assign(form, { class_teacher_name: '', class_teacher_sex: '男', stu_class_id: undefined })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

function handleEdit(row: ClassTeacher) {
  editingId.value = row.class_teacher_id
  dialogTitle.value = `修改班主任 - ${row.class_teacher_name}`
  Object.assign(form, {
    class_teacher_name: row.class_teacher_name,
    // 性别要回填数据库里的真实值，不能一律当「男」，
    // 否则改个名字就把女班主任的性别给改了
    class_teacher_sex: row.class_teacher_sex || '男',
    stu_class_id: row.stu_class_id,
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
      class_teacher_name: form.class_teacher_name,
      class_teacher_sex: form.class_teacher_sex,
      stu_class_id: form.stu_class_id,
    }
    if (editingId.value === null) {
      await createClassTeacher(payload)
      ElMessage.success('新增成功')
    } else {
      await updateClassTeacher(editingId.value, payload)
      ElMessage.success('修改成功')
    }
    dialogVisible.value = false
    await load()
  } catch {
    // 提示已由拦截器统一处理
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: ClassTeacher) {
  try {
    await ElMessageBox.confirm(
      `确定要删除班主任「${row.class_teacher_name}」吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteClassTeacher(row.class_teacher_id)
    ElMessage.success('删除成功')
    await load()
  } catch {
    // 用户取消
  }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div class="page-heading">
        <span class="page-eyebrow">Head Teachers</span>
        <div class="page-title">班主任</div>
        <p class="page-subtitle">
          共 <span class="num">{{ filtered.length }}</span> 位班主任<template
            v-if="keyword.trim()"
          >（全部 {{ rows.length }} 位）</template>
        </p>
      </div>
    </div>

    <ProTable
      ref="tableRef"
      :columns="columns"
      :data="filtered"
      :loading="loading"
      row-key="class_teacher_id"
      border
      stripe
      narrow
      @search="applySearchParams"
      @reset="applySearchParams"
      @refresh="handleRefresh"
    >
      <template #tableHeader>
        <el-button type="primary" :icon="Plus" @click="handleCreate">新增班主任</el-button>
      </template>

      <template #class_teacher_sex="{ row }">
        <el-tag
          :type="sexTagType(row.class_teacher_sex)"
          :class="sexTagClass(row.class_teacher_sex)"
          size="small"
          effect="light"
        >
          {{ row.class_teacher_sex || '未知' }}
        </el-tag>
      </template>

      <template #operation="{ row }">
        <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">修改</el-button>
        <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
      </template>

      <template #empty>
        <div class="empty-hint">暂无班主任数据</div>
      </template>
    </ProTable>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="440px" destroy-on-close>
      <div class="card">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
          <el-form-item label="姓名" prop="class_teacher_name">
            <el-input v-model="form.class_teacher_name" placeholder="请输入姓名" maxlength="10" />
          </el-form-item>
          <el-form-item label="性别" prop="class_teacher_sex">
            <el-radio-group v-model="form.class_teacher_sex">
              <el-radio value="男">男</el-radio>
              <el-radio value="女">女</el-radio>
            </el-radio-group>
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
