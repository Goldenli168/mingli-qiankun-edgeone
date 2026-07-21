# 命理乾坤 · 开发踩坑记录 (Pitfalls & Lessons Learned)

> **规则：每次分析/修改代码前必须先阅读本文档，最新踩坑排最前面。**
> **EdgeOne 部署：每次 push 后必须登录控制台「...」→「重新部署」，commit 必须选最新 hash。Git push 只创建部署记录，不触发云函数重建。**

---

## #16 2026-07-22: 大运 5 维内容错位 1 档
- **现象**: 35-44 大运综合解读 0 字；5 维标签下的内容都向前偏移 1：财富标签下显示"此十年大运行至子女宫"（实际是综合内容），事业标签下显示财运内容，依此类推
- **根因**: LLM 输出格式不稳定，常见问题：
  - 开头加 `|||`（空段污染），导致 `parts[0]=""` 
  - 6 段但缺少末尾段（如漏【父母】）
  - 顺序颠倒
- **代码层错误**: 解析只用 `parts[0..5]` 位置索引，LLM 输出错位时整个映射错误
- **修复**（v8.0.1）:
  1. Prompt 要求 LLM 输出**字段名前缀**：`【综合】...|||【财富】...|||...`
  2. 解析层：先按字段名匹配（`【财富】`/`[财富]`/`财富:`），匹配不上再按位置回退
  3. 过滤空段 + 智能去前缀
- **教训**: LLM 结构化输出必须有"双保险"——**Prompt 约束 + 代码容错**。位置索引脆弱，必须按字段名匹配
- **检测**: 部署后必须用 API 实测，检查所有 5 维内容关键词是否对应正确字段

## #15 2026-07-22: 字符串中混用全角引号 → SyntaxError → 全部 404
- **现象**: v7.17 部署后 `/api/health` 和 `/api/analyze` 都返回 404
- **根因**: 改 dayun prompt 时把闭合 `"""`
  写成了 `星曜。"""`（末尾的 `"` 是中文右双引号 U+201D），Python 解析三重引号失败，整个模块 SyntaxError，云函数起不来
- **修复**: 全文统一使用 ASCII `"` `'` `"""`
- **教训**: 写 Python 字符串时，闭合引号必须严格使用 ASCII 引号；中文标点只能放在字符串内容中
- **检测**: 修改 .py 后必须 `python -c "from module import *"` 做语法检查再 push

## #14 2026-07-22: EdgeOne 「New Deployment」≠「重新部署」
- **现象**: 在 EdgeOne 控制台点 New Deployment 选 commit，弹出 Success，但云函数仍是旧代码
- **根因**: EdgeOne 部署有 3 个层级：
  - **Git push** → 仅在部署列表新增一条记录（不构建）
  - **New Deployment** → 创建部署任务但可能只构建不重启云函数
  - **... → 重新部署** → 真正的「重建 + 重启云函数」
- **修复**: 永远用「...」→「重新部署」按钮，并截图确认 commit hash 正确
- **教训**: 每次代码 push 后，部署流程是手动必做步骤；让用户操作前要明确说明点哪个按钮

## #13 2026-07-22: max_tokens 越大不一定越好，复杂 prompt 反而全空
- **现象**: dayun prompt 改为 7 段 `|||` 分隔 + max_tokens=2000，结果 LLM 返回 0 字
- **根因**: DeepSeek 对「结构化分段+长输出」组合的稳定性差；用 max_tokens=800 单段反而 100% 成功（summary 验证返回 587 字）
- **修复**: dayun 降回 800 单词数 + 简化为单段 100 字综合解读，放弃 7 段同时输出的方案
- **教训**: LLM 调优先从最简单的 prompt 试起，再逐步加复杂度；改 max_tokens 前先看 prompt 复杂度

## #12 2026-07-22: 紫微 v7.0 调试 11 次才成功，根因 = 部署机制
- **完整时间线**：
  1. v7.7: 改 prompt 100 字/段（代码层面修复）
  2. v7.8-7.9: 各种参数调整，无效
  3. v7.10-7.13: 改并发/超时/cache_key，无效
  4. v7.14.1: 修 cache_key 哈希 bug → 仍然空
  5. v7.15-7.17: 加诊断日志发现是 prompt 结构问题（max_tokens+7段组合不工作）
  6. v7.17.1: 修闭合引号 SyntaxError
  7. v7.18: 简化为单段 100 字 → 终于返回 LLM 内容 ✓
- **核心教训**：
  - **EdgeOne 部署是手动阻塞环节**，不是自动；不点「重新部署」一切修复都无效
  - **调试流程缺诊断日志**：v7.15 加 `_last_llm_debug` 后立刻定位到 prompt 结构问题
  - **不要小看 LLM 兼容性**：max_tokens 与 prompt 复杂度需匹配，不是越大越好
- **方法论**：每次迭代必须有可观测指标（_last_llm_debug），否则在猜

## #11 2026-07-21: 大运 LLM max_tokens 装不下 7 段内容
- **现象**: 紫微大运展开后，"综合解读"和"财富_llm/事业_llm"等仍是模板文本（带"王亭之云"等引用），不是 LLM 输出
- **根因**: v7.7 prompt 要求 LLM 输出 7 段每段 ≥100 字 + `|||` 分隔 ≈ 800 字，但 `llm_call()` 默认 `max_tokens=800`，DeepSeek 实际可用输出空间更小，LLM 返回被截断或为空
- **修复**: 大运调用单独传 `max_tokens=2000`，其他 LLM 调用仍用 800
- **教训**: 修改 prompt 字数要求时必须同步调整 `max_tokens`；LLM 返回空时要检查 token 限制

