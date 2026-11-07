"""
数据库连接与会话管理（整个项目只有这一个文件负责"怎么连数据库"）。

【这个文件解决 3 个问题】
    1. 怎么从 .env 读到数据库配置
    2. 怎么创建连接池（以及为什么必须开 pre_ping）
    3. 怎么把"一个请求一个数据库会话"这件事交给 FastAPI
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# load_dotenv() 会把 .env 文件里的内容读进"环境变量"。
# 好处：密码不用写在代码里，换数据库只要改 .env，不用改代码。
load_dotenv()

# 从环境变量里取配置（.env 里没有的会返回 None）
host = os.getenv("DB_HOST")
port = os.getenv("DB_PORT")
user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
database = os.getenv("DB_NAME")

# create_engine 创建一个"引擎"，它内部管理着一个连接池。
# 注意：create_engine 本身【不会】连接数据库，只有真正执行查询时才会连。
#       所以这里就算数据库没启动，这个文件也能正常 import。
engine = create_engine(
    f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}',
    # 连接池最多保持 5 条连接，同时来的请求超过 5 个就排队等
    pool_size=5,
    # 一条连接最多用 1 小时就丢弃重建。
    # 原因：MySQL 默认 8 小时后会断开空闲连接，
    #       而连接池不知道这件事，下一次把这条"死连接"交给请求，
    #       就会报 MySQL server has gone away。
    pool_recycle=3600,
    # 取连接之前先 ping 一下，服务器已经断开就自动换一条新的。
    # 这一条能挡掉绝大多数"服务跑了一晚上就崩"的线上事故。
    pool_pre_ping=True,
    # 显式指定字符集，避免中文乱码
    connect_args={'charset': 'utf8mb4'},
)

# declarative_base() 创建一个"基类"。
# 所有 ORM 模型都要继承它，这样 SQLAlchemy 才知道
# 你的表有哪些表、哪些列、哪些外键 —— 建表和查询都靠这份"登记表"。
Base = declarative_base()

# sessionmaker 创建一个"会话工厂"。
# Session 可以理解成"一次数据库操作的上下文"：
# 在同一个 Session 里做的多次查询，可能共用一条连接、同一个事务。
Session = sessionmaker(bind=engine)


def get_db():
    """
    FastAPI 依赖：每个请求拿一个 Session，用完自动关掉。

    【为什么用 yield 而不是 return】
        yield 之前 = 准备阶段（相当于"打开"）
        yield 之后 = 清理阶段（相当于"关闭"）
        FastAPI 会在响应发出去之后，再执行 yield 之后的部分来关连接。

    【为什么 except 里要 rollback】
        假设某个请求执行 INSERT 时违反了唯一索引：
        1. 数据库报错，事务进入了"失败"状态
        2. 如果不 rollback，这个 Session 后续任何操作都会报
           PendingRollbackError
        3. 而这个 Session 是从连接池拿的，
           不 rollback 就等于把一个"坏掉的会话"还回池子里，
           下一个人拿到它照样报错 —— 故障会莫名其妙地"传给别人"。

    异常往上抛（raise），交给 FastAPI 处理；
    业务上的失败（404 / 409 / 422）由接口层抛 HTTPException。
    """
    db = Session()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
