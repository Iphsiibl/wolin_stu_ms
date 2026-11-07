"""
模型包统一入口。

【为什么所有模型都要在这里 import 一遍？】

SQLAlchemy 的 relationship() 认的是【类名字符串】，
比如 Student_info 里写 relationship("Class", back_populates="students")。
这个 "Class" 要能在 SQLAlchemy 的类注册表里找到，才知道该关联哪张表。

如果只 import 了 model.student_table 而没 import model.class_model，
那么 Student_info.clazz 这个关系在真正查库时才会报错：
    "Class ... is not found in the registry"

把所有模型集中 import 一遍，等于一次性把所有类登记进注册表，
后面无论谁先被 import，关系都能解析成功。

【建表在哪？】

每个模型文件（class_model.py / student_table.py / ...）的末尾都写着
    Base.metadata.create_all(engine)
所以只要启动服务，这 7 张表就自动建好了，不用手动做任何事。

【⚠️ 下面这 5 行 import 的顺序不能随便调】

因为每个模型文件会在自己末尾执行 create_all，
而建表有先后顺序：被别的表外键引用的表，必须先建出来。

    clazz（班级）   <- student_info 引用它
    agent（顾问）   <- student_info 引用它
    student_info    <- employment 引用它

所以要按"被引用的先 import"来排：
    1. class_model    （clazz、class_teacher）—— 没有外键，最先建
    2. student_table  （agent、student_info）—— 引用 clazz
    3. score_model    （scores）—— 没有外键
    4. teacher        （teacher）—— 没有外键
    5. employment     （employment）—— 引用 student_info

如果把 student_table 提到最前面，它的 create_all 会因为
"找不到 clazz 这张表"直接报 NoReferencedTableError。

另外 model/__init__.py 里把所有模型集中 import 了一遍 ——
因为 relationship 里写的是类名字符串（relationship("Class", ...)），
SQLAlchemy 需要在"类注册表"里找到 "Class" 才知道该关联哪张表。
"""

from model.class_model import Class, Class_teacher
from model.student_table import Agent, Student_info
from model.score_model import Score
from model.teacher import Teacher
from model.employment import Emp

__all__ = [
    'Agent',
    'Student_info',
    'Class',
    'Class_teacher',
    'Score',
    'Teacher',
    'Emp',
]
