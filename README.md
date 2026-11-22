# NX 10 C++ 对话框自动化测试脚手架

在 NX 10 里无人值守地测 C++ Block Styler 对话框：注入块值、调用 `apply_cb`、
断言、自动关窗、出报告。测试钩子编译进 `baseDialog_test.dll`，生产 DLL 不含钩子。

## 构建

```bat
scripts\build.bat          :: 生成 build\baseDialog_test.dll（含 AUTODLG_TEST 钩子）
scripts\build.bat prod     :: 生成 build\baseDialog.dll（生产，无钩子）
python tools\check_prod.py build\baseDialog.dll   :: 确认生产 DLL 无钩子
```

依赖：NX 10、VS2019、无空格 junction `C:\Users\feather\nx10 -> NX 安装目录`。
DLL 输出到 `build\`；脚本会把 `src\baseDialog.dlx` 复制到 `application\`。

## 启动

```bat
scripts\launch.bat
```

它设置 `UGII_USER_DIR=E:\Code\auto-dialog` 以及固定的
`AUTODLG_CASE=tmp\cases\current.ini` / `AUTODLG_OUT=tmp\results\current.ini`，
然后启动 NX 10。打开一个带实体的零件，再运行编排器：

- **MCP（推荐，全自动）**：
  ```python
  import sys
  sys.path.insert(0, r"E:\Code\auto-dialog\harness")
  import run_cases
  run_cases.main(cases_path=r"E:\Code\auto-dialog\harness\cases.json", dry_run=False)
  ```
- **NX 菜单**：`Tools → Journal → Play...`，选 `harness\run_cases.py`。

> 本机实测 `ugraf.exe -journal <py>` 不会执行 journal，所以 `scripts\launch.bat` 不用它。

## 结果

- `tmp\results.json` — 汇总（`summary` + 每条的 `checks`/`result`）
- `tmp\summary.txt` — 人读的 PASS/FAIL
- `tmp\results\<name>.ini` — 每条用例的原始结果

## 用例

`cases.json` 每项：

```json
{"name": "set_enum", "set": {"enum0": 2}, "expect": {"enum0": 2}}
```

- `set.<blockId>=<value>`：注入值；selection 用 `first_body`。
- `apply: true`：注入后调用 `apply_cb()`。
- `expect`：与结果比对；`shown`/`hook_ran`/`close_attempted`/`apply_rc` 是顶层字段。

## 环境变量

| 变量 | 作用 |
|---|---|
| `AUTODLG_CASE` | 固定 case 文件路径（launch.bat 设置） |
| `AUTODLG_OUT` | 固定结果文件路径（launch.bat 设置） |
| `AUTODLG_TIMEOUT_MS` | 关窗看门狗超时，默认 8000 |
| `AUTODLG_NO_CLOSE` | `1` = 故意不关窗（失败容错测试） |
| `AUTODLG_KILL_ON_HANG` | `1`（默认）= 超时后强制结束 NX |

> NX Python 里运行时改 `os.environ` 对 DLL 的 CRT `getenv` 不可靠，所以编排器
> 复用 launcher 启动时设好的固定 `current.ini` 路径，每条用例只改文件内容。

## 重新生成对话框

Block Styler 重新生成 `.cpp/.dlx` 后：

```bat
python tools\autodlg_patch.py --cpp src\baseDialog.cpp --dlx src\baseDialog.dlx
scripts\build.bat
```

补丁会加 `USER_EXIT_OR_MENU`、测试钩子一行，以及枚举 A/B/C 的 `Titles`/`Titles_1`。
