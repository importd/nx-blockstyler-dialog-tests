# 根目录按职责归类 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把根目录里混放的 C++ 源码、Python 脚手架、工具和入口 bat 按职责收进 `src/`、`harness/`、`tools/`、`scripts/`，构建产物集中到 `build/`，并保持 17 个单测与 NX 构建全部可用。

**Architecture:** 纯文件移动 + 路径重写。移动全部用 `git mv` 保留历史；脚本改为基于 `%~dp0..` / 模块 `__file__` 定位仓库根；`uflink.bat` 在 `build/` 里执行以就地链接。`application/` 因 NX 的 `UGII_USER_DIR` 约定留在根目录。

**Tech Stack:** Windows cmd/bat、Python 3.3（NX 内）/ 3.14（单测）、VS2019 + NX 10 `uflink.bat`。

**Spec:** `docs/superpowers/specs/2026-11-22-root-layout-reorg-design.md`

## Global Constraints

- NX 10 内 Python 固定为 3.3：`harness/` 下的代码禁 f-string、类型注解、`subprocess.run`。
- `application/` 必须直接位于 `UGII_USER_DIR`（仓库根）之下，不得移动。
- 标签/命令仅限 Windows 语义；bat 用 `%~dp0..` 定位根目录。
- 构建链为 VS2019 `vcvars64.bat` + `cl` + `C:\Users\feather\nx10\UGOPEN\uflink.bat`。
- `git mv` 移动所有已跟踪文件；`.claude/skills/**/templates/`、根目录 `.bak`、`.backup-v1/`、`.superpowers/` 一律不动。
- `baseDialog.cpp` 已有的未提交删注释改动原样带进本次提交，不额外修改其内容。
- 每个任务结束跑 `python -m unittest discover -s tests -v`，必须 17 个测试全绿。

## Review Focus

- **从任意 cwd 调用 `scripts\build.bat`**：必须仍能找到 `src\`、`build\`、`application\`（Task 3 在 `C:\` 下实跑验证）。
- **NX journal 执行 `harness\run_cases.py`**：`import harness_core` 必须靠脚本目录成功（Task 2 从 `C:\` 用绝对路径跑 dry-run 验证）。
- **在 `build\` 里调 `uflink.bat`**：nmake 必须找到 `baseDialog_test.obj` 并把 DLL 写在 `build\`（Task 3 实跑验证）。
- **单测 import 迁移后的模块**：四个测试的 `sys.path` 必须指向 `harness/` 或 `tools/`（Task 1 跑全量单测验证）。
- **不再从根目录加载 DLL**：`run_cases.DLL` 必须只指向 `build\baseDialog_test.dll`，避免旧产物被误用（Task 2 常量断言）。

---

### Task 1: 移动文件、更新测试导入、清理 git 索引

**Files:**
- Move: `baseDialog.cpp`、`baseDialog.hpp`、`baseDialog.dlx`、`baseDialog_test.cpp`、`autodlg_test.h` → `src/`
- Move: `run_cases.py`、`harness_core.py`、`report.py`、`cases.json` → `harness/`
- Move: `autodlg_patch.py`、`check_prod.py` → `tools/`
- Move: `build.bat`、`launch.bat` → `scripts/`
- Modify: `.gitignore`
- Modify: `tests/test_autodlg_patch.py:1-5`、`tests/test_harness_core.py:1-5`、`tests/test_report.py:1-5`、`tests/test_run_cases_dryrun.py:1-5`
- Modify (git index only): `__pycache__/`、`tests/__pycache__/`

**Interfaces:**
- Consumes: 无。
- Produces: 后续任务使用的路径 `src/`、`harness/`、`tools/`、`scripts/`、`build/`。

- [ ] **Step 1: 建分支并创建目录**

```bash
git switch -c chore/root-layout-reorg
mkdir -p src harness tools scripts build
```

- [ ] **Step 2: 用 git mv 移动已跟踪文件**

```bash
git mv baseDialog.cpp baseDialog.hpp baseDialog.dlx baseDialog_test.cpp autodlg_test.h src/
git mv run_cases.py harness_core.py report.py cases.json harness/
git mv autodlg_patch.py check_prod.py tools/
git mv build.bat launch.bat scripts/
```

- [ ] **Step 3: 把根目录的旧构建产物移入 build/（非 git 跟踪）**

移动这 8 个文件，不存在则跳过：`baseDialog.dll`、`baseDialog.exp`、`baseDialog.lib`、`baseDialog.obj`、`baseDialog_test.dll`、`baseDialog_test.exp`、`baseDialog_test.lib`、`baseDialog_test.obj`。

不要移动 `baseDialog.cpp.bak`、`baseDialog.dlx.bak`（用户选择保留在根目录）。

- [ ] **Step 4: 更新四个测试的模块搜索路径**

每个测试保留现有 `HERE`（仓库根），在 `import` 前插入对应子目录：

- `tests/test_autodlg_patch.py`：插入 `os.path.join(HERE, "tools")`
- `tests/test_harness_core.py`、`tests/test_report.py`、`tests/test_run_cases_dryrun.py`：插入 `os.path.join(HERE, "harness")`

写法示例（放到 `if HERE not in sys.path` 之后）：

```python
MODDIR = os.path.join(HERE, "harness")   # 或 "tools"
if MODDIR not in sys.path:
    sys.path.insert(0, MODDIR)
