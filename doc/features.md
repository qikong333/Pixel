## Feature: Pyxelate fifth algorithm

Date: 2026-04-23

### Summary
把 `pyxelate` 接入现有图片批量像素化流程，作为第 5 种对比算法输出 JPG 和 SVG，并展示在首页对比页面中。

### Usage
1. 使用 `.venv/bin/python server.py` 启动服务。
2. 打开 `http://localhost:8082`。
3. 调整尺寸、像素格和分色数量后提交。
4. 在结果页查看 `Pyxelate` 一列，或下载对应 SVG。

### Changed Files
- `generate.py`
- `server.py`
- `test_generate.py`
- `index.html`

### Edge Cases
- 如果运行环境没有安装 `pyxelate`，生成流程会在 `Pyxelate` 步骤打印错误，不会阻塞其他算法输出。
- `pyxelate` 对某些调色板大小会发出冗余颜色警告，但仍可生成输出。

### Tests
已运行：`.venv/bin/python -m unittest test_generate.py`

### Maintenance Notes
测试当前依赖 `.venv` 内的 `pyxelate` 安装。若切换 Python 环境，需要先同步安装 `requirements.txt`。

## Feature: Single-image upload frontend

Date: 2026-05-07

### Summary
前端改为单张图片上传工作流，移除了首页默认样例图和默认参数值。上传图片后，浏览器会自动读取原图宽高，并填入宽高、像素格 `1x1`、分色 `5` 作为推荐参数；生成后可继续复用同一张图片反复调参。

### Usage
1. 使用 `.venv/bin/python server.py` 启动服务。
2. 打开 `http://localhost:8082`。
3. 点击上传区域选择单张图片。
4. 页面会自动填入原图宽高、像素格 `1x1`、分色 `5`。
5. 如有需要手动修改参数，再点击“生成像素画对比”。

### Changed Files
- `generate.py`
- `server.py`
- `test_generate.py`
- `index.html`

### Edge Cases
- 初始首页不展示任何历史默认图片，但如果刚刚成功生成过结果，刷新后会保留当前图片的结果页和可复用参数。
- 若未上传图片且没有可复用的已上传图片，提交时会提示重新上传。
- `cgi` 方案在 Python 3.13 之后会移除，后续可以替换为更现代的 multipart 解析实现。

### Tests
- `.venv/bin/python -m unittest test_generate.py`
- `curl -i -s -F image_file=@img/SLIDE1-original\ artwork.jpeg -F img_w=120 -F img_h=160 -F px_w=1 -F px_h=1 -F num_colors=5 http://localhost:8082/generate`
- `curl -s http://localhost:8082/`

### Maintenance Notes
当前结果页通过隐藏字段 `source_image` 复用最近一次上传图片，因此用户在不重新上传的情况下也能继续调参重生成。

## Feature: In-memory one-shot generation

Date: 2026-05-07

### Summary
生成流程改为纯内存一次性响应：上传图片不落盘，像素化结果不落盘，服务端在同一请求里直接返回包含原图预览和各算法结果的 HTML。刷新页面或关闭服务后，这些结果会自动消失，不再占用服务器文件空间。

### Usage
1. 使用 `.venv/bin/python server.py` 启动服务。
2. 打开 `http://localhost:8082`。
3. 上传图片后点击“生成像素画对比”。
4. 页面会显示 loading 遮罩，完成后直接展示结果。

### Changed Files
- `generate.py`
- `server.py`
- `test_generate.py`

### Edge Cases
- 大尺寸图片在 `1x1` 像素格下生成会比较慢，页面会显示 loading。
- 当像素网格过大时，SVG 会被自动跳过，以避免一次性返回过大的页面数据。
- 当前结果只存在于当前响应页面中，刷新后需要重新上传图片。

### Tests
- `.venv/bin/python -m unittest test_generate.py`

### Maintenance Notes
当前项目目录中历史 `uploads/` / `output/` 文件不会被新流程继续使用，但也不会自动删除；如果你想，我可以下一步单独帮你清理这些旧文件。

## Feature: Thumbnail-first result delivery

Date: 2026-05-07

### Summary
结果页改成“缩略图优先”模式。页面只内嵌原图和 5 个算法结果的缩略图，默认不再生成或展示 SVG；用户点击卡片时，浏览器才会向服务端临时会话路由按需加载对应大图，从而显著减轻刷新和回显压力。页面刷新或离开时，前端还会主动通知后端删除当前会话中的原图和结果数据。
每个算法结果卡片同时提供 `下载 JPG` 按钮，用户可以直接下载当前生成的大图结果。

### Usage
1. 使用 `.venv/bin/python server.py` 启动服务。
2. 打开 `http://localhost:8082`。
3. 上传图片并点击“生成像素画对比”。
4. 结果页先展示缩略图。
5. 点击任意缩略图后，再按需加载对应大图进行放大预览。
6. 点击 `下载 JPG` 可以下载当前算法的生成结果。

### Changed Files
- `generate.py`
- `server.py`
- `test_generate.py`

### Edge Cases
- 大图资源只保存在服务进程内存中，不会写入磁盘。
- 结果页刷新后会回到空白上传态，并主动清理当前会话中的原图和结果大图。
- 服务进程关闭后，所有临时大图都会一起消失。
- 当前没有保留 SVG 下载入口；如果后续需要，可以再改成单独按需生成。
- `下载 JPG` 链接依赖当前内存会话；刷新页面或离开当前结果页后，该下载地址会失效。

### Tests
- `.venv/bin/python -m unittest test_generate.py`
- `curl -s http://localhost:8082/`
- `curl -i -s -F image_file=@img/SLIDE1-original\ artwork.jpeg -F img_w=120 -F img_h=160 -F px_w=5 -F px_h=5 -F num_colors=5 http://localhost:8082/generate`
- `curl -s -D - http://localhost:8082/media/<session>/<media_id>`

### Maintenance Notes
服务端通过内存会话缓存大图；页面刷新或离开时会主动删除当前会话，约 10 分钟的 TTL 只作为异常中断时的兜底清理策略。
