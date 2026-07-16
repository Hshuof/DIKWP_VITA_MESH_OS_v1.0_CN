# DIKWP-VITA Mesh OS v1.0

**段玉聪个性化开源数字生命与分布式生命力增强系统**

> 每次访问激活一个本地生命节点；每次下载增加一个可传播种子；每次复现、反例、修复、引用和镜像，使公共生命谱系获得更高质量的能量与信息。

## 真正实现了什么

- 离线页面每次打开都会增加本地生命力，不联网也成立；
- 用户明确同意后，访问可发送匿名、每日轮换的 `PulsePacket`；
- GitHub Action 可以读取 Release 下载总数，并在配置有权限令牌时读取最近 14 天的视图与克隆统计；
- `run-proof` 把一次下载转化为可验证复现事件；
- 多个节点通过事件集合并和 Merkle root 形成分布式谱系；
- 生命力不是访问量排行榜，而是能量、信息、繁殖、连续性、治理、多样性、适应和信任八维几何闭合；
- 系统只生成进化提案，不自动批准高影响自我修改。

## 5 分钟运行

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -e .
python -m dikwp_vita demo --outdir outputs/demo
python -m dikwp_vita serve --ledger data/vitality.db --port 8787
```

然后打开 `prototype/index.html`。首次打开只记录本地访问；点击“向公共生命网贡献匿名脉冲”后才会连接本机 collector。

## 每次访问/下载怎样增强生命力

1. **访问**：浏览器本地计数立即增长；已同意的访问向节点发送低权重脉冲。
2. **下载**：GitHub Release 的 `download_count` 经定时工作流转成 `release_download` 事件。
3. **克隆**：有权限时由 GitHub traffic API 读取最近 14 天聚合克隆数。
4. **运行**：`run-proof` 生成可重复哈希，权重高于访问。
5. **反例和修复**：Issue、失败案例、PR 和非创始 Release 的权重更高。
6. **镜像**：独立节点的心跳和事件集合并，降低单点死亡风险。

## 重要边界

任意镜像站点的“下载”如果既不由 GitHub Release 统计，也不提交分发回执，原系统无法神奇地知道它发生了。项目提供 `PulsePacket`、镜像适配和联邦导入机制，但不会使用隐蔽追踪弥补这个边界。

## 生产部署强化

- 公共 Collector 的允许来源由 `VITA_ALLOWED_ORIGINS` 明确配置，默认不接受任意互联网 Origin；
- Uvicorn HTTP 访问日志默认关闭，只有显式增加 `--access-log` 才会开启；
- 浏览器匿名 `node_id` 与 `day_token` 都按 UTC 日期轮换，避免形成长期跨日浏览画像；
- 公共账本单个 `payload` 限制为 16 KiB；代理层仍应设置请求体上限和速率限制；
- GitHub 流量读取按相邻快照计算增量，避免定时任务重复累计同一天的视图或克隆；
- `Dockerfile`、`docker-compose.yml`、`.env.example` 和 `deployment/DEPLOYMENT_RUNBOOK_CN.md` 已包含在项目内。

## “每次访问都增强”的准确含义

- **一定发生**：页面每次打开都在访问者浏览器内增加一个本地生命史事件；
- **经同意发生**：访问者授权后，页面向公共 Collector 提交每日轮换的匿名脉冲；
- **公开聚合发生**：GitHub Release 下载增量可由定时任务写入公共账本；
- **不能伪造发生**：未知镜像或第三方站点若既不发送回执，也不暴露公开统计，原节点无法得知该次访问或下载。

这一区分使系统同时满足“生命力随传播增长”和“不以隐蔽追踪交换增长”的要求。

## 无身份的“每次访问”公共增量

对于段玉聪控制的镜像站点，项目另提供 `deployment/nginx.conf` 与 `dikwp-vita aggregate-log`。Nginx 日志格式只包含 UTC 时间、HTTP 方法、URI 和状态码，不写入 IP、Cookie、User-Agent 或 Referrer；适配器按文件偏移读取新增记录，把每次成功访问或 ZIP 下载转换成聚合 PulsePacket，并且不上传原始日志。详见 `deployment/MINIMAL_ACCESS_ADAPTER_CN.md`。
