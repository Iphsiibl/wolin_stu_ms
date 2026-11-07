"""
utils 包。

====================================================================
【为什么要有这个文件】
====================================================================
项目根目录下原本有一个【单文件模块】 utils.py，里面放着通用小工具
model_to_dict（API/emp_api.py、API/stu_info_api.py 都这么 import 它）：

    from utils import model_to_dict

后来 utils/ 下面要放新的子模块（company_cities.py），
于是 utils/ 变成了一个【包】。而 Python 里
「同名包」和「同名模块」撞车时【包优先】——
一旦 utils/ 有了 __init__.py，根目录那个 utils.py 就再也 import 不到了，
上面两行老代码会直接报 ImportError。

这个文件就是来解决这个撞车的：
按【文件路径】把根目录下的 utils.py 加载进来，
model_to_dict 照常可用，老代码一行都不用改，
根目录的 utils.py 本身也不用动。

注意这里为什么不用 `__path__.append(项目根目录)` 那种写法：
那样做的话，导入 `utils.utils` 时会先在包目录里匹配到【包自己】，
于是 utils/__init__.py 又被执行一遍，无限递归。
按路径加载就没有这个坑。
====================================================================
"""
import importlib.util as _importlib_util
import os as _os

# 项目根目录（本包的上一级）
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))

# 按文件路径加载根目录下原来的 utils.py，挂成 utils._legacy_utils
_spec = _importlib_util.spec_from_file_location(
    'utils._legacy_utils', _os.path.join(_ROOT, 'utils.py')
)
_legacy = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)

# 兼容老写法：from utils import model_to_dict
model_to_dict = _legacy.model_to_dict

__all__ = ['model_to_dict']
