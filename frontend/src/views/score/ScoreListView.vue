/**
 * =====================================================================
 * 学生成绩页
 * =====================================================================
 * 可以按「学号」查某个学生的所有成绩，或按「考试次序」查某场考试的全部成绩。
 *
 * 【ProTable 改造说明】
 *   - 表格换成 ProTable，数据用静态 :data 传入（本次查询的结果），
 *     ProTable 内部自动切片分页
 *   - 查询条件是三个搜索项：「查询方式」+「学号」+「考试次序」
 *   - 中文字段映射仍然由 @/utils/mappers 的 toScore 负责（api/score.ts 里调用），
 *     页面里只看到 stu_id / test_id / score
 *
 * 【⚠️ 为什么要有「查询方式」这一项？—— 这是一个修过的 bug】
 *
 *   原来的写法是两个框，谁填了值就按谁查：
 *
 *       if (stuId !== null)      按学号查
 *       else if (testId !== null) 按考试次序查
 *
 *   看起来没问题，但「学号」那个框配了默认值 1（defaultValue: 1），
 *   所以 stuId 永远不为 null —— 第二个分支是【永远走不到的死代码】。
 *
 *   后果：不管你在「考试次序」里填什么，点查询都去查学号 1。
 *   而每个学生本来就只有 3 场考试，所以表格里永远是 3 行，
 *   看起来就像"数据没查全"。
 *
 *   现在改成「查询方式」说了算：先选按学号还是按考试次序，再填对应的框。
 *   两个框可以都填，只有查询方式指定的那个生效，不会再打架。
 *
 * 【⚠️ 默认值为什么是「按考试次序查」？—— 这是第二轮改的】
 *
 *   修完上面那个 bug 之后又发现：页面一打开还是只有 3 条。
 *   原因不是 bug 没修好，而是【默认值选错了】：
 *   查询方式默认「按学号查」+ 学号默认 1  ->  一进来就是"某个学生的 3 场考试"。
 *   看起来就像"数据没查全"，其实只是查法选窄了。
 *
 *   现在改成：默认「按考试次序查」+ 考试次序默认 1  ->  一进来就是第 1 次考试的全场成绩（209 条）。
 *   同时把「学号」框的默认值去掉（空着），
 *   这样一眼就能看出当前是按哪一场考试在查，不会误以为学号框里的数字在起作用。
 *
 *   注意：后端成绩模块只有「按学号」「按考试次序」两个查询接口，
 *   没有"查全部成绩"的接口，所以一次最多能看到一场考试（209 条）。
 * =====================================================================
 */
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, Edit, Plus } from '@element-plus/icons-vue'

import { createScore, deleteScore, fetchScoresByStudent, fetchScoresByTest, updateScore } from '@/api/score'
import ProTable from '@/components/ProTable/index.vue'
import type { ColumnProps, ProTableSort } from '@/components/ProTable/interface'
import type { Score } from '@/types/models'
import { scoreTagType } from '@/utils/format'

const loading = ref(false)

/** 表格行：Score 加上一个用于表格唯一标识的 row_id（见下面 loadScores 的注释） */
type ScoreRow = Score & { row_id: string }
const scores = ref<ScoreRow[]>([])

/** 查询方式：默认「按考试次序查」（一进页面就是全场成绩，不会只看到 3 条） */
const queryMode = ref<'stu' | 'test'>('test')
/** 查询参数 */
const queryValue = ref<number | null>(null)

/* ---------------------------------------------------------------------
 * 表格列配置（ProTable）
 * ------------------------------------------------------------------ */

/** 「查询方式」下拉框的选项 */
const QUERY_MODE_OPTIONS = [
  { label: '按学号查', value: 'stu' },
  { label: '按考试次序查', value: 'test' },
]

/** 默认排序：分数降序（高分在前）→ 学号升序（同分时按学号排） */
const defaultSort: ProTableSort[] = [
  { prop: 'score', order: 'descending' },
  { prop: 'stu_id', order: 'ascending' },
]

