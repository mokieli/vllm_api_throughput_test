#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vLLM 日志解析器 - CSV 输出版
实时解析 vLLM Docker 容器日志，提取 Engine 性能指标，并写入到 CSV 文件中。
"""

import subprocess
import re
import sys
import json
import csv
import os
from typing import Optional, List, Any

# ==================== 全局配置 ====================

# CSV 输出文件名
CSV_OUTPUT_FILE = "../output/vllm_metrics.csv"

# 日志刷新间隔（秒），用于控制刷新频率
REFRESH_INTERVAL = 0.1

# ==================== 正则表达式定义 ====================

# Engine 性能指标日志正则表达式
# 示例：(APIServer pid=1) INFO 03-01 08:06:00 [loggers.py:259] Engine 000: Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 215.8 tokens/s, Running: 8 reqs, Waiting: 0 reqs, GPU KV cache usage: 8.2%, Prefix cache hit rate: 0.0%
ENGINE_LOG_PATTERN = re.compile(
    r'\(APIServer pid=\d+\)\s+INFO\s+(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+'
    r'\[loggers.py:\d+\]\s+(Engine\s+\d+):\s+'
    r'Avg prompt throughput:\s+([\d.]+)\s+tokens/s,\s+'
    r'Avg generation throughput:\s+([\d.]+)\s+tokens/s,\s+'
    r'Running:\s+(\d+)\s+reqs,\s+'
    r'Waiting:\s+(\d+)\s+reqs,\s+'
    r'GPU KV cache usage:\s+([\d.]+)%,\s+'
    r'Prefix cache hit rate:\s+([\d.]+)%'
)


# ==================== 日志解析器 ====================

class LogParser:
    """日志解析器类"""

    @staticmethod
    def parse_engine_log(line: str) -> Optional[List[Any]]:
        """
        解析 Engine 性能指标日志

        Args:
            line: 日志行字符串

        Returns:
            解析后的数据列表，包含 [timestamp, prompt_throughput, 
            generation_throughput, running, waiting, gpu_kv_cache, prefix_cache_hit]
            如果解析失败则返回 None
        """
        match = ENGINE_LOG_PATTERN.match(line.strip())
        if match:
            return [
                match.group(1),                    # Timestamp
                match.group(3),                    # Avg prompt throughput (tokens/s)
                match.group(4),                    # Avg generation throughput (tokens/s)
                match.group(5),                    # Running requests
                match.group(6),                    # Waiting requests
                match.group(7),                    # GPU KV cache usage (%)
                match.group(8)                     # Prefix cache hit rate (%)
            ]
        return None


# ==================== CSV 写入器 ====================

class CSVWriter:
    """CSV 写入器类"""

    # CSV 表头
    HEADERS = [
        'Timestamp',
        'Avg prompt throughput(tokens/s)',
        'Avg generation throughput(tokens/s)',
        'Running requests',
        'Waiting requests',
        'GPU KV cache usage(%)',
        'Prefix cache hit rate(%)'
    ]

    def __init__(self, filepath: str):
        """
        初始化 CSV 写入器

        Args:
            filepath: CSV 文件路径
        """
        self.filepath = filepath
        self.file = None
        self.writer = None
        self._init_csv()

    def _init_csv(self):
        """初始化 CSV 文件，写入表头"""
        # 如果文件已存在，先删除它，确保每次启动都是新的 CSV 文件
        if os.path.exists(self.filepath):
            os.remove(self.filepath)
            print(f"已删除旧 CSV 文件：{self.filepath}")
        
        # 创建新文件并写入表头
        self.file = open(self.filepath, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file)
        self.writer.writerow(self.HEADERS)
        self.file.flush()
        print(f"已创建新的 CSV 文件：{self.filepath}")

    def write_row(self, row: List[Any]):
        """
        写入一行数据到 CSV 文件

        Args:
            row: 数据行列表
        """
        self.writer.writerow(row)
        self.file.flush()

    def close(self):
        """关闭 CSV 文件"""
        if self.file:
            self.file.close()


# ==================== Docker 日志监控器 ====================

class DockerLogMonitor:
    """Docker 日志监控器类"""

    def __init__(self, container_name: str, csv_filepath: str):
        """
        初始化 Docker 日志监控器

        Args:
            container_name: Docker 容器名称
            csv_filepath: CSV 输出文件路径
        """
        self.container_name = container_name
        self.parser = LogParser()
        self.csv_writer = CSVWriter(csv_filepath)
        self.running = True

    def process_line(self, line: str):
        """
        处理单行日志

        Args:
            line: 日志行字符串
        """
        line = line.strip()
        if not line:
            return

        # 尝试解析 Engine 日志
        parsed_data = self.parser.parse_engine_log(line)
        if parsed_data:
            self.csv_writer.write_row(parsed_data)
            # 在终端也输出解析结果
            print(f"[CSV] {parsed_data[0]} | Prompt: {parsed_data[1]} | Gen: {parsed_data[2]} | "
                  f"Running: {parsed_data[3]} | Waiting: {parsed_data[4]}")

    def run(self):
        """运行日志监控"""
        print(f"开始监控容器：{self.container_name}")
        print(f"CSV 输出文件：{self.csv_writer.filepath}")
        print("按 Ctrl+C 退出\n")

        # 启动 docker logs 命令
        # 使用 --since 1s 只获取最近 1 秒的日志，然后 -f 跟踪新日志
        # 这样可以避免输出程序启动前的历史日志
        process = subprocess.Popen(
            ['docker', 'logs', '--since', '1s', '-f', self.container_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        try:
            for line in process.stdout:
                self.process_line(line)

        except KeyboardInterrupt:
            print("\n\n监控已停止")
        finally:
            process.terminate()
            process.wait()
            self.csv_writer.close()
            print(f"CSV 文件已关闭：{self.csv_writer.filepath}")


# ==================== 配置文件读取器 ====================

def load_config(config_path: str = "../config/config.json") -> dict:
    """
    从配置文件读取配置

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典

    Raises:
        FileNotFoundError: 配置文件不存在
        KeyError: 配置文件中缺少必要字段
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在：{config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    if 'docker_container_name' not in config:
        raise KeyError("配置文件中缺少 'docker_container_name' 字段")

    return config


# ==================== 主程序 ====================

def print_usage():
    """打印使用说明"""
    print("用法：python vllm_log_to_csv.py [config_file]")
    print("")
    print("参数:")
    print("  config_file  配置文件路径（默认为当前目录的 config.json）")
    print("")
    print("示例:")
    print("  python tools/vllm_log_to_csv.py")
    print("  python tools/vllm_log_to_csv.py config/config.json")
    print("")
    print("输出:")
    print(f"  CSV 文件：{CSV_OUTPUT_FILE}")


def main():
    """主函数"""
    # 获取配置文件路径
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = "../config/config.json"

    try:
        # 读取配置文件
        config = load_config(config_path)
        container_name = config['docker_container_name']

        # 创建并启动监控器
        monitor = DockerLogMonitor(container_name, CSV_OUTPUT_FILE)
        monitor.run()

    except FileNotFoundError as e:
        print(f"错误：{e}")
        print_usage()
        sys.exit(1)
    except KeyError as e:
        print(f"错误：{e}")
        print_usage()
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"错误：配置文件格式错误 - {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
