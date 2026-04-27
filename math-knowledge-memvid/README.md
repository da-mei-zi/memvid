# Math-Knowledge-Memvid

**基于嵌入式向量的个人数学知识库学习助手**  
*以 Memvid 单文件记忆系统为基础*

---

## 项目简介

本项目在 [Memvid](https://github.com/memvid/memvid) 的单文件记忆架构之上，构建了一套面向个人数学学习资料的知识库助手系统。

系统将 PDF、讲义、笔记等学习资料切分为知识片段，并通过 Memvid 的混合检索引擎（BM25 全文检索 + 语义向量检索）建立索引。用户输入自然语言问题后，系统检索相关片段，返回来源、相似度、主题标签和（可选）生成式回答。

### 核心改进点

| 改进 | 描述 |
|------|------|
| 数学结构感知切分 | 识别 Definition/Theorem/Proof 等关键词，保持逻辑单元完整 |
| 知识片段元数据 | 每个 chunk 携带来源、页码、主题、难度标签 |
| 混合检索接口 | 封装 keyword / vector / hybrid 三种模式 |
| 批量评测模块 | Top-k 命中率、MRR、检索延迟自动计算 |
| 可视化模块 | 主题分布、命中率、延迟对比图表自动生成 |

---

## 系统架构

```
math-knowledge-memvid/
│
├── data/
│   ├── raw_docs/                 # 原始 PDF、txt、md
│   ├── processed/                # 清洗后的文本 (docs.jsonl)
│   ├── chunks.csv                # 切分后的知识片段
│   ├── questions.csv             # 测试问题集
│   └── labels.csv                # 人工标注的相关 chunk
│
├── memory/
│   └── math_knowledge.mv2        # Memvid 生成的记忆文件
│
├── src/
│   ├── config.py                 # 参数配置
│   ├── ingest.py                 # 文档导入
│   ├── chunker.py                # 文本切分（三种策略）
│   ├── build_memory.py           # 写入 Memvid
│   ├── search.py                 # 检索接口
│   ├── qa.py                     # 问答接口
│   ├── evaluate.py               # 实验评测
│   └── visualize.py              # 图表生成
│
├── results/
│   ├── retrieval_results.csv     # 每个问题的检索结果
│   ├── metrics.csv               # Top-k、延迟等指标
│   └── figures/                  # 汇报图表
│
├── app/
│   └── demo.py                   # 命令行交互演示
│
├── requirements.txt
└── README.md
```

---

## 快速开始

### 1. 构建 Memvid CLI 二进制

```bash
# 在仓库根目录（不是 math-knowledge-memvid/）
cd <repo_root>
cargo build --bin memvid-cli
```

构建完成后，二进制位于 `target/debug/memvid-cli`（release 版本：`target/release/memvid-cli`）。

如果二进制不在默认路径，通过环境变量指定：

```bash
export MEMVID_CLI=/path/to/memvid-cli
```

### 2. 安装 Python 依赖

```bash
cd math-knowledge-memvid
pip install -r requirements.txt
```

### 3. 第一步：导入资料

将 PDF、Markdown、txt 文件放入 `data/raw_docs/`，然后：

```bash
python src/ingest.py
# 输出：data/processed/docs.jsonl
```

指定目录和输出路径：

```bash
python src/ingest.py --input data/raw_docs --output data/processed/docs.jsonl
```

### 4. 第二步：切分文本

```bash
python src/chunker.py \
    --input data/processed/docs.jsonl \
    --strategy math-aware \
    --chunk-size 400 \
    --overlap 80 \
    --output data/chunks.csv
```

**三种切分策略：**

| 策略 | 描述 |
|------|------|
| `fixed` | 固定长度窗口，带重叠 |
| `paragraph` | 按段落边界切分 |
| `math-aware` | 感知 Definition/Theorem/Proof 等数学结构（**推荐**） |

### 5. 第三步：构建知识库

```bash
python src/build_memory.py \
    --chunks data/chunks.csv \
    --output memory/math_knowledge.mv2
```

如需覆盖已有文件：

```bash
python src/build_memory.py --force
```

### 6. 检索测试

```bash
python src/search.py \
    --query "Bochner公式在梯度估计中有什么作用？" \
    --mode hybrid \
    --top-k 5
```

输出 JSON 格式：

```bash
python src/search.py --query "harmonic function" --mode keyword --json
```

### 7. 问答

```bash
# 检索式回答（无需 LLM）
python src/qa.py \
    --question "什么是 Bochner 公式？" \
    --mode retrieval

# 生成式回答（需要 OPENAI_API_KEY）
export OPENAI_API_KEY=sk-...
python src/qa.py \
    --question "Laplacian 比较定理的几何意义是什么？" \
    --mode generative
```

### 8. 批量评测

```bash
python src/evaluate.py \
    --questions data/questions.csv \
    --labels    data/labels.csv \
    --memory    memory/math_knowledge.mv2 \
    --output    results/metrics.csv \
    --detail    results/retrieval_results.csv
```

输出示例：

```
=== Evaluation Results ===
keyword     Hit@1=40.00%  Hit@3=70.00%  Hit@5=85.00%  MRR=0.5250  Latency=28.5ms
hybrid      Hit@1=55.00%  Hit@3=80.00%  Hit@5=90.00%  MRR=0.6400  Latency=31.2ms
```

### 9. 生成图表

```bash
python src/visualize.py \
    --chunks  data/chunks.csv \
    --metrics results/metrics.csv \
    --output  results/figures
```

生成的图表：

| 文件 | 内容 |
|------|------|
| `topic_distribution.png` | 知识库各主题 chunk 数量 |
| `chunk_size_distribution.png` | chunk 长度分布直方图 |
| `topk_hit_rate.png` | 不同检索模式的 Top-k 命中率对比 |
| `mrr_comparison.png` | MRR 对比 |
| `latency_comparison.png` | 平均延迟对比 |

### 10. 交互式演示

```bash
python app/demo.py
```

演示界面支持命令：

```
>> <问题>            — 直接提问
>> /mode hybrid      — 切换检索模式
>> /top-k 10         — 修改 top-k
>> /answer generative — 切换为生成式回答
>> /search <关键词>   — 原始检索
>> /quit
```

---

## 检索模式说明

| 模式 | 原理 | 适用场景 |
|------|------|---------|
| `keyword` | BM25 全文检索（Tantivy） | 精确关键词，如公式名称 |
| `vector` | 语义向量检索（需 `vec` feature） | 语义相近的表述 |
| `hybrid` | BM25 + 向量，RRF 重排序 | 综合效果最佳（**推荐**） |

> 注意：向量检索需在编译时启用 `--features vec` 并提供 ONNX embedding 模型。
> 默认构建仅支持 BM25 全文检索；hybrid 模式会自动对 BM25 结果用 RRF 重排序。

---

## 配置说明

所有可调参数集中在 `src/config.py`：

```python
CHUNK_STRATEGY = "math-aware"   # 切分策略
CHUNK_SIZE     = 400            # 目标字符数
CHUNK_OVERLAP  = 80             # 重叠字符数
SEARCH_TOP_K   = 5              # 默认检索数量
MEMVID_CLI     = "..."          # CLI 二进制路径
```

---

## 论文核心贡献

1. **数学结构感知切分**：识别 Definition/Theorem/Proof 等关键词，避免将完整的定理或证明切断
2. **知识片段元数据管理**：为每个 chunk 附加来源、页码、主题、标签等元数据，支持结果溯源
3. **混合检索对比实验**：评测 keyword / hybrid 两种检索模式在数学学习问答中的表现
4. **批量评测框架**：Top-k 命中率、MRR、检索延迟等标准指标的自动化评测
5. **可视化分析**：自动生成论文与汇报所需图表

---

## 依赖

| 包 | 用途 | 是否必须 |
|----|------|---------|
| `numpy` | 数值计算 | 是 |
| `matplotlib` | 图表生成 | 是 |
| `pypdf` | PDF 文本提取 | 推荐 |
| `pdfminer.six` | PDF 备用提取 | 可选 |
| `openai` | 生成式问答 | 可选 |
