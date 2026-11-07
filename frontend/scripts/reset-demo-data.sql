-- =====================================================================
-- 演示数据复位脚本（前端 scripts/reset-demo-data.sql）
-- ---------------------------------------------------------------------
-- 用途：把演示库恢复到「种子基线」，清掉测试脚本留下的垃圾行。
--
-- 为什么需要它：
--   后端在并发调试时会往正式库里写测试数据（命名特征很明显：
--   Z###### / ZZTEST###### / 回归班2759 / 重复班2801 / 状态码老师2801 /
--   测试班5040改 / 探针班2834 / 待删5251 …）。
--   这些行会直接出现在前端列表页上，看着像「数据出错了」。
--
-- 怎么用：
--   mysql -u root -p --default-character-set=utf8mb4 -D student_ms_demo `
--     --execute="source frontend/scripts/reset-demo-data.sql"
--   （-p 会提示输入密码；密码见项目根目录 .env 的 DB_PASSWORD）
--
-- 安全性：
--   ① 只按「命名特征」删，不碰任何种子行（种子行是 1..N 的连续 id，
--      且名字是「软件工程1班 / 李家怡 / 余涵」这类正常数据）。
--   ② 先删子表再删父表，不破坏外键（employment / scores / student_info / clazz）。
--   ③ 跑完最后一段 SELECT 会打印各表行数，对照 sql/02_seed_demo_data.sql
--      里的基线：学生 200 / 成绩 600 / 就业 134 / 班级 36 / 班主任 12 / 老师 24 / 顾问 12。
--
--   ⚠️ 如果某个种子行被测试脚本「改值」而不是「加行」（比如把学生1的院校改成
--      'string'），这个脚本救不回来 —— 那种情况得对着 sql/02_seed_demo_data.sql
--      手工比对还原。
-- =====================================================================

-- ---------------------------------------------------------------------
-- 一、先删子表（employment / scores 引用 student_info）
-- ---------------------------------------------------------------------
DELETE FROM employment
WHERE stu_id > 200
   OR company LIKE 'Z%'
   OR company REGEXP '(测试|回归|重复|探针|状态码)';

DELETE FROM scores
WHERE stu_id > 200
   OR id > 600
   OR test_id > 3;

-- ---------------------------------------------------------------------
-- 二、再删学生（引用 clazz 和 agent）
-- ---------------------------------------------------------------------
DELETE FROM student_info
WHERE stu_id > 200
   OR stu_name LIKE 'Z%'
   OR stu_name LIKE '%测试%'
   OR stu_name LIKE '%回归%'
   OR stu_name LIKE '%重复%'
   OR stu_name LIKE '%探针%'
   OR stu_name = 'string';

-- ---------------------------------------------------------------------
-- 三、删班级 / 班主任 / 老师 / 顾问
-- ---------------------------------------------------------------------
DELETE FROM clazz
WHERE stu_class_id > 36
   OR class_name LIKE 'Z%'
   OR class_name LIKE '%测试%'
   OR class_name LIKE '%回归%'
   OR class_name LIKE '%重复%'
   OR class_name LIKE '%探针%'
   OR class_name = 'string';

DELETE FROM class_teacher
WHERE class_teacher_id > 12
   OR class_teacher_name LIKE 'Z%'
   OR class_teacher_name LIKE '%班导%'
   OR class_teacher_name LIKE '%测试%'
   OR class_teacher_name LIKE '%回归%'
   OR class_teacher_name LIKE '%探针%'
   OR class_teacher_name = 'string';

DELETE FROM teacher
WHERE teacher_id > 24
   OR teacher_name LIKE 'Z%'
   OR teacher_name LIKE '%老师%'
   OR teacher_name LIKE '%测试%'
   OR teacher_name LIKE '%回归%'
   OR teacher_name LIKE '%重复%'
   OR teacher_name LIKE '%探针%'
   OR teacher_name LIKE '%状态码%'
   OR teacher_name = 'string';

DELETE FROM agent
WHERE agent_id > 12
   OR agent_name LIKE 'Z%'
   OR agent_name LIKE '%顾问%'
   OR agent_name LIKE '%测试%'
   OR agent_name LIKE '%回归%'
   OR agent_name LIKE '%重复%'
   OR agent_name LIKE '%探针%'
   OR agent_name LIKE '%状态码%'
   OR agent_name LIKE '待删%'
   OR agent_name = 'string';

-- ---------------------------------------------------------------------
-- 四、把残留的软删标记清回去（种子里没有一条 is_del=1）
-- ---------------------------------------------------------------------
UPDATE student_info SET is_del = 0 WHERE is_del <> 0;
UPDATE scores       SET is_del = 0 WHERE is_del <> 0;
UPDATE employment   SET is_del = 0 WHERE is_del <> 0;
UPDATE clazz        SET is_del = 0 WHERE is_del <> 0;
UPDATE class_teacher SET is_del = 0 WHERE is_del <> 0;
UPDATE agent        SET is_del = 0 WHERE is_del <> 0;
UPDATE teacher      SET is_delete = 0 WHERE is_delete <> 0;

-- ---------------------------------------------------------------------
-- 五、自检：对照种子基线
--    期望：200 / 600 / 134 / 36 / 12 / 24 / 12
-- ---------------------------------------------------------------------
SELECT
  (SELECT COUNT(*) FROM student_info)   AS student_expect_200,
  (SELECT COUNT(*) FROM scores)         AS score_expect_600,
  (SELECT COUNT(*) FROM employment)     AS employment_expect_134,
  (SELECT COUNT(*) FROM clazz)          AS clazz_expect_36,
  (SELECT COUNT(*) FROM class_teacher)  AS class_teacher_expect_12,
  (SELECT COUNT(*) FROM teacher)        AS teacher_expect_24,
  (SELECT COUNT(*) FROM agent)          AS agent_expect_12;
