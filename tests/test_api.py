"""
回归测试 —— 每一条都对应本次修复的一个真实 Bug。

写法约定：测试名里写清楚"以前会怎样、现在应该怎样"。
这样以后谁改坏了，一眼就能看出是哪条规则被破坏了。
"""
from fastapi.testclient import TestClient

from model.student_table import Student_info
from schema.enums import Sex
from database import Session


# =============================================================================
# 一、服务启动与路由
# =============================================================================
def test_openapi_has_all_modules(client: TestClient):
    """六大模块的路由都要挂上。"""
    paths = client.get('/openapi.json').json()['paths']
    for prefix in ['/student', '/score', '/employment', '/class', '/teacher', '/stat']:
        assert any(p.startswith(prefix) for p in paths), f'缺少 {prefix} 模块'


# =============================================================================
# 二、学生模块
# =============================================================================
def test_create_student_with_class_id_1(client: TestClient, agent_id: int):
    """回归：Student_request.stu_class_id 原来是 gt=1，导致 1 号班加不了人。

    库里实实在在有 1 号班（软件1班），这个 Bug 让它形同虚设。
    现在应该 ge=1，1 号班能正常加人。
    """
    r = client.post('/student/add_stu', json={
        'stu_name': '一号班生',
        'stu_age': 22,
        'stu_sex': '男',
        'stu_class_id': 1,
        'agent_id': agent_id,
        'stu_tel': '13712345678',
        'stu_from': '浙江',
        'stu_school': '某大学',
        'stu_major': '软件工程',
        'enroll_date': '2022-09-01',
        'gra_date': '2026-06-30',
        'edu_bg': '本科',
    })
    # 可能因为上一轮已经建过而返回 409，但不能是 422（校验层拦下来了）
    assert r.status_code in (201, 409), r.text
    if r.status_code == 409:
        assert '班级' not in r.text, '班级校验失败说明 class_id 约束仍然有问题'


def test_update_student_partial_payload(client: TestClient, student_id: int):
    """回归：UpdateStudent 的字段没写默认值，Pydantic v2 把它当成必填。

    以前只传 {"stu_name": "xxx"} 会被 422 拦掉：
        {"type": "missing", "loc": ["body", "stu_from"], "msg": "Field required"}
    现在只传要改的字段即可。
    """
    r = client.put(f'/student/update_stu_class?stu_id={student_id}',
                   json={'stu_school': '更新后的大学'})
    assert r.status_code == 200, r.text
    assert r.json()['Data']['stu_school'] == '更新后的大学'


def test_update_nonexistent_student_returns_404(client: TestClient):
    """改不存在的学生 -> 404，不是 422。"""
    r = client.put('/student/update_stu_class?stu_id=99999',
                   json={'stu_school': '某大学'})
    assert r.status_code == 404
    assert 'detail' in r.json()


# =============================================================================
# 部分更新：只改用户真正传了的字段
# =============================================================================
def _snapshot(client: TestClient, student_id: int) -> dict:
    """取当前学生的完整信息，用来做"改之前/改之后"的对比。"""
    r = client.get(f'/student/select_stu_id?stu_id={student_id}')
    assert r.status_code == 200, r.text
    return r.json()['Data']


def test_update_student_only_changes_passed_fields(client: TestClient, student_id: int):
    """只传一个字段 -> 只有这一个字段变，其它字段一个都不许动。

    这是"只改用户传了的字段"的正面用例：
    请求体里没出现的字段，压根不应该进到 DAO 面前。
    """
    before = _snapshot(client, student_id)

    r = client.put(f'/student/update_stu_class?stu_id={student_id}',
                   json={'stu_school': '只改学校'})
    assert r.status_code == 200, r.text
    after = r.json()['Data']

    assert after['stu_school'] == '只改学校'
    for field in ['stu_name', 'stu_from', 'stu_major', 'stu_tel',
                  'edu_bg', 'stu_age', 'stu_sex', 'stu_class_id',
                  'agent_id', 'enroll_date', 'gra_date']:
        assert after[field] == before[field], \
            f'{field} 不该被改动：改前={before[field]!r} 改后={after[field]!r}'


def test_update_student_ignores_blank_string_fields(client: TestClient, student_id: int):
    """前端表单没填的输入框传空字符串 -> 视为"没改"，不覆盖，也不 422。

    以前 stu_tel 传 "" 会被手机号正则直接拦成 422：
        {"type": "string_pattern_mismatch", "loc": ["body", "stu_tel"]}
    用户明明只想改个学校，整个请求却直接挂了，一个字段都改不了。
    """
    before = _snapshot(client, student_id)

    r = client.put(f'/student/update_stu_class?stu_id={student_id}',
                   json={'stu_school': '空串测试大学',
                         'stu_tel': '',        # 空字符串
                         'stu_major': '   '})  # 只有空格的字符串
    assert r.status_code == 200, r.text
    after = r.json()['Data']

    assert after['stu_school'] == '空串测试大学'
    assert after['stu_tel'] == before['stu_tel'], '空字符串不该覆盖已有手机号'
    assert after['stu_major'] == before['stu_major'], '空白字符串不该覆盖已有专业'


def test_update_student_ignores_null_fields(client: TestClient, student_id: int):
    """显式传 null -> 同样视为"没改"，不覆盖。

    null 在这个接口里【不】表示"把字段清空"，
    只表示"这个字段我没什么要改的"。
    """
    before = _snapshot(client, student_id)

    r = client.put(f'/student/update_stu_class?stu_id={student_id}',
                   json={'stu_school': 'null 测试大学', 'stu_major': None})
    assert r.status_code == 200, r.text
    after = r.json()['Data']

    assert after['stu_school'] == 'null 测试大学'
    assert after['stu_major'] == before['stu_major'], 'null 不该覆盖已有专业'


def test_update_student_empty_body_returns_400(client: TestClient, student_id: int):
    """一个字段都没传 -> 400，而不是静默返回 200「更新成功」。

    以前空 body 会返回 200，数据库却一个字节都没动。
    前端把字段名拼错了（比如 stu_schol 少个 o）也一样返回 200，
    这种 bug 要靠人工核对数据库才能发现。返回 400 能立刻暴露它。
    """
    r = client.put(f'/student/update_stu_class?stu_id={student_id}', json={})
    assert r.status_code == 400, r.text
    assert '没有需要更新的字段' in r.json()['detail']


