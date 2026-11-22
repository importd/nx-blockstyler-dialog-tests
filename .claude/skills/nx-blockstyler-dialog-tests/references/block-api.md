# Block / PropertyList API 笔记（NX 10）

本文只记与“注入 + 读回 + 断言”直接相关的事实。签名来自 NX 10 的
`UGOPEN\NXOpen\BlockStyler_PropertyList.hxx`、`BlockStyler_BlockDialog.hxx`、
`BlockStyler_UIBlock.hxx`。

---

## 1. 对话框对象

```cpp
NXOpen::BlockStyler::BlockDialog *theDialog;
```

NX 10 的公开方法（与测试相关的）：

| 方法 | 说明 |
|---|---|
| `Show()` / `Show(DialogMode)` | 模态显示；返回 `NXOpen::Selection::Response` |
| `PerformApply()` | 应用并重启对话框；**要求对话框已显示** |
| `TopBlock` | `CompositeBlock*`；`Show()` 之前是 `NULL` |
| `GetBlockProperties(const char *blockID)` | 返回该块的 `PropertyList*` |

没有 `PerformCancel` / `PerformOK` / `Destroy`。生成的 `Dialog::Show()` 会丢弃
`Show()` 的返回值，也没有注册 Cancel/Close handler，所以无法判断“谁关的”。

块对象（`UIBlock`）也有 `GetProperties()`，但测试钩子用对话框级的
`GetBlockProperties(id)` 更直接；每次访问都重新取，**不要缓存** `PropertyList`。

---

## 2. PropertyList 类型矩阵

`GetPropertyType(const char *name)` 返回 `PropertyList::PropertyType`。NX 10 的
枚举值（相关部分）：

```
PropertyTypeString
PropertyTypeDouble
PropertyTypeLogical
PropertyTypeInteger
PropertyTypeEnum
PropertyTypeStrings
PropertyTypeUIBlock
PropertyTypePoint
PropertyTypeVector
PropertyTypeBits
PropertyTypeTaggedObject
PropertyTypeArray
...
PropertyTypeTaggedObjectVector
PropertyTypeFile
PropertyTypeSelectionFilter
PropertyTypeUndefined
```

### 2.1 常用写入 / 读回

| PropertyType | 属性键 | 写 | 读 | 备注 |
|---|---|---|---|---|
| `Double` | `Value` | `SetDouble(name, double)` | `double GetDouble(name)` | Linear/Angle Dimension、Double |
| `Integer` | `Value` | `SetInteger(name, int)` | `int GetInteger(name)` | 颜色、数量；**不要**用 `SetEnum` |
| `Enum` | `Value` | `SetEnum(name, int)` / `SetEnumAsString(name, text)` | `int GetEnum(name)` / `NXString GetEnumAsString(name)` | 需要 dlx 的 `Titles` + `Titles_1` |
| `Logical` | `Value` | `SetLogical(name, bool)` | `bool GetLogical(name)` | Toggle / Check |
| `String` | `Value` | `SetString(name, text)` | `NXString GetString(name)` | 只读 Label 写会抛 |
| `TaggedObjectVector` | `SelectedObjects` | `SetTaggedObjectVector(name, std::vector<TaggedObject*>)` | `std::vector<TaggedObject*> GetTaggedObjectVector(name)` | Select Object；键也可能是 `Value` |
| `Strings` | 视块而定 | `SetStrings(name, std::vector<NXString>)` | `GetStrings(name)` | 多值字符串 |

`GetString` 返回 `NXString`，不是 `const char*`；用 `GetLocaleText()` 转换。

### 2.2 Selection 的键

Select Object 块的属性列表里**没有** `Value`。正确读法：

```cpp
std::vector<NXOpen::TaggedObject *> objs =
    pl->GetTaggedObjectVector("SelectedObjects");
```

写：