const columns: ColumnProps[] = [
  { type: 'index', label: '#', width: 55, align: 'center', isSetting: false },
  {
    // 查询方式：只用于搜索，不在表格里显示
    prop: 'query_mode',
    label: '查询方式',
    width: 150,
    align: 'center',
    isShow: false,
    isSetting: false,
    search: {
      el: 'select',
      props: { placeholder: '请选择查询方式' },
      // 默认按考试次序查：页面一打开就是第 1 次考试的全场成绩（209 条）
      defaultValue: 'test',
    },
    enum: QUERY_MODE_OPTIONS,
  },
  {
    prop: 'stu_id',
    label: '学号',
    minWidth: 96,
    align: 'center',
    className: 'num',
    sortable: true,
    search: {
      el: 'input-number',
      // 这里【故意不设默认值】：留空才看得出当前是按哪一场考试在查。
      // 以前默认填 1，配合旧逻辑就成了"永远按学号查"的元凶。
      props: { controls: false, min: 1, placeholder: '请输入学号' },
    },
  },
  {
    // 学生姓名 —— 后端 /score 接口直接带回来的，不用再查一遍学生表
    prop: 'stu_name',
    label: '学生姓名',
    minWidth: 120,
  },
  {
    // 班级 —— 同样是后端 JOIN 出来的（scores -> student_info -> clazz），
    // 成绩列表要一眼看出这场考试里都有哪些班的人，不用再查班级表。
    prop: 'class_name',
    label: '班级',
    minWidth: 124,
    showOverflowTooltip: true,
    // 班级也能排：按班级看成绩分布，比按学号看更直观
    sortable: true,
  },
  {
    prop: 'test_id',
    label: '考试次序',
    minWidth: 106,
    align: 'center',
    className: 'num',
    sortable: true,
    search: {
      el: 'input-number',
      props: { controls: false, min: 1, placeholder: '请输入考试次序' },
      // 默认第 1 次考试（全场 209 条）
      defaultValue: 1,
    },
  },
  {
    prop: 'score',
    label: '分数',
    minWidth: 104,
    align: 'center',
    slotName: 'score',
    sortable: true,
    // 高分在前：第一次点表头就是降序
    sortOrders: ['descending', 'ascending', null],
  },
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

/** 搜索框的值转成数字，空值返回 null */
function toNumberOrNull(value: unknown): number | null {
  if (value === undefined || value === null || value === '') return null
  const num = Number(value)
  return Number.isNaN(num) ? null : num
}

/** 把 ProTable 搜索表单里的值同步到本页的查询条件 */
function applySearchParams() {
  const params = (tableRef.value?.searchParam ?? {}) as Record<string, any>
  // 【查询方式说了算】
  // 不再用"哪个框有值就用哪个"来判断 —— 那种写法会让"按考试次序查"
  // 变成永远走不到的死代码。
  // 现在由用户明确选查询方式，两个框可以都填，不会打架。
  // 兜底值用 'test'，和搜索框的默认值保持一致。
  const mode = (params.query_mode ?? 'test') as 'stu' | 'test'
  if (mode === 'test') {
    queryMode.value = 'test'
    queryValue.value = toNumberOrNull(params.test_id)
  } else {
    queryMode.value = 'stu'
    queryValue.value = toNumberOrNull(params.stu_id)
  }
}

async function loadScores() {
  if (queryValue.value === null) {
    scores.value = []
    return
  }
  loading.value = true
  try {
    const res =
      queryMode.value === 'stu'
        ? await fetchScoresByStudent(queryValue.value)
        : await fetchScoresByTest(queryValue.value)
    // 补一个 row_id 当表格的行唯一标识。
    // 为什么不用 stu_id？因为"同一个学生有多场考试"时，这几行的 stu_id 完全一样，
    // 拿来当行标识就会出现重复 key（Element Plus 会警告，选中行之类的功能也会错乱）。
    scores.value = (res.data ?? []).map((s) => ({
      ...s,
      row_id: `${s.stu_id}-${s.test_id}`,
    }))
    if (!scores.value.length) {
      ElMessage.info('没有查询到成绩记录')
    }
  } finally {
    loading.value = false
  }
}

/** 查询（ProTable 搜索表单的「搜索」按钮触发） */
function handleQuery() {
  applySearchParams()
  if (queryValue.value === null) {
    ElMessage.warning(queryMode.value === 'test' ? '请输入考试次序' : '请输入学号')
    scores.value = []
    return
  }
  loadScores()
}

/** 重置（ProTable 搜索表单的「重置」按钮触发，恢复默认：按考试次序查 + 第 1 次考试） */
function handleReset() {
  applySearchParams()
  loadScores()
}

/** 刷新（ProTable 右上角的刷新按钮触发） */
async function handleRefresh() {
  await loadScores()
  ElMessage.success('已刷新')
}

/* ---------------- 新增 / 修改 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('录入成绩')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingKey = ref<string>('')

const form = reactive({ stu_id: null as number | null, test_id: null as number | null, score: 0 })

const rules: FormRules = {
  stu_id: [{ required: true, message: '请输入学号', trigger: 'blur' }],
  test_id: [{ required: true, message: '请输入考试次序', trigger: 'blur' }],
  score: [
    { required: true, message: '请输入分数', trigger: 'blur' },
    {
      type: 'number',
      min: 0,
      max: 100,
      message: '分数需在 0-100 之间',
      trigger: 'blur',
    },
  ],
}

function handleCreate() {
  editingKey.value = ''
  dialogTitle.value = '录入成绩'
  Object.assign(form, {
    stu_id: queryMode.value === 'stu' ? queryValue.value : null,
    test_id: queryMode.value === 'test' ? queryValue.value : null,
    score: 0,
  })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

function handleEdit(row: Score) {
  editingKey.value = `${row.stu_id}-${row.test_id}`
  dialogTitle.value = `修改成绩 - ${row.stu_name || '未知学生'}（学号 ${row.stu_id}）`
  Object.assign(form, { stu_id: row.stu_id, test_id: row.test_id, score: row.score })
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload = {
      stu_id: form.stu_id!,
      test_id: form.test_id!,
      score: form.score,
    }
    if (editingKey.value) {
      await updateScore(payload)
      ElMessage.success('修改成功')
    } else {
      await createScore(payload)
      ElMessage.success('录入成功')
    }
    dialogVisible.value = false
    await loadScores()
  } catch {
    // 提示已由拦截器统一处理
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: Score) {
  try {
    await ElMessageBox.confirm(
      `确定要删除${row.stu_name ? `「${row.stu_name}」` : `学号 ${row.stu_id}`} 第 ${row.test_id} 次考试的成绩吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteScore(row.stu_id, row.test_id)
    ElMessage.success('删除成功')
    await loadScores()
  } catch {
    // 用户取消
  }
}

onMounted(async () => {
  // 页面一打开就查「第 1 次考试的全场成绩」（209 条）。
  // 跟搜索表单的默认值一致：查询方式=按考试次序查，考试次序=1。
  applySearchParams()
  await loadScores()
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div class="page-heading">
        <span class="page-eyebrow">Examination Records</span>
        <div class="page-title">学生成绩</div>
        <p class="page-subtitle">
          「按考试次序查」= 某场考试的全部学生成绩；「按学号查」= 某个学生的各场次成绩。默认显示第 1
          次考试的全场成绩
        </p>
      </div>
    </div>

    <ProTable
      ref="tableRef"
      :columns="columns"
      :data="scores"
      :default-sort="defaultSort"
      :loading="loading"
      row-key="row_id"
      border
      stripe
      :search-col="{ xs: 1, sm: 3, md: 4, lg: 4, xl: 4 }"
      @search="handleQuery"
      @reset="handleReset"
      @refresh="handleRefresh"
    >
      <template #tableHeader>
        <el-button type="primary" :icon="Plus" @click="handleCreate">录入成绩</el-button>
      </template>

      <template #class_name="{ row }">
        {{ row.class_name || '-' }}
      </template>

      <template #score="{ row }">
        <el-tag :type="scoreTagType(row.score)" size="large" effect="light">
          {{ row.score }}
        </el-tag>
      </template>

      <template #operation="{ row }">
        <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">修改</el-button>
        <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
      </template>

      <template #empty>
        <div class="empty-hint">请先选择查询条件并点击「查询」</div>
      </template>
    </ProTable>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="440px" destroy-on-close>
      <div class="card">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
          <el-form-item label="学号" prop="stu_id">
            <el-input-number
              v-model="form.stu_id"
              :min="1"
              :controls="false"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="考试次序" prop="test_id">
            <el-input-number
              v-model="form.test_id"
              :min="1"
              :controls="false"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="分数" prop="score">
            <el-input-number
              v-model="form.score"
              :min="0"
              :max="100"
              step="0.5"
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
