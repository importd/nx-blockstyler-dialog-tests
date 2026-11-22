# NX 10 对话框测试脚手架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 NX 10 里无人值守地跑 C++ Block Styler 对话框：注入块值、调用 `apply_cb`、断言、自动关窗、出报告。

**Architecture:** 测试钩子编译进测试 DLL，在 `dialogShown_cb` 里读 case 文件、通过公开 `PropertyList` 注入/读回、按需调用 `apply_cb`、写结果后由后台线程向 `#32770` 对话框发 `WM_CLOSE` 关窗。NX 内 Python 3.3 编排器逐条调用 `ufusr`；进程外 `report.py` 负责在 NX 被看门狗强杀时补齐报告。

**Tech Stack:** NX 10.0.0.24、C++ NXOpen/BlockStyler、Windows Win32（WM_CLOSE/窗口枚举）、NX 内置 Python 3.3、系统 Python（测试与报告）。

**Spec:** `E:\Code\auto-dialog\docs\superpowers\specs\2026-11-22-nx10-dialog-test-harness-design.md`

## Global Constraints

- 只在 `E:\Code\auto-dialog` 下工作；所有文件路径用绝对路径。
- NX 10 的 C++ `BlockDialog` 没有 `PerformCancel`/`PerformOK`/`Destroy`；关窗只能用 Win32：向本进程的 `#32770` Block UI 对话框发 `WM_CLOSE`（ESC 实测无效；对话框有 owner，不能用 `GW_OWNER==0` 过滤）。
- 测试代码只在 `#ifdef AUTODLG_TEST` 下参与编译；生产 DLL 里不得出现 `autodlg::collect` / `autodlg::finish` / `autodlg::run_hook` 符号。
- 块的读写只用 `BlockDialog::GetBlockProperties(id)` + `PropertyList` 公有 API；不改 `baseDialog.hpp`、不改构造函数、不改 `Show()`。
- case/result 文件统一 `key=value`，UTF-8；`set.<blockId>=<value>` 是唯一的注入写法。
- NX 内脚本必须兼容 Python 3.3；进程外脚本用系统 Python。
- `baseDialog.dlx` 的 `enum0` 必须有 3 个选项（A/B/C）。
- 该目录不是 git 仓库；Task 1 初始化一个，用于检查点。若不想用 git，跳过所有 commit 步骤。

## Review Focus

1. **对话框根本弹不出来**（`dialogShown_cb` 未触发）：结果必须 `shown=0`，Python 必须判 FAIL，不能因为“没有报错”就 PASS。测试在 Task 2 / Task 5。
2. **WM_CLOSE 关不掉导致卡死**：每条结果先落盘；看门狗超时后由 `report.py` 把该条标记 FAIL(timeout)。测试在 Task 6 / Task 8。
3. **选对象时零件里没有实体**：钩子必须记录 `error`、照常写结果并尝试关窗，不能崩溃。手动验证在 Task 4。
4. **枚举索引越界或选项为空**：`SetEnum` 抛异常时记录 `error`，仍写结果并关窗。手动验证在 Task 4。
5. **生产构建泄漏测试代码**：`build.bat prod` 后扫描 DLL，不能出现 `autodlg::*` 符号。测试在 Task 7。

---

### Task 1: 构建 spike —— 最小 DLL 能被 NX 10 加载并显示对话框

**Files:**
- Modify: `E:\Code\auto-dialog\baseDialog.cpp`（顶部加 `#define USER_EXIT_OR_MENU 1`）
- Create: `E:\Code\auto-dialog\build.bat`
- Create: `E:\Code\auto-dialog\.gitignore`

**Interfaces:**
- Produces: `baseDialog.dll`，带 `ufusr` 导出，能被 NX 10 的 File → Execute → NX Open 加载。
- Produces: `build.bat` 的初步构建命令，Task 7 会扩展为 test/prod。

- [ ] **Step 1: 初始化 git 与忽略文件**

```bash
cd /e/Code/auto-dialog
git init
printf 'tmp/\n*.dll\n*.obj\n*.pdb\n*.ilk\n*.exp\n*.lib\n*.bak\n' > .gitignore
```

- [ ] **Step 2: 打开 `ufusr` 入口**

在 `baseDialog.cpp` 第 1 行之前加：

```cpp
#define USER_EXIT_OR_MENU 1
```

- [ ] **Step 3: 写 `build.bat`（实测可用版本）**

NX 10 没有 `ufcomp`，`uflink` 只链接不编译；且 NX 安装在 `D:\Program Files\...`，`uflink.bat` 遍历 lib 时会在空格处断开。所以先建一个无空格 junction，再用 VS2019 的 `cl` 编译、`uflink` 链接。