```

- [ ] **Step 5: 更新 .gitignore 并取消跟踪 pycache**

`.gitignore` 追加三行：

```
__pycache__/
*.pyc
build/
```

然后：

```bash
git rm -r --cached __pycache__ tests/__pycache__
```

磁盘上的 `.pyc` 保留。

- [ ] **Step 6: 跑全量单测**

Run: `python -m unittest discover -s tests -v`
Expected: `Ran 17 tests ... OK`

- [ ] **Step 7: 确认索引状态**

Run: `git status --short` 与 `git ls-files | grep -i pycache`
Expected: 无 `__pycache__` 跟踪项；可见 `R  baseDialog.cpp -> src/baseDialog.cpp` 等重命名。

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: move sources, harness, tools and scripts into subdirectories"
```

---

### Task 2: 重定向 harness 路径

**Files:**
- Modify: `harness/run_cases.py:12-21`（`HERE`/`DLL`/`DEFAULT_CASES`/`FIXED_*` 常量区）
- Modify: `harness/run_cases.py:19-20`（`_tmp` 默认目录）
- Test: `tests/test_run_cases_dryrun.py`（新增 `LayoutTests`）

**Interfaces:**
- Consumes: Task 1 建立的 `harness/`、`build/`、`tmp/` 布局。
- Produces: 模块常量 `HERE`（harness 目录）、`ROOT`（仓库根）、`DLL`（`<ROOT>/build/baseDialog_test.dll`）、`DEFAULT_CASES`（`<HERE>/cases.json`）、`FIXED_CASE`（`<ROOT>/tmp/cases/current.ini`）、`FIXED_OUT`（`<ROOT>/tmp/results/current.ini`）、`_tmp(None) == <ROOT>/tmp`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_run_cases_dryrun.py` 追加：

```python
class LayoutTests(unittest.TestCase):
    def test_paths_point_into_layout(self):
        root = HERE
        self.assertEqual(run_cases.DEFAULT_CASES,
                         os.path.join(root, "harness", "cases.json"))
        self.assertEqual(run_cases.DLL,
                         os.path.join(root, "build", "baseDialog_test.dll"))
        self.assertEqual(run_cases.FIXED_CASE,
                         os.path.join(root, "tmp", "cases", "current.ini"))
        self.assertEqual(run_cases.FIXED_OUT,
                         os.path.join(root, "tmp", "results", "current.ini"))
        self.assertEqual(run_cases._tmp(None), os.path.join(root, "tmp"))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m unittest tests.test_run_cases_dryrun.LayoutTests -v`
Expected: FAIL（`DLL` 仍指向仓库根，其余断言至少一处不符）。

- [ ] **Step 3: 改 `harness/run_cases.py` 常量**

```python
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DLL = os.path.join(ROOT, "build", "baseDialog_test.dll")
DEFAULT_CASES = os.path.join(HERE, "cases.json")
FIXED_CASE = os.path.join(ROOT, "tmp", "cases", "current.ini")
FIXED_OUT = os.path.join(ROOT, "tmp", "results", "current.ini")


def _tmp(tmp_dir):
    return tmp_dir or os.path.join(ROOT, "tmp")
```

不做 DLL 回退搜索：`build/` 是唯一口径。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m unittest discover -s tests -v`
Expected: `Ran 18 tests ... OK`

- [ ] **Step 5: 从仓库外的 cwd 验证 NX journal 式入口**

Run（PowerShell）:

```powershell
Set-Location C:\
python "E:\Code\auto-dialog\harness\run_cases.py" --dry-run --cases "E:\Code\auto-dialog\harness\cases.json"
```

Expected: 输出包含 `"dry_run": true`，且没有 `ImportError`。

