# 坑目录（NX Block Styler 对话框自动化）

按阶段排列。每条都是“现象 → 原因 → 修法”。先扫标题，命中后再看细节。
标了 **NX 10 实测** 的，是在 NX 10 + VS2019 + Windows 11 上实际踩过的；
NX 11/12 请先用 `scripts/inspect_dialog.py` 和一条 smoke 用例复核。

## 目录

- A. 认知与 API（A1–A12）
- B. 构建与加载（B1–B11）
- C. 运行、环境、关窗（C1–C15）
- D. 用例与断言（D1–D10）
- E. 报告与诊断（E1–E6）
- F. NX 11 / 12 的差异

---

## A. 认知与 API

### A1. `The requested property list not found.`

**现象**：`CreateDialog(dlx)` 成功，随后 `GetBlockProperties("any_id")` 抛
`The requested property list not found.`；`dlg.TopBlock` 是 `None`。

**原因**：Block Styler 的块在 `Show()` 进入模态循环后才创建。`CreateDialog`
只是建了一个空壳。

**修法**：不要在 `Show()` 之前探测块。把测试钩子放在 `dialogShown_cb` 的
`try` 块**末尾**（生成的初始化之后）。无界面 `run_journal` 跑不了这类测试，
必须用带 GUI 的 NX 会话。

### A2. `PerformApply()` 在 `dialogShown_cb` 里抛异常

**现象**：想用 `theDialog->PerformApply()` 模拟点 OK，报
“在对话框没有显示时无法执行应用”（或英文等价）。

**原因**：`dialogShown_cb` 触发时，NX 内部还没把对话框置为“已显示”；
`PerformApply` 要求对话框处于可应用状态。

**修法**：直接调用生成的 `apply_cb()`。它和 `ok_cb()` 走同一条业务路径
（`ok_cb` 内部就是 `apply_cb()`）。注意这绕过了 NX 的 OK 流程，见 A9。

### A3. `PerformCancel` / `PerformOK` / `Destroy` 不存在

**现象**：Python 里 `getattr(dlg, "PerformCancel")` 是 `None`；C++ 里编译不过。

**原因**：NX 10 的 `BlockDialog` 只有 `Show`、`PerformApply`、`TopBlock`、
`GetBlockProperties`（以及回调注册）。生成的 `Show()` 还丢弃了
`Show()` 的返回值。

**修法**：关窗走 Win32（见 C3/C4）。不要指望从 `Show()` 返回值判断
“用户点了取消还是 ESC”。

### A4. 枚举 `SetEnum` 报 “Second parameter is invalid”

**现象**：`pl->SetEnum("Value", 2)` 抛异常，或枚举块运行时根本没有选项。

**原因**：dlx 里的枚举需要**两个**属性都有内容：
- `Titles`（`type="utfstrings"`）：界面显示的文字；
- `Titles_1`（`type="enum"`）：运行时 `Value` 的选项表。

只填 `Titles` 时，运行时枚举没有选项，索引 2 越界。

**修法**：跑 `autodlg_patch.py --dlx <Dialog>.dlx` 补空选项（脚本只补**空**的
`Titles` / `Titles_1`，不会覆盖已有选项）。或者在 Block Styler 里正式定义选项。
补完确认 XML 里两处都有 A/B/C（或你的真实选项）。

### A5. 选对象读的键不是 `Value`

**现象**：`pl->GetDouble("Value")` / `GetEnum("Value")` 对 selection 块报
“invalid property name”。

**原因**：Select Object 块的属性列表里没有 `Value`；键叫 `SelectedObjects`，
类型是 `TaggedObjectVector`。个别版本/块也可能用 `Value`。

**修法**：先 `GetPropertyType("SelectedObjects")`，如果是
`PropertyTypeTaggedObjectVector` 就走 selection 分支：
`SetTaggedObjectVector("SelectedObjects", objs)` /
`GetTaggedObjectVector("SelectedObjects")`。探测失败再试 `Value`。

**NX 10 实测**：选面/选体的正确读法就是 `GetTaggedObjectVector("SelectedObjects")`。
不要在没有 `GetPropertyNames()` 的情况下盲猜键名。

### A6. 整数块用 `SetEnum` 写不进去

**现象**：颜色、数量等整数块注入失败，或读回值不对。

**原因**：`PropertyTypeInteger` 和 `PropertyTypeEnum` 是两种类型。
整数块要用 `SetInteger` / `GetInteger`，不是 `SetEnum`。

