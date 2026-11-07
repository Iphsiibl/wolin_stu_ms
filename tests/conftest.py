"""
pytest 公共 fixture。

说明：这些测试跑在真实的开发库 student_ms 上（和 smoke_test.py 一样）。
为了让每次跑都不互相干扰，所有测试数据都带唯一标记，且只创建不删除。
"""
import time

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope='session')
def client():
    """FastAPI 测试客户端。

    raise_server_exceptions=False：
    Starlette 默认会在测试里把异常重新抛出来（测试直接崩掉），
    设置 False 之后，未处理的异常会变成一个 500 响应，我们才能断言状态码。
    """
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(scope='session')
def stamp():
    """本轮测试的唯一标记，保证测试数据不互相覆盖。"""
    return str(int(time.time()))[-4:]


@pytest.fixture(scope='session')
def teacher_id(client, stamp):
    """造一个老师，返回他的 id。"""
    r = client.post('/teacher/', json={
        'teacher_name': f'回归老师{stamp}',
        'teacher_tel': '13900002222',
        'teacher_job': '讲师',
    })
    assert r.status_code in (201, 409), r.text
    if r.status_code == 201:
        return r.json()['data']['teacher_id']
    # 已存在就查出来
    for t in client.get('/teacher/').json():
        if t['teacher_name'] == f'回归老师{stamp}':
            return t['teacher_id']
    raise AssertionError('老师创建失败')


@pytest.fixture(scope='session')
def class_teacher_id(client, stamp):
    """造一个班主任，返回他的 id。

    注意：班级模块的接口返回体是你定的那套（{'message': ...}），
    不带 data，所以只能建完之后从"查询所有班主任"里按名字反查 id。
    """
    name = f'回归班导{stamp}'
    r = client.post('/class_teacher/class_teacher', json={
        'class_teacher_name': name,
        'class_teacher_sex': '男',
    })
    assert r.status_code in (201, 422), r.text
    for t in client.get('/class_teacher/all_class_teacher').json():
        if t['班主任名字'] == name:
            return t['班主任id']
    raise AssertionError('班主任创建失败')


@pytest.fixture(scope='session')
def class_id(client, stamp, teacher_id, class_teacher_id):
    """造一个班级，返回它的 id。"""
    name = f'回归班{stamp}'
    r = client.post('/class/', json={
        'class_name': name,
        'start_date': '2024-09-01',
        'class_teacher_id': class_teacher_id,
        'teacher_id': teacher_id,
    })
    assert r.status_code in (201, 422), r.text
    for row in client.get('/class/all_class').json():
        if row['班级名字'] == name:
            return row['班级id']
    raise AssertionError('班级创建失败')


@pytest.fixture(scope='session')
def agent_id(client, stamp):
    """造一个顾问，返回他的 id。"""
    r = client.post('/agent/add_agent', json={
        'agent_name': f'回归顾问{stamp}',
        'agent_sex': '男',
        'agent_age': 30,
    })
    assert r.status_code == 201, r.text
    return r.json()['data']['agent_id']


@pytest.fixture(scope='session')
def student_id(client, stamp, class_id, agent_id):
    """造一个学生，返回他的 id。

    注意：agent_id（顾问）是【必填】的 —— 业务规则是每个学生都必须有顾问。
    """
    r = client.post('/student/add_stu', json={
        'stu_name': f'回归生{stamp}',
        'stu_age': 22,
        'stu_sex': '男',
        'stu_class_id': class_id,
        # 负责招这个学生的顾问（必填）
        'agent_id': agent_id,
        # 电话是必填的（你本轮新加的业务规则），格式必须是 11 位手机号。
        # 这里用 stamp 拼一个唯一号码，避开"姓名 + 电话"重复校验。
        'stu_tel': f'137{stamp}8888',
        'stu_from': '浙江',
        'stu_school': '测试大学',
        'stu_major': '软件工程',
        'enroll_date': '2022-09-01',
        'gra_date': '2026-06-30',
        'edu_bg': '本科',
    })
    assert r.status_code in (201, 409), r.text
    if r.status_code == 201:
        return r.json()['data']['stu_id']
    r2 = client.get(f'/student/select_stu_name?stu_name=回归生{stamp}')
    return r2.json()['Data'][0]['stu_id']