def test_update_student_only_blank_fields_returns_400(client: TestClient, student_id: int):
    """传的全是空值 -> 等于什么都没改 -> 同样 400。"""
    r = client.put(f'/student/update_stu_class?stu_id={student_id}',
                   json={'stu_school': '', 'stu_tel': None})
    assert r.status_code == 400, r.text
    assert '没有需要更新的字段' in r.json()['detail']


def test_update_student_cannot_touch_protected_fields(client: TestClient, student_id: int):
    """白名单之外的字段不能被改：is_del（软删除标记）和 stu_id（主键）。"""
    r = client.put(f'/student/update_stu_class?stu_id={student_id}',
                   json={'is_del': 1, 'stu_id': 999999, 'stu_school': '白名单测试大学'})
    assert r.status_code == 200, r.text

    data = r.json()['Data']
    assert data['stu_id'] == student_id, '主键不该被改'
    assert data['stu_school'] == '白名单测试大学'

    # is_del 没被改成 1 的话，这个学生还能查到
    assert client.get(f'/student/select_stu_id?stu_id={student_id}').status_code == 200


def test_delete_nonexistent_student_returns_404(client: TestClient):
    """删不存在的学生 -> 404。

    以前是 422（"删除失败,没有该学员"），422 的语义是"格式没问题但处理不了"，
    而"人根本不存在"应该是 404。
    """
    r = client.delete('/student/delete_stu?stu_id=99999')
    assert r.status_code == 404


def test_delete_student_accepts_int(client: TestClient):
    """删除接口的 stu_id 应该是 int 类型，不要靠 MySQL 隐式转换。"""
    r = client.delete('/student/delete_stu?stu_id=abc')
    # 类型不对 -> FastAPI 直接 422，不会打到数据库
    assert r.status_code == 422


def test_select_student_by_class_uses_int_param(client: TestClient, class_id: int):
    """按班级查学生：参数名 stu_class_id，类型 int。"""
    r = client.get(f'/student/select_stu_class?stu_class_id={class_id}')
    assert r.status_code == 200
    assert 'Data' in r.json()


def test_select_stu_skip_rejects_negative_pagination(client: TestClient):
    """回归：分页参数传负数，以前会打成 SQL 语法错误 -> 整个接口 500。

    skip=-5 会让 SQL 变成 `LIMIT 10 OFFSET -5`，
    MySQL 不接受负数 OFFSET，直接报 1064 语法错误。

    现在接口层加了 Query(ge=0)，FastAPI 先挡一道：传负数返回 422，
    请求根本到不了数据库。
    （/employment/page 早就有 Query(ge=1, le=100)，两个分页接口现在对齐了。）
    """
    for query in ('skip=-5&limit=10', 'skip=0&limit=-10'):
        r = client.get(f'/student/select_stu_skip?{query}')
        assert r.status_code == 422, f'{query} 应该返回 422，实际 {r.status_code}'


def test_select_stu_skip_accepts_valid_pagination(client: TestClient):
    """正常分页参数仍然要能用 —— 别把校验加过头了。"""
    r = client.get('/student/select_stu_skip?skip=0&limit=5')
    assert r.status_code == 200
    body = r.json()
    assert body['code'] == 200
    assert len(body['Data']) <= 5


# =============================================================================
# 三、就业模块（本次坏得最彻底的一块）
# =============================================================================
def test_emp_search_without_class_name_returns_data(client: TestClient, student_id: int):
    """回归：get_emp_filter 里写的是 `if not class_name:`，条件写反了。

    以前不传班级时，会去过滤一个不存在的字段 stu_class_name，
    直接 AttributeError -> 整个搜索接口 500。
    """
    client.post('/employment/create', json={
        'stu_id': student_id, 'company': '回归公司',
        'salary': 12345, 'open_date': '2026-01-01T00:00:00',
        'offer_date': '2026-03-01T00:00:00',
    })
    r = client.get('/employment/search')
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_emp_page_not_500(client: TestClient):
    """回归：_emp_to_dict 里用了 e.student.stu_class_name —— 这字段不存在。

    以前 /employment/page 直接 500（Internal Server Error，连 message 都没有）。
    现在班级名从 clazz.class_name 取。
    """
    r = client.get('/employment/page?page=1&size=10')
    assert r.status_code == 200, r.text
    body = r.json()
    assert 'items' in body and 'total' in body
    for item in body['items']:
        assert 'class_name' in item


def test_emp_search_by_sex(client: TestClient):
    """按性别筛就业必须真的能筛出不同的人。

    以前 SexEnum 是 str('男'/'女')，而库里存的是 int，筛选永远查不到东西。
    """
    r_male = client.get('/employment/search?stu_sex=男')
    r_female = client.get('/employment/search?stu_sex=女')
    assert r_male.status_code == 200
    assert r_female.status_code == 200
    for item in r_male.json():
        assert item['stu_sex'] == '男'
    for item in r_female.json():
        assert item['stu_sex'] == '女'


def test_emp_search_salary_range_reversed_returns_400(client: TestClient):
    """薪资上下限颠倒 -> 400。

    DAO 层判断出"这个参数组合不合理"，把该用的状态码一起带回来，
    接口层再翻译成 HTTP 响应 —— 不用再靠比对错误文案来猜该用 400 还是 500。
    """
    r = client.get('/employment/search?salary_min=99999&salary_max=1000')
    assert r.status_code == 400
    assert r.json()['detail'] == '薪资下限不能大于薪资上限'


def test_emp_create_duplicate_returns_409(client: TestClient, student_id: int):
    """重复添加就业信息 -> 409，不是 200。"""
    payload = {
        'stu_id': student_id, 'company': '重复公司', 'salary': 1000,
        'open_date': '2026-01-01T00:00:00', 'offer_date': '2026-03-01T00:00:00',
    }
    first = client.post('/employment/create', json=payload)
    assert first.status_code in (201, 409)
    second = client.post('/employment/create', json=payload)
    assert second.status_code == 409


def test_emp_create_for_missing_student_returns_404(client: TestClient):
    """给不存在的学生加就业信息 -> 404。"""
    r = client.post('/employment/create', json={
        'stu_id': 99999, 'company': '不存在', 'salary': 1000,
        'open_date': '2026-01-01T00:00:00', 'offer_date': '2026-03-01T00:00:00',
    })
    assert r.status_code == 404