**修法**：按 `GetPropertyType("Value")` 分派：
`Double → SetDouble`，`Enum → SetEnum`，`Integer → SetInteger`，
`Logical → SetLogical`，`String → SetString`。

### A7. 布尔/字符串块报 `unsupported`

**现象**：结果里 `error=unsupported:<id>`。

**原因**：v1 钩子只处理 Double / Enum / Integer / Selection；Toggle（Logical）
和 String 没分支。

**修法**：加分支（NX 10 签名）：

```cpp
} else if (vt == PropertyList::PropertyTypeInteger) {
    if (has) pl->SetInteger("Value", atoi(v.c_str()));
    os << pl->GetInteger("Value");
} else if (vt == PropertyList::PropertyTypeLogical) {
    if (has) pl->SetLogical("Value", v == "1" || v == "true");
    os << (pl->GetLogical("Value") ? "1" : "0");
} else if (vt == PropertyList::PropertyTypeString) {
    NXString s = pl->GetString("Value");
    os << s.GetLocaleText();   // 只读；Label 写会抛
}
```

`GetString` 返回 `NXString`，不是 `const char*`；用 `GetLocaleText()` 转。
只读 Label 不要放进需要 `set` 的用例。

### A8. `update_cb` 不会因为 `SetXxx` 自动跑

**现象**：枚举/数值注入成功、读回也正确，但依赖它的块（联动下拉、只读回显、
重算）没变；业务 `apply_cb` 拿到的还是旧值。

**原因**：`PropertyList::SetDouble/SetEnum/SetLogical` 只改值，不触发 NX 的
update 回调链。人点界面时 NX 会调 `update_cb`；程序注入不会。

**修法**：
- 在钩子里显式调用生成的 `update_cb(block)`（它是 public 成员），或者
- 把所有依赖块的值都写全，让 `apply_cb` 不依赖联动结果。
- 设计用例时，优先断言 `collect()` 读到的原始值；联动行为单独加用例。

### A9. `apply_cb()` 直调不等于“人点 OK”

**现象**：`apply_rc=0`，但真实点 OK 时 NX 还会做校验/联动/关窗，行为不同。

**原因**：直调绕过 NX 的 Apply/OK 流程：不跑 update 链、不做框架级校验、
不关闭对话框。

**修法**：
- 大多数插件：接受。测的是业务回调本身，配合 A8 显式 update。
- 如果 `apply_cb` 依赖“对话框已显示/用户已提交”：用 **Mode B**——在对话框
  真正显示后，从 UI 线程定时器/后台线程触发 `PerformApply()`（或官方 OK 路径），
  而不是在 `dialogShown_cb` 里直调。Mode B 是版本相关的，先做一条 smoke 证明
  它不重入、不卡死。见 `block-api.md`。

### A10. 回调里的消息框把钩子卡死

**现象**：某条用例永远不结束；没有结果文件；看门狗超时后 NX 被杀。

**原因**：`apply_cb` 的 catch 里 `NXMessageBox.Show(...)` 是模态的，不点掉不返回；
`AUTODLG_HOOK` 的 `finish()`（写结果/起关窗线程）在 `apply_cb()` 之后，永远走不到。

**修法**：测试构建里不要弹模态框。用
`#ifndef AUTODLG_TEST` 包住 `NXMessageBox`，改写到
`Session::ListingWindow` 或结果文件的 `error=`。至少要保证 `apply_cb`
在测试模式下不阻塞。

### A11. `ufusr` 自己弹的错误框看门狗找不到

**现象**：`shown=0`、没有结果、NX 卡在一个错误对话框上。

**原因**：`Show()` 抛异常（常见：dlx 没找到、dlx 损坏）时，生成的 `ufusr`
catch 会 `NXMessageBox.Show` 一个 `#32770`。它不是 Block UI 对话框，没有
`UGS::BlockStyler::DialogCreator` 子窗口；`find_dialog()` 找不到它，看门狗
直接返回，NX 看起来就死了。

**修法**：先修 dlx 路径（`UGII_USER_DIR`、`application\` 副本）。如果要在
测试里兜底，给看门狗加一个“硬截止”：超时后若本进程仍有可见 `#32770`，
`WM_CLOSE` 它，再按 `AUTODLG_KILL_ON_HANG` 结束进程。不要默认开启硬杀，
否则慢机器会被误杀。

