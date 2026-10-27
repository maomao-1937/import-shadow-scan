# 中文快速开始

`import-shadow-scan` 只检查你明确提供的目录中的第一层文件名，提示潜在的 Python 标准库同名文件和本地具体候选重复。它不读取候选源码、不导入候选模块，也不修改 `sys.path`。需要 Python 3.11 或更新版本，无第三方依赖。

在本项目源码副本的目录中执行：

```console
python import_shadow_scan.py --help
python import_shadow_scan.py . --format json
python -I import_shadow_scan.py . --format json
python examples/demo.py harmless
python examples/demo.py stdlib --format json
python examples/demo.py duplicate
python examples/demo.py namespace --format json
python examples/demo.py builtin
python -m unittest discover -s tests -v
```

- `harmless` 退出码为 0；`stdlib` 和 `duplicate` 为 1，表示检测到了预期问题。
- `namespace` 为 0：前一个目录中的命名空间候选不会盖过后一个目录中的具体模块，也不因此构成重复。
- `builtin` 为 0：`sys.py` 提供内置模块豁免信息，因为通常由内置导入器优先处理。
- 退出码 2 表示输入、链接/重解析点、数量限制、文件系统或输出错误。演示脚本只创建并清理项目内的临时示例目录，不改动实际源码。

实际使用的命令形式为 `python import_shadow_scan.py ROOT [ROOT ...] [--format json|text]`。按你要审阅的顺序传入真实目录；路径有空格时加引号。报告中的 `root_index` 从 0 开始。同一目录同名包排在 `.py` 模块之前；这只是候选排列，不保证真实运行时会导入哪个模块。

上述“不执行候选源码”指清单扫描代码本身。Python 启动、扫描器自身的标准库依赖、已有 `PYTHONPATH` 和 site 启动钩子仍须可信；若待查目录与扫描器安装或启动路径重叠，不能绝对保证解释器启动期间没有加载其中的代码。建议从任意目录使用 `python -I <扫描器绝对路径> ROOT ...`，减少当前目录和 `PYTHONPATH` 对启动搜索路径的影响；上方也提供了源码目录内可直接运行的 `-I` 示例。这不是安全沙箱，Python 安装及 site 配置仍须可信。

目录上限 32 个，每个目录第一层条目上限 10,000 个，总候选上限 50,000 个。拒绝重复解析目录、根路径组件中的链接、候选链接和 Windows 重解析点。假定扫描期间文件系统不变且没有恶意并发替换，这不是防竞态的安全沙箱。标准库名称参考来自当前 Python，并包含当前平台不可用的模块；冻结模块、扩展模块、自定义导入器等不在解析范围内。

一般代码检查建议先使用 [Ruff A005](https://docs.astral.sh/ruff/rules/stdlib-module-shadowing/)。完整范围见 [README](README.md)，实际测试结果见 [TESTING](TESTING.md)。
