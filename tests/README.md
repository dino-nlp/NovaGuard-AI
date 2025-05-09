# NovaGuard-AI Test
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

# Integration graph test
python -m unittest tests.test_integration_graph
```

Hoặc để chạy tất cả các test trong thư mục tests: 

```bash
python -m unittest discover tests

```

### Issue

```bash
Error: File was unable to be removed Error: EACCES: permission denied, unlink '/home/dino/Documents/actions-runner/_work/novaguard-test-project/novaguard-test-project/results/novaguard.sarif'
```


```bash
sudo rm -rf /home/dino/Documents/actions-runner/_work/novaguard-test-project/novaguard-test-project/results
```
