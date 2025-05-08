# NovaGuard-AI
AI Code review

Run test:

```bash
python -m unittest tests.core.test_config_loader
python -m unittest tests.core.test_prompt_manager
python -m unittest tests.core.test_sarif_generator
python -m unittest tests.core.test_ollama_client
python -m unittest tests.core.test_tool_runner
python -m unittest tests.orchestrator.test_nodes
python -m unittest tests.orchestrator.test_graph_definition

```

Hoặc để chạy tất cả các test trong thư mục tests: 

```bash
python -m unittest discover tests

```