```bat
@echo off
setlocal
cd /d E:\Code\auto-dialog

set "NX=C:\Users\feather\nx10"
set "UGII_BASE_DIR=%NX%"
set "UGII_USERFCN=%NX%\UGOPEN"
set "UGII_ROOT_DIR=%NX%\UGII"
set "PATH=%NX%\UGII;%NX%\UGOPEN;%PATH%"

call "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1

if not exist application mkdir application
copy /y baseDialog.dlx application\baseDialog.dlx >nul

set "NODEBUG=1"
cl -nologo -c -EHsc -DCRTAPI1=_cdecl -DCRTAPI2=_cdecl -GS ^
   -D_AMD64_=1 -DWIN64 -D_WIN64 -DWIN32 -D_WIN32 -W4 ^
   -D_WIN32_IE=0x0500 -DWINVER=0x0500 -Ox -DNDEBUG ^
   -D_MT -D_DLL -MD -I. -I"%UGII_USERFCN%" baseDialog.cpp
if errorlevel 1 exit /b 1

call "%UGII_USERFCN%\uflink.bat" UFDLL baseDialog.dll
if errorlevel 1 exit /b 1

echo built baseDialog.dll
```

junction 只需建一次：
`cmd /c mklink /J C:\Users\feather\nx10 "D:\Program Files\Siemens\NX 10.0"`

- [ ] **Step 4: 跑构建**

Run: `build.bat`
Expected: 生成 `E:\Code\auto-dialog\baseDialog.dll`。

若失败：把完整编译/链接错误贴进 `README.md` 并 **停止本计划**，先解决工具链（备选：NX 10 自带 VS 向导 `UGOPEN\vs_files\VC\vcprojects\NX10_NXOpenCPP.vsz`）。这是方案 A 的硬门槛。

- [ ] **Step 5: 在 NX 10 里加载 DLL**

1. 启动 NX 10 前设置 `UGII_USER_DIR=E:\Code\auto-dialog`，并确保 `application\baseDialog.dlx` 存在（Step 3 会复制）。
2. 启动 NX 10 GUI，新建或打开任意零件。
3. File → Execute → NX Open（Ctrl+U），选 `E:\Code\auto-dialog\baseDialog.dll`。
4. Expected: 弹出 `baseDialog` 对话框（class `#32770`，标题「无标题」），能看到 Select Object / Enumeration / Linear Dimension。
5. 用 Cancel 关闭；自动化关窗用 `PostMessageW(hwnd, WM_CLOSE, 0, 0)`（实测 ESC 关不掉）。

注：本机 `ugraf.exe -journal <py>` 不执行 journal，所以这一步必须手动；Task 8 的 launcher 会记录这个限制。

- [ ] **Step 6: 提交**

```bash
git add .gitignore baseDialog.cpp baseDialog.hpp baseDialog.dlx build.bat docs/
git commit -m "build: spike NX 10 DLL that shows baseDialog"
```

---

### Task 2: `harness_core.py` —— 纯逻辑（case/result/compare/summary）

**Files:**
- Create: `E:\Code\auto-dialog\harness_core.py`
- Test: `E:\Code\auto-dialog\tests\test_harness_core.py`

**Interfaces:**
- Produces:
  - `load_cases(path: str) -> dict`
  - `write_case_file(case: dict, path: str) -> None`
  - `parse_result(path: str) -> dict` → `{"shown": int, "hook_ran": int, "apply_rc": int|None, "close_attempted": int, "error": str, "got": dict[str, str]}`
  - `compare(case: dict, result: dict) -> list[dict]` → `[{"name","pass","got","expect"}]`
  - `summarize(rows: list[dict]) -> dict` → `{"total","passed","failed"}`
  - `write_outputs(rows: list[dict], out_json: str, out_txt: str) -> dict`

- [ ] **Step 1: 写失败测试**

`tests/test_harness_core.py`：

