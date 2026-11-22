---
name: nx-blockstyler-dialog-tests
description: Use when / 当需要给 C++ NX Open 插件的 Block UI Styler 对话框（NX 10/11/12，.dlx + 生成的 .cpp/.hpp）做无人值守自动化回归时使用；用户提到对话框回归、自动化测试、免手点、无人值守、注入块、apply_cb、Block Styler、dlx、NX 10 测试时触发，即使没明说“skill”。只适用于 C++ 插件对话框；纯算法测试或 Python 对话框不要用。
---

# NX Block Styler 对话框无人值守测试（C++ 插件）

**原则：测试钩子编进真实 DLL，在 `dialogShown_cb` 里注入 → 读回 → 断言 → 关窗。**
不要用 Python `CreateDialog` 复刻对话框：它注册的是 Python 回调，插件的
`apply_cb` 不会执行。

一条用例：`ufusr` → `Show()` → `dialogShown_cb` → `AUTODLG_HOOK` 注入/读回
→ 写结果 → 后台 `WM_CLOSE`。命令按 Windows + NX 10 + VS2019 写。

---

## 0. 前置检查

```bat
:: 无空格 junction：uflink 的 lib 路径遇空格会断
cmd /c mklink /J C:\Users\feather\nx10 "D:\Program Files\Siemens\NX 10.0"
dir "C:\Users\feather\nx10\UGOPEN\uflink.bat"
dir "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
```

- 构建前关掉 NX（否则 `LNK1104`）。
- 准备一个带实体的零件（NX 10 自带 `flange.prt` 可用）。
- 工程路径全 ASCII（C++ 的 `ofstream`/`getenv` 走 ANSI）。

**验证：** 两条 `dir` 都存在，NX 未运行，零件路径已确定。

## 1. 复制模板并配置

```bat
xcopy /E /I /Y "<skill>\templates" "<插件目录>"
```

改三个地方：

- `build.bat` 顶部：`DIALOG`、`NX`、`VCVARS`
- `launch.bat` 顶部：`DIALOG`、`NX_EXE`、`PART`、`TIMEOUT_MS`
- `cases.json`：`dll`、`part`、`timeout_ms`、`cases`

`DIALOG=baseDialog` 同时决定 `baseDialog.cpp`、`baseDialog.dlx`、
`baseDialog_test.dll`、`baseDialog.dll`。

**验证：** 9 个模板文件在工程根目录，三处配置都指向你的对话框。

## 2. 列 Block ID 并校验用例

```bat
python "<skill>\scripts\inspect_dialog.py" --dlx baseDialog.dlx --hpp baseDialog.hpp
```

输出末尾会给出建议的 hook 行，例如：

```
AUTODLG_HOOK(theDialog, "selection0", "enum0", "linear_dim0")
```

只把**可注入**块放进 hook：Selection、Enumeration、Double、Integer、Logical、
String。Group / Label / Separator / Button / Tab 不要放。顺序固定。

改完 `cases.json` 先校验，比在 NX 里看 `error=` 便宜：

```bat
python "<skill>\scripts\inspect_dialog.py" --dlx baseDialog.dlx --cases cases.json
```

它报未知 Block ID、不可注入的 ID、枚举索引越界、`set`/`expect` 拼写错误。
枚举块在 dlx 的 `Titles` 和 `Titles_1` 里都要有选项，缺 `Titles_1` 时 `SetEnum`
会报 “Second parameter is invalid”。

**验证：** 拿到可注入 ID 列表；`--cases` 零 error。

## 3. 打补丁

```bat
python autodlg_patch.py --cpp baseDialog.cpp --dlx baseDialog.dlx ^
    --ids selection0,enum0,linear_dim0 --make-test-cpp
```

补丁做三件事（都在 `#ifdef AUTODLG_TEST` 下）：

1. 定义 `USER_EXIT_OR_MENU`（否则 `ufusr` 不编译）。
2. 包含 `autodlg_test.h`。
3. 在 `dialogShown_cb` 的 `try` 块**末尾**插入 `AUTODLG_HOOK(...)`。
   块只在 `Show()` 之后才存在，钩子必须在生成的初始化之后跑。

**验证：**

```bat
findstr /n "AUTODLG_HOOK autodlg_test.h USER_EXIT_OR_MENU" baseDialog.cpp
```

恰好三处。Block Styler 重新生成 `.cpp` 后补丁会丢，重跑本步（脚本幂等）。

## 4. 构建并确认 test/prod 隔离

```bat
build.bat            :: baseDialog_test.dll（含钩子）
build.bat prod       :: baseDialog.dll（无钩子）

python check_prod.py baseDialog.dll          :: 期望 prod ok
python check_prod.py baseDialog_test.dll     :: 期望非 0，并列出标记
dumpbin /exports baseDialog_test.dll | findstr /i "ufusr"
```

需要 `/MD`、无空格 junction；`build.bat` 会把 `.dlx` 复制到 `application\`，
改了 dlx 要重新构建复制。

**验证：** prod 报 `prod ok`；test DLL 非 0；导出表有 `ufusr`。

## 5. 启动 NX 并运行

```bat
launch.bat
```

`launch.bat` 会在启动 NX 之前设好 `UGII_USER_DIR`、`AUTODLG_CASE`、
`AUTODLG_OUT`、`AUTODLG_TIMEOUT_MS`。不要用 `-batch` 或 `-journal`
（实测 `-journal` 不执行）。

在 NX 里运行编排器：

```python
import sys
sys.path.insert(0, r"E:\Code\auto-dialog")
import run_cases
run_cases.main(cases_path=r"E:\Code\auto-dialog\cases.json", dry_run=False)
```

或 `Tools → Journal → Play…`，选 `run_cases.py`。只开一个 NX 会话。

**验证：** `tmp\summary.txt` 已生成，用例数与 `cases.json` 一致。

## 6. 判读结果（PASS 判据）

```bat
type tmp\summary.txt
type tmp\results\<case>.ini
```

| 字段 | 含义 | 不正常时先查 |
|---|---|---|
| `shown=1` | `dialogShown_cb` 触发了 | `0` = 对话框没弹：dlx 路径 / `UGII_USER_DIR` / 零件 |
| `hook_ran=1` | 钩子走完 | `0` = 钩子没跑 |
| `close_attempted=1` | 已尝试关窗 | `0` = `AUTODLG_NO_CLOSE=1` |
| `apply_rc=` | `apply_cb()` 返回值 | 空 = 没调用；`1` = 回调内部报错 |
| `error=` | 注入/读回异常 | 非空要查 |
| `got.<id>=` | 读回值 | selection 写数量，enum/integer 写索引，double 写数值 |

**“没报错”不等于 PASS。** 默认要求 `shown=1`、`hook_ran=1`、
`close_attempted=1`、`error` 为空；失败路径用例显式写 `"allow_error": true`
或 `"expect": {"error_contains": "..."}`。

用例顺序：`defaults` → 赋值 → 选对象 → `apply` + 业务断言 → 失败路径；
每层绿了再加下一层。

**验证：** 每条 PASS 的 `.ini` 满足四项默认检查；apply 用例有具体业务数值
（体积/面数/特征数），不只看 `apply_rc`。全部满足后再连跑一遍：结果一致、
无残留对话框。

## 7. 出问题

按报错/现象查 `references/pitfalls.md`（`LNK1104`、`C2039`、`SetEnum` 报错、
对话框不弹/关不掉、结果不对）。构建与启动细节见 `references/build-and-run.md`；
块属性键见 `references/block-api.md`；用例字段见 `references/cases-and-report.md`。

参考实现：`E:\Code\auto-dialog`（NX 10）。
