# 快速修复指南 - BGE-M3 模型加载错误

## 问题
上传简历时出现：`OSError: [Errno 22] Invalid argument`

## 最快解决方案

### 方法1：预下载模型（推荐，只需做一次）

1. **停止 Streamlit 应用**（如果正在运行）

2. **运行预下载脚本**：
   ```bash
   download_model.bat
   ```
   这会下载 BGE-M3 模型（约 1-2GB，需要几分钟）

3. **重新启动应用**：
   ```bash
   launch_app.bat
   ```

4. **再次尝试上传简历**

### 方法2：使用备用模型（如果方法1不行）

如果 BGE-M3 持续有问题，可以临时使用更小的模型：

修改 `InfoMatching_Team1/matching_utils.py` 第 71 行：
```python
# 将这行：
"bge-m3": {"loader": lambda: BGEM3FlagModel('BAAI/bge-m3', use_fp16=False), "dim": 1024},

# 改为使用备用模型（需要同时修改所有调用处）：
# 或者直接修改上传页面的调用
```

或者在 `InfoMatching_Team4/my_app/pages/1_Resume.py` 中：
```python
# 将第 116 行：
insert_resumes(all_resumes, model_name="bge-m3")

# 改为：
insert_resumes(all_resumes, model_name="all-MiniLM-L6-v2")
```

## 为什么会出现这个问题？

- Windows 上 tqdm 进度条与 Streamlit 环境不兼容
- 模型首次下载时会使用 tqdm 显示进度
- 预下载模型可以避免在 Streamlit 中下载

## 推荐流程

1. **首次使用前**：运行 `download_model.bat`
2. **正常使用**：直接上传，模型会从缓存加载（很快）
3. **如果出错**：检查模型是否已下载，如果没有则运行 `download_model.bat`

