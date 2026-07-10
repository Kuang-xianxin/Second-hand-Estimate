# Hermes 修复任务：实时估价连续 0 样本与 SSE Network Error

> 日期：2026-07-10
> 优先级：P0 线上故障
> 设计与验收：Codex
> 实施：Hermes

## 1. 用户可见症状

查询 `ixus 130` 时，多组关键词连续显示“已收集 0 条原始样本”，进入第二轮后前端显示 `network error`，估价无法完成。

## 2. 已确认事实

### 2.1 0 样本不是普通关键词无结果

线上 `guessr.service` 日志在 2026-07-10 15:41～15:43 持续出现：

```text
响应解析失败: 'utf-8' codec can't decode byte 0x80 in position 10: invalid start byte
```

说明闲鱼搜索接口已经返回响应，但响应体解析失败，所有候选数据被丢弃。

当前 `backend/app/crawler/xianyu.py` 的 `_try_decode_body()` 首先执行：

```python
json.loads(response_body)
```

但只捕获 `json.JSONDecodeError`。当 `bytes` 不是 UTF-8 文本时，`json.loads()` 会抛出 `UnicodeDecodeError`，异常直接逃逸，后面的 gzip/zlib 检测不会执行。

### 2.2 Network Error 是 SSE 被服务重启打断

线上日志显示 15:43:59 正在处理估价的 `guessr.service` 及其 Chrome 子进程被 SIGKILL。浏览器正在读取的 SSE 连接被直接断开，因此前端只能得到网络层错误，而不是后端 `event: error`。

### 2.3 服务器存在两个冲突的后端 Unit

当前同时存在：

- `guessr.service`：实际服务，监听 `127.0.0.1:8000`。
- `guessr-backend.service`：监听 `0.0.0.0:8000`，每 3 秒重启一次并报 `address already in use`。

诊断时 `guessr-backend.service` 的重启计数已经超过 1000。它持续消耗 CPU、污染日志并增加错误重启风险。

### 2.4 流式入口缺少早期失败分类

`_debug_not_enough_items()` 已存在于 `backend/app/api/valuate.py`，但 `/api/valuate/stream` 的关键词循环没有在空批次后调用它。因此系统会继续执行多组关键词和第二轮，而不是在首次明确的登录、风控、接口或解析故障时停止。

## 3. 修复目标

1. 正确解析闲鱼搜索接口响应，恢复有效样本采集。
2. 解析失败时返回明确错误，不再伪装成“关键词 0 条”。
3. SSE 发生服务端异常时尽可能发出结构化 `event: error`。
4. 服务器只保留一个 canonical 后端 Unit。
5. 为响应解码和空结果分类增加回归测试。

## 4. 非目标

- 不改估价算法、RAG、LangGraph 或前端视觉样式。
- 不更换爬虫框架。
- 不修改闲鱼账号、Cookie 内容或风控策略。
- 不批量清理仓库调试文件。
- 不顺带修改当前用户已有的 `frontend/package-lock.json` 工作区变更。

## 5. 代码修改设计

### 5.1 抽取可测试的响应解码函数

修改 `backend/app/crawler/xianyu.py`：

将内嵌 `_try_decode_body()` 抽取为模块级纯函数，例如：

```python
def decode_xianyu_json_body(
    body: bytes,
    *,
    content_encoding: str | None = None,
) -> dict | None:
    ...
```

处理顺序：

1. 空 Body 直接返回 `None`。
2. 尝试 UTF-8 JSON，捕获：
   - `UnicodeDecodeError`
   - `json.JSONDecodeError`
   - `TypeError`
3. 根据 `Content-Encoding` 和魔数尝试解压：
   - gzip：`1f 8b`
   - zlib：常见 `78 01`、`78 9c`、`78 da`
   - 若线上响应头明确为 `br`，使用 Brotli；依赖必须显式写入 `requirements.txt`，不得依赖传递依赖。
   - 若响应头明确为 `zstd`，使用 zstandard；同样显式声明依赖。
4. 每种解压结果再次执行 UTF-8 JSON 解析。
5. 所有候选均失败时返回 `None`，不得从 Response Handler 抛出解码异常。

不要根据未经确认的两个字节猜测压缩格式。先记录响应头中的 `content-encoding` 和 Body 前 20 字节 Hex，再决定是否增加 Brotli/Zstd。

### 5.2 增加安全诊断字段

在单次搜索的调试摘要中增加：

```python
response_parse_error_count: int
response_content_encodings: list[str]
response_body_magic_samples: list[str]
```

限制要求：

- Hex 只保留前 20 字节。
- 最多保留 3 个样本。
- 不记录 Cookie、完整 URL Query、响应正文或用户身份信息。

当 `decode_xianyu_json_body()` 返回 `None` 时，递增 `response_parse_error_count`。

### 5.3 修复空结果分类

修改 `backend/app/api/valuate.py::_debug_not_enough_items()`：

- `response_count > 0` 且 `response_parse_error_count > 0` 且 `raw_item_count == 0`：返回 502，文案为“闲鱼接口响应解析失败，请稍后重试或联系管理员检查响应编码”。
- 登录态标记仍返回 401。
- 风控标记仍返回 429。
- 真正无商品数据才返回 422。

优先级建议：

```text
明确风控/登录标记
→ HTTP 401/403/429
→ 响应解析失败
→ 未命中搜索接口
→ 普通空结果
```

### 5.4 流式入口首次明确失败时熔断

修改 `/api/valuate/stream` 的关键词循环：

