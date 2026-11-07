"""
端到端冒烟测试：按业务顺序把每个接口打一遍，打印状态码 + 响应摘要。

它和 tests/test_api.py 的分工：
    test_api.py   —— 用 pytest + TestClient（进程内），跑 33 项回归测试，
                     每条对应一个历史 Bug，用来防回归。CI 里跑这个。
    smoke_live.py —— 打真实跑起来的服务（走真实 HTTP、真实 socket），
                     用来确认"部署出去的那份"也正常。发布前跑这个。

用法:
    # 先启动服务
    python main.py
    # 再执行
    python tests/smoke_live.py
    python tests/smoke_live.py http://127.0.0.1:8002   # 指定地址
"""
import json
import os
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8002"

# 每次跑用不同的名字，这样脚本可以反复执行而不会撞上"已存在"的冲突。
# 注意名字长度：stu_name / class_teacher_name 在数据库里是 varchar(10)，
# 校验也按 10 拦，所以标记只用 4 位。
STAMP = str(int(time.time()))[-4:]
TEACHER_NAME = f"测试老师{STAMP}"
CLASS_NAME = f"测试班{STAMP}"
CT_NAME = f"测试班主任{STAMP}"
STU_NAME = f"测试学生{STAMP}"

PASS, FAIL = "PASS", "FAIL"
results = []


def call(method, path, label="", expect=None, **kw):
    """发一个请求，记录结果。expect 可以是状态码或状态码集合。"""
    url = BASE + path
    try:
        r = httpx.request(method, url, timeout=20.0, **kw)
        status = r.status_code
        try:
            body = r.json()
            brief = json.dumps(body, ensure_ascii=False)[:200]
        except Exception:
            brief = r.text[:200]
    except Exception as e:
        status, brief = 0, f"请求异常: {type(e).__name__}: {e}"

    ok = True
    if expect is not None:
        exp = {expect} if isinstance(expect, int) else set(expect)
        ok = status in exp

    results.append((PASS if ok else FAIL, method, path, label, status, brief))
    print(f"[{'PASS' if ok else 'FAIL'}] {method:6} {path:48} -> {status}")
    print(f"        {label}: {brief}")
    return body if ok else None


print("=" * 100)
print(f"目标服务: {BASE}    测试批次: {STAMP}")
print("=" * 100)

# ---------------------------------------------------------------- 老师
print("\n--- 老师模块 ---")
call("POST", "/teacher/", "新增老师 -> 201",
     json={"teacher_name": TEACHER_NAME, "teacher_tel": "13800001111", "teacher_job": "讲师"},
     expect=201)
call("POST", "/teacher/", "新增老师-重复 -> 409",
     json={"teacher_name": TEACHER_NAME, "teacher_tel": "13800001111", "teacher_job": "讲师"},
     expect=409)
call("GET", "/teacher/", "查询所有老师", expect=200)
call("GET", "/teacher/1", "按ID查老师", expect=(200, 404))
call("PUT", "/teacher/1", "修改老师", json={"teacher_job": "高级讲师"}, expect=(200, 404))
call("DELETE", "/teacher/99999", "删除不存在的老师 -> 404", expect=404)

# ---------------------------------------------------------------- 班主任 + 班级
print("\n--- 班级模块 ---")
# 两个班主任：一个用来建班级（全程保留），一个专门用来测删除
call("POST", "/class_teacher/class_teacher", "新增班主任A -> 201",
     json={"class_teacher_name": CT_NAME, "class_teacher_sex": "男"}, expect=201)
call("POST", "/class_teacher/class_teacher", "新增班主任B(待删) -> 201",
     json={"class_teacher_name": CT_NAME + "B", "class_teacher_sex": "女"}, expect=201)

# 列表接口返回的是 [{'班主任id':..., '班主任名字':...}]，按名字反查 id
_ct_list = httpx.get(f"{BASE}/class/all_class_teacher", timeout=20.0).json()
ct_id = next(t['班主任id'] for t in _ct_list if t['班主任名字'] == CT_NAME)
ct_del_id = next(t['班主任id'] for t in _ct_list if t['班主任名字'] == CT_NAME + "B")
call("GET", "/class_teacher/all_class_teacher", "查询所有班主任", expect=200)
call("GET", f"/class_teacher/get_class_teacher/{ct_id}", "查询单个班主任", expect=200)
call("PUT", f"/class_teacher/update_class_teacher/"{ct_id}", "修改班主任",
     json={"class_teacher_name": CT_NAME + "改", "class_teacher_sex": "女"}, expect=200)
