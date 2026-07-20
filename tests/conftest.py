"""
命理乾坤 — 单元测试配置文件
"""
import sys
import os

# 确保 cloud-functions/api 在 Python 路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UTILS_DIR = os.path.join(PROJECT_ROOT, "cloud-functions", "api")
sys.path.insert(0, UTILS_DIR)
