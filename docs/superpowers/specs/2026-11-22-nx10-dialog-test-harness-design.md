# NX 10 对话框自动化测试脚手架 — 设计

日期：2026-11-22
项目目录：`E:\Code\auto-dialog`（不是 git 仓库）
状态：待批准（含 2 个待你确认的默认值，见 §13）

## 1. 意图与原因

目标是给 **C++ 二次开发的 NX 插件**做自动化测试：加载真实对话框、注入参数、触发 C++ 回调、断言结果、自动关窗。

已有的 `baseDialog` 是 NX 10 Block Styler 生成的最小对话框（`group0` → `selection0` / `enum0` / `linear_dim0`），回调目前是空壳。它先作为脚手架的试验田；脚手架跑通后，每个真实插件对话框只需加一行测试钩子。

为什么不用 Python 直接驱动 `.dlx`：Python `CreateDialog` 会创建一个 **Python 自己的对话框实例**，注册的是 Python 回调，C++ 的 `apply_cb`/`ok_cb` 根本不会执行。要测 C++ 行为，必须让编译后的 DLL 真正跑起来。

## 2. 目标

- 用真实编译的 DLL 跑 `dialogShown_cb` → 注入 → 读回 → 调用 `apply_cb`。
- 用例数据驱动（JSON），结果可机读、可汇总、可 diff。
- 无人值守：对话框自动关闭；关不掉时结果不丢，并且能确定性地判失败。
- 钩子可复用到后续 C++ 对话框：共享头文件 + 每个对话框一行调用，块用 **Block ID** 绑定。
- 生产 DLL 不含测试逻辑（`#ifdef AUTODLG_TEST` 编译期隔离）。

## 3. 非目标

- 不迁移/不测试 D:\code\nx-shear-angle 的剪切角对话框。
- 不做 Win32 控件级驱动（找控件、填文本框、点按钮）。
- 不追求一次性支持所有 Block 类型；先覆盖 selection / enum / double。
- 不做发布签名；DLL 只用于开发测试。

## 4. 反目标（技术成功也算失败）

- 报告 PASS 但 `apply_cb` 实际没被调用（必须记录 `hook_ran` 与 `apply_rc`）。
- 测试代码进入生产 DLL 的正常执行路径（必须编译期消失）。
- 靠固定 sleep 假装成功：必须记录 `dialogShown_cb` 已触发、块已读到。
- 关窗失败时丢掉结果：每条结果必须在尝试关窗前落盘。

## 5. 约束（已在 NX 10 安装目录核实）

- `NXOpen::BlockStyler::BlockDialog` 只有 `Show` / `PerformApply` / `TopBlock`，**没有 PerformCancel / PerformOK / Destroy**。自动关窗只能用 Win32：向本进程的 Block UI `#32770` 对话框发 `WM_CLOSE`（2026-11-22 实测 ESC 无效，`WM_CLOSE` 有效）。
- Block UI 对话框是可见的 `#32770` 顶层窗口，**有 owner**（挂在 NX 主窗口下）；子控件里有 `UGS::BlockStyler::DialogCreator`，可用来精确定位。不要用 `GW_OWNER==0` 过滤。
- 生成的 `baseDialog.cpp` 里 `ufusr` 被 `#if USER_EXIT_OR_MENU` 包着，默认不编译；必须定义该宏。
- Block Styler 会覆盖 `baseDialog.cpp`；钩子放在独立头文件里，补丁脚本幂等补回。
- `enum0` 当前没有任何选项（`Titles` 为空）；要测枚举必须补 2–3 项。
- NX 10 的 Python 是 3.3（`UGII\python\python33.dll`）；编排器必须兼容 3.3。
- 本机实测 `ugraf.exe -journal <py>` 没有执行 journal（2512 与 NX 10 都一样）。启动方式必须有退路。
- NX 10 的 C++ 库是 2014 年的；本机有 VS2019 / VS2026，能否链接成功未知，这是最大的构建风险。
- `BlockDialog::Show()` 的返回值被生成的 `Show()` 丢弃，且没有注册 Cancel/Close handler；无法从返回值判断“用户关的”还是“ESC 关的”。

## 6. 方案

### 6.1 选定方案 A：DLL 内测试钩子 + NX 内 Python 编排

