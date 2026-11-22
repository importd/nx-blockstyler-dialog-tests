# 用例格式、结果与报告

本文定义 `cases.json` 的完整字段、结果文件语义、比对规则，以及 NX 被杀时的
离线报告行为。模板实现以此为准；如果你改脚本，先保持这些语义。

---

## 1. `cases.json` 顶层

```json
{
  "title": "baseDialog regression",
  "dll": "baseDialog_test.dll",
  "part": "D:/Program Files/Siemens/NX 10.0/UGII/drafting_welcome/sample_parts/flange.prt",
  "timeout_ms": 8000,
  "cases": [ ... ]
}
```

| 字段 | 默认 | 说明 |
|---|---|---|
| `title` | `NX dialog harness` | 报告标题 |
| `dll` | `<Dialog>_test.dll` | 被测 DLL；相对路径按工程目录解析 |
| `part` | 内置 sample（NX 10 flange） | 启动时打开/确保有实体的零件；可为 `null` |
| `timeout_ms` | `8000` | 写进每条 case 文件，钩子读到后覆盖看门狗超时；`AUTODLG_TIMEOUT_MS` 只作启动默认值 |
| `cases` | 必填 | 用例数组 |

`part` 为 `null` 时，`run_cases.py` 的 `ensure_part()` 会尝试用当前工作零件；
没有实体就打开自带的 `flange.prt`。最稳的做法是 `launch.bat -part` 直接打开
一个带实体的零件。

---

## 2. 单条用例

```json
{
  "name": "set_enum",
  "title": "枚举切到第 3 项",
  "set": {"enum0": 2},
  "apply": false,
  "expect": {"enum0": 2}
}
```

| 字段 | 说明 |
|---|---|
| `name` | 用例标识；建议 ASCII。**不直接当文件名**（模板用序号），所以中文也可以，但 ASCII 更省事 |
| `title` | 人读的显示名；可中文 |
| `set` | `{blockId: value}`；见 §3 |
| `apply` | `true` = 注入后调用 `apply_cb()` |
| `expect` | 断言；见 §4 |
| `allow_error` | `true` = 允许 `error=` 非空（失败路径用例） |
| `allow_invalid` | `true` = 预检时允许非法的 `set` 值（负向用例，例如越界枚举） |
| `error_contains` | 也可写在 `expect` 里；见 §4 |

模板会分配 `id`（`000`、`001`…）和 `file`（`000.ini`…），写进
`tmp/manifest.json`。这样用例名里的 `/`、重名、中文都不会影响文件系统。

---

## 3. `set` 的值格式

| Block 类型 | 值 | 例 |
|---|---|---|
| Selection | `"first_body"`（取工作零件第一个实体） | `"selection0": "first_body"` |
| Enumeration | 选项索引（整数） | `"enum0": 2` |
| Double | 数值 | `"linear_dim0": 12.5` |
| Integer | 整数 | `"int_color": 55` |
| Logical | `true` / `false` | `"toggle0": true` |
| String | 字符串 | `"text0": "hello"` |

`apply` 是布尔；`run_cases.py` 写成 `apply=1`。
`set` 的键必须是 `AUTODLG_HOOK` 列表里出现的 Block ID；否则钩子不会读它
（hook 只遍历自己的 ID 列表）。

---

## 4. `expect` 的键与默认检查

`expect` 可以包含：

- **顶层结果字段**：`shown`、`hook_ran`、`close_attempted`、`apply_rc`、
  `returned`；
- **块读回值**：直接用 Block ID（`enum0`、`linear_dim0`、`selection0`…），
  等价于 `got.<id>`；
- **`error`**：精确匹配 `error=`；
- **`error_contains`**：`error=` 的子串匹配。

### 4.1 默认检查（防止假 PASS）

`harness_core.compare` 在用户 `expect` 之前先加这些检查：

| 检查 | 默认 | 何时跳过 |
|---|---|---|
| `shown == 1` | 总是 | `expect` 显式给 `shown` |
| `hook_ran == 1` | 总是 | `expect` 显式给 `hook_ran` |
| `close_attempted == 1` | 总是 | `expect` 显式给 `close_attempted` |
| `error == ""` | 总是 | `allow_error: true`，或 `expect` 里有 `error` / `error_contains` |

这意味着：

- 正常用例不用写 `"shown": 1, "hook_ran": 1`，也会被检查；
- 失败路径用例必须显式允许错误：

  ```json
  {"name": "bad_enum", "set": {"enum0": 99},
   "expect": {"error_contains": "block:enum0"}}
  ```

- 不关窗的 meta-test 必须显式期望 `close_attempted: 0`，否则默认检查会判失败。
  注意 `AUTODLG_NO_CLOSE` 是**启动级**环境变量，不能在同一次运行里逐条切换。

### 4.2 数值比较

- 数字（int/float）：绝对差 `< 1e-6` 判等；业务体积断言请另给容差。
- 布尔：`bool(got) == bool(expect)`。
- 其它：字符串比较（`"2" == 2` 会转成字符串比较，结果相等）。

### 4.3 `returned`

`run_cases.py` 在 `ufusr` 正常返回后写 `result["returned"] = 1`。可以用
`"expect": {"returned": 1}` 断言“对话框确实关掉、`Show()` 返回了”。如果 NX 被杀，
这个字段不会存在（由 `report.py` 恢复的结果也没有），所以不要把它设成所有用例
的默认检查。

---

## 5. 结果文件

C++ 钩子每条用例写一个 `key=value` 文件：

