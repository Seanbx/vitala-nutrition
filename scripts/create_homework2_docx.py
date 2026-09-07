"""
生成作业二报告：检索模块实现
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


def create_report():
    doc = Document()

    style = doc.styles["Normal"]
    style.font.name = "SimSun"
    style.font.size = Pt(12)
    style.paragraph_format.line_spacing = 1.5

    title = doc.add_heading("", level=0)
    run = title.add_run("作业二：检索模块实现")
    run.font.size = Pt(22)
    run.font.color.rgb = RGBColor(0, 0, 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("个性化智能营养助手 —— 基于RAG的智能饮食推荐系统")
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(100, 100, 100)

    doc.add_paragraph("")

    # 1. 检索方案设计
    doc.add_heading("1. 检索方案设计", level=1)

    doc.add_heading("1.1 整体架构", level=2)
    doc.add_paragraph(
        "本系统采用混合检索架构，结合向量语义检索和BM25关键词检索两种方法，"
        "通过RRF（Reciprocal Rank Fusion）算法进行结果融合，以提高检索的召回率和准确率。"
    )

    doc.add_paragraph("检索流程如下：")
    doc.add_paragraph("用户输入查询", style="List Number")
    doc.add_paragraph("查询重写（可选）：利用LLM将模糊查询改写为更精确的检索词", style="List Number")
    doc.add_paragraph("向量检索：基于BGE-M3 Embedding模型，计算查询与文档块的语义相似度", style="List Number")
    doc.add_paragraph("BM25检索：基于jieba中文分词的关键词匹配", style="List Number")
    doc.add_paragraph("RRF融合：对两路检索结果进行排名融合", style="List Number")
    doc.add_paragraph("元数据过滤：根据用户画像（目标、过敏原等）过滤结果", style="List Number")
    doc.add_paragraph("结果返回Top-K文档", style="List Number")

    doc.add_heading("1.2 向量检索方案", level=2)
    doc.add_paragraph(
        "Embedding模型：BAAI/bge-m3（SiliconFlow API）\n"
        "向量维度：1024维\n"
        "向量数据库：ChromaDB\n"
        "最大输入长度：8192 tokens\n"
        "相似度计算：余弦相似度"
    )
    doc.add_paragraph(
        "BGE-M3是多语言Embedding模型，在中文场景下表现优异，"
        "支持最长8192 tokens的输入，适合处理较长的菜谱文档。"
        "通过SiliconFlow API调用，无需本地部署GPU资源。"
    )

    doc.add_heading("1.3 BM25检索方案", level=2)
    doc.add_paragraph(
        "分词工具：jieba中文分词\n"
        "检索库：rank_bm25\n"
        "检索数量：Top-K×2（获取更多候选）"
    )
    doc.add_paragraph(
        "BM25是经典的基于词频的检索算法，擅长精确匹配关键词。"
        "对于包含特定食材名称、疾病名称等精确查询，BM25能提供比向量检索更精准的结果。"
        "使用jieba进行中文分词，避免了默认空格分词导致的中文检索失效问题。"
    )

    doc.add_heading("1.4 RRF融合策略", level=2)
    doc.add_paragraph(
        "RRF（Reciprocal Rank Fusion）公式：score(d) = 1/(k + rank)\n"
        "参数k=60（标准值）\n"
        "两路结果独立计算RRF分数后累加，按总分排序"
    )
    doc.add_paragraph(
        "RRF的优势在于无需对两路检索的分数进行归一化，直接基于排名进行融合，"
        "简单有效且鲁棒性强。"
    )

    # 2. 分块策略
    doc.add_heading("2. 分块策略", level=1)

    doc.add_heading("2.1 分块参数", level=2)
    doc.add_paragraph(
        "分块器：RecursiveCharacterTextSplitter\n"
        "块大小（chunk_size）：500字符\n"
        "重叠大小（chunk_overlap）：50字符\n"
        "分隔符优先级：\\n## > \\n### > \\n- > \\n > 。> ！> ？> . > 空格"
    )

    doc.add_heading("2.2 分块效果", level=2)
    doc.add_paragraph(
        "共加载文档213篇（菜谱150篇 + 营养知识30篇 + 根目录菜谱33篇），"
        "切分后得到295个文档块。"
    )
    doc.add_paragraph("分块策略说明：")
    doc.add_paragraph(
        "按Markdown标题层级优先切分，保证每个块在语义上相对完整；"
        "当单个段落超过500字符时，按句子边界进一步切分；"
        "50字符的重叠确保上下文信息不因切分而丢失。"
    )

    # 3. 元数据设计
    doc.add_heading("3. 元数据设计", level=1)
    doc.add_paragraph("每个文档块携带以下元数据：")

    table = doc.add_table(rows=8, cols=3, style="Table Grid")
    headers = ["字段名", "类型", "说明"]
    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = h
    data = [
        ["source", "string", "文件路径"],
        ["title", "string", "文档标题（文件名）"],
        ["doc_type", "string", "文档类型：recipe / knowledge / other"],
        ["category", "string", "菜谱分类：减脂餐 / 增肌餐 / 维持餐"],
        ["meal_type", "string", "餐次：breakfast / lunch / dinner / snack"],
        ["tags", "list", "标签：low_cal, high_protein, quick 等"],
        ["chunk_id", "int", "块序号"],
    ]
    for i, row in enumerate(data):
        for j, val in enumerate(row):
            table.rows[i + 1].cells[j].text = val

    doc.add_paragraph(
        "\n元数据用于支持条件过滤检索，例如：用户只想看减脂餐时，"
        "在向量检索基础上增加 category='减脂餐' 的过滤条件。"
    )

    # 4. 检索测试
    doc.add_heading("4. 检索测试", level=1)

    doc.add_heading("4.1 测试问题与结果", level=2)

    test_results = [
        ("减脂期早餐吃什么好？", "蒸红薯、蒸玉米等低卡主食", "✅ 相关"),
        ("增肌每天需要多少蛋白质？", "高蛋白食物排行（知识文档）", "✅ 相关"),
        ("乳糖不耐受能吃什么高蛋白食物？", "高蛋白食物排行 + 高血压饮食指南", "✅ 相关"),
        ("红烧肉怎么做才不腻？", "高蛋白食物排行（部分相关）", "⚠️ 部分相关"),
        ("糖尿病患者饮食注意事项？", "番茄鸡蛋面（维持餐）", "⚠️ 部分相关"),
        ("运动前后怎么吃？", "蒜蓉炒菜心（维持餐）", "⚠️ 部分相关"),
        ("哪些食物蛋白质含量最高？", "高蛋白食物排行", "✅ 相关"),
        ("减脂期晚餐吃什么？", "蒸红薯、清蒸鲈鱼", "✅ 相关"),
        ("孕妇需要补充哪些营养？", "清蒸鲈鱼、凉拌黄瓜", "⚠️ 部分相关"),
        ("怎么计算每天需要多少热量？", "虾仁豆腐煲（不相关）", "❌ 不相关"),
    ]

    table2 = doc.add_table(rows=len(test_results) + 1, cols=3, style="Table Grid")
    for i, h in enumerate(["测试问题", "Top-1结果", "评价"]):
        table2.rows[0].cells[i].text = h
    for i, (q, r, e) in enumerate(test_results):
        table2.rows[i + 1].cells[0].text = q
        table2.rows[i + 1].cells[1].text = r
        table2.rows[i + 1].cells[2].text = e

    doc.add_heading("4.2 测试结论", level=2)
    doc.add_paragraph(
        "准确率：5/10（50%完全相关）\n"
        "部分相关率：3/10（30%部分相关）\n"
        "不相关率：2/10（20%不相关）"
    )
    doc.add_paragraph(
        "向量检索在语义相近的查询上表现良好，但在需要精确知识检索的场景（如热量计算公式）"
        "和需要特定疾病饮食指导的场景下，检索结果不够精准。"
    )

    # 5. Bad Case 分析
    doc.add_heading("5. Bad Case 分析与优化方案", level=1)

    doc.add_heading("5.1 Bad Case 1：热量计算问题", level=2)
    doc.add_paragraph(
        "问题：「怎么计算每天需要多少热量？」检索到虾仁豆腐煲\n"
        "原因：知识库中有BMR和TDEE计算文档，但分块后关键公式信息分散\n"
        "优化方案：对知识类文档采用更细粒度的语义分块，确保公式和定义完整保留"
    )

    doc.add_heading("5.2 Bad Case 2：疾病饮食指导", level=2)
    doc.add_paragraph(
        "问题：「糖尿病患者饮食注意事项？」检索到番茄鸡蛋面\n"
        "原因：番茄鸡蛋面属于维持餐，与糖尿病饮食指南语义距离较远\n"
        "优化方案：增加元数据过滤，在疾病相关查询时优先检索知识文档而非菜谱"
    )

    doc.add_heading("5.3 Bad Case 3：运动营养指导", level=2)
    doc.add_paragraph(
        "问题：「运动前后怎么吃？」检索到蒜蓉炒菜心\n"
        "原因：运动营养知识文档存在但排名不够靠前\n"
        "优化方案：引入查询重写，将「运动前后」改写为「运动前后营养补充蛋白质碳水」"
    )

    doc.add_heading("5.4 优化措施总结", level=2)
    doc.add_paragraph("已实施的优化：")
    doc.add_paragraph("混合检索（向量 + BM25 + RRF）替代单一向量检索", style="List Bullet")
    doc.add_paragraph("查询重写：利用LLM将模糊查询改写为精确检索词", style="List Bullet")
    doc.add_paragraph("元数据过滤：根据用户目标（减脂/增肌/维持）过滤菜谱分类", style="List Bullet")
    doc.add_paragraph("中文分词：使用jieba分词优化BM25检索效果", style="List Bullet")

    doc.add_paragraph("\n待实施的优化：")
    doc.add_paragraph("知识文档专用分块策略（保留公式完整性）", style="List Bullet")
    doc.add_paragraph("交叉编码器重排序（bge-reranker-base）", style="List Bullet")
    doc.add_paragraph("小到大检索（Small-to-Big）：用小块检索，返回大块上下文", style="List Bullet")

    # 6. 技术实现
    doc.add_heading("6. 技术实现", level=1)

    doc.add_heading("6.1 核心代码结构", level=2)
    doc.add_paragraph(
        "项目src/目录包含以下模块：\n"
        "• data_loader.py — 数据加载与分块\n"
        "• retriever.py — 混合检索器（向量+BM25+RRF）\n"
        "• generator.py — LLM生成模块（查询重写+回答生成）\n"
        "• user_profile.py — 用户画像管理\n"
        "• safety.py — 安全与健康风险控制\n"
        "• rag_service.py — RAG服务层（整合所有模块）\n"
        "• api.py — FastAPI服务接口"
    )

    doc.add_heading("6.2 技术栈", level=2)
    tech_table = doc.add_table(rows=7, cols=2, style="Table Grid")
    tech_data = [
        ("组件", "技术选型"),
        ("Embedding模型", "BAAI/bge-m3（SiliconFlow API）"),
        ("向量数据库", "ChromaDB"),
        ("LLM", "DeepSeek-V3（SiliconFlow API）"),
        ("分词工具", "jieba"),
        ("检索框架", "LangChain + rank_bm25"),
        ("服务框架", "FastAPI + Uvicorn"),
    ]
    for i, (k, v) in enumerate(tech_data):
        tech_table.rows[i].cells[0].text = k
        tech_table.rows[i].cells[1].text = v

    doc.add_heading("6.3 启动方式", level=2)
    doc.add_paragraph(
        "1. 配置 .env 文件，填入 SILICONFLOW_API_KEY\n"
        "2. 安装依赖：pip install -r requirements.txt\n"
        "3. 运行检索测试：python scripts/retrieval_test.py\n"
        "4. 启动API服务：python main.py\n"
        "5. 访问 http://localhost:8000 使用前端界面"
    )

    output_path = Path(__file__).parent / "作业二_检索模块实现.docx"
    doc.save(str(output_path))
    print(f"报告已生成: {output_path}")
    return output_path


if __name__ == "__main__":
    create_report()
