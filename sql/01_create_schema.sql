-- ============================================================================
--  01_create_schema.sql  ——  建库 + 建表
-- ============================================================================
--
--  【这个脚本干什么】
--    1. 建一个全新的数据库 student_ms_demo
--    2. 建 7 张表（顾问、班主任、班级、老师、学生、成绩、就业）
--    3. 把外键、唯一约束、CHECK 约束、索引一次性建好
--
--  【怎么用】
--    方式一（推荐，不用装 MySQL 命令行）：
--        在项目根目录执行
--            python sql/run_sql.py
--        它会自动按顺序执行本文件和 02_seed_demo_data.sql
--
--    方式二（Navicat / MySQL Workbench / DBeaver）：
--        新建查询窗口，打开本文件，点"运行"即可
--
--  【注意：这和"迁移脚本"不一样】
--    迁移脚本（migrations/）是给"已经在跑的旧数据库"打补丁用的，
--    绝不能写 USE，因为执行器已经连好了目标库。
--    而【本文件】就是用来"从零建一个库"的，
--    所以这里写 USE 是必须的、正确的。
--
--  【想换个库名？】
--    把下面两处的 student_ms_demo 换成你想要的库名就行。
--    第一处：CREATE DATABASE
--    第二处：USE
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 0. 字符集（必须放在最前面）
-- ---------------------------------------------------------------------------
-- 【为什么这里必须有这一句？——实测踩过的坑】
--
--   建表语句里的 CHECK 约束含中文常量：
--       CONSTRAINT `ck_stu_sex` CHECK (`stu_sex` IS NULL OR `stu_sex` IN ('男', '女'))
--
--   如果建表时【连接字符集】不对，MySQL 会把这个中文常量按错误字符集存进
--   约束表达式里。实测在 Docker 里表现为：
--
--       ERROR 3819 (HY000): Check constraint 'ck_stu_sex' is violated.
--
--   而且表结构里能看到乱码：
--       CHECK (((`stu_sex` is null) or (`stu_sex` in (_latin1'?',_latin1'?'))))
--
--   现象很有迷惑性：种子数据里的性别值【明明全是 男/女】，
--   但每一条 INSERT 都被判定违反约束，200 个学生一个都插不进去。
--
--   根因：MySQL 执行 SQL 文件时，连接字符集由【客户端】决定。
--   本地用 Navicat / PyMySQL(utf8mb4) 执行都正常，
--   但 Docker 的 /docker-entrypoint-initdb.d 用的是 mysql 客户端默认字符集，
--   它【不会】继承 02_seed_demo_data.sql 里的 SET NAMES
--   （每个文件是独立进程，SET NAMES 只在本文件内有效）。
--
--   所以【每个建表/灌数据的 SQL 文件开头都必须自己声明字符集】，
--   不能指望另一个文件里的 SET NAMES 生效。
--
--   02_seed_demo_data.sql 里本来就有一句，这里补上的是 01 这一份。
SET NAMES utf8mb4;

-- ---------------------------------------------------------------------------
-- 1. 建库
-- ---------------------------------------------------------------------------
-- IF NOT EXISTS：库已经存在也不报错，直接往下走
DROP DATABASE IF EXISTS `student_ms_demo`;
CREATE DATABASE `student_ms_demo`
    DEFAULT CHARACTER SET utf8mb4          -- utf8mb4 才能存 emoji 和生僻字
    DEFAULT COLLATE utf8mb4_general_ci;    -- 通用排序规则，不区分大小写

-- 切到这个库，后面所有语句都在这个库里执行
USE `student_ms_demo`;