```python
import os, sys, tempfile, unittest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import harness_core as H


class CaseFileTests(unittest.TestCase):
    def test_write_case_file_emits_set_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "case.ini")
            H.write_case_file({"name": "x", "apply": True,
                               "set": {"enum0": 2, "linear_dim0": 12.5,
                                       "selection0": "first_body"}}, p)
            lines = open(p, encoding="utf-8").read().splitlines()
            self.assertIn("apply=1", lines)
            self.assertIn("set.enum0=2", lines)
            self.assertIn("set.linear_dim0=12.5", lines)
            self.assertIn("set.selection0=first_body", lines)


class ResultTests(unittest.TestCase):
    def test_parse_result_flattens_got(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "r.ini")
            open(p, "w", encoding="utf-8").write(
                "shown=1\nhook_ran=1\ngot.enum0=2\ngot.linear_dim0=12.5\n"
                "apply_rc=0\nerror=\nclose_attempted=1\n")
            r = H.parse_result(p)
            self.assertEqual(r["shown"], 1)
            self.assertEqual(r["got"]["enum0"], "2")
            self.assertEqual(r["apply_rc"], 0)

    def test_missing_result_is_fail_shown_zero(self):
        case = {"name": "x", "expect": {"shown": 1, "enum0": 2}}
        result = H.parse_result("does-not-exist.ini")
        checks = H.compare(case, result)
        self.assertFalse(all(c["pass"] for c in checks))
        self.assertEqual(result["shown"], 0)


class CompareTests(unittest.TestCase):
    def test_compare_passes_numbers_and_strings(self):
        case = {"name": "x", "expect": {"enum0": 2, "linear_dim0": 12.5}}
        result = {"shown": 1, "hook_ran": 1, "apply_rc": None, "error": "",
                  "got": {"enum0": "2", "linear_dim0": "12.5"}}
        checks = H.compare(case, result)
        self.assertTrue(all(c["pass"] for c in checks))

    def test_compare_reports_mismatch(self):
        case = {"name": "x", "expect": {"enum0": 3}}
        result = {"shown": 1, "hook_ran": 1, "apply_rc": None, "error": "",
                  "got": {"enum0": "2"}}
        checks = H.compare(case, result)
        self.assertFalse(all(c["pass"] for c in checks))


class SummaryTests(unittest.TestCase):
    def test_summarize_counts(self):
        rows = [{"name": "a", "pass": True, "checks": []},
                {"name": "b", "pass": False, "checks": []}]
        self.assertEqual(H.summarize(rows),
                         {"total": 2, "passed": 1, "failed": 1})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m unittest tests.test_harness_core -v`
Expected: FAIL（`ModuleNotFoundError: harness_core`）。

- [ ] **Step 3: 实现 `harness_core.py`**

实现要点：
- `load_cases`：`json.load`，校验 `cases` 是 list、每项有 `name`。
- `write_case_file`：先 `os.makedirs(os.path.dirname(path), exist_ok=True)`；`apply` 为真写 `apply=1`；`set` 按 key 排序写 `set.<id>=<value>`；bool 写 `1/0`。
- `parse_result`：文件不存在返回 `{"shown":0,"hook_ran":0,"apply_rc":None,"close_attempted":0,"error":"result file missing","got":{}}`；逐行 `split("=",1)`；`got.` 前缀进 `got`；`shown/hook_ran/apply_rc/close_attempted` 转 int（空串为 None）。
- `compare`：先加 `shown` 检查（期望取 `case["expect"].get("shown", 1)`）；再对 `case["expect"]` 逐项（跳过已处理的 `shown`）：若 key 在 `result["got"]` 则比较该值，否则比较 `result` 顶层字段；数值用 `abs(float(a)-float(b)) < 1e-6`，bool 用布尔比较，其余字符串相等。
- `summarize`、`write_outputs`：`write_outputs` 写 `{"time","cases","summary"}` 的 JSON，以及和剪切角项目同风格的 `PASS/FAIL` 文本摘要。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m unittest tests.test_harness_core -v`
Expected: 6 个测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add harness_core.py tests/test_harness_core.py
git commit -m "feat: add pure harness core (case/result/compare/summary)"
```

---

### Task 3: `autodlg_patch.py` —— 幂等补丁（cpp + dlx）

**Files:**
- Create: `E:\Code\auto-dialog\autodlg_patch.py`
- Test: `E:\Code\auto-dialog\tests\test_autodlg_patch.py`

**Interfaces:**
- Produces:
  - `patch_cpp(text: str) -> str`：加 `#define USER_EXIT_OR_MENU 1`、`#ifdef AUTODLG_TEST` 的 include、以及 `dialogShown_cb` 里的一行 hook。
  - `patch_dlx(text: str) -> str`：给 `enum0` 的 `Titles` 属性加 `<Strings value="A/B/C"/>`。
  - CLI：`python autodlg_patch.py --cpp baseDialog.cpp --dlx baseDialog.dlx`，原地写回并各留 `.bak`。

- [ ] **Step 1: 写失败测试**

`tests/test_autodlg_patch.py`：

