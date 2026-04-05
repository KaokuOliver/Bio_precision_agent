# 🔬 Bio-Precision Agent (BPA) v4

**面向生命科学研究的循证多智能体实验方案生成平台**

> 让每一个实验参数都有据可查

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-red.svg)
![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-green.svg)
![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)

---

## 简介

在生物学、植物学等实验科学领域，通用型大语言模型（LLM）在回答"用多少浓度的激素""引物退火温度是多少"这类具体问题时，经常给出听起来合理、实则无法验证的参数——这种现象通常被称为**幻觉（Hallucination）**。

**Bio-Precision Agent（BPA）** 的目标是解决这一问题。它不是一个简单的问答工具，而是一套三阶段的多智能体协作系统：先理解你的实验意图，再联网检索 PubMed 等权威文献数据库，最后将查到的证据与你的需求交叉比对，生成一份有明确参数来源、可操作的实验方案。

凡是未能在文献中找到支撑依据的参数，均会被明确标注 **`[UNVERIFIED]`**，而不是悄悄填写一个"看起来合理"的数字。

---

## 核心工作流程

BPA 将一次完整的分析拆分为三个阶段，并在人机协作节点（HITL）让你参与其中：

```
你的实验描述
      │
      ▼
┌─────────────────────────┐
│  Phase 1 · 解析架构师   │  提取物种、目标、关键参数（Pydantic 强校验）
└────────────┬────────────┘
             │ ⏸ 暂停 — 你来确认／修改解析结果
             ▼
┌─────────────────────────┐
│  Phase 2 · 文献研究员   │  PubMed + DuckDuckGo + 语义分块 PDF
│                         │  → 生成结构化 EvidenceChunk 列表
│                         │  → 若证据不足，自动触发补充检索
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Phase 3 · 校验裁判员   │  对照原始证据核对参数
│                         │  打 [UNVERIFIED] 标记，清理 Mermaid 语法
│                         │  生成最终 Markdown 报告
└─────────────────────────┘
```

### Phase 1 · 解析架构师（Architect）

接收你的自然语言描述，使用 DeepSeek JSON 结构化输出提取以下信息：

- **目标物种**（Species）
- **实验类型**（Experiment_Type）：wet / dry / mixed
- **核心目标**（Key_Goal）
- **关键参数列表**（Params）

**特点**：输出经过 `Pydantic` 运行时校验和清洗。如果 LLM 返回的 JSON 字段缺失或类型错误，会被自动修复或抛出明确异常。同时增加了 Prompt Injection 防御：若检测到异常输入，会返回安全占位符而不是被操控。

### Phase 2 · 文献研究员（Researcher）

根据第一步确认的参数，同步发起多路检索：

1. **NCBI PubMed**：通过 BioPython 的 `Entrez` 接口直连官方 API，按 PMID 拆分记录，生成结构化 `EvidenceChunk`。
2. **DuckDuckGo 补充检索**：对 PubMed 覆盖不足的长尾需求进行搜索，对每个结果做深度网页抓取（去导航、去广告、去脚本），并通过 URL 去重避免上下文被重复内容占满。
3. **PDF 语义锚定**：若上传了 PDF，系统会按段落打分（关键词命中 Methods/Protocol 相关内容者得分高），优先把高价值段落插入证据池，而不是简单截取前 N 字符。

**自我修正循环**：如果 Researcher 在首轮综合分析后认为某些参数证据不足，它会输出 `FOLLOW_UP_QUERIES`，系统自动执行补充检索并重新合成。

### Phase 3 · 校验裁判员（Validator）

这是幻觉控制的最后一道闸门。Validator **不仅看到 Researcher 的总结，还直接看到所有原始 `EvidenceChunk`**，可以逐条核对：

- 有明确文献依据的参数：直接援引数值与来源
- 无法找到文献支撑的参数：强制标注 **`[UNVERIFIED]`**
- 输出包含：Mermaid 流程图、实验步骤、BOM 表格、证据溯源链接

**输出校验层**：Validator 生成报告后，系统会自动检查：
- 是否包含必需的 4 个章节标题（缺失则自动补占位符）
- Mermaid 代码块是否包含会破坏语法的中文标点（自动替换为英文符号）

---

## 功能一览

