# 根目录按职责归类 — 设计

日期：2026-11-22
状态：待批准

## 1. 意图

根目录目前混着被测 C++ 源码、Python 脚手架、入口 bat、用例配置和构建产物。
把文件按职责收进子目录，让“被测对话框 / 测试脚手架 / 辅助工具 / 入口脚本 / 产物”
一眼可分；不改任何脚本的行为和测试语义。

## 2. 目标

- 根目录只留目录 + `README.md` + `.gitignore`。
- 源码、脚手架、工具、入口脚本各归其位。
- 构建产物集中到 `build/`（git 忽略）。
- 所有脚本用“相对脚本自身位置”的路径，不再依赖 `cd /d E:\Code\auto-dialog`。
- 现有 17 个单元测试全绿；`scripts\build.bat` 能重新产出 DLL。

## 3. 非目标

- 不升级/重写脚手架（`templates/` 里的通用新版不合并进来）。
- 不改用例语义、结果格式、环境变量协议。
- 不改 `.claude/skills/.../templates/`（它是给新项目复制用的独立副本）。
- 不重写历史设计文档。

## 4. 目标结构

```
auto-dialog/
├─ src/                   被测对话框
│  ├─ baseDialog.cpp
│  ├─ baseDialog.hpp
│  ├─ baseDialog.dlx
│  ├─ baseDialog_test.cpp
│  └─ autodlg_test.h
├─ harness/               测试脚手架（NX 内 Python 3.3）
│  ├─ run_cases.py
│  ├─ harness_core.py
│  ├─ report.py
│  └─ cases.json
├─ tools/                 离线辅助工具
│  ├─ autodlg_patch.py
│  └─ check_prod.py
├─ scripts/               入口脚本
│  ├─ build.bat
│  └─ launch.bat
├─ build/                 编译产物（忽略：*.dll *.obj *.lib *.exp *.pdb）
├─ application/           NX 运行时 dlx（忽略，必须在根）
├─ tests/
├─ docs/
├─ tmp/                   （忽略）
├─ .claude/  .superpowers/
├─ README.md
└─ .gitignore
```

`application/` 必须直接位于 `UGII_USER_DIR` 下，而 `UGII_USER_DIR` 仍保持为仓库根，
所以它留在根目录。

## 5. 方案取舍

- **A（选定）按职责四层**：被测物、脚手架、工具、入口脚本分开，产物集中。
  分层最清楚，代价是 6 个路径点要同步改。
- **B 按文件类型二分**（`src/` + `tools/`）：改动最少，但脚手架和被测物都算
  “源码类”，职责仍然混。
- **C 被测/脚手架两分**（`dialog/` + `harness/`）：目录更少，但 pytest 与 NX
  journal 脚本同处一室，入口 bat 也塞进 harness，不够清楚。

## 6. 具体改动

### 6.1 文件移动（保留 git 历史：`git mv`）

| 文件 | 去向 |
|---|---|
| `baseDialog.cpp` / `.hpp` / `.dlx` | `src/` |
| `baseDialog_test.cpp` | `src/` |
| `autodlg_test.h` | `src/` |
| `run_cases.py` / `harness_core.py` / `report.py` / `cases.json` | `harness/` |
| `autodlg_patch.py` / `check_prod.py` | `tools/` |
| `build.bat` / `launch.bat` | `scripts/` |

`baseDialog.cpp` 当前未提交的“删注释”改动原样保留，不额外处理。

### 6.2 `scripts/build.bat`

- `set "ROOT=%~dp0.."`，`cd /d "%ROOT%"`（去掉写死的 `E:\Code\auto-dialog`）。
- 编译：`cl ... -I src -I"%UGII_USERFCN%" -Fo build\ src\baseDialog_test.cpp`
  （prod 目标同理用 `src\baseDialog.cpp`）。
- 链接：`pushd build` → `call "%UGII_USERFCN%\uflink.bat" UFDLL baseDialog_test.dll`
  → `popd`。原因是 `uflink.mak` 在当前目录找 `$*.obj`、把 DLL 写在当前目录。
  nmake 只做链接（obj 已存在），不再触发编译。