call("DELETE", f"/class_teacher/delete_class_teacher/"{ct_del_id}", "删除班主任", expect=200)
call("GET", f"/class_teacher/get_class_teacher/{ct_del_id}", "查已删班主任 -> 404", expect=404)

call("POST", "/class/", "新建班级 -> 201",
     json={"class_name": CLASS_NAME, "start_date": "2024-09-01",
           "class_teacher_id": ct_id, "teacher_id": 1},
     expect=201)
# 同理，班级 id 也从列表接口反查
_cls_list = httpx.get(f"{BASE}/class/all_class", timeout=20.0).json()
class_id = next(c['班级id'] for c in _cls_list if c['班级名字'] == CLASS_NAME)
call("POST", "/class/", "新建班级-重名 -> 422",
     json={"class_name": CLASS_NAME, "start_date": "2024-09-01",
           "class_teacher_id": ct_id, "teacher_id": 1},
     expect=422)
call("GET", "/class/all_class", "查询所有班级", expect=200)
call("GET", f"/class/get_class/{class_id}", "查询班级", expect=200)
call("PUT", f"/class/update_class/{class_id}", "修改班级",
     json={"class_name": CLASS_NAME + "改", "start_date": "2024-09-02",
           "class_teacher_id": ct_id, "teacher_id": 1},
     expect=200)
call("GET", "/class/get_class/99999", "查不存在的班级 -> 404", expect=404)

# ---------------------------------------------------------------- 学生
print("\n--- 学生模块 ---")
agent = call("POST", "/agent/add_agent", "新增顾问 -> 201",
             json={"agent_name": f"顾问{STAMP}", "agent_sex": "男", "agent_age": 30},
             expect=201)
agent_id = agent['data']['agent_id'] if agent and 'data' in agent else None
call("GET", "/agent/agent", "查询所有顾问", expect=200)

stu = call("POST", "/student/add_stu", "新增学生 -> 201",
           json={"stu_name": STU_NAME, "stu_age": 22, "stu_sex": "男",
                 "stu_class_id": class_id, "agent_id": agent_id,
                 "stu_tel": f"137{STAMP}8888",
                 "stu_from": "浙江", "stu_school": "测试大学",
                 "stu_major": "软件工程", "enroll_date": "2022-09-01",
                 "gra_date": "2026-06-30", "edu_bg": "本科"},
           expect=201)
stu_id = stu['data']['stu_id'] if stu and 'data' in stu else None
call("GET", "/student/select_stu_skip?skip=0&limit=5", "分页查学生", expect=200)
call("GET", "/student/select_all", "查询全部学生", expect=200)
call("GET", f"/student/select_stu_name?stu_name={STU_NAME}", "按姓名查学生", expect=200)
call("GET", f"/student/select_stu_class?stu_class_id={class_id}", "按班级查学生", expect=200)
call("GET", f"/agent/select_stu_agent?agent_id={agent_id}", "按顾问查学生", expect=200)
call("GET", "/student/select_stu_id?stu_id=99999", "查不存在的学生 -> 404", expect=404)

# ---------------------------------------------------------------- 顾问 CRUD
print("\n--- 顾问模块 ---")
call("GET", f"/agent/select_agent?agent_id={agent_id}", "按id查顾问", expect=200)
call("GET", "/agent/select_agent?agent_id=99999", "查不存在的顾问 -> 404", expect=404)
call("PUT", f"/agent/update_agent?agent_id={agent_id}",
     json={"agent_sex": "女"}, expect=200)
call("PUT", "/agent/update_agent?agent_id=99999",
     json={"agent_name": "不存在"}, expect=404)

# 单独建一个顾问专门用来测删除（不影响上面那个还关联着学生的）
_tmp_agent = call("POST", "/agent/add_agent", "新增待删顾问 -> 201",
                  json={"agent_name": f"待删{STAMP}", "agent_sex": "男", "agent_age": 30},
                  expect=201)
if _tmp_agent and 'data' in _tmp_agent:
    call("DELETE", f"/agent/delete_agent?agent_id={_tmp_agent['data']['agent_id']}",
         "删除顾问 -> 200", expect=200)
call("DELETE", "/agent/delete_agent?agent_id=99999", "删不存在的顾问 -> 404", expect=404)
call("PUT", f"/student/update_stu_class?stu_id={stu_id}",
     json={"stu_name": STU_NAME + "改", "stu_school": "测试大学"}, expect=200)
call("DELETE", "/student/delete_stu?stu_id=99999", "删除不存在的学生 -> 404", expect=404)

# ---------------------------------------------------------------- 就业
print("\n--- 就业模块 ---")
call("POST", "/employment/create", "新增就业信息 -> 201",
     json={"stu_id": stu_id, "company": "阿里巴巴", "salary": 25000,
           "open_date": "2026-03-01T00:00:00", "offer_date": "2026-05-01T00:00:00"},
     expect=201)
call("POST", "/employment/create", "新增就业信息-重复 -> 409",
     json={"stu_id": stu_id, "company": "阿里巴巴", "salary": 25000,
           "open_date": "2026-03-01T00:00:00", "offer_date": "2026-05-01T00:00:00"},
     expect=409)
call("POST", "/employment/create", "给不存在的学生加就业信息 -> 404",
     json={"stu_id": 99999, "company": "某公司", "salary": 10000,
           "open_date": "2026-03-01T00:00:00", "offer_date": "2026-05-01T00:00:00"},
     expect=404)
call("POST", "/employment/create", "缺少日期 -> 422",
     json={"stu_id": stu_id, "company": "缺日期", "salary": 1000},
     expect=422)
call("POST", "/employment/create", "offer 早于 open -> 422",
     json={"stu_id": stu_id, "company": "倒序", "salary": 1000,
           "open_date": "2026-05-01T00:00:00", "offer_date": "2026-03-01T00:00:00"},
     expect=422)
call("GET", f"/employment/search?stu_id={stu_id}", "按学号搜就业", expect=200)
call("GET", "/employment/search?company=阿里", "按公司搜就业", expect=200)
call("GET", f"/employment/search?class_name={CLASS_NAME}改", "按班级名搜就业", expect=200)
call("GET", "/employment/search?stu_sex=男", "按性别搜就业", expect=200)
call("GET", "/employment/search?stu_sex=女", "按性别搜就业(女)", expect=200)
call("GET", "/employment/search?salary_min=1000&salary_max=99999", "按薪资区间搜", expect=200)
call("GET", "/employment/search?salary_min=99999&salary_max=1000", "薪资上下限颠倒 -> 400",
     expect=400)
call("GET", "/employment/page?page=1&size=10", "分页查就业", expect=200)
call("GET", "/employment/unemployed", "查询未就业的学生", expect=200)
call("PUT", f"/employment/put/{stu_id}", "改就业信息", json={"company": "字节跳动"}, expect=200)
call("DELETE", "/employment/delete/99999", "删除不存在的就业信息 -> 404", expect=404)

# ---------------------------------------------------------------- 成绩
print("\n--- 成绩模块 ---")
call("POST", "/score/score", "录入成绩 -> 201",
     json={"stu_id": stu_id, "test_id": 1, "score": 88.5}, expect=201)
call("POST", "/score/score", "录入成绩-重复 -> 409",
     json={"stu_id": stu_id, "test_id": 1, "score": 88.5}, expect=409)
call("POST", "/score/score", "给不存在的学生录成绩 -> 404",
     json={"stu_id": 99999, "test_id": 1, "score": 88.5}, expect=404)
call("GET", f"/score/stu_id/{stu_id}", "查学生所有成绩", expect=200)
call("GET", "/score/test_id/1", "查某次考试所有成绩", expect=200)
call("GET", f"/score/stu_id/{stu_id}/test_id/1", "查学生某次成绩", expect=200)
call("PUT", "/score/put", "改成绩",
     json={"stu_id": stu_id, "test_id": 1, "score": 95.0}, expect=200)
call("GET", "/score/get_del", "查已删除成绩 -> 404", expect=404)

# ---------------------------------------------------------------- 统计
print("\n--- 统计模块 ---")
call("GET", "/stat/students/over_age?age=20", "查超龄学员", expect=200)
call("GET", "/stat/class/statistics", "班级人数统计", expect=200)
call("GET", "/stat/score/all_above_80", "全优学生", expect=200)
call("GET", "/stat/score/failed_twice?pass_score=60", "两次不及格", expect=200)
call("GET", "/stat/score/avg_by_class", "班级平均分", expect=200)
call("GET", "/stat/emp/top5_salary", "薪资前五", expect=200)
call("GET", "/stat/emp/duration", "就业时长", expect=200)
call("GET", "/stat/emp/avg_duration_by_class", "班级平均就业时长", expect=200)

# ---------------------------------------------------------------- 汇总
print("\n" + "=" * 100)
failed = [r for r in results if r[0] == FAIL]
print(f"总计 {len(results)} 项，失败 {len(failed)} 项")
if failed:
    print("\n失败清单:")
    for _, m, p, lbl, st, brief in failed:
        print(f"  - {m} {p}  ({lbl})  实际状态码={st}")
        print(f"      {brief}")
print("=" * 100)
sys.exit(1 if failed else 0)