```python
import os, sys, unittest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import autodlg_patch as P


class CppPatchTests(unittest.TestCase):
    SRC = (
        '#include "baseDialog.hpp"\n'
        'void baseDialog::dialogShown_cb()\n'
        '{\n'
        '    try\n    {\n'
        '        //---- Enter your callback code here -----\n'
        '    }\n'
        '    catch(exception& ex)\n    {\n    }\n'
        '}\n'
    )

    def test_adds_define_include_and_hook_once(self):
        out = P.patch_cpp(self.SRC)
        self.assertEqual(out.count("AUTODLG_HOOK"), 1)
        self.assertIn("#define USER_EXIT_OR_MENU 1", out)
        self.assertIn('#include "autodlg_test.h"', out)

    def test_is_idempotent(self):
        once = P.patch_cpp(self.SRC)
        twice = P.patch_cpp(once)
        self.assertEqual(once, twice)


class DlxPatchTests(unittest.TestCase):
    SRC = ('<Dialog><item id="enum0"><PropertyList>'
           '<Property id="Titles" type="utfstrings" sname="Items"/>'
           '</PropertyList></item></Dialog>')

    def test_adds_three_titles(self):
        out = P.patch_dlx(self.SRC)
        for v in ("A", "B", "C"):
            self.assertIn('value="%s"' % v, out)

    def test_is_idempotent(self):
        once = P.patch_dlx(self.SRC)
        twice = P.patch_dlx(once)
        self.assertEqual(twice.count('value="A"'), 1)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m unittest tests.test_autodlg_patch -v`
Expected: FAIL（找不到 `autodlg_patch`）。

- [ ] **Step 3: 实现 `autodlg_patch.py`**

实现要点：
- `patch_cpp`：若文本里没有 `#define USER_EXIT_OR_MENU 1`，插到文件最前；若没有 `autodlg_test.h`，在 `#include "baseDialog.hpp"` 后插：
  ```cpp
  #ifdef AUTODLG_TEST
  #include "autodlg_test.h"
  #endif
  ```
  若没有 `AUTODLG_HOOK`，在 `void baseDialog::dialogShown_cb()` 的 `try {` 之后插：
  ```cpp
  #ifdef AUTODLG_TEST
          AUTODLG_HOOK(theDialog, "selection0", "enum0", "linear_dim0");
  #endif
  ```
  用明确的字符串定位（`"void baseDialog::dialogShown_cb()"` 之后第一个 `"try"` 后的 `{`），找不到就抛 `RuntimeError`。
