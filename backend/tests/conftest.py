"""Pytest 环境引导：在导入任何 app 模块之前，先把敏感配置设成测试值。

为什么要在 conftest 顶部做这件事：
  app.core.config 在 import 时就会实例化 settings（模块级单例），
  而 pydantic-settings 的优先级是「环境变量 > .env 文件 > 默认值」。
  测试如果沿用开发机的 .env，结果会随机器而变；这里主动覆盖，
  保证不论在哪台机器上跑，测试结果都一样。
"""
import os

from cryptography.fernet import Fernet

os.environ["SSH_CREDENTIAL_KEY"] = Fernet.generate_key().decode()
os.environ["ALERT_WEBHOOK_TOKEN"] = "unit-test-token"
os.environ["ALERT_HEAL_COOLDOWN_SECONDS"] = "600"
# ENVIRONMENT 现在收敛为 development/staging/production 三个枚举值，
# 单测用 development 语义（逃生舱测试会再单独 monkeypatch）。
os.environ["ENVIRONMENT"] = "development"