## #10 2026-07-21: 八字联合 ImportError — 相对导入失败
- **现象**: 紫微页面显示「八字暂不可用(ImportError)」
- **根因**: ziwei_core.py 用 `import bazi_core`（绝对导入），但 bazi_core.py 顶层有 `from .bazi_data import *`（相对导入），当 bazi_core 被当作顶层模块 import 时，相对导入失败
- **修复**: 改为 `from . import bazi_core`（相对导入，因为 ziwei_core 也在 utils 包内）
- **教训**: 同一 package 内的模块互引用，永远用相对导入 `from . import xxx`

## #9 2026-07-21: WX_GAN 未定义 — 注释整理时误删变量
- **现象**: 八字页面显示「分析失败：WX_GAN is not defined」
- **根因**: 给 JS 加分区注释 `// ---- 全局状态 ----` 时，把 `var WX_GAN = {...}`、`var WX_ZHI = {...}`、`var currentSex`、`var __lastResult` 一起删了
- **修复**: 在注释下方补回这 4 行全局变量
- **教训**: 修改代码块时，确认注释行下方的业务代码没有一起被替换

## #8 2026-07-21: 紫微斗数 504 — LLM 双重调用
- **现象**: 紫微斗数分析超时，EdgeOne 返回 504 Gateway Timeout
- **根因**: `full_ziwei_analysis()` 中有两段 LLM 调用代码：
  - Phase 1 (line 736-747): 串行逐个调流年 LLM（每个 8s，大运剩余几年就几倍）
  - Phase 2 (line 750-790): 并行 ThreadPoolExecutor 调流年+大运+总结
  - Phase 1 串行跑完 40s+ 后 Phase 2 才开始 → 总耗时 68s > EdgeOne 60s → 504
- **修复**: 删除 Phase 1 串行代码，仅保留 Phase 2 并行，且流年 LLM 限当前+未来3年
- **教训**: 模块化重构时注意代码重复，别留两段功能一样的逻辑

## #7 2026-07-20: 紫微斗数 500 — 翻译表缺失
- **现象**: 紫微斗数 API 返回 500 Internal Server Error
- **根因**: 模块化拆分时删除 ziwei_core.py 的 lines 10-75 数据表，但 STAR_EN2CN、PALACE_EN2CN、JU_EN2CN、SIHUA_EN2CN 未加入 ziwei_data.py
- **修复**: 补回 4 张翻译表到 ziwei_data.py 并更新 `__all__`
- **教训**: 拆分数据文件后用 grep 验证所有被删符号是否在新文件中定义

## #6 2026-07-20: 庙旺函数误提走
- **根因**: `_get_miaowang_label()` 和 `_get_miaowang_coeff()` 被一起提取到 ziwei_data.py 中，数据文件不应包含逻辑函数
- **修复**: 从 ziwei_data.py 删除，移回 ziwei_core.py
- **教训**: 数据文件只放纯数据（dict/list/常量），不放函数

## #5 2026-07-20: API 鉴权密钥不匹配 — 默认密钥不一致
- **现象**: 网页弹出「未授权访问」
- **根因**: 后端 `_get_api_key()` fallback 生成 `ml-dev-{hash}`，前端传 `mingli-qiankun-v7`，不匹配
- **修复**: fallback 改为 `mingli-qiankun-v7`（前后端统一）
- **教训**: 鉴权密钥的前后端默认值必须一致

## #4 2026-07-20: _JIE_MONTH 结构错误 — 黄经 vs 月份
- **根因**: 抄写 `_JIE_MONTH` 时把键从黄经度数(315)错写成月份号(1-12)
- **修复**: 修正为 `{315:(2,4), 345:(3,6), ...}` 格式（黄经→(月,日)）
- **教训**: 迁移数据表时必须理解数据结构（键的含义）

## #3 2026-07-20: JIE_LON 结构错误 — 字符串 vs 元组
- **根因**: JIE_LON 写成 `["春分","清明",...]`，实际需要 `[(0,"春分","卯"),...]`
- **修复**: 改为 `(黄经, 名称, 月支)` 三元组格式
- **教训**: 同上

## #2 2026-07-20: `__all__` 缺失 — 下划线前缀符号未导出
- **根因**: 用下划线前缀的变量（如 `_JIE_MONTH`）不会被 `from .bazi_data import *` 导出，除非在 `__all__` 中显式声明
- **修复**: 在 bazi_data.py 和 ziwei_data.py 中添加完整的 `__all__` 列表
- **教训**: Python `from module import *` 不会导出 `_` 前缀名称

## #1 2026-07-20: sed 删除行号偏移 — 孤儿代码和函数丢失
- **根因**: 用 `sed '1351,1371d'` 删除数据表时，部分内容未完全删除，留下了孤立的函数体代码和缺失的函数定义（_liunian_brief 被删）
- **修复**: 手动清理 orphaned code，从 git 恢复 `_liunian_brief` 函数
- **教训**: 大范围 sed 删除后用 `python -c "import module"` 做语法检查

---

## 🛡️ 开发检查清单（每次修改后执行）

- [ ] `python -m pytest tests/ -q` — 34 测试全通过
- [ ] `python -c "from utils.bazi_core import full_analysis"` — 八字导入正常
- [ ] `python -c "from utils.ziwei_core import full_ziwei_analysis"` — 紫微导入正常
- [ ] `python -c "full_analysis(1990,5,15,10,'男')"` — 八字分析正常
- [ ] `python -c "full_ziwei_analysis(1990,5,15,10,'男')"` — 紫微分析正常
- [ ] 所有 HTML 的 `<script>` 中用到的 JS 变量必须已定义
- [ ] 文件间 import 路径：同包用相对导入 `from .xxx import`，跨包用绝对导入