- `patch_dlx`：用正则找到 `<Property ... id="Titles" ... type="utfstrings" .../>`，替换成带三个 `<Strings value="A"/>...` 的版本；如果标签里已有 `<Strings`，原样返回。正则要同时匹配 `id="Titles"` 与 `type="utfstrings"`（顺序无关）。
- `main`：读文件 → patch → 写回；写回前把原文件复制成 `<name>.bak`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m unittest tests.test_autodlg_patch -v`
Expected: 4 个测试 PASS。

- [ ] **Step 5: 对真实文件跑一次并验证 XML**

```bash
python autodlg_patch.py --cpp baseDialog.cpp --dlx baseDialog.dlx
python -c "import xml.etree.ElementTree as ET; ET.parse(r'E:\Code\auto-dialog\baseDialog.dlx'); print('xml ok')"
```

Expected: `xml ok`；`baseDialog.cpp` 里恰好一处 `AUTODLG_HOOK`。

在 NX 里重新打开对话框，确认 `enum0` 下拉框有 A/B/C。如果下拉框是空的，给 `Titles_1` 属性补三个 `<Option name="A" value="0"/>`（B=1, C=2）后重试。

- [ ] **Step 6: 提交**

```bash
git add autodlg_patch.py tests/test_autodlg_patch.py baseDialog.cpp baseDialog.dlx
git commit -m "feat: idempotent hook/dlx patcher"
```

---

### Task 4: `autodlg_test.h` —— C++ 钩子 + 测试 DLL

**Files:**
- Create: `E:\Code\auto-dialog\autodlg_test.h`
- Create: `E:\Code\auto-dialog\baseDialog_test.cpp`（test 构建包装）
- Modify: `E:\Code\auto-dialog\build.bat`（增加 test 目标）

**Interfaces:**
- Produces:
  - `autodlg::Context`（字段见下）
  - `bool autodlg::collect(NXOpen::BlockStyler::BlockDialog* dlg, const char* const* ids, int n, Context* ctx)`
  - `void autodlg::finish(Context* ctx)`
  - 宏 `AUTODLG_HOOK(dlg, ...)`
- Consumes: Task 3 的补丁点；Task 1 的构建环境。

`Context` 字段：
```cpp
std::map<std::string, std::string> sets;
std::map<std::string, std::string> got;
bool apply;
int apply_rc;
std::string error;
std::string out_path;
int timeout_ms;
bool no_close;
bool kill_on_hang;
```

- [ ] **Step 1: 写 `autodlg_test.h`**

实现要点：
- 宏：
  ```cpp
  #ifdef AUTODLG_TEST
  #define AUTODLG_HOOK(dlg, ...) do { \
      const char* _autodlg_ids[] = {__VA_ARGS__}; \
      autodlg::Context _autodlg_ctx; \
      if (autodlg::collect(dlg, _autodlg_ids, \
              (int)(sizeof(_autodlg_ids)/sizeof(_autodlg_ids[0])), &_autodlg_ctx)) { \
          if (_autodlg_ctx.apply) { \
              try { _autodlg_ctx.apply_rc = apply_cb(); } \
              catch (std::exception& ex) { \
                  _autodlg_ctx.error = ex.what(); _autodlg_ctx.apply_rc = -1; } \
          } \
          autodlg::finish(&_autodlg_ctx); \
      } \
  } while (0)
  #else
  #define AUTODLG_HOOK(...) ((void)0)
  #endif
  ```
- `collect`：`getenv("AUTODLG_CASE")` 为空返回 `false`；读 case 文件、填 `sets/apply`；`out_path = getenv("AUTODLG_OUT")`；`timeout_ms/no_close/kill_on_hang` 用 `getenv` 读，返回 NULL 时用默认值（8000 / 0 / 1）。**没出现在 `set` 里的块也要读回**。逐块处理：
  - `PropertyList* pl = dlg->GetBlockProperties(id)`，`NXException` 捕获后写 `error`。
  - 先试 `pl->GetPropertyType("SelectedObjects")`；成功则按 selection 处理：
    - Work part 为空 → `error="no part"`。
    - 值 `first_body`：用 `BodyCollection::begin()/end()` 取 `Session::GetSession()->Parts()->Work()->Bodies()` 的第一个 `Body*`；没有实体则 `error="no body"`。
    - 其它值（例如数字 tag）v1 记 `error="unsupported:selection value"`。
    - `pl->SetTaggedObjectVector("SelectedObjects", objs)`；`got[id] = to_string(pl->GetTaggedObjectVector("SelectedObjects").size())`。
  - 否则试 `pl->GetPropertyType("Value")`：
    - `PropertyTypeEnum` / `PropertyTypeInteger`：`SetEnum("Value", atoi(v))`；`got[id] = to_string(GetEnum("Value"))`。
    - `PropertyTypeDouble`：`SetDouble("Value", atof(v))`；`got[id] = to_string(GetDouble("Value"))`。
    - 其他：`error = "unsupported:" + id`。
  - 单个块失败只记 `error`，继续处理其它块。
- `finish`：先写 `out_path`（`shown=1`、`hook_ran=1`、`apply_rc`、`error`、`got.*`、`close_attempted` = `no_close ? 0 : 1`），关闭文件；然后 `_beginthreadex` 起关窗线程（延迟 600ms：枚举本进程可见顶层窗口，找 class=`#32770` 且子控件含 `UGS::BlockStyler::DialogCreator` 的窗口，`PostMessageW(hwnd, WM_CLOSE, 0, 0)`）和看门狗线程（等 `timeout_ms`；若对话框仍在，再发 `WM_CLOSE`；再等 1000ms；仍在且 `kill_on_hang` 则 `ExitProcess(3)`）。`no_close` 时跳过第一次关窗，只走看门狗。ESC 只作最后兜底。
- 头文件里 `#include <windows.h> <process.h> <map> <string> <vector> <cstdlib> <cstdio>` 和 NXOpen 的 `BlockStyler_BlockDialog.hxx`、`BlockStyler_PropertyList.hxx`、`Part.hxx`、`BodyCollection.hxx`、`NXException.hxx`。

- [ ] **Step 2: 写 test 构建包装 `baseDialog_test.cpp`**

```cpp
#define USER_EXIT_OR_MENU 1
#define AUTODLG_TEST 1
#include "baseDialog.cpp"
```

- [ ] **Step 3: 扩展 `build.bat`**

```bat
@echo off
setlocal
cd /d E:\Code\auto-dialog
if "%~1"=="prod" goto prod
call "%UGII_BASE_DIR%\ugopen\uflink.bat" UFDLL=baseDialog_test.dll baseDialog_test.cpp
if errorlevel 1 exit /b 1
echo built baseDialog_test.dll
exit /b 0
:prod
call "%UGII_BASE_DIR%\ugopen\uflink.bat" UFDLL=baseDialog.dll baseDialog.cpp
if errorlevel 1 exit /b 1
echo built baseDialog.dll
```

- [ ] **Step 4: 构建测试 DLL**

Run: `build.bat`
Expected: 生成 `baseDialog_test.dll`。

- [ ] **Step 5: 手动 smoke（钩子能跑、能关窗）**

1. 准备 `E:\Code\auto-dialog\tmp\cases\smoke.ini`：
   ```ini
   apply=0
   set.enum0=1
   set.linear_dim0=3.5
   set.selection0=first_body
   ```