-- ---------------------------------------------------------------------------
-- 2. 顾问表（业务上叫"顾问"，代码里的 Agent / 表名 agent 是历史沿用）
-- ---------------------------------------------------------------------------
CREATE TABLE `agent` (
    `agent_id`   INT          NOT NULL AUTO_INCREMENT COMMENT '顾问编号',
    `agent_name` VARCHAR(20)  DEFAULT NULL                COMMENT '顾问姓名',
    `agent_sex`  VARCHAR(20)  DEFAULT NULL                COMMENT '顾问性别：男/女',
    `agent_age`  INT          DEFAULT NULL                COMMENT '顾问年龄',
    `is_del`     INT          DEFAULT '0'                 COMMENT '是否删除：0未删除，1已删除',
    PRIMARY KEY (`agent_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '顾问表';


-- ---------------------------------------------------------------------------
-- 3. 班主任表
-- ---------------------------------------------------------------------------
CREATE TABLE `class_teacher` (
    `class_teacher_id`   INT         NOT NULL AUTO_INCREMENT COMMENT '班主任编号',
    `class_teacher_name` VARCHAR(10) DEFAULT NULL               COMMENT '班主任姓名',
    `class_teacher_sex`  VARCHAR(1)  DEFAULT NULL               COMMENT '班主任性别',
    `is_del`             INT         DEFAULT NULL               COMMENT '是否删除：0未删除，1已删除',
    PRIMARY KEY (`class_teacher_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '班主任表';


-- ---------------------------------------------------------------------------
-- 4. 老师表
-- ---------------------------------------------------------------------------
CREATE TABLE `teacher` (
    `teacher_id`   INT         NOT NULL AUTO_INCREMENT COMMENT '老师编号',
    `teacher_name` VARCHAR(20) NOT NULL                COMMENT '老师姓名',
    `teacher_tel`  VARCHAR(20) DEFAULT NULL           COMMENT '老师手机号',
    `teacher_job`  VARCHAR(20) NOT NULL                COMMENT '老师岗位',
    `is_delete`    INT         DEFAULT NULL           COMMENT '是否删除：0未删除，1已删除',
    PRIMARY KEY (`teacher_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '老师表';


-- ---------------------------------------------------------------------------
-- 5. 班级表
--    班级 id 是人工指定的（1 号班就是 1），不是自增
-- ---------------------------------------------------------------------------
CREATE TABLE `clazz` (
    `stu_class_id`     INT         NOT NULL AUTO_INCREMENT COMMENT '班级编号',
    `class_name`       VARCHAR(20) DEFAULT NULL               COMMENT '班级名称',
    `start_date`       DATE        DEFAULT NULL               COMMENT '开课时间',
    `class_teacher_id` INT         DEFAULT NULL               COMMENT '班主任id',
    `teacher_id`       INT         DEFAULT NULL               COMMENT '授课老师id',
    `is_del`           INT         DEFAULT '0'                COMMENT '是否删除：0未删除，1已删除',
    PRIMARY KEY (`stu_class_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '班级表';


-- ---------------------------------------------------------------------------
-- 6. 学生表
--    这张表最关键：成绩表和就业表都外键指向它
-- ---------------------------------------------------------------------------
CREATE TABLE `student_info` (
    `stu_id`       INT          NOT NULL AUTO_INCREMENT COMMENT '学生编号',
    `stu_name`     VARCHAR(10)  DEFAULT NULL                COMMENT '学生姓名',
    `stu_age`      INT          DEFAULT NULL                COMMENT '学生年龄',
    `stu_sex`      VARCHAR(10)  DEFAULT NULL                COMMENT '性别：男/女',
    `stu_tel`      VARCHAR(20)  DEFAULT NULL                COMMENT '学生联系电话',
    `stu_class_id` INT          DEFAULT NULL                COMMENT '所在班级id',
    `agent_id`     INT          DEFAULT NULL                COMMENT '负责招生的顾问id',
    `stu_from`     VARCHAR(20)  DEFAULT NULL                COMMENT '生源地',
    `stu_school`   VARCHAR(20)  DEFAULT NULL                COMMENT '毕业院校',
    `stu_major`    VARCHAR(20)  DEFAULT NULL                COMMENT '专业',
    `enroll_date`  DATETIME     DEFAULT NULL                COMMENT '入学时间',
    `gra_date`     DATETIME     DEFAULT NULL                COMMENT '毕业时间',
    `edu_bg`       VARCHAR(20)  DEFAULT NULL                COMMENT '教育背景',
    `is_del`       INT          DEFAULT '0'                 COMMENT '是否删除：0未删除，1已删除',

    PRIMARY KEY (`stu_id`),

    -- 索引：外键列必须建索引，否则关联查询会全表扫
    KEY `fk_student_class` (`stu_class_id`),
    KEY `idx_student_agent_id` (`agent_id`),

    -- 外键 1：所在班级必须真实存在
    CONSTRAINT `fk_student_class`
        FOREIGN KEY (`stu_class_id`) REFERENCES `clazz` (`stu_class_id`),

    -- 外键 2：顾问可以为空（校方直招），顾问被删了学生的这一列自动置空
    CONSTRAINT `fk_student_agent`
        FOREIGN KEY (`agent_id`) REFERENCES `agent` (`agent_id`)
        ON DELETE SET NULL ON UPDATE CASCADE,

    -- CHECK 约束：性别只允许 男 / 女，防止写进脏数据
    -- （老代码把性别存成 int，是历史遗留，这里统一成字符串）
    CONSTRAINT `ck_stu_sex`
        CHECK (`stu_sex` IS NULL OR `stu_sex` IN ('男', '女'))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '学生信息表';


-- ---------------------------------------------------------------------------
-- 7. 成绩表
--    一行 = 一个学生某一次考试的成绩
-- ---------------------------------------------------------------------------
CREATE TABLE `scores` (
    `id`      INT     NOT NULL AUTO_INCREMENT COMMENT '主键自增',
    `stu_id`  INT     NOT NULL                COMMENT '学生编号',
    `test_id` INT     NOT NULL                COMMENT '考试序次',
    `score`   FLOAT   NOT NULL                COMMENT '分数',
    `is_del`  INT     NOT NULL DEFAULT '0'    COMMENT '是否删除：0未删除，1已删除',

    PRIMARY KEY (`id`),
    KEY `idx_scores_stu_id` (`stu_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '成绩表';


-- ---------------------------------------------------------------------------
-- 8. 就业信息表
--    一个学生最多一条就业记录（uk_emp_stu_id 唯一索引保证）
-- ---------------------------------------------------------------------------
CREATE TABLE `employment` (
    `id`         INT          NOT NULL AUTO_INCREMENT COMMENT '主键自增',
    `stu_id`     INT          NOT NULL                COMMENT '学生编号',
    `open_date`  DATETIME     DEFAULT NULL            COMMENT '简历开放日期',
    `offer_date` DATETIME     DEFAULT NULL            COMMENT '收到offer日期',
    `company`    VARCHAR(50)  NOT NULL                COMMENT '就业公司',
    `salary`     DECIMAL(10, 2) NOT NULL              COMMENT '薪资，单位：元',
    `is_del`     INT          DEFAULT '0'             COMMENT '是否删除：0未删除，1已删除',

    PRIMARY KEY (`id`),

    -- 唯一索引：一个学生只能有一条就业信息
    UNIQUE KEY `uk_emp_stu_id` (`stu_id`),

    -- 外键：就业记录必须指向真实存在的学生
    CONSTRAINT `fk_emp_student`
        FOREIGN KEY (`stu_id`) REFERENCES `student_info` (`stu_id`)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '学生就业信息表';


-- ============================================================================
--  建库建表完成。表结构说明：
--
--    agent          顾问           12 行   （带 is_del 软删除标记）
--    class_teacher  班主任          12 行
--    teacher        老师           24 行
--    clazz          班级           36 行
--    student_info   学生          200 行   （约 15% 没有顾问，模拟校方直招）
--    scores         成绩          600 行   （每个学生 3 次考试）
--    employment     就业          130 行
--                        ─────────────────
--                        合计        1014 行
--
--  下一个文件 02_seed_demo_data.sql 会把这些数据插进去。
-- ============================================================================