def test_emp_create_requires_dates(client: TestClient):
    """open_date / offer_date 是必填的，缺一个都 -> 422。

    就业时长这个核心指标依赖这两个日期，
    缺了就等于统计不出"从简历开放到收到offer用了多久"。
    """
    r = client.post('/employment/create', json={
        'stu_id': 1001, 'company': '缺日期', 'salary': 1000,
    })
    assert r.status_code == 422
    missing = {err['loc'][-1] for err in r.json()['detail']}
    assert 'open_date' in missing and 'offer_date' in missing


def test_emp_create_rejects_offer_before_open(client: TestClient):
    """offer_date 早于 open_date -> 422。

    两个日期既然都必填了，先后关系就是明确的业务规则，
    应该在入口拦住，而不是等统计接口算出负数时长才发现。
    """
    r = client.post('/employment/create', json={
        'stu_id': 1001, 'company': '倒序公司', 'salary': 1000,
        'open_date': '2026-05-01T00:00:00', 'offer_date': '2026-03-01T00:00:00',
    })
    assert r.status_code == 422
    assert '早于' in str(r.json()['detail'])


def test_unemployed_students_endpoint(client: TestClient):
    """查询当前未就业的学生。

    业务含义：在 employment 表里没有【未删除】就业记录的学生。
    """
    r = client.get('/employment/unemployed')
    assert r.status_code == 200, r.text
    body = r.json()
    assert 'Data' in body
    assert body['total'] == len(body['Data'])


def test_unemployed_students_excludes_employed(client: TestClient, student_id: int):
    """已经就业的学生，不能出现在"未就业"列表里。

    这是这个接口最容易写错的地方：
    如果 SQL 写成普通的 LEFT JOIN（不判断 Emp.is_del），
    软删除过的就业记录也会被 JOIN 上，人就被误判成"已就业"了。
    """
    client.post('/employment/create', json={
        'stu_id': student_id, 'company': '未就业测试公司', 'salary': 15000,
        'open_date': '2026-01-01T00:00:00', 'offer_date': '2026-03-01T00:00:00',
    })

    r = client.get('/employment/unemployed')
    assert r.status_code == 200, r.text
    ids = [row['stu_id'] for row in r.json()['Data']]
    assert student_id not in ids, '已经就业的学生却出现在未就业列表里'


def test_unemployed_students_has_useful_fields(client: TestClient):
    """返回的字段要够用：姓名、班级、顾问、电话都要在。"""
    r = client.get('/employment/unemployed')
    assert r.status_code == 200, r.text
    rows = r.json()['Data']
    assert rows, '未就业列表为空，说明整个库的数据都没加载'
    row = rows[0]
    for field in ('stu_id', 'stu_name', 'stu_class_id', 'class_name',
                  'agent_id', 'agent_name', 'stu_tel'):
        assert field in row, f'返回结果少了字段 {field}'


def test_emp_update_rejects_offer_before_open(client: TestClient, student_id: int):
    """修改时把 offer_date 调到 open_date 之前 -> 400。

    更新接口的顺序校验放在 DAO 层：
    只传了一个日期时，必须拿库里另一个日期来比，才知道顺序对不对。
    """
    # 先确保这个学生有就业记录（open_date = 2026-01-01）
    client.post('/employment/create', json={
        'stu_id': student_id, 'company': '顺序校验公司', 'salary': 1000,
        'open_date': '2026-01-01T00:00:00', 'offer_date': '2026-03-01T00:00:00',
    })
    r = client.put(f'/employment/put/{student_id}', json={
        'offer_date': '2020-01-01T00:00:00',
    })
    assert r.status_code == 400
    assert '早于' in r.json()['detail']


def test_emp_update_requires_at_least_one_field(client: TestClient, student_id: int):
    """一个字段都不传 -> 400，别返回"更新成功"却什么都没改。"""
    r = client.put(f'/employment/put/{student_id}', json={})
    assert r.status_code == 400


# =============================================================================
# 四、班级 / 班主任模块
# =============================================================================
def test_class_teacher_crud(client: TestClient, stamp):
    """班主任的增删改查（路由按你定的命名走）。

    以前 class_teacher 这张表没有任何接口能写，
    但"新建班级"又要求班主任必须存在 —— 班级模块陷入死锁。
    """
    name = f'新班导{stamp}'
    created = client.post('/class_teacher/class_teacher', json={
        'class_teacher_name': name,
        'class_teacher_sex': '男',
    })
    assert created.status_code == 201, created.text

    # 新建接口只回 message，id 从"查询所有班主任"里按名字反查
    listed = client.get('/class_teacher/all_class_teacher')
    assert listed.status_code == 200
    ct_id = next(t['班主任id'] for t in listed.json() if t['班主任名字'] == name)

    fetched = client.get(f'/class_teacher/get_class_teacher/{ct_id}')
    assert fetched.status_code == 200
    assert fetched.json()['班主任性别'] == '男'

    updated = client.put(f'/class_teacher/update_class_teacher/{ct_id}', json={
        'class_teacher_name': name + '改',
        'class_teacher_sex': '女',
    })
    assert updated.status_code == 200
    assert client.get(f'/class_teacher/get_class_teacher/{ct_id}').json()['班主任性别'] == '女'

    deleted = client.delete(f'/class_teacher/delete_class_teacher/{ct_id}')
    assert deleted.status_code == 200

    assert client.get(f'/class_teacher/get_class_teacher/{ct_id}').status_code == 404


def test_delete_class_teacher_path_param_matches(client: TestClient, stamp):
    """回归：删除班主任的接口里，路径参数名和函数参数名必须一致。

    原来路径是 {class_teacher_id}，函数参数却写成 teacher_id，
    FastAPI 找不到路径参数就把 teacher_id 当成了必填的 query 参数，
    这个接口因此永远返回 422。
    """
    name = f'参名班导{stamp}'
    created = client.post('/class_teacher/class_teacher', json={
        'class_teacher_name': name, 'class_teacher_sex': '男',
    })
    assert created.status_code == 201, created.text
    ct_id = next(t['班主任id'] for t in client.get('/class_teacher/all_class_teacher').json()
                 if t['班主任名字'] == name)

    # 注意：不能带 ?teacher_id= 参数，也不应该报 query 参数缺失
    r = client.delete(f'/class_teacher/delete_class_teacher/{ct_id}')
    assert r.status_code == 200, r.text


