from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os

# 读取现有文档
doc_path = r'C:\Users\Sean.bx\Desktop\project_based_training\nutri_assistant\docs\reports\作业一_项目选题与知识库建设_提交版.docx'
doc = Document(doc_path)

# 找到"四、元数据设计"的位置，在它前面插入新章节
target_index = None
for i, para in enumerate(doc.paragraphs):
    if '四、元数据设计' in para.text or '元数据设计' in para.text:
        target_index = i
        break

# 如果没找到，就在最后添加
if target_index is None:
    target_index = len(doc.paragraphs)

# 在目标位置前插入新内容
# 先找到"三、分块样例"下的最后一个示例位置
insert_pos = None
for i, para in enumerate(doc.paragraphs):
    if '3.3 分块示例2' in para.text or '分块示例2' in para.text:
        # 找到这个标题后，找到下一个标题或段落
        for j in range(i+1, len(doc.paragraphs)):
            if doc.paragraphs[j].style.name.startswith('Heading'):
                insert_pos = j
                break
        break

if insert_pos is None:
    insert_pos = target_index

# 创建新段落内容
new_paragraphs = []

# 添加空行
doc.add_paragraph('')

# 添加3.4标题
doc.add_heading('3.4 分块结果截图', level=2)

# 添加说明
doc.add_paragraph('以下为VSCode终端运行分块脚本的输出结果截图：')

# 添加空行
doc.add_paragraph('')

# 添加截图1标题
doc.add_paragraph('【截图1：分块总览】')
doc.add_paragraph('说明：显示知识库的分块统计信息，包括文档总数、分块总数、分类分布等。')

# 添加占位符（用户需要手动粘贴截图）
placeholder1 = doc.add_paragraph('（请在此处粘贴截图1：分块总览）')
placeholder1.alignment = WD_ALIGN_PARAGRAPH.CENTER

# 添加空行
doc.add_paragraph('')

# 添加截图2标题
doc.add_paragraph('【截图2：分块详情】')
doc.add_paragraph('说明：显示单个菜谱的分块详情，包括每个块的chunk_id、字数、标题路径和内容预览。')

# 添加占位符（用户需要手动粘贴截图）
placeholder2 = doc.add_paragraph('（请在此处粘贴截图2：分块详情）')
placeholder2.alignment = WD_ALIGN_PARAGRAPH.CENTER

# 保存文档
output_path = r'C:\Users\Sean.bx\Desktop\project_based_training\nutri_assistant\docs\reports\作业一_项目选题与知识库建设_提交版.docx'
doc.save(output_path)
print(f"文档已更新: {output_path}")
print("已添加 3.4 分块结果截图 章节")
