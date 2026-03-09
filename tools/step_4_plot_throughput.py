import pandas as pd
import matplotlib.pyplot as plt
import json
import argparse

# 解析命令行参数
parser = argparse.ArgumentParser(description='Plot throughput data')
parser.add_argument('--en', action='store_true', help='Use English labels')
args = parser.parse_args()

# 根据命令行参数设置标签
if args.en:
    print("Using English labels")
    # 英文标签
    title1 = 'Total Generation Throughput'
    title2 = 'Average Per-Request Throughput'
    xlabel = 'Concurrent Requests'
    ylabel = 'Throughput (tokens/s)'
else:
    print("使用中文标签")
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun']  # 设置中文字体
    plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
    # 中文标签
    title1 = '并发请求总生成吞吐量'
    title2 = '平均每请求吞吐量'
    xlabel = '并发请求数'
    ylabel = '吞吐量 (tokens/s)'

# 读取CSV文件
df = pd.read_csv('../output/throughput_summary.csv')

# 读取config.json文件，获取测试说明
with open('../config/config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
test_remarks = config.get('test_result_remarks', '测试结果图表')

# 提取数据
running_requests = df['Running requests']
avg_gen_throughput = df['Avg generation throughput(tokens/s)']
avg_per_req_throughput = df['Avg per-request throughput(tokens/s)']

# 创建图表，增加顶部空间用于测试说明
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 13))

# 在图表最上方添加测试说明
fig.suptitle(test_remarks, fontsize=18, fontweight='bold', y=0.98)

# 图表1：总生成吞吐量
ax1.plot(running_requests, avg_gen_throughput, marker='o', linestyle='-', color='b')
ax1.set_title(title1)
ax1.set_xlabel(xlabel)
ax1.set_ylabel(ylabel)
ax1.grid(True)

# 设置横坐标为Running requests的实际值
ax1.set_xticks(running_requests)
ax1.set_xticklabels(running_requests, rotation=45, ha='right')

# 动态设置纵坐标范围
min_gen = min(avg_gen_throughput)
max_gen = max(avg_gen_throughput)
ax1.set_ylim(min_gen * 0.9, max_gen * 1.1)

# 在每个数据点上方显示数值
for i, (x, y) in enumerate(zip(running_requests, avg_gen_throughput)):
    ax1.text(x, y * 1.02, f'{y:.2f}', ha='center', va='bottom')

# 图表2：平均每请求吞吐量
ax2.plot(running_requests, avg_per_req_throughput, marker='o', linestyle='-', color='r')
ax2.set_title(title2)
ax2.set_xlabel(xlabel)
ax2.set_ylabel(ylabel)
ax2.grid(True)

# 设置横坐标为Running requests的实际值
ax2.set_xticks(running_requests)
ax2.set_xticklabels(running_requests, rotation=45, ha='right')

# 动态设置纵坐标范围
min_per_req = min(avg_per_req_throughput)
max_per_req = max(avg_per_req_throughput)
ax2.set_ylim(min_per_req * 0.9, max_per_req * 1.1)

# 在每个数据点上方显示数值
for i, (x, y) in enumerate(zip(running_requests, avg_per_req_throughput)):
    ax2.text(x, y * 1.02, f'{y:.2f}', ha='center', va='bottom')

# 调整布局
plt.tight_layout()

# 保存图表
plt.savefig('../output/throughput_charts.png', dpi=300, bbox_inches='tight')

if args.en:
    print("Chart saved as output/throughput_charts.png")
else:
    print("如果图表中文字体显示异常，请检查是否安装了中文字体，或执行 'python tools/plot_throughput.py --en' 使用英文标签")
    print("图表已保存为 output/throughput_charts.png")