2. 写 `E:\Code\auto-dialog\tmp\smoke.bat`：
   ```bat
   set AUTODLG_CASE=E:\Code\auto-dialog\tmp\cases\smoke.ini
   set AUTODLG_OUT=E:\Code\auto-dialog\tmp\results\smoke.ini
   start "" "D:\Program Files\Siemens\NX 10.0\UGII\ugraf.exe"
   ```
3. 运行 `smoke.bat`，在 NX 里新建一个带实体的零件，File → Execute → NX Open 选 `baseDialog_test.dll`。
4. Expected: 对话框出现后约 1 秒自动关闭；`tmp\results\smoke.ini` 里有 `shown=1`、`hook_ran=1`、`got.enum0=1`、`got.linear_dim0=3.5`、`got.selection0=1`。

- [ ] **Step 6: 手动验证两个失败路径**

- 把 `smoke.ini` 的 `set.enum0` 改成 `99`，重跑：结果里有 `error=...`，对话框仍然自动关闭。
- 把 `set.selection0` 改成 `missing`，重跑：结果里有 `error=no body`（或类似），对话框仍然自动关闭。

- [ ] **Step 7: 提交**

```bash
git add autodlg_test.h baseDialog_test.cpp build.bat
git commit -m "feat: in-DLL test hook with inject/read/apply/WM_CLOSE"
```

---

### Task 5: `run_cases.py` —— NX 内 Python 3.3 编排器

**Files:**
- Create: `E:\Code\auto-dialog\run_cases.py`
- Create: `E:\Code\auto-dialog\cases.json`
- Test: `E:\Code\auto-dialog\tests\test_run_cases_dryrun.py`

**Interfaces:**
- Consumes: `harness_core.*`（Task 2）、`baseDialog_test.dll` 的 `ufusr`（Task 4）。
- Produces: `main(cases_path: str, dry_run: bool, tmp_dir: str = None) -> dict`
- CLI: `run_cases.py [--cases PATH] [--dry-run]`

- [ ] **Step 1: 写 `cases.json`**

```json
{
  "part": null,
  "cases": [
    {"name": "defaults", "expect": {"shown": 1, "selection0": 0, "enum0": 0, "linear_dim0": 0.0}},
    {"name": "set_enum", "set": {"enum0": 2}, "expect": {"enum0": 2}},
    {"name": "set_dim", "set": {"linear_dim0": 12.5}, "expect": {"linear_dim0": 12.5}},
    {"name": "select_body", "set": {"selection0": "first_body"}, "expect": {"selection0": 1}},
    {"name": "apply", "set": {"enum0": 1, "linear_dim0": 3.0}, "apply": true,
     "expect": {"apply_rc": 0, "hook_ran": 1}}
  ]
}
```

- [ ] **Step 2: 写 dry-run 测试**

`tests/test_run_cases_dryrun.py`：

```python
import json, os, sys, tempfile, unittest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import run_cases


class DryRunTests(unittest.TestCase):
    def test_dry_run_writes_manifest_and_cases(self):
        with tempfile.TemporaryDirectory() as d:
            cases = os.path.join(d, "cases.json")
            out = os.path.join(d, "tmp")
            json.dump({"part": None, "cases": [
                {"name": "a", "set": {"enum0": 1}, "expect": {"enum0": 1}},
                {"name": "b", "expect": {"shown": 1}}]},
                open(cases, "w", encoding="utf-8"))
            run_cases.main(cases_path=cases, dry_run=True, tmp_dir=out)
            manifest = json.load(open(os.path.join(out, "manifest.json"), encoding="utf-8"))
            self.assertEqual([c["name"] for c in manifest["cases"]], ["a", "b"])
            self.assertTrue(os.path.exists(os.path.join(out, "cases", "a.ini")))
```

- [ ] **Step 3: 跑测试确认失败**

Run: `python -m unittest tests.test_run_cases_dryrun -v`
Expected: FAIL（`ModuleNotFoundError: run_cases`）。

- [ ] **Step 4: 实现 `run_cases.py`**

要点：
- 顶部只 import `os/sys/json/ctypes/harness_core`；**不要**在模块级 import `NXOpen`，否则 dry-run 在系统 Python 下跑不了。
- `main(cases_path, dry_run, tmp_dir=None)`：
  - `cfg = H.load_cases(cases_path)`；`tmp_dir` 默认 `<HERE>/tmp`。
  - 写 `tmp/manifest.json`（`{"cases": cfg["cases"]}`）。
  - 为每条 case 写 `tmp/cases/<name>.ini`（`H.write_case_file`）。
  - `dry_run` 时直接返回 `{"dry_run": True}`。
  - 非 dry-run：`import NXOpen`；`ensure_part()`；`lib = ctypes.CDLL(DLL)`；配置 `ufusr` 的 `argtypes/restype`。
  - 逐条：设 `os.environ` 的 `AUTODLG_CASE`/`AUTODLG_OUT`/`AUTODLG_TIMEOUT_MS`；`ret = ctypes.c_int(0)`；`lib.ufusr(None, ctypes.byref(ret), 0)`；`result = H.parse_result(out)`；`result["returned"] = 1`；`checks = H.compare(case, result)`；row = `{"name","pass","checks","result"}`。
  - 汇总 `H.write_outputs(rows, tmp/results.json, tmp/summary.txt)`；返回最终 dict。
