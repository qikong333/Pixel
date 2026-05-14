# Handoff

## Current Status

`pyxelate` 已接入现有单图上传流程，项目现在会输出以下对比结果：
- Pillow + OpenCV
- scikit-image
- pixelate
- Pyxelate
- 清晰图案（边缘保留法）

## What Works

- 页面支持单张图片上传。
- 上传后会自动填入原图宽高、像素格 `1x1`、分色 `5`。
- 页面可继续手动修改所有参数。
- 生成流程会以内存方式返回原图和 5 个算法结果的缩略图。
- 点击缩略图后，会通过 `/media/...` 临时路由按需加载对应大图。
- 每个结果卡片都有 `下载 JPG` 按钮，直接指向当前会话中的大图资源。
- 页面刷新或离开时，会通过 `/clear-session` 主动删除当前会话中的原图和结果大图。
- 自动化测试覆盖了 `Pyxelate` 接入、上传前端、缩略图结果链路和内存媒体会话。

## How To Run

- 生成结果：`.venv/bin/python generate.py`
- 启动服务：`.venv/bin/python server.py`
- 跑测试：`.venv/bin/python -m unittest test_generate.py`

## Known Traps

- 系统自带 `python3` 可能没有装全依赖，优先使用项目内 `.venv/bin/python`。
- `pyxelate` 首次导入和运行相对更慢，测试会比纯字符串测试稍重。
- 当前 `server.py` 使用 `cgi` 解析 multipart 表单，在 Python 3.13 之后需要替换。
- 当前大图在 `1x1` 像素格下仍然可能生成较慢，但页面已有 loading 提示。
- 大图资源不落盘，只保存在服务进程内存中；刷新页面会主动清理，TTL 只是异常中断时的兜底，服务关闭后也会全部消失。
- 历史 `uploads/` / `output/` 文件仍然留在仓库里，新流程不会再使用它们。
- 仓库当前不是 git 仓库，后续如果要继续工程化，建议先补版本控制和依赖安装说明。

## Next Steps

- 如果你想继续提升体验，可以把表单提交改成 AJAX，这样 loading 和错误提示会更丝滑。
- 如果你想继续完善性能，可以给大图弹窗增加独立 loading 状态，避免首次点击大图时出现短暂空白。
- 如果你想提高稳定性，可以把 `cgi` 上传解析替换成更现代的 multipart 处理方案。
- 如果你想回收磁盘空间，可以单独清理历史 `uploads/` / `output/` 目录中的旧文件。
