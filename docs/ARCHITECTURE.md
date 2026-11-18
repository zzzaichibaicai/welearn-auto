# 架构与调试记录

## 整体链路

```
Edge (--remote-debugging-port=9224)
  ↓ CDP over WebSocket
wl_cdp.py  (Mini 客户端, 超时 60s)
  ↓ Runtime.evaluate
主框架 document  → 左侧目录 a[onclick*="SelectSCO"]
        ↓ 点击
iframe#contentFrame  → AngularJS 1.5.11 应用
        ↓ $rootScope 遍历
scope.blank / scope.choice  → 答案与提交
        ↓ button[ng-click="btn.doAction()"]
.ng-confirm-box  → button.btn-primary「继续提交」
        ↓
服务端落库  →  左侧目录 li 加 course_disable
```

## 页面结构

### 主框架（StudyCourse.aspx）

```html
<li class="courseware_list_1_4 course_disable">   <!-- 已完成 -->
  <a onclick="SelectSCO('ITEM-xxxxxxxx-....')">05. Task 1</a>
</li>
<li class="courseware_list_1_4">                  <!-- 未完成 -->
  <a onclick="SelectSCO('ITEM-yyyyyyyy-....')">06. Task 2</a>
</li>
```

左侧目录共 140 个 SCO，每个 `a` 的 `onclick` 里带完整 `ITEM-uuid`。

### iframe（centercourseware.sflep.com）

AngularJS 1.5.11 应用，三类关键自定义元素：

| 元素 | 作用 |
|---|---|
| `et-blank` | 填空空位，内部 `span.key`（`display:none`）存正确答案 |
| `et-choice` | 选择题，选项为 `<ol><li>`，无 `data-solution` |
| `et-recorder` | 录音题，一律跳过 |

### Angular scope

`$rootScope` 通过 `angular.element(document.body).injector().get('$rootScope')` 获取，遍历 `$$childHead` / `$$nextSibling`。

```javascript
// blank 对象
{ key: ["Hamlet"], value: "", isCorrect: false, hasKey: true,
  keyString: '["Hamlet"]', noInput: false }

// choice 对象
{ key: [3], value: [], multiple: false, optionLength: 4,
  isCorrect: false, select: ƒ, isChosen: ƒ }

// item 对象
{ id: "...", isSubmitted: false, realProgressRate: 0, isScored: true,
  lastSubmitTime: "", submit: ƒ, reset: ƒ, handleStatusChange: ƒ }
```

## 提交链路（三层，缺一不可）

```html
<span class="main btn-group">                    <!-- 容器，点了无效 -->
  <et-button action="item.submit()"
             processing-text="Submiting..."
             success-text="Submitted">
    <button ng-click="btn.doAction()">Submit</button>   <!-- ← 只能点这个 -->
  </et-button>
</span>
```

```html
<!-- 点击后 0.5-1.5 秒出现 -->
<div class="ng-confirm-box">
  <span class="ng-confirm-title">确认提交？</span>
  客观题的作答只能提交一次，是否继续提交？
  <input type="checkbox"> 以后不再提示
  <button class="btn btn-primary">继续提交</button>    <!-- ← 必须点这个 -->
  <button class="btn btn-default">取消</button>
</div>
```

## 调试过程中确认过的坑

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 1 | 点 Submit 无任何网络请求 | 点的是 `et-button` 或 `span`，只是容器 | 点 `button[ng-click="btn.doAction()"]` |
| 2 | 点真 button 后弹窗出现但不落库 | 没点确认弹窗 | `.ng-confirm-box button.btn-primary` |
| 3 | `confirm: hit:[]` 一直为空 | 匹配文案写的「是/确定」，实际是「继续提交」 | 文案表加 `继续提交` |
| 4 | 误点视频控件 | `[class*="popup"] button` 命中 `vjs-playback-rate` | 排除 `vjs-` 前缀 |
| 5 | scope 收集到 20 个 blank，DOM 只有 10 个 | 父子 scope 共享同一对象 | `Set` 按对象引用去重 |
| 6 | 页面显示 100% 但目录 TODO | 两者是独立数据，页面分是前端算的 | 判据换成 `course_disable` |
| 7 | `item.isSubmitted` 刷新后变 false | 它是会话内状态，不是服务端状态 | 不用它做判据 |
| 8 | `realProgressRate` 全为 0 | 无区分度 | 不用它做判据 |
| 9 | 一页三组题只交了一组 | `I. II. III.` 各自独立 Submit | 遍历 tab 逐个提交 |
| 10 | 明明全填对却 50%/70% | 全局 key 列表跨 Exercise 混序 | 按元素内嵌 key 取，不用全局列表 |
| 11 | `contenteditable` 写值不生效 | 只设 `textContent`，Angular 收不到 | 需 `InputEvent('input')` + `$apply()` |
| 12 | 无 `contenteditable` 的空位填不进 | 它是 `ng-bind="blank.value"` 单向绑定 | 走 scope 写 `blank.value` |
| 13 | 长会话里 CDP 超时 | 页面 JS 被 `for(1..99999){clearInterval}` 卡死 | `Runtime.terminateExecution` + `Page.reload` |
| 14 | 目录复检一直 TODO | 只看了页面分，未对比服务端 | 每节后重读目录 `course_disable` |

## 判定可靠性排序

| 判据 | 可靠性 | 说明 |
|---|---|---|
| 左侧目录 `course_disable` | **最高** | 服务端渲染 |
| 课程首页 `已完成：N / M` | 高 | 整数，可用于整体核对 |
| 页面 `[class*="score"]` | 中 | 只覆盖判分题型，且是前端算的 |
| `item.isSubmitted` | 低 | 会话状态，刷新即重置 |
| `item.realProgressRate` | 低 | 实测恒为 0 |

## 已验证数据（2026-11-17）

```
课程总计   140 节
已完成     118 节
Unit 1-4   47 / 69
```

单节验证样例：

| 节 | 内容 | 结果 |
|---|---|---|
| `#/1/3-1` | 12 空 + 录音元件 | 录音跳过 |
| `#/1/5-1` | 5 空 | DONE ✓ |
| `#/1/7-3` | 9 空 + 3 选 × 2 tab | DONE ✓ |
| `#/2/7-4` | 12 空 + 3 选 × 2 tab | DONE ✓ |
| `#/8/7-4` | 10 空 + 3 选 | 正确率 100% |