- `ensure_part()`：
  ```python
  part = session.Parts.Work
  if part is None or not list(part.Bodies):
      path = os.path.join(TMP, "harness_part.prt")
      part = session.Parts.NewDisplay(path, NXOpen.PartUnits.Millimeters)
      ufs = NXOpen.UF.UFSession.GetUFSession()
      ufs.Modl.CreateBlock1(0, [0.0, 0.0, 0.0], ["20", "20", "20"])
      try:
          ufs.Modl.Update()
      except Exception:
          session.UpdateManager.DoUpdate(0)
  ```
- 结果里记录 `returned=1` 表示 `ufusr` 已返回；`report.py` 用 `shown`/`hook_ran` 判断钩子是否真的跑过。

- [ ] **Step 5: 跑 dry-run 测试**

Run: `python -m unittest tests.test_run_cases_dryrun -v`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add run_cases.py cases.json tests/test_run_cases_dryrun.py
git commit -m "feat: NX python orchestrator with dry-run"
```

---

### Task 6: `report.py` —— 进程外汇总（含 NX 被强杀）

**Files:**
- Create: `E:\Code\auto-dialog\report.py`
- Test: `E:\Code\auto-dialog\tests\test_report.py`

**Interfaces:**
- Consumes: `harness_core.*`。
- Produces: `collect(manifest_path: str, results_dir: str) -> list[dict]`；`main(argv) -> dict`
- CLI: `python report.py --manifest tmp/manifest.json --results tmp/results --out-json tmp/results.json --out-txt tmp/summary.txt`

- [ ] **Step 1: 写失败测试**

```python
import json, os, sys, tempfile, unittest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import report