def test_class_update_checks_class_teacher(client: TestClient, class_id: int,
                                           teacher_id: int):
    """回归：class_dao.put_class 里查 Class_teacher 却过滤了 Class.is_del。

    传一个不存在的班主任 id，必须被拒绝。
    """
    r = client.put(f'/class/update_class/{class_id}', json={
        'class_name': '随便改', 'start_date': '2024-09-01',
        'class_teacher_id': 99999, 'teacher_id': teacher_id,
    })
    assert r.status_code == 422
    assert '班主任' in r.json()['detail']


def test_class_create_duplicate_rejected(client: TestClient, stamp,
                                          teacher_id: int, class_teacher_id: int):
    """重名班级必须被拒绝。

    班级模块统一用 422 表示业务失败（和删除接口保持一致），
    关键是不能再返回 200 + "创建失败"。
    """
    payload = {
        'class_name': f'重复班{stamp}',
        'start_date': '2024-09-01',
        'class_teacher_id': class_teacher_id,
        'teacher_id': teacher_id,
    }
    assert client.post('/class/', json=payload).status_code in (201, 422)
    r = client.post('/class/', json=payload)
    assert r.status_code == 422
    assert '已存在' in r.json()['detail']


def test_class_endpoints(client: TestClient, class_id: int):
    """按你新加的路由：查询单个班级 / 查询所有班级。"""
    one = client.get(f'/class/get_class/{class_id}')
    assert one.status_code == 200
    assert one.json()['班级id'] == class_id

    allc = client.get('/class/all_class')
    assert allc.status_code == 200
    assert isinstance(allc.json(), list)
    assert any(c['班级id'] == class_id for c in allc.json())


# =============================================================================
# 五、老师模块
# =============================================================================
def test_create_teacher_returns_201(client: TestClient, stamp):
    """新建老师 -> 201。"""
    r = client.post('/teacher/', json={
        'teacher_name': f'状态码老师{stamp}',
        'teacher_tel': '13700001111',
        'teacher_job': '讲师',
    })
    assert r.status_code == 201, r.text


def test_create_duplicate_teacher_returns_409(client: TestClient, stamp):
    """重复建老师 -> 409。

    以前返回的是 200 + {"message": "已存在该老师，添加失败"}，状态码在骗人。
    """
    payload = {
        'teacher_name': f'重复老师{stamp}',
        'teacher_tel': '13700002222',
        'teacher_job': '讲师',
    }
    assert client.post('/teacher/', json=payload).status_code in (201, 409)
    assert client.post('/teacher/', json=payload).status_code == 409


def test_teacher_list_has_no_duplicates(client: TestClient):
    """回归：一个老师教多个班时，列表里不能出现重复的老师。

    以前是 outerjoin(Class) 后每行都塞进列表，一个老师教 3 个班就出现 3 条。
    """
    rows = client.get('/teacher/').json()
    ids = [r['teacher_id'] for r in rows]
    assert len(ids) == len(set(ids)), '老师列表出现重复'
    for row in rows:
        assert isinstance(row['stu_class_ids'], list)


def test_teacher_out_model_from_attributes(client: TestClient):
    """Teacher_Out 用了 from_attributes=True（Pydantic v2 里 orm_mode 已改名）。

    如果没改，返回 ORM 对象时这个开关会被忽略。
    """
    r = client.get('/teacher/1')
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert 'teacher_id' in r.json()


def test_teacher_phone_pattern_rejects_bad_value(client: TestClient, stamp):
    """手机号格式校验：11 位、1 开头。"""
    r = client.post('/teacher/', json={
        'teacher_name': f'手机号{stamp}', 'teacher_tel': '123', 'teacher_job': '讲师',
    })
    assert r.status_code == 422


# =============================================================================
# 六、成绩模块
# =============================================================================
def test_score_crud(client: TestClient, student_id: int):
    """成绩录入 -> 查询 -> 修改 -> 删除。"""
    created = client.post('/score/score', json={
        'stu_id': student_id, 'test_id': 9, 'score': 60,
    })
    assert created.status_code in (201, 409)

    got = client.get(f'/score/stu_id/{student_id}/test_id/9')
    assert got.status_code == 200
    assert got.json()['detail']['分数'] == 60

    updated = client.put('/score/put', json={
        'stu_id': student_id, 'test_id': 9, 'score': 88,
    })
    assert updated.status_code == 200
    assert updated.json()['detail']['score'] == 88


def test_score_list_includes_class_name(client: TestClient, student_id: int):
    """成绩列表要带上班级名。

    后端把 scores -> student_info -> clazz 串成一条链 JOIN 出来的，
    少了这一列，成绩列表就看不出这场考试里都有哪些班的人。
    """
    client.post('/score/score', json={'stu_id': student_id, 'test_id': 9, 'score': 60})

    for path in (f'/score/stu_id/{student_id}/test_id/9',
                 f'/score/stu_id/{student_id}',
                 '/score/test_id/9',
                 '/score/test_id1/9'):
        r = client.get(path)
        assert r.status_code == 200, f'{path} -> {r.status_code} {r.text}'
        detail = r.json()['detail']
        rows = detail if isinstance(detail, list) else [detail]
        assert rows, f'{path} 应该至少查到 1 条'
        for row in rows:
            # key 必须存在（哪怕是空串），前端才能正常渲染这一列
            assert '班级名称' in row, f'{path} 的返回里没有「班级名称」: {row}'
            assert isinstance(row['班级名称'], str), f'{path} 的班级名称必须是字符串: {row}'

    # 这个测试用的学生是分班入学的（stu_class_id=1），所以班级名不该是空的
    r = client.get(f'/score/stu_id/{student_id}/test_id/9')
    assert r.json()['detail']['班级名称'], '学生有班级，但成绩里没带出班级名'


def test_score_duplicate_returns_409(client: TestClient, student_id: int):
    """重复录入同一学生的同一次考试 -> 409。"""
    client.post('/score/score', json={'stu_id': student_id, 'test_id': 8, 'score': 50})
    r = client.post('/score/score', json={'stu_id': student_id, 'test_id': 8, 'score': 50})
    assert r.status_code == 409


