## 1. 规格与上下文

- [x] 1.1 将 delta 同步到 `openspec/specs/min-agent-app/spec.md`
- [x] 1.2 更新 `openspec/config.yaml` 产品定位与验收句（对齐总体规划 ChatOps；去掉睿德志行佣金主验收）
- [x] 1.3 更新根 `README.md` 说明与示例命令

## 2. 代码与测试

- [x] 2.1 `gateway.py`：中性示例桩数据；注释改为预留 go-admin
- [x] 2.2 `agent.py` / `tools/query.py`：prompt 与 description 去实习佣金叙事
- [x] 2.3 更新 `tests/` 中依赖旧验收句或桩店名的用例与脚本注释
- [x] 2.4 单测：本机无 `uv`/项目 venv 时未跑通；逻辑为 Mock 字符串替换，无行为变更。有环境时执行 `uv run python -m unittest discover -s tests -p "test_*.py" -v`

## 3. 总体规划

- [x] 3.1 在 `documents/系统总体规划.md` 注明本仓 M0 文案已清（不勾 R3 接 REST 项）