### A12. `Show()` 返回值被丢弃

**现象**：想用 `Show()` 的 `Selection::Response` 判断用户点了 OK/Cancel。

**原因**：生成的 `Dialog::Show()` 调了 `theDialog->Show()` 但不返回它的值；
而且没有注册 Cancel/Close handler。

**修法**：不要依赖它。测试只关心 `shown/hook_ran/apply_rc/close_attempted`。
“关窗失败”用看门狗和离线报告判定。

---

## B. 构建与加载

### B1. `uflink.bat` 不是编译器

**现象**：直接 `uflink.bat ... .cpp` 没有生成 DLL，或报找不到 obj。

**原因**：NX 10 没有 `ufcomp`；`uflink.bat` 只做链接。它要一个已经编好的
`.obj`（或默认同名 obj）。

**修法**：`vcvars64` → `cl /c` 编译 → `uflink.bat UFDLL <name>.dll` 链接。
模板 `build.bat` 就是这个顺序。

### B2. NX 路径含空格，`uflink` 断掉

**现象**：`uflink` 报 lib 找不到 / 路径被截断。

**原因**：`uflink.bat` 内部遍历 `UGII_BASE_DIR` 下的 lib，空格会把它拆开。

**修法**：建无空格 junction：

```bat
cmd /c mklink /J C:\Users\feather\nx10 "D:\Program Files\Siemens\NX 10.0"
```

然后 `UGII_BASE_DIR=C:\Users\feather\nx10`，`UGII_USERFCN=%NX%\UGOPEN`，
`UGII_ROOT_DIR=%NX%\UGII`。junction 只需建一次。

### B3. `ufusr` 没导出

**现象**：`ctypes.CDLL(dll).ufusr` 抛 `AttributeError`；`dumpbin /exports`
看不到 `ufusr`。

**原因**：生成的 `ufusr` 被 `#if USER_EXIT_OR_MENU` 包着，没定义该宏就不编译。

**修法**：在 `.cpp` 顶部（或 `*_test.cpp`）定义 `#define USER_EXIT_OR_MENU 1`。
`autodlg_patch.py` 会补。构建后 `dumpbin /exports` 确认
`ufusr` / `ufusr_ask_unload` / `ufusr_cleanup` 都在。

### B4. `LNK1104 无法打开输出 DLL`

**原因**：NX 正在加载这个 DLL（或上一次的 obj/lib 被占用）。

**修法**：关掉所有 NX；确认没有 `ugraf.exe` 进程；再构建。构建和测试不要
共用同一个 NX 进程。

### B5. `C2039` / `C1017`：`CreateDialog` / `CALLBACK` 宏冲突

**原因**：`windows.h` 把 `CreateDialog`、`CALLBACK` 定义成宏；生成的 NX 代码
用 `NXOpen::UI::CreateDialog` 和 `#if CALLBACK`。

**修法**：钩子头 include `windows.h` 后：

```cpp
#undef CreateDialog
#undef CreateDialogA
#undef CreateDialogW
#undef CALLBACK
```

并把 Win32 回调写成 `BOOL __stdcall`，不要写 `CALLBACK`。

### B6. `LNK2019 __imp_PostMessageW`

**原因**：用了 `PostMessageW` 但没链 user32。

**修法**：钩子头加 `#pragma comment(lib, "user32.lib")`。

### B7. 改了 dlx，NX 还是旧界面

**原因**：NX 从 `$UGII_USER_DIR\application\<name>.dlx` 读；你改的是工程根
目录的副本。`build.bat` 会复制，但如果你单独改 dlx 没重新构建，副本是旧的。

**修法**：每次改 dlx 后重新复制（或重跑 `build.bat`）；比较两个文件的时间戳。
`inspect_dialog.py` 读的是你给它的那个 dlx，确认它是新的。

### B8. `UGII_USER_DIR` 没在启动前设置

**原因**：NX 启动时决定搜索路径；启动后设环境变量无效。

**修法**：在 `launch.bat` / 同一个 `cmd` 里 `set` 完再启动 `ugraf.exe`。
不要在 NX 的 Python 里补设。

### B9. VS 版本 / CRT 不匹配

**现象**：链接通过，但 NX 加载时崩溃，或 `apply_cb` 里堆损坏。