- [ ] **Step 6: Commit**

```bash
git add harness/run_cases.py tests/test_run_cases_dryrun.py
git commit -m "refactor(harness): resolve dll and paths from repo root"
```

---

### Task 3: 重写 build.bat

**Files:**
- Modify: `scripts/build.bat`（整文件替换）

**Interfaces:**
- Consumes: `src/` 源文件、`build/` 产物目录、`application/` 运行目录。
- Produces: `build/baseDialog_test.dll`（默认目标）、`build/baseDialog.dll`（`prod` 目标）。

- [ ] **Step 1: 替换 `scripts/build.bat` 为**

```bat
@echo off
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"

set "NX=C:\Users\feather\nx10"
set "UGII_BASE_DIR=%NX%"
set "UGII_USERFCN=%NX%\UGOPEN"
set "UGII_ROOT_DIR=%NX%\UGII"
set "PATH=%NX%\UGII;%NX%\UGOPEN;%PATH%"

call "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1

cd /d "%ROOT%"
if not exist build mkdir build
if not exist application mkdir application
copy /y src\baseDialog.dlx application\baseDialog.dlx >nul
if errorlevel 1 exit /b 1

set "NODEBUG=1"

if "%~1"=="prod" goto prod

cl -nologo -c -EHsc -DCRTAPI1=_cdecl -DCRTAPI2=_cdecl -GS ^
   -D_AMD64_=1 -DWIN64 -D_WIN64 -DWIN32 -D_WIN32 -W4 ^
   -D_WIN32_IE=0x0500 -DWINVER=0x0500 -Ox -DNDEBUG ^
   -D_MT -D_DLL -MD -Isrc -I"%UGII_USERFCN%" -Fobuild\ src\baseDialog_test.cpp
if errorlevel 1 exit /b 1

pushd build
call "%UGII_USERFCN%\uflink.bat" UFDLL baseDialog_test.dll
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" exit /b 1
echo built build\baseDialog_test.dll
exit /b 0

:prod
cl -nologo -c -EHsc -DCRTAPI1=_cdecl -DCRTAPI2=_cdecl -GS ^
   -D_AMD64_=1 -DWIN64 -D_WIN64 -DWIN32 -D_WIN32 -W4 ^
   -D_WIN32_IE=0x0500 -DWINVER=0x0500 -Ox -DNDEBUG ^
   -D_MT -D_DLL -MD -Isrc -I"%UGII_USERFCN%" -Fobuild\ src\baseDialog.cpp
if errorlevel 1 exit /b 1

pushd build
call "%UGII_USERFCN%\uflink.bat" UFDLL baseDialog.dll
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" exit /b 1
echo built build\baseDialog.dll
exit /b 0
```

- [ ] **Step 2: 从仓库根构建测试 DLL**

Run: `cmd /c scripts\build.bat`
Expected: 输出 `built build\baseDialog_test.dll`，且 `build\baseDialog_test.dll` 存在。

- [ ] **Step 3: 从仓库外的 cwd 再构建一次**

Run: `Set-Location C:\; cmd /c "E:\Code\auto-dialog\scripts\build.bat"`
Expected: 同样输出 `built build\baseDialog_test.dll`，文件时间戳更新。

- [ ] **Step 4: 构建生产 DLL 并做钩子检查**

Run: `cmd /c scripts\build.bat prod`，然后 `python tools\check_prod.py build\baseDialog.dll`
Expected: `built build\baseDialog.dll`；`prod ok: build\baseDialog.dll has no test hook markers`。

- [ ] **Step 5: Commit**

```bash
git add scripts/build.bat
git commit -m "build: resolve paths from script location and emit into build/"
```

---

### Task 4: 重写 launch.bat

**Files:**
- Modify: `scripts/launch.bat`（整文件替换）

**Interfaces:**
- Consumes: `src/baseDialog.dlx`、`application/`、`tmp/`、`harness/report.py`。
- Produces: 启动 NX 的固定环境变量 `UGII_USER_DIR`、`AUTODLG_CASE`、`AUTODLG_OUT`；`--check` 模式只做环境准备并打印 `ROOT=` 后退出。

- [ ] **Step 1: 替换 `scripts/launch.bat` 为**

