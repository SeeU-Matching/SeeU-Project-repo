# 故障排除指南

## BGE-M3 模型加载错误

### 问题症状
上传简历或职位描述时，出现以下错误：
```
OSError: [Errno 22] Invalid argument
```

### 原因
这是 Windows 上 tqdm 进度条与 Streamlit 环境的兼容性问题，发生在下载或加载 BGE-M3 模型时。

### 解决方案

#### 方案1：预下载模型（推荐）
在首次使用前，运行：
```bash
download_model.bat
```
这会预先下载模型，避免在 Streamlit 中下载时出错。

#### 方案2：检查环境变量
确保以下环境变量已设置（代码已自动设置）：
- `HF_HUB_DISABLE_PROGRESS_BARS=1`
- `TRANSFORMERS_VERBOSITY=error`
- `TOKENIZERS_PARALLELISM=false`

#### 方案3：使用备用模型
如果 BGE-M3 持续出现问题，可以修改代码使用较小的模型：
- `all-MiniLM-L6-v2` (384维，更小更快)

### 预防措施
1. **首次运行前**：先运行 `download_model.bat` 预下载模型
2. **确保网络连接**：模型下载需要稳定的网络连接
3. **足够的磁盘空间**：模型文件约 1-2GB

## Milvus 连接问题

### 问题症状
- "Fail connecting to server on 127.0.0.1:19530"
- Collection 显示 0 个条目

### 解决方案
1. 检查 Docker 是否运行：
   ```bash
   docker ps
   ```
   应该看到 3 个容器：etcd, minio, milvus

2. 重启 Milvus：
   ```bash
   stop_milvus.bat
   launch_app.bat
   ```

3. 检查端口是否被占用：
   - 19530 (Milvus)
   - 9000 (MinIO)
   - 19121 (Milvus 管理)

## 数据同步问题

### 问题症状
- SQLite 有数据，但 Milvus 为空
- 上传后数据没有出现在匹配结果中

### 解决方案
运行同步脚本：
```bash
sync_to_milvus.bat
```

这会从 SQLite 重新同步所有数据到 Milvus。

## 常见问题

### Q: 为什么每次上传都要运行 sync_to_milvus.bat？
A: 不需要！正常情况下，上传时会自动插入到 Milvus。只有在数据丢失或不一致时才需要运行同步脚本。

### Q: 模型加载很慢？
A: 首次加载需要下载模型（约 1-2GB），可能需要几分钟。后续加载会使用缓存，会快很多。

### Q: 匹配结果为空？
A: 检查：
1. 是否上传了简历和职位描述
2. 运行 `check_milvus.bat` 检查 Milvus 状态
3. 检查 `search_results.csv` 文件是否存在

