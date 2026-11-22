# 构建、加载与启动

本文是 SKILL.md Step 0/5/6/7 的展开。命令按 Windows + NX 10 + VS2019 写。
NX 11/12 先看文末的差异表，再改路径。

---

## 1. 目录与文件

建议把工程放成：

```
<project>\
  <Dialog>.dlx                 Block Styler 生成的对话框定义
  <Dialog>.hpp / .cpp          Block Styler 生成的 C++
  <Dialog>_test.cpp            4 行：定义 AUTODLG_TEST 后 include <Dialog>.cpp
  autodlg_test.h               测试钩子（从 templates 复制）
  autodlg_patch.py             幂等补丁
  harness_core.py              case/result/compare 纯逻辑
  run_cases.py                 NX 内编排器
  report.py                    NX 外报告
  check_prod.py                生产 DLL 钩子检查
  build.bat / launch.bat       构建/启动
  cases.json                   用例
  application\<Dialog>.dlx     由 build.bat 复制；NX 从这里加载
  tmp\cases\                   每条用例的 .ini（编排器写）
  tmp\results\                 每条用例的结果 .ini（钩子写）
  tmp\manifest.json            本次用例清单
  tmp\running.json             当前正在跑的用例（用于强杀后恢复）
```

不要让 NX 从工程根目录直接找 dlx：它按相对名从
`$UGII_USER_DIR\application` 解析。`build.bat` 负责复制。

---

## 2. 构建链

### 2.1 为什么不用 `ufcomp` / 为什么 `uflink` 不够

NX 10 没有 `ufcomp`；`uflink.bat` 只做链接。可用组合：

```
VS2019 vcvars64 → cl /c（编译 .obj）→ uflink.bat UFDLL（链接 .dll）
```

模板 `build.bat` 的关键片段：

```bat
set "NX=C:\Users\feather\nx10"
set "UGII_BASE_DIR=%NX%"
set "UGII_USERFCN=%NX%\UGOPEN"
set "UGII_ROOT_DIR=%NX%\UGII"
set "PATH=%NX%\UGII;%NX%\UGOPEN;%PATH%"

call "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"

cl -nologo -c -EHsc -DCRTAPI1=_cdecl -DCRTAPI2=_cdecl -GS ^
   -D_AMD64_=1 -DWIN64 -D_WIN64 -DWIN32 -D_WIN32 -W4 ^
   -D_WIN32_IE=0x0500 -DWINVER=0x0500 -Ox -DNDEBUG ^
   -D_MT -D_DLL -MD -I. -I"%UGII_USERFCN%" <Dialog>_test.cpp

call "%UGII_USERFCN%\uflink.bat" UFDLL <Dialog>_test.dll
```

要点：

- `-MD` 是 release DLL CRT；不要 `/MT`，不要 debug CRT。
- `-D_AMD64_ -DWIN64 -D_WIN64 -DWIN32 -D_WIN32` 是 NX 头文件要的。
- `-I"%UGII_USERFCN%"` 让 `<NXOpen/...>` 能被找到。
- NX 路径含空格会让 `uflink` 的 lib 遍历断掉；用无空格 junction。

### 2.2 无空格 junction

```bat
cmd /c mklink /J C:\Users\feather\nx10 "D:\Program Files\Siemens\NX 10.0"
```

只需一次。之后 `UGII_BASE_DIR` 用 `C:\Users\feather\nx10`，不要用
`D:\Program Files\...`。

### 2.3 test / prod 两个 DLL 的隔离

`<Dialog>_test.cpp` 只有：

```cpp
#define _CRT_SECURE_NO_WARNINGS
#define USER_EXIT_OR_MENU 1
#define AUTODLG_TEST 1
#include "<Dialog>.cpp"
```

- **test** 编译 `<Dialog>_test.cpp`：`AUTODLG_TEST` 打开，钩子进 DLL。
- **prod** 编译 `<Dialog>.cpp`：没有 `AUTODLG_TEST`，`AUTODLG_HOOK` 展开为
  `((void)0)`，钩子代码根本不参与编译。

