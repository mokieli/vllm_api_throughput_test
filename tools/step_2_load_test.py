import asyncio
import aiohttp
import json
import time
from datetime import datetime
import logging
from rich.logging import RichHandler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[RichHandler()]
)
logger = logging.getLogger('load_test')

def load_config():
    """从config.json加载配置"""
    try:
        with open('../config/config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 验证必填字段
        required_fields = [
            'max_concurrent', 'step', 'api_url', 'api_key', 
            'model', 'max_tokens', 'temperature', 'top_p', 'request_timeout'
        ]
        
        for field in required_fields:
            if field not in config:
                raise ValueError(f"配置文件缺少必填字段: {field}")
        
        # 验证字段类型
        if not isinstance(config['max_concurrent'], int):
            raise ValueError("max_concurrent 必须是整数")
        if not isinstance(config['step'], int):
            raise ValueError("step 必须是整数")
        if not isinstance(config['max_tokens'], int):
            raise ValueError("max_tokens 必须是整数")
        if not isinstance(config['temperature'], (int, float)):
            raise ValueError("temperature 必须是数字")
        if not isinstance(config['top_p'], (int, float)):
            raise ValueError("top_p 必须是数字")
        if not isinstance(config['request_timeout'], int):
            raise ValueError("request_timeout 必须是整数")
        
        # 读取批次间等待时间（可选，默认为0）
        if 'interval_between_batches' in config:
            if not isinstance(config['interval_between_batches'], int):
                raise ValueError("interval_between_batches 必须是整数")
        else:
            config['interval_between_batches'] = 0
        
        return config
    except FileNotFoundError:
        logger.error("配置文件 config/config.json 未找到")
        exit(1)
    except json.JSONDecodeError:
        logger.error("配置文件格式错误，请检查JSON语法")
        exit(1)
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        exit(1)

def generate_concurrent_sequence(max_concurrent, step):
    """生成测试并发数序列"""
    sequence = [1]  # 第一轮固定为1
    
    current = step
    while current <= max_concurrent:
        sequence.append(current)
        current += step
    
    return sequence

async def make_request(session, config):
    """发起单个API请求"""
    start_time = time.time()
    error_type = None
    
    try:
        url = config['api_url'].strip('`')  # 移除可能的反引号
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config["api_key"]}'
        }
        
        data = {
            'model': config['model'],
            'messages': [{"role": "user", "content": "什么是人工智能？请详细解释。"}],
            'temperature': config['temperature'],
            'top_p': config['top_p'],
            'max_tokens': config['max_tokens'],
            'stream': False
        }
        
        async with session.post(
            url,
            headers=headers,
            json=data,
            timeout=aiohttp.ClientTimeout(total=config['request_timeout'])
        ) as response:
            if response.status == 200:
                await response.json()
            else:
                error_type = f"HTTP {response.status}"
    except asyncio.TimeoutError:
        error_type = "Timeout"
    except aiohttp.ClientError as e:
        error_type = f"ClientError: {str(e)}"
    except Exception as e:
        error_type = f"OtherError: {str(e)}"
    
    end_time = time.time()
    return end_time - start_time, error_type

async def run_test_round(session, config, concurrent):
    """运行一轮测试"""
    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始测试并发数: {concurrent}")
    
    start_time = time.time()
    tasks = []
    
    # 使用Semaphore控制并发数
    semaphore = asyncio.Semaphore(concurrent)
    
    async def bounded_request():
        async with semaphore:
            return await make_request(session, config)
    
    # 创建并发任务
    for _ in range(concurrent):
        tasks.append(bounded_request())
    
    # 等待所有任务完成
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # 统计结果
    success_count = 0
    request_times = []
    error_counts = {}
    
    for req_time, error in results:
        if error is None:
            success_count += 1
            request_times.append(req_time)
        else:
            if error in error_counts:
                error_counts[error] += 1
            else:
                error_counts[error] = 1
    
    # 计算统计数据
    avg_time = sum(request_times) / len(request_times) if request_times else 0
    fastest_time = min(request_times) if request_times else 0
    slowest_time = max(request_times) if request_times else 0
    success_rate = (success_count / concurrent) * 100 if concurrent > 0 else 0
    failure_count = concurrent - success_count
    
    # 打印结果
    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 并发数: {concurrent}")
    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 本轮总耗时: {total_time:.2f} 秒")
    if request_times:
        logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 平均单请求耗时: {avg_time:.2f} 秒")
        logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 最快/最慢单请求耗时: {fastest_time:.2f} / {slowest_time:.2f} 秒")
    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 成功数/总请求数: {success_count}/{concurrent} ({success_rate:.2f}%)")
    if failure_count > 0:
        logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 失败数: {failure_count}")
        for error, count in error_counts.items():
            logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   - {error}: {count} 次")
    logger.info("-" * 80)

async def main():
    """主函数"""
    # 加载配置
    config = load_config()
    
    # 生成并发序列
    concurrent_sequence = generate_concurrent_sequence(
        config['max_concurrent'],
        config['step']
    )
    
    logger.info(f"测试并发数序列: {concurrent_sequence}")
    logger.info("-" * 80)
    
    # 创建aiohttp会话
    async with aiohttp.ClientSession() as session:
        # 运行每轮测试
        for i, concurrent in enumerate(concurrent_sequence):
            await run_test_round(session, config, concurrent)
            
            # 在批次之间添加等待时间（除了最后一轮）
            if i < len(concurrent_sequence) - 1 and config['interval_between_batches'] > 0:
                wait_time = config['interval_between_batches']
                logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 等待 {wait_time} 秒后进行下一轮测试...")
                await asyncio.sleep(wait_time)
    
    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 测试完成")

if __name__ == "__main__":
    asyncio.run(main())
