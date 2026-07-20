# 命理乾坤 · 开发踩坑记录 (Pitfalls & Lessons Learned)

> **规则：每次分析/修改代码前必须先阅读本文档，最新踩坑排最前面。**

---

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