`build.bat` / `build.bat prod` 分别产出两个 DLL。不要把 test 的 obj 链接进
prod。

### 2.4 构建后自检

```bat
dumpbin /exports <Dialog>_test.dll | findstr /i "ufusr"
:: ufusr / ufusr_ask_unload / ufusr_cleanup

python check_prod.py <Dialog>.dll          :: 期望 prod ok
python check_prod.py <Dialog>_test.dll     :: 期望非 0，并列出标记
```

`check_prod.py` 的标记是钩子里的环境变量字符串，不是 `user32.dll`。
`autodlg::` 符号可能被内联，不要单独依赖。

### 2.5 常见构建失败

| 错误 | 原因 | 修法 |
|---|---|---|
| `LNK1104` | NX 正在用 DLL | 关掉 NX，确认没有 `ugraf.exe` |
| `LNK2019 __imp_PostMessageW` | 没链 user32 | 钩子头 `#pragma comment(lib, "user32.lib")` |
| `C2039 "CreateDialog"` / `C1017` | `windows.h` 宏 | `#undef CreateDialog` / `#undef CALLBACK` |
| `uflink` 找不到 lib | 路径含空格 | 用 junction |
| 找不到 `ufusr` 导出 | 没定义 `USER_EXIT_OR_MENU` | 补 define；重编 |
| 链接通过但 NX 崩溃 | CRT/工具集不匹配 | VS2019 + `/MD`；试 NX 自带向导 |

---

## 3. dlx 的加载

NX 按相对文件名解析 dlx，搜索路径包括：

1. 当前目录；
2. `$UGII_USER_DIR\application`（推荐）；
3. `$UGII_CUSTOM_DIRECTORY_FILE` 指向的目录树。

所以：

```bat
set "UGII_USER_DIR=E:\Code\auto-dialog"
copy /y <Dialog>.dlx application\<Dialog>.dlx
```

`build.bat` 会复制。**每次改 dlx 后重新复制**；否则 NX 用旧副本。
`UGII_USER_DIR` 必须在启动 NX 前设好。

---

## 4. 启动 NX

### 4.1 推荐：launch.bat

`launch.bat` 的要点：

```bat
set "PROJECT=E:\Code\auto-dialog"
set "DIALOG=baseDialog"
set "NX_EXE=D:\Program Files\Siemens\NX 10.0\UGII\ugraf.exe"
set "PART=D:\Program Files\Siemens\NX 10.0\UGII\drafting_welcome\sample_parts\flange.prt"

set "UGII_USER_DIR=%PROJECT%"
set "AUTODLG_HOME=%PROJECT%"
set "AUTODLG_CASE=%PROJECT%\tmp\cases\current.ini"
set "AUTODLG_OUT=%PROJECT%\tmp\results\current.ini"
set "AUTODLG_TIMEOUT_MS=8000"

start "" "%NX_EXE%" -part "%PART%"
```

- 不要 `-batch`：Block Styler 需要 GUI 会话。
- `-part` 直接打开一个带实体的零件，省去手动新建。
- `-journal` 在实测机器上不执行，不要依赖。
- 环境变量必须在同一个 `cmd` 里、启动 `ugraf.exe` 之前设好。

### 4.2 手动启动

```bat
set "UGII_USER_DIR=E:\Code\auto-dialog"
set "AUTODLG_CASE=E:\Code\auto-dialog\tmp\cases\current.ini"
set "AUTODLG_OUT=E:\Code\auto-dialog\tmp\results\current.ini"
set "AUTODLG_TIMEOUT_MS=8000"
"D:\Program Files\Siemens\NX 10.0\UGII\ugraf.exe" ^
    -part "...\flange.prt"
```

### 4.3 在 NX 里运行编排器

三种方式：

1. **MCP（推荐）**：在已开的 NX 会话里执行：

   ```python
   import sys
   sys.path.insert(0, r"E:\Code\auto-dialog")
   import run_cases
   run_cases.main(cases_path=r"E:\Code\auto-dialog\cases.json", dry_run=False)
   ```

2. **Journal**：`Tools → Journal → Play…`，选 `run_cases.py`。

