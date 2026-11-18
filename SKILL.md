---
name: welearn-auto
description: 批量完成 WeLearn（welearn.sflep.com）课程作业。用 Chrome DevTools Protocol 驱动 Edge，从页面 Angular scope 直读答案（blank.key / choice.key），按左侧目录 course_disable 标记判定服务端完成状态。适用于换账号批量刷题、按单元范围执行、每节停留控时。不依赖题库、不依赖 AI、不碰账号密码。
---

# WeLearn 自动做题

## 何时用这个 skill

- 要在 `welearn.sflep.com` 上批量完成多节作业
- 要按单元范围（如只做 Unit 1-4）执行
- 要控制每节停留时长，让行为不像机器
- 换账号后只需改两个参数即可复用

不适用：录音题（口语/朗读）不处理；无标准答案的开放改写题会跳过。

## 前置条件

| 项 | 要求 |
|---|---|
| 浏览器 | Edge（Chrome 亦可） |
| Python | 3.9+，装 `websocket-client` `requests` |
| 登录 | **用户手动登录**，脚本不接触账号密码 |
| 调试端口 | Edge 启动时加 `--remote-debugging-port=9224` |

## 执行步骤

### 1 启动带调试端口的浏览器

```powershell
msedge.exe --remote-debugging-port=9224 --user-data-dir="C:\path\to\profile" --remote-allow-origins=*
```

用户手动登录 `https://welearn.sflep.com`。

### 2 配置

编辑 `assets/wl_config.json`：

```json
{
  "cid": "2415",
  "classid": "783311",
  "catalog_url": "https://welearn.sflep.com/student/studycourse.aspx?cid={cid}&classid={classid}",
  "debug_port": 9224,
  "units": [1, 2, 3, 4],
  "stay_seconds": 60,
  "stay_jitter": 8,
  "skip_record": true,
  "max_sections": 200
}
```

`cid` / `classid` 从登录后的地址栏取。

### 3 扫描

```powershell
cd <skill>/scripts
$env:PYTHONIOENCODING="utf-8"
python wl_run.py --scan
```

输出示例：

```
只做单元: [1, 2, 3, 4]
目录: 共 140 | 已完成 118 | 待做 22
   1. [U1] 03. Lead-in    ITEM-0bea3905-...
```

### 4 执行

```powershell
python wl_run.py              # 跑全部（受 units 限制）
python wl_run.py --plan 20    # 跑 20 节
python wl_run.py --sco ITEM-xxx
```

### 5 验收

看 `wl_run_log.json`：

```powershell
Select-String -Path wl_run_log.json -Pattern 'TODO ✗|not-verified|submit-fail'
```

只有 `DONE ✓` 代表服务端目录已标记完成。

## 技术要点（改动前必读）

| 环节 | 实现 | 为什么不能换写法 |
|---|---|---|
| 完成判定 | `li.className.includes('course_disable')` | 页面上的「正确率」与服务端完成状态不一致 |
| 进入节点 | 点 `a[onclick*="SelectSCO('ITEM-...')"]` | `NextSCO()` 会跳节 |
| 填空答案 | `scope.blank.key[0]` → `blank.value` → `$apply()` | 答案藏在该空位元素的 `span.key` 里，`display:none` 但可读 |
| 选择答案 | `scope.choice.key[0]` → `choice.select(k)` | `li` 没有 `data-solution`，点击 DOM 无效 |
| scope 去重 | 按对象引用 `Set` 去重 | 父子 scope 共享同一对象，不去重会重复收集导致错位 |
| 提交按钮 | `button[ng-click="btn.doAction()"]` | `et-button` / `span` 只是容器，点它们不弹窗不发请求 |
| 确认弹窗 | `.ng-confirm-box` 内 `button.btn-primary`（文案「继续提交」） | 不点这一层，服务端不落库 |
| 多 tab | `I.` `II.` `III.` 各有一个独立 Submit | 一页可能三组题，必须逐个切 |
| 录音题 | `et-recorder` / `[class*="record"]` / `[class*="microphone"]` | 整页跳过 |
| 停留 | 每节计时补足 `stay_seconds` + 随机 `stay_jitter` | 避免等间隔特征 |

## 失败排错

| 现象 | 原因 | 处理 |
|---|---|---|
| `TODO ✗` | 提交没落库 | 看同行的 `submit:` 是否为 `clicked:BUTTON`；是 `clicked:SPAN` 说明点错元素 |
| `confirm: {"hit":[],"done":false}` | 弹窗没出现 | Submit 没点中真实 button，或该节无可提交内容 |
| `submit-fail` | 找不到可见 Submit | 可能已提交（`submit` 被 `ng-hide`） |
| `no-answer` | `blank.key` 全空 | 开放改写题，跳过属预期 |
| `already-done` | 页面无 Submit | 已提交过，0% 的节不处理属预期 |
| 全部 `open-fail` | 目录点击失败 | 检查 `cid` / `classid` 是否正确 |

## 约束

- 不 `taskkill` 浏览器进程，会打断 localStorage 导致掉登录
- 不改 `location.hash` 切节点，SPA 不重渲染
- 不用页面文本判断登录状态，会读到遗留弹窗
- 不碰账号密码，登录由用户手动完成

## 文件

| 文件 | 作用 |
|---|---|
| `scripts/wl_run.py` | 主执行器 |
| `scripts/wl_cdp.py` | 最小 CDP 客户端（超时 60s） |
| `assets/wl_config.json` | 配置 |
| `assets/oneclick.bat` | Windows 一键启动 |
| `docs/ARCHITECTURE.md` | 详细原理与调试记录 |