**原因**：NX 10 是 release、`/MD` 的旧 CRT。用 `/MT`、debug CRT 或过新的
工具集可能不兼容。

**修法**：VS2019 `vcvars64` + `-MD -DNDEBUG`。模板的 `cl` 参数包含
`-D_AMD64_ -DWIN64 -D_WIN64 -DWIN32 -D_WIN32 -D_MT -D_DLL -MD`。
如果 VS2019 不行，试 NX 自带的向导 `UGOPEN\vs_files\...\NX10_NXOpenCPP.vsz`。

### B10. 生产 DLL 泄漏测试代码

**现象**：`check_prod.py` 报测试标记，或更糟——生产环境真的进入了钩子分支。

**原因**：`AUTODLG_TEST` 没隔离，或 hook 写在了 `#ifdef` 外面。

**修法**：钩子整体在 `#ifdef AUTODLG_TEST`；生产编译 `baseDialog.cpp` 时
不定义它。`check_prod.py` 默认找 `AUTODLG_CASE` / `AUTODLG_OUT` 等字符串；
不要用 `user32.dll` 当唯一标记（生产代码可能合法导入）。

### B11. 中文/空格工程路径

**现象**：结果文件写不出来，或 `getenv` 返回乱码。

**原因**：`std::ofstream(const char*)`、`getenv` 走 ANSI 代码页。

**修法**：工程目录、`AUTODLG_CASE`、`AUTODLG_OUT` 全用 ASCII 路径。
必须用中文路径时，C++ 侧改用 `_wfopen` / 宽字符转换，并确认 NX 的 ANSI
代码页；成本高，能避就避。

---

## C. 运行、环境、关窗

### C1. `os.environ` 改了，DLL 看不到

**现象**：在 NX 的 Python 里逐条 `os.environ["AUTODLG_CASE"] = ...`，
结果还是写同一个文件，或者钩子完全不跑。

**原因**：Python 的 `putenv` 改的是进程环境块；MSVC CRT 的 `getenv` 读的是
启动时初始化的私有副本。NX 10 实测不可见。

**修法**：**在启动 NX 前**设好固定的 `AUTODLG_CASE` / `AUTODLG_OUT`；
编排器每条只改这两个文件的**内容**。不要依赖运行时的 `os.environ`。
同理，`AUTODLG_TIMEOUT_MS` / `AUTODLG_NO_CLOSE` 也要在启动前设。

### C2. NX 的 cwd 不是工程目录

**现象**：`open("cases.json")` / `ctypes.CDLL("x.dll")` 找不到文件。

**原因**：实测 NX 进程的 cwd 可能是 `D:\code\nx-shear-angle`，与 launcher
的目录不同。

**修法**：所有路径从 `__file__` 或 `AUTODLG_HOME` 推绝对路径。`launch.bat`
设 `AUTODLG_HOME`；`run_cases.py` 把 `HERE` 插入 `sys.path` 后再
`import harness_core`（否则 Journal 执行时可能 import 失败）。

### C3. ESC 关不掉对话框

**现象**：发 `WM_KEYDOWN/WM_KEYUP VK_ESCAPE` 后对话框还在。

**原因**：NX 10 / 2512 实测 ESC 被静默忽略（或只关掉焦点，不关对话框）。

**修法**：`PostMessageW(hwnd, WM_CLOSE, 0, 0)`。必须从后台线程发；在
`dialogShown_cb` 里同步发会重入。

### C4. 找不到对话框 / 关错窗口

**现象**：`EnumWindows` 找到 0 个，或关掉了别的 `#32770`。

**原因**：
- Block UI 对话框是**带 owner** 的 `#32770`（挂在 NX 主窗口下）；
  用 `GW_OWNER == 0` 过滤会一个都找不到。
- 确认框、消息框也是 `#32770`；只按类名会误关。

**修法**：枚举本进程（校验 pid）的可见顶层窗口，要求：
`class == "#32770"` **且** 子窗口标题 `UGS::BlockStyler::DialogCreator`
（`EnumChildWindows` 是递归的）。子窗口类名通常是 `Afx:...`，可作辅助。
不要用 `GetForegroundWindow()`（前台可能是别的程序）。

### C5. 看门狗关掉了下一条用例

**现象**：用例 A 超时后，用例 B 的对话框刚出现就被关掉。

**原因**：看门狗在超时后重新扫描“任意对话框”，或者上一轮的线程还活着，
只按 HWND 值匹配（HWND 会被系统复用）。

