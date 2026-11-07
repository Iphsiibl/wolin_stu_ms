import logging
import os

import uvicorn
from fastapi import FastAPI
# import model 会触发各个模型文件末尾的 Base.metadata.create_all(engine)，
# 也就是"把表建出来"—— 所以启动服务时表会自动建好，不用手动建。
import model  # noqa: F401
from API.class_api import router04
from API.emp_api import router03
from API.reset_api import router09
from API.score_api import router02
from API.stat_api import router06
from API.stu_info_api import router01
from API.teacher_api import router05
from API.stu_info_api import router07
from API.class_teacher_api import router08

# logging 全都能解决。
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

# -----------------------------------------------------------------------------
# 应用对象
# -----------------------------------------------------------------------------
app = FastAPI(
    title='学生管理系统 API',
    version='1.0.0',
)

# -----------------------------------------------------------------------------
# 路由
# -----------------------------------------------------------------------------
app.include_router(router01, prefix='/student', tags=['学生基本信息接口'])
app.include_router(router02, prefix='/score', tags=['学生成绩管理接口'])
app.include_router(router03, prefix='/employment', tags=['就业信息管理'])
app.include_router(router04, prefix='/class', tags=['班级信息管理'])
app.include_router(router07,prefix='/agent',tags = ['顾问信息管理'])
app.include_router(router05, prefix='/teacher', tags=['老师信息管理'])
app.include_router(router06, prefix='/stat', tags=['统计分析'])

app.include_router(router08, prefix='/class_teacher', tags=['班主任信息管理'])

# 演示数据重置（不挂在 Swagger 里，靠口令保护）
app.include_router(router09, prefix='/reset', tags=['演示数据重置'])


if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host=os.getenv('APP_HOST', '127.0.0.1'),
        port=int(os.getenv('APP_PORT', '8003')),
        reload=os.getenv('APP_RELOAD', '0') == '1',
    )