- **C++ 钩子**（`autodlg_test.h`，header-only）：
  - 在 `dialogShown_cb` 末尾调用 `AUTODLG_HOOK(theDialog, "selection0", "enum0", "linear_dim0");`。
  - 若环境变量 `AUTODLG_CASE` 不存在 → 直接返回，生产行为不变（该分支只在 `AUTODLG_TEST` 下编译）。
  - 存在则：读 case 文件 → 按 Block ID 注入 → 读回 → 可选调用 `apply_cb()` → 写结果文件 → 后台线程发 ESC 关窗。
  - 块的读写一律走公开的 `theDialog->GetBlockProperties(blockId)` + `PropertyList`，不碰私有成员，也不改 `.hpp`。
- **Python 编排器**（`run_cases.py`，在 NX GUI 内跑）：
  - 读 `cases.json`；逐条写 case 文件、设置环境变量，调用 DLL 的 `ufusr`；读结果；与期望比对；汇总。
  - 被测 DLL 只加载一次，`ufusr` 每条用例调用一次（每次创建/销毁一个对话框）。
- **离线报告**（`report.py`，在 NX 进程外跑）：
  - 扫描 `tmp/results/` + `tmp/manifest.json`，对缺失结果标记 FAIL(timeout)。
  - 即使 NX 被看门狗强制结束，也能给出完整报告。
- **启动**：`launch.bat` 优先尝试 `ugraf -journal`；若 journal 仍不执行，退化为在已打开的 NX 10 里手动“文件 → 执行 → NX Open”选 `run_cases.py`（一次性点击，之后全自动）。

### 6.2 被否决的方案

- **B：业务逻辑抽成纯函数 + 单元测试**。长期有价值，但今天回调是空的，抽出来没有内容，且不验证回调接线。留作 A 的补充。
- **C：Win32 驱动真实窗口**。Block Styler 是自绘控件，设值和点击都脆弱，读回更不可靠。否决。

## 7. 执行流程

```
launch.bat
  ├─ cd 到 E:\Code\auto-dialog（保证 "baseDialog.dlx" 相对路径可解析）
  ├─ 启动 NX 10 GUI + run_cases.py
  │    └─ run_cases.py
  │         ├─ 确保有工作零件（没有就新建一个带简单实体的 part）
  │         ├─ 写 tmp/manifest.json（本次要跑的全部用例名）
  │         ├─ LoadLibrary(baseDialog_test.dll) → ufusr
  │         └─ for case in cases.json:
  │              ├─ 写 tmp/cases/<name>.ini
  │              ├─ 设 AUTODLG_CASE / AUTODLG_OUT
  │              ├─ ufusr()
  │              │    └─ baseDialog::Show()
  │              │         └─ dialogShown_cb → AUTODLG_HOOK
  │              │              ├─ 注入块（PropertyList）
  │              │              ├─ 读回块
  │              │              ├─ [apply] apply_cb()
  │              │              ├─ 写 tmp/results/<name>.ini（先落盘）
  │              │              └─ 后台 ESC 关窗 → Show() 返回
  │              ├─ 读结果，与 case.expect 比对
  │              └─ 记录 returned=1
  │         └─ tmp/results.json + tmp/summary.txt + 信息窗口
  └─ 等 NX 退出（正常或超时），再跑 report.py
```

## 8. 文件布局

```
E:\Code\auto-dialog\
  baseDialog.dlx / .hpp / .cpp        给定文件（.cpp 只打两处最小补丁）
  autodlg_test.h                      C++ 测试钩子（注入/读回/ESC/写结果）
  autodlg_patch.py                    幂等补丁：define + include + 一行 hook
  build.bat                           构建 baseDialog_test.dll（含 AUTODLG_TEST）
  cases.json                          用例（期望值由 Python 侧断言）
  run_cases.py                        NX 10 Python 3.3 编排器
  report.py                           进程外汇总（处理 NX 被强杀的情况）
  launch.bat                          拉起 NX 10 + run_cases.py；含手动退路说明
  README.md                           一页跑法
  tmp/                                结果与日志（不提交）
    results/                          每条用例一个 .ini
    manifest.json                     本次期望的用例清单
  docs/superpowers/specs/2026-11-22-nx10-dialog-test-harness-design.md
```

## 9. 关键接口

### 补丁范围（`autodlg_patch.py`）

只允许两处，且在 `AUTODLG_TEST` 下编译：

1. 文件头补：
   ```cpp
   #define USER_EXIT_OR_MENU 1
   #ifdef AUTODLG_TEST
   #include "autodlg_test.h"
   #endif
   ```