```cpp
std::vector<NXOpen::TaggedObject *> objs;
objs.push_back(body);
pl->SetTaggedObjectVector("SelectedObjects", objs);
```

探测顺序：先 `GetPropertyType("SelectedObjects")`，成功且为
`TaggedObjectVector` 就走 selection；否则再试 `"Value"`。不同块/版本可能
用 `Value`。

取第一个实体：

```cpp
NXOpen::Part *part = NXOpen::Session::GetSession()->Parts()->Work();
NXOpen::BodyCollection *bodies = part->Bodies();
for (NXOpen::BodyCollection::iterator it = bodies->begin(); it != bodies->end(); ++it) {
    body = *it; break;
}
```

如果工作零件没有实体，记录 `error=no body`，照常写结果、照常关窗。

### 2.3 Enum 的双属性

dlx 里一个枚举块通常有：

```xml
<Property id="Titles"   type="utfstrings"><Strings value="A"/>...</Property>
<Property id="Titles_1" type="enum">
  <Option name="A" value="0"/><Option name="B" value="1"/>...
</Property>
```

- `Titles` 是界面文字；
- `Titles_1` 是运行时 `Value` 的选项表。

只填 `Titles` 时，运行时枚举没有选项，`SetEnum` 抛
“Second parameter is invalid”。`autodlg_patch.py --dlx` 只补**空**的
`Titles` / `Titles_1`，不覆盖已有选项。

读回用索引；要标签用 `GetEnumAsString`。断言时优先索引，避免本地化文字变化。

---

## 3. Hook 的位置与形态

`autodlg_patch.py` 在生成的 `dialogShown_cb` 的 `try` 块**末尾**插入：

```cpp
#ifdef AUTODLG_TEST
    AUTODLG_HOOK(theDialog, "selection0", "enum0", "linear_dim0");
#endif
```

`AUTODLG_HOOK` 展开为：

```cpp
do {
    const char* ids[] = { ... };
    autodlg::Context ctx;
    if (autodlg::collect(dlg, ids, n, &ctx)) {
        if (ctx.apply) {
            try { ctx.apply_rc = apply_cb(); }
            catch (...) { ctx.error += "apply:..."; ctx.apply_rc = -1; }
        }
        autodlg::finish(&ctx);
    }
} while (0)
```

要点：

- 必须在生成的初始化之后；否则块还没好。
- 必须在 `try` 内部；否则回调抛异常时钩子不跑。
- `apply_cb()` 是成员函数，宏在 `dialogShown_cb` 里展开，能直接解析。
- 如果对话框没有 apply 回调，或回调名不是 `apply_cb`，需要改宏/补丁，
  否则编译失败。
- `AUTODLG_HOOK` 至少给一个 ID；零长度数组不是标准 C++。

---

## 4. `update_cb` 与联动

`PropertyList::SetDouble/SetEnum/SetLogical` **不会**触发 NX 的 update 回调链。
人点界面时 NX 会调 `update_cb`；程序注入不会。

如果业务逻辑依赖联动：

- 在钩子里注入后显式调用生成的 `update_cb(block)`（public 成员）；
- 或把所有依赖块的值写全；
- 或把联动逻辑从 UI 回调里抽成纯函数，单独测。

不要假设“我设了 A，B 会自动变”。先加一条用例断言 B，确认联动是否发生。

---

## 5. `apply_cb()` 的两种触发模式

### Mode A：在 `dialogShown_cb` 里直调（默认，v1）

```cpp
ctx.apply_rc = apply_cb();
```

- 优点：简单、同步、可重复；不需要等对话框真正显示。
- 缺点：绕过 NX 的 OK 流程（校验、update 链、关闭）；如果 `apply_cb`
  依赖“对话框已显示/用户已提交”，语义不对。
- 适用：大多数业务回调；配合显式 `update_cb`。

### Mode B：对话框显示后再触发（真实 OK 路径）

如果 `apply_cb` 必须在对话框真正显示后跑：