```bat
@echo off
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"

set "UGII_USER_DIR=%ROOT%"
set "AUTODLG_CASE=%ROOT%\tmp\cases\current.ini"
set "AUTODLG_OUT=%ROOT%\tmp\results\current.ini"
set "AUTODLG_TIMEOUT_MS=8000"

if not exist application mkdir application
copy /y src\baseDialog.dlx application\baseDialog.dlx >nul
if errorlevel 1 exit /b 1
if not exist tmp\cases mkdir tmp\cases
if not exist tmp\results mkdir tmp\results

echo ROOT=%ROOT%
echo Environment ready for NX 10.
echo Start NX 10, open a part with a body, then run the harness:
echo   1) MCP: nx_run_python -^> run_cases.main(cases_path=r"%ROOT%\harness\cases.json", dry_run=False)
echo   2) or NX menu: Tools -^> Journal -^> Play... and select %ROOT%\harness\run_cases.py
echo.
echo Close NX when done; this script then writes tmp\summary.txt.
echo.

if "%~1"=="--check" exit /b 0

"D:\Program Files\Siemens\NX 10.0\UGII\ugraf.exe"

echo.
if exist tmp\manifest.json (
  python harness\report.py --manifest tmp\manifest.json --results tmp\results ^
    --out-json tmp\results.json --out-txt tmp\summary.txt
  if exist tmp\summary.txt type tmp\summary.txt
) else (
  echo No tmp\manifest.json - run_cases.py was not run.
)
```

- [ ] **Step 2: 用 --check 从仓库外验证**

Run: `Set-Location C:\; cmd /c "E:\Code\auto-dialog\scripts\launch.bat --check"`
Expected: 打印 `ROOT=E:\Code\auto-dialog`、`Environment ready for NX 10.`，随后退出，不启动 NX。

- [ ] **Step 3: 确认 dlx 已被复制**

Run: `Test-Path E:\Code\auto-dialog\application\baseDialog.dlx`
Expected: `True`，且时间戳晚于本次运行。

- [ ] **Step 4: Commit**

```bash
git add scripts/launch.bat
git commit -m "launch: resolve paths from script location and add --check mode"
```

---

### Task 5: 更新 README 并做整体验收

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 1-4 的最终路径。
- Produces: 与仓库一致的用户文档；验收记录。

- [ ] **Step 1: 替换 README 中的命令与路径**

逐项改：

| 原内容 | 新内容 |
|---|---|
| `build.bat` | `scripts\build.bat` |
| `build.bat prod` | `scripts\build.bat prod` |
| `python check_prod.py baseDialog.dll` | `python tools\check_prod.py build\baseDialog.dll` |
| `launch.bat` | `scripts\launch.bat` |
| `run_cases.py`（MCP 内 `import run_cases`） | `sys.path.insert(0, r"E:\Code\auto-dialog\harness")` |
| `cases.json`（MCP 的 `cases_path`） | `harness\cases.json` |
| `Tools → Journal → Play...` 的脚本 | `E:\Code\auto-dialog\harness\run_cases.py` |
| `python autodlg_patch.py --cpp baseDialog.cpp --dlx baseDialog.dlx` | `python tools\autodlg_patch.py --cpp src\baseDialog.cpp --dlx src\baseDialog.dlx` |

并在“构建”段补一句：DLL 输出到 `build\`；`application\` 由脚本自动复制。

- [ ] **Step 2: 跑全量单测**

Run: `python -m unittest discover -s tests -v`
Expected: `Ran 18 tests ... OK`

- [ ] **Step 3: dry-run 从仓库外执行**

Run: `Set-Location C:\; python "E:\Code\auto-dialog\harness\run_cases.py" --dry-run --cases "E:\Code\auto-dialog\harness\cases.json"`
Expected: 输出 `"dry_run": true`。

- [ ] **Step 4: 最终构建验收**

Run: `cmd /c scripts\build.bat`；`cmd /c scripts\build.bat prod`；`python tools\check_prod.py build\baseDialog.dll`
Expected: 两个 `built ...`；`prod ok: build\baseDialog.dll has no test hook markers`。

- [ ] **Step 5: 检查根目录与索引**

Run: `git status --short`；`Get-ChildItem E:\Code\auto-dialog -Name`
Expected: 根目录只剩目录与 `README.md`、`.gitignore`，以及用户选择保留的 `baseDialog.cpp.bak`、`baseDialog.dlx.bak`；无未跟踪的 `.pyc`。

Run: `git ls-files | grep -i pycache`
Expected: 无输出。

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: update paths for new directory layout"
```

---

## 验收后

分支 `chore/root-layout-reorg` 上完成后，用 `superpowers:finishing-a-development-branch` 决定合并方式。NX 端到端（开 NX 跑 5 条用例）不在本计划内，按需另跑。