3. **单条 smoke**：`File → Execute → NX Open`，选 `<Dialog>_test.dll`。
   每次 `ufusr` 弹一个对话框，钩子读固定的 `AUTODLG_CASE`。

### 4.4 多开 NX

MCP 桥可能报 `AMBIGUOUS_SESSION`；`nx_run_python` 的 schema 不接受 pid。
只留一个 NX 会话。构建时也要确认没有 NX 占用 DLL。

---

## 5. 环境变量速查

| 变量 | 何时设 | 作用 |
|---|---|---|
| `UGII_USER_DIR` | 启动 NX 前 | dlx 搜索根；必须含 `application\<Dialog>.dlx` |
| `AUTODLG_HOME` | 启动 NX 前 | 编排器推绝对路径（可选，但推荐） |
| `AUTODLG_CASE` | 启动 NX 前 | case 文件路径；不设 = 钩子空操作 |
| `AUTODLG_OUT` | 启动 NX 前 | 结果文件路径 |
| `AUTODLG_TIMEOUT_MS` | 启动 NX 前 | 看门狗超时，默认 8000 |
| `AUTODLG_NO_CLOSE` | 启动 NX 前 | `1` = 故意不关窗 |
| `AUTODLG_KILL_ON_HANG` | 启动 NX 前 | `1`（默认）= 超时强杀 NX；`0` = 留给人工 |

**这些变量都不能在 NX 的 Python 里可靠修改**；DLL 的 `getenv` 看不到。
编排器逐条只改 `current.ini` / `current.ini` 的内容。

---

## 6. NX 10 内置 Python 3.3 的限制

- 没有 f-string、`subprocess.run`、`asyncio` 新 API、`typing` 新语法。
- `dict` 顺序不保证；不要依赖。
- `os.makedirs(..., exist_ok=True)` 可用（3.2+）。
- `open(path, encoding="utf-8")` 可用。
- 用 `%` 格式化字符串。
- 不要在模块级 `import NXOpen`；否则系统 Python 的 dry-run 失败。
- 所有路径用绝对路径；`__file__` 缺失时用 `AUTODLG_HOME` 或 cwd 兜底。

系统 Python（3.8+）用于：

- `run_cases.py --dry-run`；
- `report.py`；
- `inspect_dialog.py`；
- 单元测试。

---

## 7. NX 版本差异表

| 项 | NX 10（实测） | NX 11/12（需复核） |
|---|---|---|
| 内置 Python | 3.3 | 3.x，版本可能更高 |
| `ufcomp` | 无 | 可能有；先查 `UGOPEN` |
| `uflink` | 只链接 | 先确认行为 |
| `BlockDialog` 方法 | Show/PerformApply/TopBlock/GetBlockProperties | 用 `dir(dlg)` 打印 |
| 关闭 | WM_CLOSE 有效，ESC 无效 | 重新验证 |
| dlx 枚举双属性 | `Titles` + `Titles_1` | 重新验证 |
| `USER_EXIT_OR_MENU` | 生成代码有 | 看生成代码 |
| `-journal` | 不执行 | 可能仍不执行 |

换版本时先跑一条 smoke：`defaults` 用例 + `shown=1` + 自动关窗。通过后再
批量迁移。

---

## 8. 启动前 preflight（建议每次做）

```bat
:: 1) junction 与工具链
dir C:\Users\feather\nx10\UGOPEN\uflink.bat
dir "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"

:: 2) dlx 副本比源文件新
dir /OD <Dialog>.dlx application\<Dialog>.dlx

:: 3) 环境变量已设（在启动 NX 的同一个 cmd 里）
echo %UGII_USER_DIR%
echo %AUTODLG_CASE%
echo %AUTODLG_OUT%

:: 4) DLL 有 ufusr
dumpbin /exports <Dialog>_test.dll | findstr /i ufusr

:: 5) cases.json 的 Block ID 都存在
python "<skill>\scripts\inspect_dialog.py" --dlx <Dialog>.dlx --cases cases.json

:: 6) 没有 NX 占用 DLL
tasklist | findstr /i ugraf
```
