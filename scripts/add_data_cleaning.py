from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

# 读取现有文档
doc_path = r'C:\Users\Sean.bx\Desktop\project_based_training\nutri_assistant\docs\reports\作业一_项目选题与知识库建设_提交版.docx'
doc = Document(doc_path)

# 找到"二、数据来源清单"下的最后一个章节位置
# 需要在"2.3 数据总量"之后，"三、分块样例"之前插入
target_index = None
for i, para in enumerate(doc.paragraphs):
    if '三、分块样例' in para.text:
        target_index = i
        break

if target_index is None:
    target_index = len(doc.paragraphs)

# 在目标位置前插入新内容
# 添加2.4标题
doc.add_heading('2.4 数据清洗说明', level=2)

# 添加数据清洗内容
doc.add_paragraph('针对收集到的菜谱数据，进行以下清洗处理：')

doc.add_paragraph('')

# 1. 格式统一
doc.add_paragraph('1. 格式统一')
doc.add_paragraph('   - 所有菜谱统一为JSON格式存储')
doc.add_paragraph('   - 字段名称统一为英文（name、category、calories等）')
doc.add_paragraph('   - 数值字段统一单位（热量kcal、蛋白质g、脂肪g、碳水g）')

doc.add_paragraph('')

# 2. 缺失值处理
doc.add_paragraph('2. 缺失值处理')
doc.add_paragraph('   - 检查必填字段：name（菜名）、calories（热量）、ingredients（食材）')
doc.add_paragraph('   - 缺失必填字段的菜谱直接删除')
doc.add_paragraph('   - 非必填字段缺失时填充默认值（如allergens为空则填充"无"）')

doc.add_paragraph('')

# 3. 异常值处理
doc.add_paragraph('3. 异常值处理')
doc.add_paragraph('   - 热量异常检测：低于50kcal或高于2000kcal的标记为异常')
doc.add_paragraph('   - 营养成分校验：蛋白质×4 + 脂肪×9 + 碳水×4 应接近总热量')
doc.add_paragraph('   - 烹饪时间异常：超过120分钟的标记审核')

doc.add_paragraph('')

# 4. 过敏原处理
doc.add_paragraph('4. 过敏原处理')
doc.add_paragraph('   - 过敏原列表统一为中文名称')
doc.add_paragraph('   - 空过敏原字段统一标记为"无"')
doc.add_paragraph('   - 常见过敏原分类：乳制品、鸡蛋、坚果、海鲜、大豆、麸质等')

doc.add_paragraph('')

# 5. 数据去重
doc.add_paragraph('5. 数据去重')
doc.add_paragraph('   - 按菜名（name）进行去重检查')
doc.add_paragraph('   - 重复菜谱保留最新版本')
doc.add_paragraph('   - 相似菜谱（如"柠檬鸡胸肉"和"柠檬味鸡胸肉"）标记人工审核')

# 保存文档（另存为新文件，避免权限问题）
output_path = r'C:\Users\Sean.bx\Desktop\project_based_training\nutri_assistant\docs\reports\作业一_项目需求说明与知识库建设_最终版.docx'
doc.save(output_path)
print(f"文档已保存: {output_path}")
print("已添加 2.4 数据清洗说明 章节")
