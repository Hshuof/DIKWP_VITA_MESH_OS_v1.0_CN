# DIKWP-VITA Mesh 部署手册

## A. 本地单节点

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
dikwp-vita serve --ledger data/vitality.db --host 127.0.0.1 --port 8787
python -m http.server 8000 --directory prototype
```

浏览器打开 `http://127.0.0.1:8000`。HTTP 访问日志默认关闭；只有显式增加 `--access-log` 才会启用 Uvicorn 访问日志。

## B. Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

- 驾驶舱：`http://127.0.0.1:8000`
- Collector 健康检查：`http://127.0.0.1:8787/health`
- SQLite 账本：Docker volume `vita-data`

## C. GitHub Pages + 独立 Collector

1. 启用仓库中的 `pages.yml`，部署静态驾驶舱。
2. 在 Collector 环境变量 `VITA_ALLOWED_ORIGINS` 中加入真实 Pages Origin，例如 `https://example.github.io`。
3. 修改 `prototype/index.html` 中 Collector 默认地址，或由用户在页面输入。
4. 开启 `vitality-sync.yml`，聚合 Release 下载增量；若要读取最近 14 天的仓库视图和克隆，需要配置具有相应只读权限的 `TRAFFIC_PAT`。
5. 公共 Collector 应位于 HTTPS 之后，并禁用或最小化反向代理访问日志。

## D. 建立第二镜像节点

节点 A 导出：

```bash
dikwp-vita export --ledger data/vitality.db --node-id node-a --out outputs/node-a.json
```

节点 B 导入：

```bash
dikwp-vita import outputs/node-a.json --ledger data/node-b.db
```

系统按 `event_id` 去重；在相同事件集合上，节点应计算出相同 Merkle root。

## E. 生产门禁

- 不把 `VITA_ALLOWED_ORIGINS=*` 用于公共部署；
- 反向代理必须设置请求体上限和速率限制；
- 高权重事件应使用 Ed25519 签名或可验证 proof；
- 数据库、密钥和公开状态文件应分别备份；
- 所有规则和权重变更必须通过 PR、测试和 before/after 报告；
- 不得将访问量、下载量或生命力分数表述为科学正确性、人格价值或意识证明。