- 复制：`copy /y src\baseDialog.dlx application\baseDialog.dlx`。
- `build\` 不存在时先 `mkdir`。

### 6.3 `scripts/launch.bat`

- `set "ROOT=%~dp0.."`，去掉写死路径。
- `UGII_USER_DIR=%ROOT%`，`AUTODLG_CASE/OUT` 仍指 `%ROOT%\tmp\...`。
- 复制 `src\baseDialog.dlx` 到 `application\`。
- 提示文本改为 `harness\run_cases.py`；退出后跑
  `python harness\report.py --manifest ... --results ...`。

### 6.4 `harness/run_cases.py`

- `HERE` = 本文件目录（`harness/`），`ROOT` = `dirname(HERE)`。
- `DLL = ROOT\build\baseDialog_test.dll`。
- `DEFAULT_CASES = HERE\cases.json`。
- `FIXED_CASE/FIXED_OUT`、默认 `tmp_dir` 都改到 `ROOT\tmp\...`。
- 与 `harness_core.py` 同目录，`import harness_core` 不变（NX journal 的
  `sys.path[0]` 就是脚本目录）。

### 6.5 `harness/report.py`、`tools/*.py`

- `report.py` 与 `harness_core.py` 同目录，无内部改动。
- `check_prod.py`、`autodlg_patch.py` 本来就只吃命令行参数，无改动。

### 6.6 `tests/`

四个测试都把仓库根插进 `sys.path` 后直接 `import` 顶层模块；移动后改为把
`harness/` 或 `tools/` 插入 `sys.path`：

- `test_harness_core.py`、`test_report.py`、`test_run_cases_dryrun.py` → `harness/`
- `test_autodlg_patch.py` → `tools/`

### 6.7 `.gitignore` 与索引

- 追加 `__pycache__/`、`*.pyc`、`build/`。
- `git rm -r --cached __pycache__ tests/__pycache__`（只取消跟踪，磁盘保留）。
- 根目录 `.bak`、`.backup-v1/`、`.superpowers/` 按你的选择保留不动。

### 6.8 `README.md`

更新所有命令路径：
- `scripts\build.bat` / `scripts\build.bat prod`
- `python tools\check_prod.py build\baseDialog.dll`
- `scripts\launch.bat`
- MCP 片段 `sys.path.insert(0, r"E:\Code\auto-dialog\harness")`，
  `cases_path=r"E:\Code\auto-dialog\harness\cases.json"`
- 重新生成：`python tools\autodlg_patch.py --cpp src\baseDialog.cpp --dlx src\baseDialog.dlx`
- 说明 DLL 输出在 `build\`。

## 7. 约束与风险

| 约束/风险 | 处理 |
|---|---|
| `uflink.bat` 的 nmake 在 cwd 找 obj、输出 DLL | 链接时 `pushd build` |
| NX 从 `%UGII_USER_DIR%\application\` 找 dlx | `application/` 留根，`UGII_USER_DIR` 仍指根 |
| NX Python 3.3 靠脚本目录 import `harness_core` | 两者同放 `harness/` |
| 绝对路径改相对后，bat 从任意 cwd 调用仍可用 | `%~dp0..`；NX journal 的 `__file__` 兜底 |
| 移动后 git 历史断裂 | 全部用 `git mv` |

## 8. 验证

1. `python -m unittest discover -s tests -v` → 17 个测试全绿。
2. `python harness/run_cases.py --dry-run --cases harness/cases.json`
   （临时 tmp 目录）能写 manifest 和 case 文件。
3. `scripts\build.bat` 产出 `build\baseDialog_test.dll`；`scripts\build.bat prod`
   产出 `build\baseDialog.dll`。
4. `python tools\check_prod.py build\baseDialog.dll` 报 `prod ok`。
5. （可选，需开 NX）按 README 跑一次 5 条用例，确认 5 PASS。

## 9. 留给 builder 的决定

- bat 里 `ROOT` 去尾斜杠的写法。
- `run_cases.py` 的 DLL 是否回退搜索：先 `build\`，找不到再看仓库根（便于旧产物）。
- README 措辞。