**修法**：
- 看门狗只绑定**自己那条用例**发现的 HWND；
- 把它改成轮询：每 50ms 检查一次 `is_our_dialog(h)`，对话框一关就提前退出，
  不要在 `Sleep(remaining)` 里睡死；
- 编排器在 `ufusr` 返回后再进入下一条；
- 需要更严格时，给对话框设置一个“用例序号”窗口属性，看门狗校验它。

### C6. `ExitProcess` 让 NX 抛 `0xC000000D`

**现象**：强杀时 NX 报未处理异常，报告/日志不完整。

**原因**：模态 Block UI 对话框期间，从工作线程 `ExitProcess()` 会触发 NX 的
清理路径异常。

**修法**：用 `TerminateProcess(GetCurrentProcess(), 3)`。结果必须在杀之前
落盘。

### C7. `AUTODLG_NO_CLOSE` 的两种语义要分清

- `AUTODLG_NO_CLOSE=1` + `AUTODLG_KILL_ON_HANG=1`：
  `finish()` 仍先写结果，然后看门狗超时强杀 NX。`report.py` 应把该条标成
  timeout/未关窗。这是**强制结束路径**测试。
- `AUTODLG_NO_CLOSE=1` + `AUTODLG_KILL_ON_HANG=0`：
  结果写盘、`close_attempted=0`，NX 停在对话框上等你手动关。这是**优雅
  不关窗**测试，用来证明“先落盘再关窗”。

混淆两者会导致“明明写了结果却被判 timeout”。

### C8. 结果文件被下一条用例覆盖

**现象**：所有用例的结果看起来都一样，或第一条重复出现。

**原因**：固定 `AUTODLG_OUT` + 编排器没删旧文件 + `ufusr` 没写新结果。

**修法**：每条用例前删除 `current.ini`；结果先写盘再关窗；用 `running.json`
标记当前用例；`report.py` 缺失时从 `current.ini` 恢复（见 E2）。

### C9. `ugraf.exe -journal` 不执行

**现象**：命令行传了 journal，NX 起来了但脚本没跑。

**原因**：实测 NX 10 与 2512 都不执行 `-journal`。

**修法**：用 `-part` 打开零件，然后在 NX 里
`Tools → Journal → Play…` 选脚本；或用 MCP `nx_run_python` 在已开的
NX 会话里执行。不要 `-batch`（没有 GUI，Block Styler 不工作）。

### C10. 多开 NX 导致 MCP `AMBIGUOUS_SESSION`

**原因**：桥不知道要发给哪个会话；`nx_run_python` 的 schema 不接受 pid。

**修法**：只留一个 NX 会话（关掉其它的），再跑 MCP。

### C11. Python 3.3 兼容性

NX 10 内置 Python 3.3：

- 不能用 f-string、`subprocess.run`、`pathlib` 的部分 API、`typing` 新语法；
- `dict` 顺序不保证；
- `os.makedirs(..., exist_ok=True)` 可以（3.2+）；
- `open(..., encoding="utf-8")` 可以；
- 结果文件用 `%` 格式化，别用 `.format_map` 之外的新特性。

`run_cases.py` / `harness_core.py` 必须能在 3.3 下 import。系统 Python 只用来
跑 `dry_run`、报告和 `inspect_dialog.py`。

### C12. 模块级 `import NXOpen` 让 dry-run 失败

**原因**：系统 Python 没有 `NXOpen` 模块。

**修法**：`run_cases.py` 顶部只 import 标准库 + `harness_core`；
`import NXOpen` 放在 `main()` 里，`dry_run` 之前不执行。

### C13. `ctypes.CDLL` 加载失败 / 依赖找不到

**原因**：DLL 依赖 NX 的库；在 NX 进程内一般已加载。若不在 NX 内加载，
或 DLL 依赖了未加载的第三方库，会失败。

**修法**：在 NX 的 Python 里加载；确认 `dumpbin /dependents` 的依赖都能在
NX 的搜索路径找到。NX 10 的 Python 3.3 没有 `os.add_dll_directory`。

### C14. 重复 `ufusr` 的资源与状态

**现象**：跑几十条后 NX 变慢/内存涨；或第二条对话框带着第一条的状态。

**原因**：每次 `ufusr` 都 `new` 一个对话框对象并 `Show()`；生成代码在返回前
`delete`，但 NX 内部窗口/块状态可能残留。几何修改也会累积。