```
shown=1
hook_ran=1
close_attempted=1
apply_rc=0
error=
got.enum0=2
got.linear_dim0=12.5
got.selection0=1
```

| 键 | 含义 |
|---|---|
| `shown` | 进入 `collect()`（`dialogShown_cb` 触发） |
| `hook_ran` | 钩子走完并写结果 |
| `close_attempted` | 已尝试关窗（`AUTODLG_NO_CLOSE=1` 时为 0） |
| `apply_rc` | `apply_cb()` 返回值；未调用为空 |
| `error` | 注入/读回/apply 的异常；单行，多个用 `;` |
| `got.<id>` | 读回值 |

**结果必须在关窗之前落盘。** 这是“关不掉也不丢结果”的唯一保证。

---

## 6. 编排器（`run_cases.py`）每条用例做什么

1. 分配 `id = "%03d" % idx`、`file = id + ".ini"`。
2. 写 `tmp\cases\<file>`（含 `id`/`name`/`timeout_ms`/`apply`/`set.*`）。
3. 写 `tmp\manifest.json`（全部用例 + `id`/`file`/`name`/`title`）。
4. 删除旧的 `tmp\results\current.ini`。
5. 写 `tmp\running.json`（当前 `id`/`file`/`name`）。
6. 调用 `ufusr()`（`ctypes.CDLL(dll).ufusr`）。
7. `ufusr` 返回后：解析 `current.ini`，复制到 `tmp\results\<file>`。
8. 删除 `tmp\running.json`。
9. 下一条。

如果第 6 步 NX 被看门狗强杀，第 7/8 步不会发生；`current.ini` 可能已经有结果，
`running.json` 还在。这就是离线报告的恢复依据。

---

## 7. 离线报告（`report.py`）

```bat
python report.py --manifest tmp\manifest.json --results tmp\results ^
    --out-json tmp\results.json --out-txt tmp\summary.txt
```

行为：

1. 读 `manifest.json` 的 `cases`。
2. 对每条用 `file`（旧 manifest 用 `name + ".ini"`）找
   `tmp\results\<file>`。
3. 文件存在 → 解析、比对。
4. 文件缺失 → 读 `tmp\running.json`：
   - 如果 `running.json` 的 `file` 正是这一条，且 `tmp\results\current.ini`
     存在且非空 → 解析 `current.ini`，标记 `recovered_from=current.ini`；
   - 否则 → `shown=0`、`error="timeout"`。
5. 汇总写 `results.json` / `summary.txt`。

这样：

- 正常跑完：每条都有 `<file>.ini`，不触发恢复。
- NX 被杀在 `ufusr` 返回前：当前用例从 `current.ini` 恢复；
  已完成用例不受影响。
- 真挂起且没写出任何结果：`FAIL (timeout)`。

`summary.txt` 里失败行会带 `got/expect` 或 `error`，先看这个再翻原始 `.ini`。

---

## 8. no-close / 强制结束的验收

这是脚手架自身的测试，不是产品用例。

### 8.1 优雅不关窗

```bat
set "AUTODLG_NO_CLOSE=1"
set "AUTODLG_KILL_ON_HANG=0"
set "AUTODLG_TIMEOUT_MS=3000"
launch.bat
```

期望：

- `current.ini` 有 `shown=1`、`hook_ran=1`、`close_attempted=0`；
- NX 停在对话框上，人工关掉；
- `report.py` 用恢复路径或 `<file>.ini` 给出该条结果；若用例显式期望
  `close_attempted: 0`，它应 PASS；否则默认检查判 FAIL（这是预期的）。

### 8.2 强制结束

```bat
set "AUTODLG_NO_CLOSE=1"
set "AUTODLG_KILL_ON_HANG=1"
set "AUTODLG_TIMEOUT_MS=3000"
launch.bat
```

期望：

- 结果先落盘，然后 `TerminateProcess(GetCurrentProcess(), 3)`；
- `report.py` 把当前用例标成未关窗/timeout，已完成用例仍 PASS；
- 不出现 `0xC000000D`（那是 `ExitProcess` 的症状）。

### 8.3 注意

`AUTODLG_NO_CLOSE` / `AUTODLG_KILL_ON_HANG` / `AUTODLG_TIMEOUT_MS` 都必须在
**启动 NX 前**设置。在 NX 的 Python 里改 `os.environ` 对 DLL 不可靠。

---

## 9. 状态重置

模板不自动重开零件。原因：`Parts.CloseAll()` 可能弹保存/丢弃对话框，反而
引入新的模态窗口。

做法：

- 不需要几何的用例（defaults/enum/double/selection）可以同进程连跑；
- 会改几何的 apply 用例：每条单独一次 NX 运行，或跑前手动重开零件；
- 业务断言用“前/后”快照，不要用绝对值；
- 不要依赖 undo；保存/某些操作会清空 undo。

---

## 10. 报告字段速查

`tmp\results.json`：

```json
{
  "time": "2026-11-22 16:30:35",
  "cases": [
    {
      "name": "apply",
      "id": "004",
      "file": "004.ini",
      "pass": true,
      "checks": [
        {"name": "shown", "pass": true, "got": 1, "expect": 1},
        {"name": "apply_rc", "pass": true, "got": 0, "expect": 0}
      ],
      "result": {"shown": 1, "hook_ran": 1, "close_attempted": 1,
                 "apply_rc": 0, "error": "", "got": {"enum0": "1"}}
    }
  ],
  "summary": {"total": 5, "passed": 5, "failed": 0}
}
```

`checks` 里每条都有 `got` / `expect`；失败时先看这里，不要只看 `pass=false`。