```python
batch = await crawler.search(...)

if not batch:
    failure = _debug_not_enough_items(crawler, q)
    if failure["status_code"] in (401, 429, 502):
        yield sse_error(failure["detail"], code=failure["status_code"])
        mark_finished()
        return
```

要求：

- 不能把真正的普通 0 结果立即熔断，仍允许尝试下一关键词变体。
- 解析失败、登录失效、风控和未命中接口属于系统性失败，应停止后续变体。
- 前端错误事件中包含稳定的机器码，例如：
  - `XIANYU_LOGIN_REQUIRED`
  - `XIANYU_RISK_CONTROL`
  - `XIANYU_RESPONSE_DECODE_FAILED`
  - `XIANYU_SEARCH_ENDPOINT_MISSED`

### 5.5 保证浏览器资源释放

`XianyuCrawler.search_sync()` 中的 Browser 和 Context 必须放入 `try/finally`：

- 无论 `page.goto()`、响应解析、滚动还是标准化是否异常，都关闭 Page/Context/Browser。
- Close 自身异常只记录，不覆盖原始异常。
- 不在每个响应回调中创建新的浏览器。

### 5.6 前端保留后端错误语义

修改 `frontend/src/views/HomeView.vue`：

- `event: error` 时先把所有 Pending Step 标为 Error，再 Reject。
- 展示后端的 `detail` 和稳定错误码。
- 只有真正的 Fetch/SSE 连接断开时显示“与估价服务的流式连接中断”，不要统一显示 `network error`。
- 登录相关错误码触发登录弹窗；解析错误不触发登录弹窗。

## 6. 测试要求

新增 `backend/tests/test_xianyu_response_decode.py`：

1. UTF-8 JSON Bytes 能解析。
2. 非 UTF-8随机 Bytes 不抛异常，返回 `None`。
3. gzip JSON 能解析。
4. zlib JSON 能解析。
5. 若实现 Brotli/Zstd，分别增加对应测试。
6. 空 Body 返回 `None`。
7. 非 JSON UTF-8文本返回 `None`。

在估价 API 测试中增加：

1. `response_parse_error_count > 0` 映射为 502 和 `XIANYU_RESPONSE_DECODE_FAILED`。
2. 风控映射为 429。
3. 登录失效映射为 401。
4. 普通无结果保持 422，并继续尝试下一关键词。
5. 流式入口首次出现系统性失败后不再调用第二个关键词。
6. 后端异常以 `event: error` 结束，而不是静默断流。

前端至少验证：

- SSE Error Detail 被展示。
- Decode Error 不会弹登录框。
- Login Required 会弹登录框。

## 7. 线上服务修复

### 7.1 审批门

停止或禁用 systemd Unit 属于线上服务状态变更。执行前必须取得用户对以下精确范围的批准：

```text
停止并禁用：guessr-backend.service
保留并作为唯一正式后端：guessr.service
不删除任何 Unit 文件
```

### 7.2 获批后的操作原则

1. 记录两个 Unit 的 `systemctl cat`、状态和端口占用。
2. 停止并禁用 `guessr-backend.service`。
3. `systemctl daemon-reload`。
4. 验证只有 `guessr.service` 监听 8000。
5. 不删除 `/etc/systemd/system/guessr-backend.service`，后续单独决定。

### 7.3 部署代码

遵循现有服务器的窄部署方式：

1. 备份将修改的线上文件到 `/opt/guessr/.codex-backups/`。
2. 上传本任务涉及的最小文件集合。
3. 在服务器执行 `py_compile` 和目标测试。
4. 只重启 canonical `guessr.service`。
5. 不执行整仓覆盖，不覆盖 `.env`、数据库或登录态文件。

## 8. 验证命令

本地：

```powershell
Set-Location 'D:\my progect\估二手\backend'
C:\Python314\python.exe -m pytest tests/test_xianyu_response_decode.py -q
C:\Python314\python.exe -m pytest tests -q
C:\Python314\python.exe -m compileall app

Set-Location 'D:\my progect\估二手\frontend'
npm run type-check
npm run build

Set-Location 'D:\my progect\估二手'
git diff --check
```

线上：

```bash
systemctl is-active guessr.service
systemctl is-enabled guessr.service
systemctl is-active guessr-backend.service
ss -ltnp 'sport = :8000'
curl -fsS http://127.0.0.1:8000/health
journalctl -u guessr.service --since '10 minutes ago' --no-pager
```

业务验收：

1. 使用 `ixus 130` 触发一次估价。
2. 首轮至少一个查询变体产生原始样本；如果失败，前端必须显示明确错误码和原因。
3. 不出现连续多组伪 0 结果后才报 Network Error。
4. SSE 正常结束为 `done` 或结构化 `error`。
5. 运行期间服务器只存在一个正式 Uvicorn 后端监听者。
6. Chrome 子进程在请求完成后回落，不持续累积。

## 9. Hermes 回传要求

```markdown
## 修复结果

- Commit：
- 修改文件：
- 实际响应 Content-Encoding：
- 实际 Body 前20字节 Hex：
- 最终采用的解码策略：

## 本地验证

- Pytest：
- Compileall：
- Vue type-check：
- Vue build：

## 线上变更

- 用户是否批准停用 guessr-backend.service：
- Canonical Unit：
- 端口监听者：
- 部署备份路径：
- 健康检查：
- ixus 130 实测结果：

## 未解决风险

- 风控/登录态：
- 浏览器进程：
- 其他：
```