2. `dialogShown_cb` 的 `try` 块末尾补：
   ```cpp
   #ifdef AUTODLG_TEST
       AUTODLG_HOOK(theDialog, "selection0", "enum0", "linear_dim0");
   #endif
   ```

不改构造函数、不改 `Show()`、不改 `.hpp`、不加 accessor。dlx 路径靠 `launch.bat` / `build.bat` 的 cwd 保证。

### 宏签名

```cpp
#ifdef AUTODLG_TEST
#define AUTODLG_HOOK(dlg, ...) do { \
    const char* _ids[] = {__VA_ARGS__}; \
    autodlg::run_hook(dlg, _ids, sizeof(_ids)/sizeof(_ids[0])); \
} while (0)
#else
#define AUTODLG_HOOK(...) ((void)0)
#endif
```

真实对话框只需把 Block ID 列表换成自己的。

### case 文件（Python → C++，`tmp/cases/<name>.ini`）

```ini
apply=1
set.selection0=first_body
set.enum0=2
set.linear_dim0=12.5
```

`set.<blockId>=<value>` 是通用写法。钩子按 `PropertyList` 的属性类型决定怎么写：

- `SelectedObjects` 是 `TaggedObjectVector` → 选对象；值 `first_body` 取工作零件第一个实体。数字 tag 解析 v1 不做，留到需要时。
- `Value` 是 `Enum` / `Integer` → `SetEnum`。
- `Value` 是 `Double` → `SetDouble`。
- 其他类型 v1 先报 `error=unsupported:<blockId>`。

### 结果文件（C++ → Python，`tmp/results/<name>.ini`）

| 键 | 含义 |
|---|---|
| `shown` | `dialogShown_cb` 已触发 = 1 |
| `hook_ran` | 测试钩子走完 = 1 |
| `got.<blockId>` | 该块的读回值（selection 写数量，enum 写索引，double 写数值） |
| `apply_rc` | `apply_cb()` 返回值（未调用则为空） |
| `error` | 异常文本（无异常则空） |
| `close_attempted` | 已尝试关窗 = 1 |

`closed_by` 不再由 C++ 报告（`Show()` 的返回值被生成代码丢弃，无法区分谁关的）。Python 侧在 `ufusr` 返回后记录 `returned=1`；`report.py` 用它判断。

### 环境变量

| 变量 | 含义 |
|---|---|
| `AUTODLG_CASE` | case 文件路径；不设则不进入测试模式 |
| `AUTODLG_OUT` | 结果文件路径 |
| `AUTODLG_TIMEOUT_MS` | 看门狗超时，默认 8000 |
| `AUTODLG_NO_CLOSE` | `1` = 故意不关窗，用于验证“关不掉时结果不丢” |
| `AUTODLG_KILL_ON_HANG` | `1`（默认）= ESC 失败后强制结束 NX；`0` = 留窗口给人工处理 |

### 用例格式（`cases.json`，按 Block ID）

```json
{
  "part": null,
  "cases": [
    {"name": "defaults",    "expect": {"shown": 1, "selection0": 0, "enum0": 0, "linear_dim0": 0.0}},
    {"name": "set_enum",    "set": {"enum0": 2}, "expect": {"enum0": 2}},
    {"name": "set_dim",     "set": {"linear_dim0": 12.5}, "expect": {"linear_dim0": 12.5}},
    {"name": "select_body", "set": {"selection0": "first_body"}, "expect": {"selection0": 1}},
    {"name": "apply",       "set": {"enum0": 1, "linear_dim0": 3.0}, "apply": true,
                            "expect": {"apply_rc": 0, "hook_ran": 1}}
  ]
}
```

`part: null` 表示编排器自己新建一个带简单实体的零件；给路径则打开该 `.prt`。

## 10. 关窗与失败容错

- `dialogShown_cb` 里起后台线程（`_beginthreadex`），延迟 0.6s：
  - 枚举本进程可见顶层窗口（`GetWindowThreadProcessId` 校验 pid）；
  - 找 class 为 `#32770`、且子控件里有 `UGS::BlockStyler::DialogCreator` 的窗口（它 **有 owner**，不要用 `GW_OWNER==0` 过滤）；
  - `PostMessageW(hwnd, WM_CLOSE, 0, 0)`；
  - 记录 `close_attempted=1`。