class ReportTests(unittest.TestCase):
    def test_missing_result_marks_timeout_and_preserves_done(self):
        with tempfile.TemporaryDirectory() as d:
            man = os.path.join(d, "manifest.json")
            res = os.path.join(d, "results")
            os.makedirs(res)
            json.dump({"cases": [
                {"name": "done", "expect": {"enum0": 1}},
                {"name": "hung", "expect": {"shown": 1}}]},
                open(man, "w", encoding="utf-8"))
            open(os.path.join(res, "done.ini"), "w", encoding="utf-8").write(
                "shown=1\nhook_ran=1\ngot.enum0=1\nclose_attempted=1\n")
            rows = report.collect(man, res)
            by = {r["name"]: r for r in rows}
            self.assertTrue(by["done"]["pass"])
            self.assertFalse(by["hung"]["pass"])
            self.assertIn("timeout", by["hung"]["error"])

    def test_malformed_result_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            man = os.path.join(d, "manifest.json")
            res = os.path.join(d, "results")
            os.makedirs(res)
            json.dump({"cases": [{"name": "bad", "expect": {"shown": 1}}]},
                      open(man, "w", encoding="utf-8"),
                      )
            open(os.path.join(res, "bad.ini"), "w", encoding="utf-8").write("garbage")
            rows = report.collect(man, res)
            self.assertFalse(rows[0]["pass"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m unittest tests.test_report -v`
Expected: FAIL。

- [ ] **Step 3: 实现 `report.py`**

要点：
- `collect`：读 manifest 的 `cases`；每条用 `H.parse_result(<results>/<name>.ini)`；若文件不存在，`result` 里 `shown=0` 且 `error="timeout"`；`checks = H.compare(case, result)`；`pass = all(c["pass"])`；行里带 `error`。
- `main`：`argparse` 解析四个参数；写 `results.json`（含 `time`/`cases`/`summary`）和 `summary.txt`；返回 dict。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m unittest tests.test_report -v`
Expected: 2 个测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add report.py tests/test_report.py
git commit -m "feat: offline report tolerates killed NX"
```

---

### Task 7: `check_prod.py` + 生产构建隔离验证

**Files:**
- Create: `E:\Code\auto-dialog\check_prod.py`
- Modify: `E:\Code\auto-dialog\build.bat`

**Interfaces:**
- Produces: `check_prod.py <dll>` → 退出码 0 表示无测试符号。

- [ ] **Step 1: 写 `check_prod.py`**

要点：读 DLL 二进制，查找 ASCII/UTF-8 字节串 `autodlg::collect`、`autodlg::finish`、`autodlg::run_hook`、`AUTODLG_HOOK`。任一出现则打印并 `sys.exit(1)`；否则打印 `prod ok` 并 `sys.exit(0)`。

- [ ] **Step 2: 构建生产 DLL**

Run: `build.bat prod`
Expected: 生成 `baseDialog.dll`。

- [ ] **Step 3: 检查**

Run: `python check_prod.py baseDialog.dll`
Expected: `prod ok`，退出码 0。

- [ ] **Step 4: 反证（可选但推荐）**

Run: `python check_prod.py baseDialog_test.dll`
Expected: 退出码 1，并列出找到的测试符号。这证明检查确实有效。

- [ ] **Step 5: 提交**

```bash
git add check_prod.py build.bat
git commit -m "build: prod target and hook leak check"
```

---

### Task 8: `launch.bat` + 端到端验收

**Files:**
- Create: `E:\Code\auto-dialog\launch.bat`
- Create: `E:\Code\auto-dialog\README.md`
- Modify: `E:\Code\auto-dialog\cases.json`（如需）

**Interfaces:**
- Consumes: 全部前序任务。

- [ ] **Step 1: 写 `launch.bat`**

```bat
@echo off
setlocal
cd /d E:\Code\auto-dialog
set "UGII_USER_DIR=E:\Code\auto-dialog"
if not exist application mkdir application
copy /y baseDialog.dlx application\baseDialog.dlx >nul
if not exist tmp mkdir tmp
if not exist tmp\results mkdir tmp\results
del /q tmp\manifest.json tmp\results\*.ini 2>nul

echo If the dialog does not start automatically, use:
echo   Tools -^> Journal -^> Play...  and select E:\Code\auto-dialog\run_cases.py
echo.
"D:\Program Files\Siemens\NX 10.0\UGII\ugraf.exe" -journal "E:\Code\auto-dialog\run_cases.py"
python report.py --manifest tmp\manifest.json --results tmp\results ^
  --out-json tmp\results.json --out-txt tmp\summary.txt
type tmp\summary.txt
```

若 `-journal` 仍不执行（本机实测如此），走手动路径；`report.py` 仍会在 NX 退出后跑。

- [ ] **Step 2: 写 `README.md`**

内容：一句话目标、构建命令、两种启动方式（自动 / 手动）、结果文件位置、三个环境变量（`AUTODLG_NO_CLOSE` / `AUTODLG_KILL_ON_HANG` / `AUTODLG_TIMEOUT_MS`）、重新生成 dlx 后要跑 `autodlg_patch.py`。

- [ ] **Step 3: 端到端正常路径**

1. `build.bat`
2. 启动 NX 10 GUI，新建零件。
3. Tools → Journal → Play…，选 `E:\Code\auto-dialog\run_cases.py`。
4. Expected: 5 条用例逐条弹窗/自动关窗；`tmp\summary.txt` 显示 `用例: 5 通过: 5 失败: 0`；`tmp\results.json` 每行 `pass=true`，`shown=1`、`hook_ran=1`、apply 用例 `apply_rc=0`。

- [ ] **Step 4: 端到端失败容错**

1. 在 NX 里设环境变量 `AUTODLG_NO_CLOSE=1`（或用一个只跑一条的脚本设 `os.environ`），再跑 `run_cases.py`。
2. Expected: 当前用例的结果文件已写；`AUTODLG_KILL_ON_HANG` 默认 1 时 NX 在超时后被结束；随后 `report.py` 把该条标为 FAIL(timeout)，已完成用例仍为 PASS。

- [ ] **Step 5: 提交**

```bash
git add launch.bat README.md
git commit -m "feat: launcher and end-to-end acceptance"
```

---

## Self-Review

- **Spec coverage:** 设计 §6 方案 A → Task 4；§7 流程 → Task 5/8；§8 文件布局 → 全部任务；§9 接口 → Task 2/3/4/5/6；§10 关窗/容错 → Task 4/6/8；§11 构建 → Task 1/7；§12 验收 → Task 8；§13 已确认默认值 → Task 4/8；§15 风险 → Task 1/4/7。
- **Step scan:** 每个测试步骤有具体断言；构建/手动步骤有明确 Expected。
- **Type consistency:** `parse_result` 返回 `got` 字典；`compare` 先读 `got` 再读顶层字段；`report.collect` 复用同一套；Task 5 的 rows 与 Task 2 的 `summarize`/`write_outputs` 对齐。
- **Review Focus:** 5 条均有归属：1→Task 2/5，2→Task 6/8，3/4→Task 4，5→Task 7。
- **Proportion:** 计划给出了签名、格式、关键命令和失败路径；没有把 C++ 钩子的完整实现抄进来，留给执行者按接口和算法实现。
