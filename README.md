# welearn-auto

WeLearn（welearn.sflep.com）课程作业批量完成工具。通过 Chrome DevTools Protocol 驱动真实浏览器，答案从页面 Angular scope 直读，完成状态以服务端左侧目录标记为准。

- 不需要题库
- 不需要 AI / 大模型
- 不接触账号密码
- 每节可控停留时长

## 安装

```powershell
git clone https://github.com/<your-name>/welearn-auto.git
cd welearn-auto
python -m pip install websocket-client requests
```

## 使用

```powershell
# 1 启动带调试端口的 Edge
msedge.exe --remote-debugging-port=9224 --user-data-dir="C:\edge-profile" --remote-allow-origins=*

# 2 手动登录 welearn.sflep.com

# 3 配置
notepad assets\wl_config.json     # 改 cid / classid / units

# 4 扫描待做
cd scripts
$env:PYTHONIOENCODING="utf-8"
python wl_run.py --scan

# 5 执行
python wl_run.py
```

或双击 `assets\oneclick.bat`。

## 配置字段

| 字段 | 说明 |
|---|---|
| `cid` / `classid` | 课程 ID，从登录后地址栏取 |
| `units` | 要做的单元，`[]` 表示全部 |
| `stay_seconds` | 每节最少停留秒数 |
| `stay_jitter` | 随机抖动上限 |
| `skip_record` | 录音题是否跳过 |
| `debug_port` | 浏览器调试端口 |

## 日志

`scripts/wl_run_log.json`，逐行数组。关键字：

| 词 | 含义 |
|---|---|
| `DONE ✓` | 服务端目录已标记完成 |
| `TODO ✗` | 提交未落库 |
| `skip-record` | 录音题跳过 |
| `no-answer` | 无标准答案 |
| `already-done` | 已提交过 |
| `submit-fail` | 找不到提交按钮 |

## 边界

- 录音题（口语/朗读）：跳过，不录不上传
- 开放改写题（`blank.key` 全空）：跳过
- 视频完整播放判定：未实现，仅按时长停留
- 单元累计时长控制：未实现，当前是每节下限

## 许可

MIT