1. 不在 `dialogShown_cb` 里直调；
2. 起一个后台线程，等到对话框窗口出现（或等 `Show()` 进入模态循环）；
3. 通过 UI 线程定时器 / `PerformApply()` 触发 Apply；
4. 结果仍在关窗前落盘。

注意：

- `PerformApply()` 在“未显示”时会抛；必须等对话框真的显示。
- 从非 UI 线程直接调 NX API 可能重入/崩溃；优先用 NX 的 UI 定时器或
  官方回调机制。
- Mode B 是版本相关的，先做一条 smoke 证明不重入、不卡死，再批量用。

---

## 6. 关窗与看门狗算法

### 6.1 找窗口

```cpp
// 只找本进程、可见、class=#32770、且有 DialogCreator 子窗口的顶层窗口
EnumWindows(enum_window_proc, (LPARAM)&found);
```

- 校验 `GetWindowThreadProcessId(h, &pid); pid == GetCurrentProcessId()`。
- `IsWindowVisible(h)`。
- `GetClassNameA(h) == "#32770"`。
- `EnumChildWindows(h, ...)` 递归找标题 `UGS::BlockStyler::DialogCreator`
  （或类名前缀 `Afx:` 作辅助）。
- **不要**用 `GW_OWNER == 0`；Block UI 对话框有 owner。
- **不要**用 `GetForegroundWindow()`；前台可能是别的程序。

### 6.2 关窗

```cpp
PostMessageW(hwnd, WM_CLOSE, 0, 0);
```

- 必须在后台线程发；在 `dialogShown_cb` 里同步 `SendMessage` 会重入。
- ESC（`WM_KEYDOWN/VK_ESCAPE`）实测无效，只作最后兜底。

### 6.3 看门狗

- 每条用例的 `finish()` 起一个线程，绑定**本条用例**发现的 HWND。
- 轮询而不是一次 `Sleep(remaining)`：每 50ms 检查 `is_our_dialog(h)`，
  对话框提前关闭就退出。这样不会在下一用例的对话框出现后误关。
- 超时后补发 `WM_CLOSE`，再等约 1s。
- 仍在且 `AUTODLG_KILL_ON_HANG=1`：
  `TerminateProcess(GetCurrentProcess(), 3)`。
- 不要用 `ExitProcess()`：模态对话框期间从工作线程调会触发
  `0xC000000D`。

### 6.4 结果先落盘

`finish()` 的顺序必须是：

1. 写结果文件（`shown/hook_ran/apply_rc/error/got.*/close_attempted`）；
2. `flush` + `close`；
3. 再起关窗/看门狗线程。

这样即使看门狗强杀 NX，结果也已经在了。

---

## 7. 结果文件格式

`key=value`，一行一个，C++ 侧零依赖：

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

- `shown=1` 由 `collect()` 成功进入时写；`hook_ran=1` 由 `write_result` 写。
- `apply_rc` 未调用时为空。
- `got.<id>`：selection 写对象数量，enum/integer 写索引，double 写数值，
  logical 写 `0/1`，string 写文本。
- `error` 是单行（换行替换成空格），多个错误用 `;` 连接。

Python 侧 `harness_core.parse_result` 把 `got.*` 收进 `got` 字典，其余是
顶层字段。

---

## 8. 快速探测脚本（Python，不加载 DLL）

```python
import NXOpen
ui = NXOpen.UI.GetUI()
dlg = ui.CreateDialog(r"...\X.dlx")
print([m for m in dir(dlg) if not m.startswith("_")])
print("TopBlock:", dlg.TopBlock)          # Show() 前应为 None
try:
    print(dlg.GetBlockProperties("enum0"))  # Show() 前应报错
except Exception as e:
    print("expected error:", e)
```

这个脚本**只能**确认“Show 前块不可用”，不能替代 GUI 里的注入测试。
不要在无界面 `run_journal` 里指望它能读到块。