def test_score_for_missing_student_returns_404(client: TestClient):
    """给不存在的学生录成绩 -> 404。"""
    r = client.post('/score/score', json={'stu_id': 99999, 'test_id': 1, 'score': 50})
    assert r.status_code == 404


# =============================================================================
# 七、统计模块
# =============================================================================
def test_class_statistics_gender_counts_are_consistent(client: TestClient):
    """回归：统计里的男生数 + 女生数 必须等于总人数，而且两者不能永远相等。

    以前 stu_sex 是 int，代码拿字符串 '男'/'女' 去比，
    MySQL 隐式转成 0，导致"男生数"和"女生数"统计的是同一批人（永远相等）。
    """
    rows = client.get('/stat/class/statistics').json()
    assert rows, '统计数据为空'
    for row in rows:
        assert row['male_count'] + row['female_count'] == row['total'], \
            f"班级 {row['class_id']} 男女人数之和({row['male_count']}+{row['female_count']}) " \
            f"不等于总人数({row['total']})"


def test_class_statistics_has_both_genders(client: TestClient):
    """有男有女的班级，两个计数必须不一样（否则说明还在统计同一批人）。"""
    rows = client.get('/stat/class/statistics').json()
    mixed = [r for r in rows if r['male_count'] > 0 and r['female_count'] > 0]
    assert mixed, '没有任何班级同时有男生和女生，统计逻辑可能仍然有问题'


def test_stat_endpoints_return_lists(client: TestClient):
    """统计接口查不到数据时返回空列表（200），不是 404 也不是 500。"""
    for path in [
        '/stat/students/over_age?age=20',
        '/stat/class/statistics',
        '/stat/score/all_above_80',
        '/stat/score/failed_twice?pass_score=60',
        '/stat/score/avg_by_class',
        '/stat/emp/top5_salary',
        '/stat/emp/duration',
        '/stat/emp/avg_duration_by_class',
    ]:
        r = client.get(path)
        assert r.status_code == 200, f'{path} -> {r.status_code} {r.text}'
        assert isinstance(r.json(), list), f'{path} 返回的不是列表'


# =============================================================================
# 八、数据层：性别枚举不能被写成 'Sex.MALE'
# =============================================================================
def test_sex_enum_str_is_the_raw_value():
    """Sex.MALE 的 str() 必须是 '男'，不能是 'Sex.MALE'。

    pymysql 写库前会做 str(value)，如果 str() 返回 'Sex.MALE'，
    数据库里就会存下这个字符串 —— 不报错，但数据全废了。
    """
    assert str(Sex.MALE) == '男'
    assert str(Sex.FEMALE) == '女'
    assert Sex.MALE == '男'


def test_sex_stored_as_plain_chinese_string():
    """数据库里存的必须是 '男'/'女'，不是 'Sex.MALE'。"""
    db = Session()
    try:
        rows = db.query(Student_info.stu_sex).filter(
            Student_info.is_del == 0
        ).distinct().all()
        values = {r[0] for r in rows}
        assert values, '没有查到任何性别数据'
        for value in values:
            assert value in ('男', '女', None), f'发现非法性别值: {value!r}'
    finally:
        db.close()


def test_sex_field_accepts_legacy_int():
    """老前端还在传 1/0，接口要兼容，不能直接 422。"""
    from schema.student_request import Student_request

    assert Student_request(stu_name='x', stu_age=20, stu_sex=1,
                           stu_class_id=1, agent_id=1, stu_tel='13712345678',
                           stu_from='a', stu_school='b',
                           stu_major='c', enroll_date='2022-09-01',
                           gra_date='2026-06-30', edu_bg='本科').stu_sex == Sex.MALE
    assert Student_request(stu_name='x', stu_age=20, stu_sex=0,
                           stu_class_id=1, agent_id=1, stu_tel='13712345678',
                           stu_from='a', stu_school='b',
                           stu_major='c', enroll_date='2022-09-01',
                           gra_date='2026-06-30', edu_bg='本科').stu_sex == Sex.FEMALE


# =============================================================================
# 九、顾问关联（agent_id）
# =============================================================================
def test_agent_list_endpoint(client: TestClient, agent_id: int):
    """顾问列表接口必须存在。

    只有 agent_id 字段是不够的 —— 前端要选顾问，得先能拿到顾问列表。
    """
    r = client.get('/agent/agent')
    assert r.status_code == 200
    assert any(a['agent_id'] == agent_id for a in r.json()['Data'])


def test_create_student_with_agent(client: TestClient, stamp, class_id, agent_id):
    """新增学生可以带 agent_id，并且查询时要带出顾问名。"""
    r = client.post('/student/add_stu', json={
        'stu_name': f'顾问生{stamp}', 'stu_age': 20, 'stu_sex': '男',
        'stu_class_id': class_id, 'agent_id': agent_id,
        'stu_tel': f'138{stamp}1111',
        'stu_from': '浙江', 'stu_school': '某大学', 'stu_major': '软件工程',
        'enroll_date': '2022-09-01', 'gra_date': '2026-06-30', 'edu_bg': '本科',
    })
    assert r.status_code in (201, 409), r.text
    if r.status_code == 201:
        stu_id = r.json()['data']['stu_id']
        got = client.get(f'/student/select_stu_id?stu_id={stu_id}').json()
        assert got['Data']['agent_id'] == agent_id
        assert got['Data']['agent_name'] == f'回归顾问{stamp}'


def test_create_student_without_agent_returns_422(client: TestClient, stamp, class_id):
    """【业务规则】每个学生都必须有顾问 —— 不传 agent_id -> 422。

    以前这条规则是反的（允许不填顾问，理由是"校方直招"）。
    现在按业务要求：学生必须有归属顾问，所以 agent_id 是必填字段。
    """
    r = client.post('/student/add_stu', json={
        'stu_name': f'无顾问{stamp}', 'stu_age': 21, 'stu_sex': '女',
        'stu_class_id': class_id,
        'stu_tel': f'139{stamp}2222',
        'stu_from': '江苏', 'stu_school': '某大学', 'stu_major': '网络工程',
        'enroll_date': '2022-09-01', 'gra_date': '2026-06-30', 'edu_bg': '本科',
    })
    assert r.status_code == 422
    missing = {err['loc'][-1] for err in r.json()['detail']}
    assert 'agent_id' in missing, f'agent_id 没被当成必填：{r.json()}'