**修法**：用例之间保持无状态；改几何的用例单独跑或重开零件；长跑时监控
NX 内存。不要依赖“上一条的对话框对象”还在。

### C15. 超时设置

- `AUTODLG_TIMEOUT_MS` 是看门狗从“发现对话框”起算的等待；默认 8000。
  新版钩子还会读 case 文件里的 `timeout_ms=`，所以 `cases.json` 的
  `timeout_ms` 可以逐次运行生效；环境变量只作启动默认值。
- 弹窗本身可能慢（首次加载 dlx、打开大零件）；模板的 `wait_dialog` 先等
  3200ms 找窗口，找不到就放弃。
- `apply_cb` 里的 `DoUpdate`、布尔、预览重建可能几秒；慢机器要加超时。
- 超时太短会假 FAIL；太长会让真挂起等很久。

---

## D. 用例与断言

### D1. `error=` 非空但用例 PASS

**现象**：结果里有 `error=block:enum0:...`，但报告 PASS。

**原因**：旧版 `compare()` 只看 `expect` 里的键；`error` 不在 `expect` 就没人管。

**修法**：新版默认加三个检查：`shown=1`、`hook_ran=1`、`close_attempted=1`，
并要求 `error` 为空。失败路径用例显式写 `"allow_error": true` 或
`"expect": {"error_contains": "block:enum0"}`。不要用“没报错”当 PASS 证据。

### D2. 用例名 → 文件名

**现象**：用例名含 `/`、`\`、`:`、`*`、`?`、`"`、`<`、`>`、`|`，写 `.ini`
失败；或两个用例同名互相覆盖。

**原因**：编排器用 `name + ".ini"` 做文件名。

**修法**：显示名放 `title`，文件名用序号（`000.ini`、`001.ini`）或
ASCII 安全 slug。新版模板用序号 + manifest 映射，彻底避开非法字符和重名。

### D3. 用例之间状态泄漏

**现象**：单跑 PASS，全量跑 FAIL；或第二条用例的默认值不是默认值。

**原因**：上一条改了几何/配方/颜色/选择；或对话框单例保留了值。

**修法**：
- 每条用例前重开零件，或让业务操作幂等；
- 体积/几何断言取“前/后”快照；
- 不要假设默认值在多次 `Show()` 之间重置；
- 对 apply 用例，考虑每条单独一个干净零件/会话。

### D4. 枚举：索引 vs 标签

**现象**：`set.<enum>=2` 写进去读回是 0，或抛越界。

**原因**：用的是标签而不是索引；或 dlx 的选项顺序不是你以为的 A/B/C。

**修法**：用索引（`GetEnum` 返回索引）；需要标签时用
`SetEnumAsString` / `GetEnumAsString`。先用 `inspect_dialog.py` 打印选项顺序。

### D5. 浮点比较

**现象**：`12.5` 注入读回 `12.499999`，判 FAIL。

**原因**：双精度二进制表示/单位换算。

**修法**：`harness_core._same` 用绝对/相对容差（默认 1e-6）；业务体积断言
单独给容差（例如 `volume_tol`），不要用严格相等。

### D6. 选择块没有实体

**现象**：`set.<selection>=first_body` 后读回 0，`error=no body`。

**原因**：工作零件没有实体；或 `Parts.Work` 为空。

**修法**：启动时 `-part` 打开带实体的零件；编排器 `ensure_part` 检查
`list(part.Bodies)`；选面/选体用例单独标记，不要和不需要几何的用例混跑。

### D7. `apply_cb` 的副作用无法回滚

**现象**：apply 用例跑完，零件被切了；后续用例基于被切的模型。

**原因**：测试就是真的改模型；NX 的 undo 在保存/某些操作后会清空。

**修法**：apply 用例用临时零件，跑完不保存；或在每条 apply 前重开零件。
不要依赖 Ctrl+Z。

### D8. 只断言 `apply_rc=0` 不够

**现象**：回调没崩，但什么都没做，报告 PASS。

**原因**：`apply_cb` 可能空实现、提前返回、或吞了异常。

**修法**：至少加一条业务断言：体积变化、面数、特征数、配方文件内容、
状态标签文字。用“前/后”差值，而不是绝对值（更稳）。

### D9. 用例顺序依赖

**现象**：调换两条用例顺序，结果变了。

