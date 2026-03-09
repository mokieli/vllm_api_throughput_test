#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vLLM 吞吐量测试数据分析器
处理 vLLM 大模型 API 吞吐量测试的 CSV 数据，计算不同并发数下的平均吞吐量。
"""

import pandas as pd
import argparse
import sys
import json
from pathlib import Path


def load_config(config_path: str = "../config/config.json") -> dict:
    """
    从配置文件读取配置

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


def get_target_concurrents(config: dict) -> list:
    """
    根据配置文件计算目标并发数列表

    Args:
        config: 配置字典，包含 max_concurrent 和 step

    Returns:
        目标并发数列表
    """
    max_concurrent = config.get('max_concurrent', 32)
    step = config.get('step', 2)
    
    # 生成目标并发数列表：1, step, step*2, step*3, ... 直到 max_concurrent
    target_concurrents = [1]
    current = step
    while current <= max_concurrent:
        target_concurrents.append(current)
        current += step
    
    return target_concurrents


def load_csv(filepath: str) -> pd.DataFrame:
    """
    读取 CSV 文件

    Args:
        filepath: CSV 文件路径

    Returns:
        数据框
    """
    print(f"正在读取文件：{filepath}")
    df = pd.read_csv(filepath)
    print(f"读取完成，共 {len(df)} 行数据")
    return df


def clean_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    数据清洗：四步过滤

    1. 删除 Avg prompt throughput(tokens/s) 列非零的行
    2. 删除 Waiting requests 列非零的行
    3. 删除 Running requests 列为零的行
    4. 删除不属于目标并发数的行

    Args:
        df: 原始数据框
        config: 配置字典，包含 max_concurrent 和 step

    Returns:
        清洗后的数据框
    """
    original_count = len(df)
    
    # 第一步：删除 prompt throughput 非零的行
    df = df[df['Avg prompt throughput(tokens/s)'] == 0.0]
    step1_count = len(df)
    print(f"步骤 1 - 过滤 prompt throughput = 0: {original_count} -> {step1_count} 行")
    
    # 第二步：删除 waiting requests 非零的行
    df = df[df['Waiting requests'] == 0]
    step2_count = len(df)
    print(f"步骤 2 - 过滤 waiting requests = 0: {step1_count} -> {step2_count} 行")
    
    # 第三步：删除 running requests 为零的行
    df = df[df['Running requests'] > 0]
    step3_count = len(df)
    print(f"步骤 3 - 过滤 running requests > 0: {step2_count} -> {step3_count} 行")
    
    # 第四步：删除不属于目标并发数的行
    target_concurrents = get_target_concurrents(config)
    print(f"目标并发数：{target_concurrents}")
    df = df[df['Running requests'].isin(target_concurrents)]
    step4_count = len(df)
    print(f"步骤 4 - 过滤目标并发数：{step3_count} -> {step4_count} 行")
    
    print(f"数据清洗完成：{original_count} -> {step4_count} 行")
    return df


def calculate_throughput(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算不同并发数下的平均吞吐量

    Args:
        df: 清洗后的数据框

    Returns:
        包含并发数、平均吞吐量、单请求吞吐量的数据框
    """
    # 按 Running requests 分组，计算 Avg generation throughput 的平均值
    grouped = df.groupby('Running requests')['Avg generation throughput(tokens/s)'].mean().reset_index()
    grouped.columns = ['Running requests', 'Avg generation throughput(tokens/s)']
    
    # 计算单请求吞吐量 = 平均吞吐量 / 并发数
    grouped['Avg per-request throughput(tokens/s)'] = (
        grouped['Avg generation throughput(tokens/s)'] / grouped['Running requests']
    )
    
    # 按并发数排序
    grouped = grouped.sort_values('Running requests').reset_index(drop=True)
    
    # 保留两位小数
    grouped['Avg generation throughput(tokens/s)'] = grouped['Avg generation throughput(tokens/s)'].round(2)
    grouped['Avg per-request throughput(tokens/s)'] = grouped['Avg per-request throughput(tokens/s)'].round(2)
    
    return grouped


def save_csv(df: pd.DataFrame, filepath: str):
    """
    保存结果到 CSV 文件

    Args:
        df: 结果数据框
        filepath: 输出文件路径
    """
    df.to_csv(filepath, index=False)
    print(f"结果已保存到：{filepath}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='vLLM 吞吐量测试数据分析器 - 计算不同并发数下的平均吞吐量'
    )
    parser.add_argument(
        '-i', '--input',
        default='../output/vllm_metrics.csv',
        help='输入 CSV 文件路径（默认：output/vllm_metrics.csv）'
    )
    parser.add_argument(
        '-o', '--output',
        default='../output/throughput_summary.csv',
        help='输出 CSV 文件路径（默认：output/throughput_summary.csv）'
    )
    parser.add_argument(
        '-c', '--config',
        default='../config/config.json',
        help='配置文件路径（默认：config/config.json）'
    )
    
    args = parser.parse_args()
    
    # 检查输入文件是否存在
    if not Path(args.input).exists():
        print(f"错误：输入文件不存在：{args.input}")
        sys.exit(1)
    
    # 检查配置文件是否存在
    if not Path(args.config).exists():
        print(f"错误：配置文件不存在：{args.config}")
        sys.exit(1)
    
    print("=" * 60)
    print("vLLM 吞吐量测试数据分析器")
    print("=" * 60)
    
    # 读取配置文件
    print(f"\n正在读取配置文件：{args.config}")
    config = load_config(args.config)
    max_concurrent = config.get('max_concurrent', 32)
    step = config.get('step', 2)
    print(f"配置：max_concurrent={max_concurrent}, step={step}")
    
    # 读取数据
    df = load_csv(args.input)
    
    # 数据清洗
    print("\n开始数据清洗...")
    df_clean = clean_data(df, config)
    
    if len(df_clean) == 0:
        print("错误：清洗后没有有效数据")
        sys.exit(1)
    
    # 计算吞吐量
    print("\n计算吞吐量...")
    df_result = calculate_throughput(df_clean)
    
    # 保存结果
    save_csv(df_result, args.output)
    
    # 打印结果预览
    print("\n结果预览:")
    print("-" * 60)
    print(df_result.to_string(index=False))
    print("-" * 60)
    print(f"\n共 {len(df_result)} 个并发等级的统计数据")
    print("=" * 60)


if __name__ == '__main__':
    main()