| 功能 | 说明 |
|------|------|
| **人机协同确认（HITL）** | Phase 1 结束后暂停，展示可编辑的参数表单 |
| **PubMed 直连检索** | BioPython `Entrez` 官方 API，按 PMID 结构化拆分 |
| **深度网页抓取** | BeautifulSoup + 重试机制 + 去重 |
| **PDF 语义锚定** | 语义分块，优先保留方法学段落 |
| **自我修正检索** | Researcher 可请求补充查询，系统自动再检索 |
| **`[UNVERIFIED]` 标记机制** | 无依据参数明确标注，不猜测 |
| **RAG 双源验证** | Validator 同时访问 Researcher 总结 + 原始证据片段 |
| **左报告右证据的双栏布局** | 左侧方案，右侧对照原始文献 |
| **结构化原始证据展示** | 右侧可展开查看每个 EvidenceChunk 的 source / query / content |
| **Markdown 报告下载** | 一键导出 `.md` |
| **PDF 报告导出** | 代码块经格式处理后保留 |
| **试剂清单 CSV 导出** | 正则识别 Markdown 表格 |
| **Jupyter Notebook 导出** | dry/mixed 类型自动生成 `.ipynb` |
| **历史记录管理** | 按用户独立存储，支持导出 JSON、一键清空 |
| **访问控制** | 登录认证 + 本地/远程权限区分 |
| **输出安全校验** | Mermaid 语法清洗、章节缺失自动补齐 |

---

## 项目结构

```
Bio_precision_agent/
│
├── app.py                # 主应用入口：UI 布局、工作流调度、历史与下载管理
├── auth.py               # 登录认证模块：SHA-256 密码校验、输入清洗
├── main.py               # CLI 调试入口
├── requirements.txt      # Python 依赖列表
├── .env                  # API Key 配置文件（首次使用需填入）
├── 启动BPA.bat           # Windows 一键启动脚本
│
├── core/
│   ├── agents.py         # 三个智能体主逻辑 + Pydantic 校验 + 输出清洗
│   ├── prompts.py        # 各智能体系统提示词（RAG / Evidence Synthesizer）
│   └── researcher.py     # 文献检索模块：PubMed API + DDG + 深度抓取 + 语义分块
│
└── history/              # 用户历史记录（JSON 文件，按用户名区分）
```

---

## 快速开始

### 前置要求

- Python **3.10** 或 **3.11**（推荐 3.11）
- 安装时请务必勾选 **"Add Python to PATH"**
- DeepSeek API Key（免费注册获取）

### 第一步：克隆仓库

```bash
git clone https://github.com/yourusername/Bio_precision_agent.git
cd Bio_precision_agent
```

### 第二步：安装依赖

在项目文件夹内打开 PowerShell 或终端，依次运行：

```powershell
# 1. 创建独立的 Python 虚拟环境
python -m venv venv

# 2. 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
```

### 第三步：配置 API Key

编辑项目根目录的 `.env` 文件：

```
DEEPSEEK_API_KEY=your_api_key_here
```