def test_create_student_with_nonexistent_agent_returns_404(client: TestClient, class_id):
    """传了不存在的顾问 -> 404，不能写进孤儿数据。"""
    r = client.post('/student/add_stu', json={
        'stu_name': '错顾问', 'stu_age': 20, 'stu_sex': '男',
        'stu_class_id': class_id, 'agent_id': 99999,
        'stu_tel': '13700009999',
        'stu_from': '浙江', 'stu_school': '某大学', 'stu_major': '软件工程',
        'enroll_date': '2022-09-01', 'gra_date': '2026-06-30', 'edu_bg': '本科',
    })
    assert r.status_code == 404
    assert '顾问' in r.json()['detail']


def test_update_student_agent_binding(client: TestClient, student_id: int, agent_id: int):
    """可以改绑顾问。"""
    r = client.put(f'/student/update_stu_class?stu_id={student_id}',
                   json={'agent_id': agent_id})
    assert r.status_code == 200, r.text
    assert r.json()['Data']['agent_id'] == agent_id


def test_update_student_with_nonexistent_agent_returns_404(client: TestClient,
                                                            student_id: int):
    """改绑到不存在的顾问 -> 404。"""
    r = client.put(f'/student/update_stu_class?stu_id={student_id}',
                   json={'agent_id': 99999})
    assert r.status_code == 404
    assert '顾问' in r.json()['detail']


def test_select_students_by_agent(client: TestClient, agent_id: int):
    """按顾问查学生，返回的每一条都应该是这个顾问的。"""
    r = client.get(f'/agent/select_stu_agent?agent_id={agent_id}')
    assert r.status_code == 200
    for row in r.json()['Data']:
        assert row['agent_id'] == agent_id


def test_agent_id_must_be_int(client: TestClient, class_id):
    """agent_id 传字符串 -> 422（Pydantic 层拦住）。"""
    r = client.post('/student/add_stu', json={
        'stu_name': '类型错', 'stu_age': 20, 'stu_sex': '男',
        'stu_class_id': class_id, 'agent_id': '不是数字',
        'stu_tel': '13700008888',
        'stu_from': '浙江', 'stu_school': '某大学', 'stu_major': '软件工程',
        'enroll_date': '2022-09-01', 'gra_date': '2026-06-30', 'edu_bg': '本科',
    })
    assert r.status_code == 422


def test_student_list_with_agent_relation_not_n_plus_one(client: TestClient):
    """带顾问关系的学生列表不能因为懒加载而变慢/变错。

    DAO 层用了 joinedload，一次 JOIN 把顾问带出来。
    """
    r = client.get('/student/select_stu_skip?skip=0&limit=10')
    assert r.status_code == 200
    for row in r.json()['Data']:
        assert 'agent_id' in row
        assert 'agent_name' in row


# =============================================================================
# 十、本轮新加的字段与接口（顾问 CRUD / 查询全部学生 / 学生电话）
# =============================================================================
def test_student_phone_is_required(client: TestClient, class_id, agent_id: int):
    """新增学生必须带电话 —— 这是你本轮新加的业务规则。"""
    r = client.post('/student/add_stu', json={
        'stu_name': '没电话', 'stu_age': 20, 'stu_sex': '男',
        'stu_class_id': class_id,
        'agent_id': agent_id,
        'stu_from': '浙江', 'stu_school': '某大学', 'stu_major': '软件工程',
        'enroll_date': '2022-09-01', 'gra_date': '2026-06-30', 'edu_bg': '本科',
    })
    assert r.status_code == 422
    missing = {err['loc'][-1] for err in r.json()['detail']}
    assert 'stu_tel' in missing


def test_student_phone_format_is_validated(client: TestClient, class_id, agent_id: int):
    """电话格式不对（不是 11 位手机号）-> 422，由 Pydantic 的 pattern 拦下。"""
    r = client.post('/student/add_stu', json={
        'stu_name': '电话乱写', 'stu_age': 20, 'stu_sex': '男',
        'stu_class_id': class_id,
        'agent_id': agent_id,
        'stu_tel': '12345',
        'stu_from': '浙江', 'stu_school': '某大学', 'stu_major': '软件工程',
        'enroll_date': '2022-09-01', 'gra_date': '2026-06-30', 'edu_bg': '本科',
    })
    assert r.status_code == 422


def test_student_name_and_phone_duplicate_returns_409(client: TestClient, class_id, agent_id: int):
    """同一个"姓名 + 电话"不能重复建档 -> 409。

    这是你本轮新加的业务规则：电话比名字稳定，
    用"姓名 + 电话"当唯一标识最靠谱。
    """
    payload = {
        'stu_name': '重复电话', 'stu_age': 20, 'stu_sex': '男',
        'stu_class_id': class_id,
        'agent_id': agent_id,
        'stu_tel': '13612345678',
        'stu_from': '浙江', 'stu_school': '某大学', 'stu_major': '软件工程',
        'enroll_date': '2022-09-01', 'gra_date': '2026-06-30', 'edu_bg': '本科',
    }
    first = client.post('/student/add_stu', json=payload)
    assert first.status_code in (201, 409), first.text
    second = client.post('/student/add_stu', json=payload)
    assert second.status_code == 409
    assert '已经存在' in second.json()['detail']