**原因**：状态泄漏、选择残留、几何累积、超时/看门狗时序。

**修法**：每条用例独立；不要写“依赖上一条设置”的用例。需要前置状态就
在用例里显式 `set`。

### D10. 多次运行不稳定

**现象**：同一份 cases 两次运行 PASS/FAIL 不同。

**原因**：时序（对话框还没完全显示就注入/关窗）、状态泄漏、看门狗竞争。

**修法**：先看 `shown/hook_ran`；把 `AUTODLG_TIMEOUT_MS` 调大；确认钩子在
`dialogShown_cb` 的 try 末尾；确认看门狗只绑自己的 HWND。连跑两遍是验收项。

---

## E. 报告与诊断

### E1. 报告里 `FAIL (timeout)` 但不一定真挂

**原因**：`report.py` 只看 `<case>.ini` 是否存在。固定路径模式下，NX 被杀在
`ufusr` 返回前，编排器没机会复制 `current.ini`，于是文件缺失。

**修法**：新版模板写 `tmp\running.json`；`report.py` 对缺失文件检查
`current.ini`，能恢复就恢复。恢复后仍按 `expect` 判；`close_attempted=0`
的 no-close 用例本来就应该 FAIL（或显式允许）。

### E2. 结果文件存在但内容为空/半截

**原因**：`write_result` 没 flush，或进程在写的过程中被杀。

**修法**：模板 `write_result` 先 `flush` 再 `close`；结果必须在关窗/强杀之前
写完。解析时把空文件当缺失处理，不要当 PASS。

### E3. 控制台中文乱码 / `UnicodeEncodeError`

**原因**：Windows 控制台默认 GBK；Python 打印 `−`、中文可能失败。

**修法**：`set PYTHONIOENCODING=utf-8`；文件读写显式 `encoding="utf-8"`。
NX 内置 Python 3.3 的控制台编码另说，尽量把诊断写到 Listing Window/文件。

### E4. `check_prod.py` 误报

**原因**：生产 DLL 合法导入 `user32.dll`；旧标记把它当测试代码。

**修法**：用 `AUTODLG_CASE` / `AUTODLG_OUT` / `AUTODLG_TIMEOUT_MS` 字符串
（只存在于钩子）作标记。`autodlg::` 符号可能被内联，不可靠。

### E5. NX Listing Window 才是第一现场

**现象**：结果文件说 `shown=0`，但不知道 `Show()` 为什么失败。

**修法**：看 NX 的 `Listing Window`（`Window → Listing Window`）。生成的
catch / 插件自己的日志通常在那里。消息框可能根本弹不出来（实测
`NXMessageBox.Show` 有环境相关失败），关键诊断要写 Listing Window 或文件。

### E6. 用 `dumpbin` 快速确认 DLL 状态

```bat
dumpbin /exports baseDialog_test.dll | findstr /i "ufusr"
dumpbin /dependents baseDialog_test.dll | findstr /i "dll"
```

`/exports` 看 `ufusr` 是否导出；`/dependents` 看依赖是否都在 NX 里。
构建后先跑这两个，比在 NX 里猜快。

---

## F. NX 11 / 12 的差异

这些事实主要来自 NX 10。换版本时，**先做一条 smoke**，逐项确认：

1. `BlockDialog` 的方法集是否仍是 `Show/PerformApply/TopBlock/GetBlockProperties`
   （用 `dir(dlg)` 打印）。
2. `TopBlock` 在 `Show()` 前是否仍为 `None`；`GetBlockProperties` 是否仍报
   “requested property list not found”。
3. 关窗：Block UI 窗口是否仍是带 owner 的 `#32770` + `DialogCreator` 子窗口；
   `WM_CLOSE` 是否有效；ESC 是否仍无效。
4. 内置 Python 版本（NX 10 = 3.3；11/12 可能不同）；编排器语法按最低版本写。
5. `uflink` / `ufcomp` 的存在与路径；NX 安装路径是否含空格。
6. 枚举 `Titles` / `Titles_1` 的双属性要求是否仍存在。
7. 生成的 `.cpp` 是否仍有 `#if USER_EXIT_OR_MENU` 和 `dialogShown_cb` 的 `try`
   块；补丁脚本的自动探测是否命中。

确认完再改 `build.bat` / `launch.bat` 的路径。不要假设 NX 10 的每条硬事实
在 11/12 自动成立。