获取 DeepSeek API Key：
1. 访问 [platform.deepseek.com](https://platform.deepseek.com)
2. 注册/登录账号
3. 进入 "API Keys" 页面创建新密钥
4. 将密钥复制到 `.env` 文件中

> **安全提示**：`.env` 文件包含你的 API Key，请勿上传至 GitHub 或分享给他人。项目已配置 `.gitignore` 忽略此文件。

### 第四步：启动应用

**Windows 用户**：双击 `启动BPA.bat`

**其他系统**：
```bash
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

稍等片刻，浏览器会自动打开 `http://localhost:8501`。

**默认登录凭据**：
- 用户名：`admin`
- 密码：`admin`

> ⚠️ 部署到生产环境前，请务必修改 `auth.py` 中的默认密码！

---

## 访问控制说明

BPA 内置了简单的多用户认证机制：

- 用户通过登录页面输入用户名和密码才能进入主界面
- **仅本地访问（localhost / 127.0.0.1）** 的用户可以看到 API Key 配置入口和"删除全部历史"按钮
- 远程 IP 访问时，API Key 只读取 `.env` 文件中的已保存值，配置入口不显示

### 添加/修改用户

打开 `auth.py`，在 `_USERS` 字典中按照现有格式添加或修改：

```python
"新用户名": hashlib.sha256("新密码".encode("utf-8")).hexdigest(),
```

---

## 使用示例

1. **登录系统**：使用默认账号 `admin` / `admin` 登录
2. **配置 API Key**（本地访问时）：在左侧边栏输入 DeepSeek API Key 并保存
3. **选择模型**：`deepseek-chat` 速度更快，`deepseek-reasoner` 推理更深入但响应时间略长
4. **输入实验描述**：例如：
   > "拟南芥光响应途径都有哪些基因？请列出主要成员并说明其功能与调控关系"
5. **上传 PDF**（可选）：上传相关文献，AI 将优先参考其中的方法和参数
6. **开始分析**：点击"开始分析我的实验需求"按钮
7. **确认参数**：检查 AI 解析的信息是否准确，可直接修改
8. **生成方案**：确认无误后，系统将自动检索文献并生成完整实验方案
9. **查看报告**：左侧为最终方案，右侧为原始文献参考来源
10. **导出结果**：支持 Markdown、PDF、CSV 试剂清单、Jupyter Notebook 等多种格式

---

## 模型与依赖

| 依赖 | 用途 |
|------|------|
| `streamlit >= 1.30` | Web 界面框架 |
| `openai >= 1.0` | 调用 DeepSeek API |
| `biopython >= 1.83` | NCBI PubMed API |
| `duckduckgo-search >= 6.0` | 补充网络搜索 |
| `beautifulsoup4 >= 4.12` | 网页深度内容抓取 |
| `requests >= 2.31` | HTTP 请求 |
| `PyPDF2 >= 3.0` | 读取上传的 PDF |
| `markdown-pdf >= 1.3` | PDF 导出 |
| `nbformat >= 5.9` | 生成 `.ipynb` |
| `python-dotenv >= 1.0` | `.env` 文件读写 |
| `pydantic >= 2.0` | 结构化数据校验 |

---

## 常见问题

**Q：方案中出现了很多 `[UNVERIFIED]` 标记，是出错了吗？**

不是。这是 BPA 设计的核心机制。`[UNVERIFIED]` 表示该参数在本次检索的文献中没有找到明确依据。你可以将其视为一个提示：这些参数需要你自己查阅文献或向专业人士确认。

**Q：PubMed 有时检索不到内容怎么办？**

PubMed 检索受网络连接影响。若超时，系统会跳过 PubMed 步骤，仍通过 DuckDuckGo 提供补充证据。如果 Researcher 认为证据仍不足，还会自动触发补充检索。

**Q：上传 PDF 有什么限制？**

目前使用 PyPDF2 读取，仅支持文字型 PDF（不支持纯扫描图片）。PDF 内容会经过语义分块处理，优先保留与方法学相关的段落。

**Q：如何修改默认密码？**

打开 `auth.py`，修改 `_USERS` 字典中的密码哈希：

```python
import hashlib
# 生成新密码的哈希
new_hash = hashlib.sha256("你的新密码".encode("utf-8")).hexdigest()
```

**Q：支持其他 LLM 吗？**

目前代码针对 DeepSeek API 进行了优化，但你可以通过修改 `core/agents.py` 中的 `BioPrecisionAgents` 类来适配其他兼容 OpenAI API 格式的服务（如 OpenAI、Claude 等）。

---

## 技术架构亮点

| 特性 | 说明 |
|------|------|
| **EvidenceChunk 结构化** | 保留 source_type / source_id / query 的溯源信息 |
| **RAG 双源验证** | Validator 同时看到 Researcher 总结 + 原始文献片段 |
| **PDF 语义分块** | 按段落打分，优先保留 Methods / Protocol 相关内容 |
| **智能截断** | 按 EvidenceChunk 截断，优先保留完整块，不腰斩句子 |
| **自我修正循环** | Researcher 可触发补充检索，系统自动执行 |
| **输出安全校验** | 自动补全缺失章节、清理 Mermaid 语法 |
| **Pydantic 强校验** | ArchitectOutput.validate_and_clean() + model_validate 双重校验 |
| **输入清洗** | 登录模块增加 `_sanitize_input`，防止 XSS 注入 |

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建你的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

---

## 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。

---

## 致谢

- 感谢 DeepSeek 提供的大语言模型 API
- 感谢 NCBI 提供的 PubMed 数据库和 BioPython 库
- 感谢 Streamlit 提供的优秀 Web 应用框架

---

*Bio-Precision Agent · 让每一个实验参数都有据可查*