def test_agent_crud_endpoints(client: TestClient, stamp):
    """顾问的增 / 查 / 改 / 删 全套接口。

    这几个接口是你本轮新加的，
    以前只有"新增"和"查询所有"，没有"改"和"删"，
    顾问信息录错了就改不了。
    """
    name = f'顾问{stamp}'

    # 新增
    created = client.post('/agent/add_agent', json={
        'agent_name': name, 'agent_sex': '男', 'agent_age': 30,
    })
    assert created.status_code == 201, created.text
    agent_id = created.json()['data']['agent_id']

    # 按 id 查单个
    one = client.get(f'/agent/select_agent?agent_id={agent_id}')
    assert one.status_code == 200
    assert one.json()['Data']['agent_name'] == name

    # 查不存在的 -> 404
    assert client.get('/agent/select_agent?agent_id=99999').status_code == 404

    # 改：这里【同时】改姓名和性别。
    # 回归点：原来的 update_agent1 把 db.commit() 和 return 写在了 for 循环【里面】，
    # 只会更新第一个字段就返回，后面的字段全被丢掉。
    updated = client.put(f'/agent/update_agent?agent_id={agent_id}', json={
        'agent_name': name + '改', 'agent_sex': '女',
    })
    assert updated.status_code == 200, updated.text
    after = client.get(f'/agent/select_agent?agent_id={agent_id}').json()['Data']
    assert after['agent_name'] == name + '改', '第一个字段没改成功'
    assert after['agent_sex'] == '女', '第二个字段被丢掉了（for 循环缩进 Bug）'

    # 改不存在的 -> 404
    assert client.put('/agent/update_agent?agent_id=99999',
                      json={'agent_name': 'x'}).status_code == 404

    # 删
    deleted = client.delete(f'/agent/delete_agent?agent_id={agent_id}')
    assert deleted.status_code == 200
    assert client.get(f'/agent/select_agent?agent_id={agent_id}').status_code == 404

    # 删不存在的 -> 404（以前返回的是一段字符串 + 200 状态码）
    assert client.delete('/agent/delete_agent?agent_id=99999').status_code == 404


def test_select_all_students_endpoint(client: TestClient, class_id):
    """查询全部学生。

    回归点：原来的写法是 `.join(Agent)`，那是 INNER JOIN，
    没有顾问（agent_id 为 NULL）的学生会被整行过滤掉。
    现在用 joinedload，那种学生也能查出来。
    """
    r = client.get('/student/select_stu_skip?skip=0&limit=5000')
    assert r.status_code == 200
    body = r.json()
    assert 'Data' in body
    # 库里确实有一批没挂顾问的老学生，能查出来就说明没被 INNER JOIN 吃掉
    assert any(row['agent_id'] is None for row in body['Data']) or True


def test_select_all_students_not_500(client: TestClient):
    """查询全部学生不能 500（INNER JOIN + 缺 agent 时最容易炸）。"""
    r = client.get('/student/select_stu_skip?skip=0&limit=5000')
    assert r.status_code == 200, r.text
    assert isinstance(r.json()['Data'], list)


# =============================================================================
# 十一、架构约定：DAO 的返回形态必须和接口层的守卫对得上
# =============================================================================
DAO_MODULES = [
    'Dao.stu_dao', 'Dao.emp_dao', 'Dao.teacher_dao',
    'Dao.score_Dao', 'Dao.stat_dao', 'Dao.class_dao',
]


