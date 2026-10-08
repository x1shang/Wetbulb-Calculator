# 第三方声明 / Third-party notices

本仓库自有源码使用 MIT（见 LICENSE）；第三方组件保留各自许可证。
GUI 产物包含 GPLv3 的 PySide2-Fluent-Widgets，不能将整个组合二进制宣称为仅 MIT。
随附组件的版权与许可证文本从安装包收集到 THIRD_PARTY_LICENSES.txt；包元数据和许可证也嵌入 GUI exe。
构建方式见 README，准确依赖版本见 requirements-build.txt 和其引用文件。

| 组件 | 用途 | 上游声明 / 源码 |
|---|---|---|
| PySide2 / Shiboken2 5.15.2.1 / Qt | GUI 运行时 | LGPL；[Qt for Python](https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=5.15.2.1)、[Qt](https://code.qt.io/cgit/qt/qtbase.git/) |
| PySide2-Fluent-Widgets 1.7.6 | 按钮、输入框、提示条等 | GPLv3；[源码](https://github.com/zhiyiYo/PyQt-Fluent-Widgets/tree/v1.7.6) |
| PySide2-Frameless-Window | 窗口支持 | LGPLv3；[源码](https://github.com/zhiyiYo/PyQt-Frameless-Window) |
| matplotlib 3.5.3 | 迭代绘图 | PSF 派生许可证；[源码](https://github.com/matplotlib/matplotlib/tree/v3.5.3) |
| NumPy / SciPy | Fluent Widgets 数值依赖 | BSD；随包包含 OpenBLAS 等独立声明；[NumPy](https://github.com/numpy/numpy)、[SciPy](https://github.com/scipy/scipy/tree/v1.10.1) |
| openpyxl 3.1.3 / et-xmlfile | Excel 读写 | MIT；[源码](https://foss.heptapod.net/openpyxl/openpyxl) |
| colorthief 0.2.1 | 图像颜色提取 | BSD；[源码](https://github.com/fengsp/color-thief-py) |
| Pillow | 图像支持 | MIT-CMU；[源码](https://github.com/python-pillow/Pillow) |
| darkdetect | 系统主题检测 | BSD-3-Clause；[源码](https://github.com/albertosottile/darkdetect) |
| pywin32 | Windows 接口 | PSF；[源码](https://github.com/mhammond/pywin32) |
| Python | 解释器 | PSF；[源码](https://github.com/python/cpython) |
| PyInstaller 6.11.1 | 冻结工具与 bootloader | GPL + bootloader exception；[源码](https://github.com/pyinstaller/pyinstaller/tree/v6.11.1) |

其余传递依赖的版本、版权和许可证以随附 THIRD_PARTY_LICENSES.txt 为准。
CLI exe 不导入 GUI 或数值库，随附本项目 LICENSE 与 Python/PyInstaller 运行时许可。
