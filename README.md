# 📄 Paper Review-Iterate System — 论文反复评审修改系统

基于 **Claude API** 的学术论文反复评审与修改工具。从格式、用语规范、AI特征、数学推导、行文逻辑、研究意义六个维度对论文进行专业评审，然后针对性修改，**反复迭代直到论文质量收敛**。

## ✨ 核心功能

- **📐 六维专业评审**：格式、用语规范、无AI特点、数学推导、行文逻辑、研究意义
- **🔄 反复迭代**：评审→修改→评审→修改... 自动循环直到收敛
- **🤖 AI特征检测**：基于 Wikipedia "Signs of AI Writing" 和 [humanizer](https://github.com/blader/humanizer) 项目的 24+ 检测模式
- **📝 人工反馈注入**：每轮评审后可注入人工修改要求
- **🔧 LaTeX实时预览**：自动编译 .tex 文件生成 PDF，HTTP 服务实时预览
- **📊 评分追踪**：每轮评分趋势可视化，差异对比
- **⚡ 并行评审**：六个维度同时评审，速度提升 6×
- **🌐 中英文双语**：评审意见用中文，支持中英文论文

## 📦 安装

```bash
# 1. 克隆项目
git clone https://github.com/zhangmai19/paper-review-iterative.git
cd paper-review-iterative

# 2. 安装依赖
pip install -r requirements.txt

# 3. (可选) 安装 LaTeX 用于 PDF 编译
sudo apt install texlive-latex-base texlive-latex-extra

# 4. 配置 API Key
cp config.yaml.example config.yaml
# 编辑 config.yaml，填入你的 API Key
```

## 🚀 快速开始

```bash
# 基本用法
python main.py papers/sample.tex

# 指定最大轮数和模型
python main.py paper.tex --max-rounds 3 --model claude-opus-4-8

# 只评审特定维度
python main.py paper.tex --dimensions format,logic,ai_free

# 全自动模式（跳过人工反馈）
python main.py paper.tex --no-human --max-rounds 5

# 从文件加载人工反馈
python main.py paper.tex --human-feedback-file feedback.txt

# 查看所有选项
python main.py --help
```

## ⚙️ 配置说明

```yaml
# config.yaml
api_key: "sk-ant-..."          # 或设置环境变量 ANTHROPIC_API_KEY
model: "claude-sonnet-4-6"     # Claude 模型
max_rounds: 5                  # 最大迭代轮数
convergence_threshold: 0.3     # 收敛阈值（平均分低于此值停止）
parallel_reviews: true         # 并行评审

dimensions:                    # 评审维度
  - format       # 格式
  - language     # 用语规范
  - ai_free      # 无AI特点
  - math         # 数学推导
  - logic        # 行文逻辑
  - significance # 研究意义

latex:
  compiler: "pdflatex"
  auto_compile: true
  serve_preview: true
  preview_port: 8765
```

## 📂 项目结构

```
paper-review-iterative/
├── main.py                      # CLI入口
├── config.yaml.example          # 配置模板
├── requirements.txt
├── README.md
├── src/
│   ├── paper_manager.py         # 论文加载/保存/差异对比
│   ├── reviewer.py              # 六维度评审引擎
│   ├── reviser.py               # 修改引擎（支持人工反馈）
│   ├── orchestrator.py          # 迭代循环控制器
│   ├── humanizer_patterns.py    # AI特征检测（24+模式）
│   ├── latex_preview.py         # LaTeX编译与预览
│   ├── utils.py                 # 工具函数
│   └── prompts/                 # 评审与修改提示模板
│       ├── format_review.py
│       ├── language_review.py
│       ├── ai_detection_review.py
│       ├── math_review.py
│       ├── logic_review.py
│       ├── significance_review.py
│       └── revise.py
├── papers/                      # 论文输入目录
│   └── sample.tex               # 示例论文
└── output/                      # 输出目录（自动创建）
```

## 🔄 工作流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│  评审    │───▶│ 人工反馈  │───▶│  修改    │
│ (6维度)  │    │ (可选)    │    │          │
└──────────┘    └──────────┘    └──────────┘
      ▲                               │
      └───────────────◀───────────────┘
               迭代直到收敛
```

每轮迭代产生：
- `Rxx_review.md` — 综合审查报告
- `Rxx_scores.json` — 评分数据
- `Rxx_revised.tex` — 修改后的论文
- `Rxx_changelog.md` — 修改说明
- `Rxx_diff.patch` — 文本差异

## 📋 评审维度详解

| 维度 | 检查内容 |
|------|---------|
| **格式** | 章节结构、图表编号、引用格式、排版细节 |
| **用语规范** | 术语一致性、语法拼写、学术语体、表达精确性 |
| **无AI特点** | AI词汇（delve/tapestry/pivotal等）、意义夸大、模糊引用、破折号过度、同义词轮换、聊天机器人痕迹 |
| **数学推导** | 推导正确性、符号一致性、假设说明、完备性 |
| **行文逻辑** | 论证主线、段落连贯性、论证质量、过渡自然性 |
| **研究意义** | 创新性、研究动机、文献定位、贡献清晰度、影响力 |

## 🛠 AI特征检测参考

本项目参考 [blader/humanizer](https://github.com/blader/humanizer) 项目（21k+ stars），基于 Wikipedia "Signs of AI Writing" 指南，实现了 24+ 种AI写作模式检测：

- **内容模式**：意义夸大、模糊引用、肤浅分词分析、推销性语言、公式化挑战段
- **语言模式**：AI词汇（3级500+词）、系词回避、否定并列、三连排比、同义词轮换、虚假范围
- **风格模式**：破折号过度（硬约束）、Title Case标题
- **交流模式**：聊天机器人痕迹、知识截止声明、讨好性语气
- **填充模糊**：过度限定、模板化结论

## 📄 许可证

MIT License

## 🙏 致谢

- [blader/humanizer](https://github.com/blader/humanizer) — AI写作特征检测
- [Wikipedia: Signs of AI Writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
- Anthropic Claude API
