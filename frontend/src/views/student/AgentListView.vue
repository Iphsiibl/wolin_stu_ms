/**
 * =====================================================================
 * 顾问管理页
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
  createAgent,
  deleteAgent,
  fetchAllAgents,
  updateAgent,
} from '@/api/student'
import ProTable from '@/components/ProTable/index.vue'
import type { ColumnProps, ProTableSort } from '@/components/ProTable/interface'
import type { Agent, AgentCreate } from '@/types/models'
import { sexTagClass, sexTagType } from '@/utils/format'

const loading = ref(false)
const agents = ref<Agent[]>([])
const keyword = ref('')

const filteredAgents = computed(() => {
  if (!keyword.value.trim()) return agents.value
  const kw = keyword.value.trim().toLowerCase()
  return agents.value.filter(
    (a) => a.agent_name.toLowerCase().includes(kw) || String(a.agent_id) === kw,
  )
})

/* ---------------------------------------------------------------------
 * 表格列配置（ProTable）
 * ------------------------------------------------------------------ */

/** 默认排序：年龄升序 → 编号升序（年龄相同时按编号排） */
const defaultSort: ProTableSort[] = [
  { prop: 'agent_age', order: 'ascending' },
  { prop: 'agent_id', order: 'ascending' },
]

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
      props: { placeholder: '姓名 / 编号' },
    },
  },
  // 【列宽口径】内容列一律用 minWidth，让剩余空间按比例摊开；
  // 可排序列不低于 80（表头文字 + 排序箭头约 50px，再窄会被省略号截断）。
  { prop: 'agent_id', label: '编号', minWidth: 96, align: 'center', className: 'num', sortable: true },
  { prop: 'agent_name', label: '姓名', minWidth: 140 },
  { prop: 'agent_sex', label: '性别', minWidth: 72, align: 'center', slotName: 'agent_sex' },
  { prop: 'agent_age', label: '年龄', minWidth: 84, align: 'center', className: 'num', sortable: true },
  {
    prop: 'operation',
    label: '操作',
    width: 170,
    align: 'center',
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

async function loadAgents() {
  loading.value = true
  try {
    const res = await fetchAllAgents()
    agents.value = res.data ?? []
  } finally {
    loading.value = false
  }
}

/** 刷新（ProTable 右上角的刷新按钮触发） */
async function handleRefresh() {
  await loadAgents()
  ElMessage.success('已刷新')
}

/* ---------------- 新增 / 修改 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('新增顾问')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)

const form = reactive<AgentCreate>({
  agent_name: '',
  agent_sex: '男',
  agent_age: 25,
})

const rules: FormRules = {
  agent_name: [
    { required: true, message: '请输入顾问姓名', trigger: 'blur' },
    { max: 20, message: '姓名最多 20 个字', trigger: 'blur' },
  ],
  agent_sex: [{ required: true, message: '请选择性别', trigger: 'change' }],
  agent_age: [
    { required: true, message: '请输入年龄', trigger: 'blur' },
    // 后端 schema/student_request.py：agent_age 是 gt=18（必须大于 18），
    // 放行 18 会被 422 拦下，所以下限取 19
    { type: 'number', min: 19, max: 100, message: '年龄需在 19-100 之间', trigger: 'blur' },
  ],
}

function handleCreate() {
  editingId.value = null
  dialogTitle.value = '新增顾问'
  Object.assign(form, { agent_name: '', agent_sex: '男', agent_age: 25 })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

function handleEdit(row: Agent) {
  editingId.value = row.agent_id
  dialogTitle.value = `修改顾问 - ${row.agent_name}`
  Object.assign(form, {
    agent_name: row.agent_name,
    agent_sex: row.agent_sex,
    agent_age: row.agent_age,
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
      await createAgent({ ...form })
      ElMessage.success('新增成功')
    } else {
      await updateAgent(editingId.value, { ...form })
      ElMessage.success('修改成功')
    }
    dialogVisible.value = false
    await loadAgents()
  } catch {
    // 提示已由拦截器统一处理
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: Agent) {
  try {
    await ElMessageBox.confirm(`确定要删除顾问「${row.agent_name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteAgent(row.agent_id)
    ElMessage.success('删除成功')
    await loadAgents()
  } catch {
    // 用户取消
  }
}

onMounted(loadAgents)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div class="page-heading">
        <span class="page-eyebrow">Advisors</span>
        <div class="page-title">顾问管理</div>
        <p class="page-subtitle">共 <span class="num">{{ agents.length }}</span> 位顾问</p>
      </div>
    </div>

    <ProTable
      ref="tableRef"
      :columns="columns"
      :data="filteredAgents"
      :default-sort="defaultSort"
      :loading="loading"
      row-key="agent_id"
      border
      stripe
      narrow
      @search="applySearchParams"
      @reset="applySearchParams"
      @refresh="handleRefresh"
    >
      <template #tableHeader>
        <el-button type="primary" :icon="Plus" @click="handleCreate">新增顾问</el-button>
      </template>

      <template #agent_sex="{ row }">
        <el-tag :type="sexTagType(row.agent_sex)" :class="sexTagClass(row.agent_sex)" size="small" effect="light">
          {{ row.agent_sex }}
        </el-tag>
      </template>

      <template #operation="{ row }">
        <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">修改</el-button>
        <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
      </template>

      <template #empty>
        <div class="empty-hint">暂无顾问数据</div>
      </template>
    </ProTable>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="440px" destroy-on-close>
      <div class="card">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
          <el-form-item label="姓名" prop="agent_name">
            <el-input v-model="form.agent_name" placeholder="请输入顾问姓名" maxlength="20" />
          </el-form-item>
          <el-form-item label="性别" prop="agent_sex">
            <el-radio-group v-model="form.agent_sex">
              <el-radio value="男">男</el-radio>
              <el-radio value="女">女</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="年龄" prop="agent_age">
            <el-input-number
              v-model="form.agent_age"
              :min="18"
              :max="100"
              style="width: 100%"
              controls-position="right"
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