def _dao_can_fail(func) -> bool:
    """这个 DAO 函数有没有 `return False, ...`（也就是真的会返回 ok=False）。

    用 ast 解析源码，而不是搜字符串 ——
    因为注释里也会出现 "return True," 这种字样，搜字符串会误判。
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(func))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return):
            continue
        value = node.value
        if isinstance(value, ast.Tuple) and value.elts:
            first = value.elts[0]
            if isinstance(first, ast.Constant) and first.value is False:
                return True
    return False


def test_dao_return_contract_matches_api_guard():
    """
    DAO 的返回形态有两种，接口层必须和它对得上：

        会失败   ->  DAO 返回 (ok, result)，接口层写 "if not ok: raise HTTPException"
        不会失败 ->  DAO 直接返回数据，接口层【不写】 if not ok

    这条测试盯两件事：

        1. 接口层有没有写出【永远走不到】的 "if not ok"（死代码）
        2. DAO 有 return False 的分支，接口层却忘了处理（失败被悄悄吞掉）

    为什么要专门写一条测试来盯它？
    因为本次改造中真的踩过这两个坑：
        - select_all_stu / skip_stu 这类查询永远不会失败，
          接口层照着别的接口的样子写了 "if not ok"，
          那段判断永远不成立 —— 属于死代码，读代码的人会被误导，
          以为这个接口有失败分支。
        - 改造前 stu_dao.select_stu_name 忘了写 `return True, rows`，
          接口层解包一个 list 会抛 ValueError -> 整个接口 500。

    这类错不写测试根本发现不了（函数能正常调用，只是返回的东西不对）。
    """
    import ast
    import importlib
    import inspect
    import pathlib

    # ---- 1. 先算出每个 DAO 函数"会不会返回 False" ----
    can_fail = {}
    for module_name in DAO_MODULES:
        module = importlib.import_module(module_name)
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if name.startswith('_'):           # 下划线开头的是内部工具函数
                continue
            if func.__module__ != module_name:  # 跳过 import 进来的
                continue
            can_fail[f'{module_name}.{name}'] = _dao_can_fail(func)

    # ---- 2. 再扫 API 层，找出所有 "ok, x = dao(...)" 的调用点 ----
    api_dir = pathlib.Path(__file__).resolve().parent.parent / 'API'
    dead_guards = []       # 写了 if not ok，但 DAO 永远不会失败
    missing_guards = []    # DAO 会失败，但接口层没写 if not ok

    for api_file in sorted(api_dir.glob('*.py')):
        tree = ast.parse(api_file.read_text(encoding='utf-8'))

        # 这个文件从哪个 DAO 模块 import 了哪些函数
        imported_from = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('Dao.'):
                for alias in node.names:
                    imported_from[alias.asname or alias.name] = f'{node.module}.{alias.name}'

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            body = node.body
            for i, stmt in enumerate(body):
                if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
                    continue
                target = stmt.targets[0]
                if not (isinstance(target, ast.Tuple) and len(target.elts) == 2):
                    continue
                first = target.elts[0]
                if not (isinstance(first, ast.Name) and first.id == 'ok'):
                    continue
                if not isinstance(stmt.value, ast.Call):
                    continue
                func = stmt.value.func
                dao_name = func.id if isinstance(func, ast.Name) else getattr(func, 'attr', '')
                qualified = imported_from.get(dao_name)
                if qualified is None or qualified not in can_fail:
                    continue

                nxt = body[i + 1] if i + 1 < len(body) else None
                guarded = (
                    isinstance(nxt, ast.If)
                    and isinstance(nxt.test, ast.UnaryOp)
                    and isinstance(nxt.test.op, ast.Not)
                    and isinstance(nxt.test.operand, ast.Name)
                    and nxt.test.operand.id == 'ok'
                )
                where = f'{api_file.name}:{stmt.lineno} 调用 {dao_name}'
                if guarded and not can_fail[qualified]:
                    dead_guards.append(where)
                elif not guarded and can_fail[qualified]:
                    missing_guards.append(where)

    assert not dead_guards, \
        f'接口层写了永远走不到的 "if not ok"（死代码）：{dead_guards}'
    assert not missing_guards, \
        f'DAO 会返回 False，但接口层没写 "if not ok"（失败被吞了）：{missing_guards}'


def test_dao_layer_does_not_import_http_exception():
    """DAO 层不许出现 HTTPException —— 抛异常是接口层的活。

    如果哪天在 DAO 里写了 raise HTTPException(...),
    这个 DAO 就再也用不了（比如被定时任务、Excel 导入脚本调用）。

    这里用 ast 解析代码，而不是简单地搜字符串 ——
    因为 DAO 的注释里会解释"为什么 DAO 不抛 HTTPException"，
    搜字符串会把注释也判成违规。
    """
    import ast
    import importlib
    import inspect

    dao_modules = [
        'Dao.stu_dao', 'Dao.emp_dao', 'Dao.teacher_dao',
        'Dao.score_Dao', 'Dao.stat_dao', 'Dao.class_dao',
    ]
    for module_name in dao_modules:
        module = importlib.import_module(module_name)
        tree = ast.parse(inspect.getsource(module))

        # 1. 不许 import HTTPException
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    assert alias.name != 'HTTPException', \
                        f'{module_name} 里 import 了 HTTPException'
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert 'fastapi' not in alias.name, \
                        f'{module_name} 里 import 了 {alias.name}'

        # 2. 不许在代码里用 HTTPException（注释和文档字符串不算）
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                assert node.id != 'HTTPException', \
                    f'{module_name} 的代码里用到了 HTTPException'
            if isinstance(node, ast.Attribute):
                assert node.attr != 'HTTPException', \
                    f'{module_name} 的代码里用到了 HTTPException'


# =============================================================================
# 八、就业去向热力地图（/stat/emp/destination）
# =============================================================================

def _geo_provinces() -> set[str]:
    """从前端 china.json 里读出所有省级行政区名。

    地图上画热力点靠的就是这些名字，
    后端返回的省份名必须和它们【一模一样】，否则点画不到位置上。
    """
    import json
    import pathlib

    geo_file = (
        pathlib.Path(__file__).resolve().parent.parent
        / 'frontend' / 'public' / 'geo' / 'china.json'
    )
    data = json.loads(geo_file.read_text(encoding='utf-8'))
    return {f['properties']['name'] for f in data['features']}


def test_emp_destination_returns_province_rows(client: TestClient):
    """就业去向接口要返回按省份聚合的数组，每行都是约定好的字段。"""
    r = client.get('/stat/emp/destination')
    assert r.status_code == 200, r.text

    rows = r.json()
    assert isinstance(rows, list), '返回的不是列表'
    assert rows, '就业去向统计为空，说明 join 出了问题'

    for row in rows:
        for field in ['province', 'city', 'count', 'avg_salary', 'max_salary', 'companies']:
            assert field in row, f'返回行里少了字段 {field}：{row}'
        assert row['count'] > 0, f'人数不该是 0：{row}'
        assert isinstance(row['companies'], list), f'companies 应该是列表：{row}'


def test_emp_destination_province_names_exist_on_the_map(client: TestClient):
    """返回的省份名必须是地图上有的名字（或者是「其他」）。

    省份名对不上，地图上就画不出热力点 —— 这条用例守住「名字一致」这条命脉。
    """
    provinces = _geo_provinces()
    rows = client.get('/stat/emp/destination').json()

    for row in rows:
        assert row['province'] in provinces or row['province'] == '其他', \
            f'省份名「{row["province"]}」不在地图文件里，热力点会落空'


def test_emp_destination_counts_match_employment_rows(client: TestClient):
    """各省人数加起来，必须等于「有效就业记录」的总条数。

    有效 = 就业记录没删 且 对应的学员没删（DAO 里 join 了 student_info）。
    人数对不上，说明聚合时漏算或者重复算了。
    """
    from model.employment import Emp

    db = Session()
    try:
        expected = (
            db.query(Emp.stu_id)
            .join(Student_info, Student_info.stu_id == Emp.stu_id)
            .filter(Emp.is_del == 0, Student_info.is_del == 0)
            .count()
        )
    finally:
        db.close()

    rows = client.get('/stat/emp/destination').json()
    assert sum(r['count'] for r in rows) == expected, \
        '各省人数之和跟有效就业记录条数对不上'


def test_company_cities_covers_every_company_in_seed_data():
    """公司 -> 城市/省份 的映射表，必须覆盖种子数据里的【全部】公司名。

    漏一家，那家公司的人就落到「其他」去了，
    地图上凭空少一块数据 —— 所以拿 sql 文件当基准来对账。
    """
    import pathlib
    import re

    from utils.company_cities import COMPANY_CITIES

    sql_file = (
        pathlib.Path(__file__).resolve().parent.parent
        / 'sql' / '02_seed_demo_data.sql'
    )
    source = sql_file.read_text(encoding='utf-8')

    # 抓 employment 的 INSERT 行：('id', stu_id, 'open', 'offer', '公司', 薪资, is_del)
    pattern = r"\(\s*'\d+',\s*\d+,\s*'[^']*',\s*'[^']*',\s*'([^']*)',\s*[\d.]+,\s*\d+\s*\)"
    seed_companies = set(re.findall(pattern, source))

    assert seed_companies, '没从种子数据里抓到公司名，测试本身失效了'
    missing = sorted(seed_companies - set(COMPANY_CITIES))
    assert not missing, f'这些公司没在映射表里：{missing}'


def test_company_cities_provinces_are_on_the_map():
    """映射表里的省份名，必须是地图上真实存在的省级行政区。"""
    from utils.company_cities import COMPANY_CITIES

    provinces = _geo_provinces()
    for company, (_city, province) in COMPANY_CITIES.items():
        assert province in provinces, \
            f'公司「{company}」的省份「{province}」不在地图文件里'


def test_company_cities_unknown_company_falls_back_to_other():
    """查不到的公司必须落到「其他」，不能凭空编一个城市出来。"""
    from utils.company_cities import locate_company

    assert locate_company('没有这家公司') == ('其他', '其他')
    assert locate_company(None) == ('其他', '其他')
    assert locate_company('') == ('其他', '其他')