- 结果文件在尝试关窗**之前**写完。
- 看门狗：超过 `AUTODLG_TIMEOUT_MS` 对话框仍在，补发一次 `WM_CLOSE`；再等 1000ms 仍在且 `AUTODLG_KILL_ON_HANG=1`，用 `ExitProcess(3)` 结束专用测试 NX 进程。`launch.bat` 之后照常跑 `report.py`，缺失结果记为 FAIL(timeout)。
- `AUTODLG_NO_CLOSE=1` 用于第 12.4 条的确定性验证。
- 注：ESC（`WM_KEYDOWN/UP VK_ESCAPE`）实测关不掉 Block UI 对话框，只作最后兜底，不放在主路径。

## 11. 构建

- `build.bat` 默认构建测试 DLL：定义 `USER_EXIT_OR_MENU` 与 `AUTODLG_TEST`。
- 实测可用组合：VS2019 `vcvars64` + `cl` 编译 + `uflink.bat` 链接。`uflink` 只链接不编译；NX 安装路径含空格会让 `uflink.bat` 的 lib 遍历断掉，因此用无空格 junction（`C:\Users\feather\nx10` → NX 安装目录）作为 `UGII_BASE_DIR`。
- DLL 输出到 `E:\Code\auto-dialog\`；`build.bat` 同时把 `baseDialog.dlx` 复制到 `application\`。`launch.bat` 设置 `UGII_USER_DIR=E:\Code\auto-dialog`，让 NX 从标准搜索路径找到 dlx。
- 生产构建（不定义 `AUTODLG_TEST`）里 `AUTODLG_HOOK` 展开为 `((void)0)`；`build.bat prod` 额外做符号/字符串检查。
- **构建是第一个 spike**：在写正式代码前，先验证一个最小 DLL 能被 NX 10 的 File → Execute 加载并显示对话框。构建不过，方案 A 无法继续。

## 12. 验证标准（脚手架本身算完成）

1. `build.bat` 能产出 `baseDialog_test.dll`。
2. 在 NX 10 GUI 里跑 `run_cases.py`，5 条用例全部 PASS。
3. 结果里 `shown=1`、`hook_ran=1`；apply 用例的 `apply_rc=0`。
4. 用 `AUTODLG_NO_CLOSE=1` 跑一条：结果文件已落盘，`report.py` 把该条标为 FAIL(timeout)；NX 被强杀或可人工关闭，均不丢已完成用例。
5. 生产构建（不定义 `AUTODLG_TEST`）里搜不到 `autodlg::run_hook` 相关符号/字符串。

## 13. 已确认的默认值（2026-11-22 用户确认）

1. **关不掉时强制结束专用 NX 进程：是。**
   `AUTODLG_KILL_ON_HANG=1`，结果先落盘，然后 `ExitProcess(3)`，由 `report.py` 出报告。测试用临时零件、不保存。

2. **`apply_cb()` 在 `dialogShown_cb` 里直接调用：v1 接受。**
   对当前空壳回调没问题。第一次接真实对话框前，若其 `apply_cb` 依赖“对话框已经显示/用户已提交”，再改成显示后触发（`PerformApply` 或 UI 线程定时器）。

## 14. 留给 builder 的决定

- 具体构建工具链（按 spike 结果定）。
- `ufusr` 的调用方式：`ctypes.CDLL(...).ufusr` vs `NXOpen.UF` 包装（优先 ctypes）。
- 结果/case 文件的解析细节（保持 `key=value`，C++ 侧零依赖）。
- 枚举项标题（A/B/C 即可）。
- 关窗目标窗口的精确匹配方式（已实测：`#32770` + 子控件 `UGS::BlockStyler::DialogCreator`；ESC 无效）。
- 选对象时 `first_body` 的取法（`Parts()->Work()->Bodies()`）。

## 15. 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| NX 10 C++ 库与现有 VS 不兼容 | 无法构建，A 阻塞 | 先做构建 spike；必要时找旧 VS/NX 向导 |
| `ugraf -journal` 不执行 | 不能全自动拉起 | 退化为 NX 内一次性手动启动；spike 时查正确开关 |
| `WM_CLOSE` 关窗时序不稳 | 对话卡住 | 后台线程 + 看门狗重试 + 结果先落盘 + 可选强杀 |
| Block Styler 重新生成覆盖补丁 | 钩子丢失 | `autodlg_patch.py` 幂等补回；README 写明 |
| `enum0` 无选项 | 枚举测试无意义 | 先给 dlx 补 2–3 项 |
| `apply_cb` 在 dialogShown 里语义不对 | 对真实插件的测试失真 | 见 §13.2；接真实对话框前改成显示后触发 |
