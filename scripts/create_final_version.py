from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

# 创建新文档
doc = Document()

# 设置默认字体
style = doc.styles['Normal']
font = style.font
font.name = 'Microsoft YaHei'
font.size = Pt(11)

# 标题
title = doc.add_heading('个性化智能营养助手', 0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

subtitle = doc.add_paragraph('作业一：项目选题与知识库建设')
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph('')

# ============== 一、项目需求说明 ==============
doc.add_heading('一、项目需求说明', level=1)

doc.add_heading('1.1 选题领域', level=2)
doc.add_paragraph('个性化智能营养助手 —— 基于 RAG 的智能饮食推荐与健康管理系统')
doc.add_paragraph('')
doc.add_paragraph('核心理念："越用越懂你" - 通过每次对话不断充实用户画像，形成专属知识库。')

doc.add_heading('1.2 目标用户', level=2)
table = doc.add_table(rows=6, cols=3)
table.style = 'Table Grid'
headers = ['用户类型', '描述', '核心需求']
for i, header in enumerate(headers):
    table.rows[0].cells[i].text = header
data = [
    ['减脂人群', '想要减重、降低体脂率', '热量控制、低卡菜谱、营养均衡'],
    ['增肌人群', '健身增肌、提升肌肉量', '高蛋白饮食、训练后营养补充'],
    ['健康管理人群', '慢病管理（糖尿病、高血压等）', '特定饮食限制、医学营养指导'],
    ['亚健康人群', '睡眠差、压力大、易疲劳', '营养调理、生活方式改善'],
    ['健身爱好者', '追求健康生活方式', '科学饮食搭配、营养知识学习'],
]
for i, row_data in enumerate(data):
    for j, cell_data in enumerate(row_data):
        table.rows[i+1].cells[j].text = cell_data

doc.add_heading('1.3 典型问题（5个）', level=2)
questions = [
    '我25岁，160cm，58kg，想减脂，今天早餐吃什么？',
    '我是增肌期，每天需要多少蛋白质？有什么高蛋白菜谱推荐？',
    '我有乳糖不耐受，有什么高蛋白食物可以吃？',
    '帮我制定一周的减脂餐计划',
    '我今天已经吃了1200大卡，晚餐还能吃多少？',
]
for i, q in enumerate(questions, 1):
    doc.add_paragraph(f'{i}. {q}')

doc.add_heading('1.4 核心功能列表', level=2)
table = doc.add_table(rows=8, cols=3)
table.style = 'Table Grid'
headers = ['功能模块', '具体功能', '优先级']
for i, header in enumerate(headers):
    table.rows[0].cells[i].text = header
data = [
    ['用户画像', '通过对话自动采集和更新用户信息', 'P0'],
    ['营养计算', '基于BMR/TDEE计算每日营养需求', 'P0'],
    ['智能推荐', '根据用户画像推荐个性化菜谱', 'P0'],
    ['热量追踪', '记录每餐摄入，实时监控热量', 'P0'],
    ['偏好学习', 'AI自动学习用户口味和饮食习惯', 'P1'],
    ['周计划生成', '自动生成一周饮食计划', 'P1'],
    ['安全风控', '危险饮食识别、过敏校验', 'P1'],
]
for i, row_data in enumerate(data):
    for j, cell_data in enumerate(row_data):
        table.rows[i+1].cells[j].text = cell_data

# ============== 二、数据来源清单 ==============
doc.add_heading('二、数据来源清单', level=1)

doc.add_heading('2.1 菜谱数据', level=2)
table = doc.add_table(rows=6, cols=4)
table.style = 'Table Grid'
headers = ['数据来源', '数据类型', '数据量', '获取方式']
for i, header in enumerate(headers):
    table.rows[0].cells[i].text = header
data = [
    ['下厨房', '中式菜谱', '50,000+', '爬虫/API'],
    ['美食杰', '中式菜谱', '30,000+', '爬虫'],
    ['CookHero开源数据集', '多语言菜谱', '10,000+', 'GitHub下载'],
    ['小红书健身餐', '健身餐菜谱', '5,000+', '爬虫'],
    ['健身社区', '减脂/增肌餐', '3,000+', '爬虫'],
]
for i, row_data in enumerate(data):
    for j, cell_data in enumerate(row_data):
        table.rows[i+1].cells[j].text = cell_data

doc.add_heading('2.2 营养数据', level=2)
table = doc.add_table(rows=4, cols=4)
table.style = 'Table Grid'
headers = ['数据来源', '数据类型', '数据量', '获取方式']
for i, header in enumerate(headers):
    table.rows[0].cells[i].text = header
data = [
    ['中国食物成分表', '食物营养成分', '2,000+', '官方数据'],
    ['USDA营养数据库', '国际食物营养', '10,000+', '官方API'],
    ['薄荷营养', '食物热量', '5,000+', 'API'],
]
for i, row_data in enumerate(data):
    for j, cell_data in enumerate(row_data):
        table.rows[i+1].cells[j].text = cell_data

doc.add_heading('2.3 数据总量', level=2)
doc.add_paragraph('• 菜谱数据：约100,000+条')
doc.add_paragraph('• 营养数据：约17,000+条')
doc.add_paragraph('• 健康知识：约500+篇')

doc.add_heading('2.4 数据清洗说明', level=2)
doc.add_paragraph('针对收集到的菜谱数据，进行以下清洗处理：')

doc.add_paragraph('')
doc.add_paragraph('1. 格式统一')
doc.add_paragraph('   - 所有菜谱统一为JSON格式存储')
doc.add_paragraph('   - 字段名称统一为英文（name、category、calories等）')
doc.add_paragraph('   - 数值字段统一单位（热量kcal、蛋白质g、脂肪g、碳水g）')

doc.add_paragraph('')
doc.add_paragraph('2. 缺失值处理')
doc.add_paragraph('   - 检查必填字段：name（菜名）、calories（热量）、ingredients（食材）')
doc.add_paragraph('   - 缺失必填字段的菜谱直接删除')
doc.add_paragraph('   - 非必填字段缺失时填充默认值（如allergens为空则填充"无"）')

doc.add_paragraph('')
doc.add_paragraph('3. 异常值处理')
doc.add_paragraph('   - 热量异常检测：低于50kcal或高于2000kcal的标记为异常')
doc.add_paragraph('   - 营养成分校验：蛋白质×4 + 脂肪×9 + 碳水×4 应接近总热量')
doc.add_paragraph('   - 烹饪时间异常：超过120分钟的标记审核')

doc.add_paragraph('')
doc.add_paragraph('4. 过敏原处理')
doc.add_paragraph('   - 过敏原列表统一为中文名称')
doc.add_paragraph('   - 空过敏原字段统一标记为"无"')
doc.add_paragraph('   - 常见过敏原分类：乳制品、鸡蛋、坚果、海鲜、大豆、麸质等')

doc.add_paragraph('')
doc.add_paragraph('5. 数据去重')
doc.add_paragraph('   - 按菜名（name）进行去重检查')
doc.add_paragraph('   - 重复菜谱保留最新版本')
doc.add_paragraph('   - 相似菜谱（如"柠檬鸡胸肉"和"柠檬味鸡胸肉"）标记人工审核')

# ============== 三、分块样例 ==============
doc.add_heading('三、分块样例', level=1)

doc.add_heading('3.1 分块策略', level=2)
doc.add_paragraph('采用语义分块策略，以单个菜谱为单位，按语义完整性分割为多个块：')
doc.add_paragraph('• 基础信息块：菜名、分类、烹饪时间、热量')
doc.add_paragraph('• 食材块：食材列表、过敏原信息')
doc.add_paragraph('• 步骤块：烹饪步骤（长菜谱拆分）')
doc.add_paragraph('• 营养块：详细营养成分')

doc.add_heading('3.2 分块示例1：柠檬鸡胸肉', level=2)
doc.add_paragraph('【基础信息块】')
doc.add_paragraph('菜名：柠檬鸡胸肉')
doc.add_paragraph('分类：减脂餐')
doc.add_paragraph('餐次：午餐')
doc.add_paragraph('难度：简单')
doc.add_paragraph('烹饪时间：25分钟')
doc.add_paragraph('热量：189kcal')

doc.add_paragraph('')
doc.add_paragraph('【食材块】')
doc.add_paragraph('食材：鸡胸肉150g、柠檬1个、蒜末5g、生抽10ml、料酒5ml、橄榄油5ml')
doc.add_paragraph('过敏原：无')

doc.add_paragraph('')
doc.add_paragraph('【步骤块】')
doc.add_paragraph('1. 鸡胸肉切片，用蒜末、生抽腌制20分钟')
doc.add_paragraph('2. 柠檬切片，铺在空气炸锅底部')
doc.add_paragraph('3. 放入鸡胸肉，180度烤8分钟')
doc.add_paragraph('4. 翻面刷少许油，再烤10分钟')

doc.add_paragraph('')
doc.add_paragraph('【营养块】')
doc.add_paragraph('热量：189kcal')
doc.add_paragraph('蛋白质：31.2g')
doc.add_paragraph('脂肪：5.8g')
doc.add_paragraph('碳水：2.1g')
doc.add_paragraph('膳食纤维：0.3g')

doc.add_paragraph('')
doc.add_paragraph('分块理由：按语义完整性分割，每个块包含完整的信息单元，便于检索时精准匹配。')

doc.add_heading('3.3 分块示例2：番茄龙利鱼豆腐汤', level=2)
doc.add_paragraph('【基础信息块】')
doc.add_paragraph('菜名：番茄龙利鱼豆腐汤')
doc.add_paragraph('分类：减脂餐')
doc.add_paragraph('餐次：晚餐')
doc.add_paragraph('难度：简单')
doc.add_paragraph('烹饪时间：20分钟')
doc.add_paragraph('热量：156kcal')

doc.add_paragraph('')
doc.add_paragraph('【食材块】')
doc.add_paragraph('食材：龙利鱼150g、嫩豆腐100g、番茄200g、金针菇50g、葱姜5g')
doc.add_paragraph('过敏原：大豆')

doc.add_paragraph('')
doc.add_paragraph('【营养块】')
doc.add_paragraph('热量：156kcal')
doc.add_paragraph('蛋白质：28.5g')
doc.add_paragraph('脂肪：3.2g')
doc.add_paragraph('碳水：8.6g')

doc.add_paragraph('')
doc.add_paragraph('分块理由：汤品类菜谱步骤简单，合并为一个步骤块；食材和营养独立分块便于过滤和匹配。')

doc.add_heading('3.4 分块结果截图', level=2)
doc.add_paragraph('以下为VSCode终端运行分块脚本的输出结果截图：')

doc.add_paragraph('')
doc.add_paragraph('【截图1：分块总览】')
doc.add_paragraph('说明：显示知识库的分块统计信息，包括文档总数、分块总数、分类分布等。')
placeholder1 = doc.add_paragraph('（请在此处粘贴截图1：分块总览）')
placeholder1.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph('')
doc.add_paragraph('【截图2：分块详情】')
doc.add_paragraph('说明：显示单个菜谱的分块详情，包括每个块的chunk_id、字数、标题路径和内容预览。')
placeholder2 = doc.add_paragraph('（请在此处粘贴截图2：分块详情）')
placeholder2.alignment = WD_ALIGN_PARAGRAPH.CENTER

# ============== 四、元数据设计 ==============
doc.add_heading('四、元数据设计', level=1)

doc.add_heading('4.1 菜谱元数据', level=2)
table = doc.add_table(rows=16, cols=3)
table.style = 'Table Grid'
headers = ['字段', '类型', '说明']
for i, header in enumerate(headers):
    table.rows[0].cells[i].text = header
data = [
    ['recipe_id', 'string', '唯一标识'],
    ['name', 'string', '菜名'],
    ['category', 'enum', '减脂/增肌/维持/素食'],
    ['meal_type', 'enum', '早餐/午餐/晚餐/加餐'],
    ['difficulty', 'int', '难度等级(1-5)'],
    ['cook_time', 'int', '烹饪时间(分钟)'],
    ['calories', 'float', '热量(kcal)'],
    ['protein', 'float', '蛋白质(g)'],
    ['fat', 'float', '脂肪(g)'],
    ['carbs', 'float', '碳水(g)'],
    ['ingredients', 'array', '食材列表'],
    ['allergens', 'array', '过敏原列表'],
    ['source', 'string', '数据来源'],
    ['credibility', 'enum', '官方/用户验证/用户生成'],
    ['update_time', 'datetime', '更新时间'],
]
for i, row_data in enumerate(data):
    for j, cell_data in enumerate(row_data):
        table.rows[i+1].cells[j].text = cell_data

doc.add_heading('4.2 用户画像元数据', level=2)
table = doc.add_table(rows=12, cols=3)
table.style = 'Table Grid'
headers = ['字段', '类型', '说明']
for i, header in enumerate(headers):
    table.rows[0].cells[i].text = header
data = [
    ['user_id', 'string', '用户唯一标识'],
    ['gender', 'enum', '男/女'],
    ['age', 'int', '年龄'],
    ['height', 'float', '身高(cm)'],
    ['weight', 'float', '体重(kg)'],
    ['fitness_goal', 'enum', '减脂/增肌/维持'],
    ['medical_conditions', 'array', '慢性疾病'],
    ['food_allergies', 'array', '食物过敏'],
    ['calorie_target', 'int', '每日热量目标'],
    ['taste_preferences', 'object', '口味偏好'],
    ['activity_level', 'enum', '活动水平'],
]
for i, row_data in enumerate(data):
    for j, cell_data in enumerate(row_data):
        table.rows[i+1].cells[j].text = cell_data

# 保存文档
output_path = r'C:\Users\Sean.bx\Desktop\project_based_training\nutri_assistant\docs\reports\作业一_项目需求说明与知识库建设_最终版.docx'
doc.save(output_path)
print(f"文档已保存: {output_path}")
