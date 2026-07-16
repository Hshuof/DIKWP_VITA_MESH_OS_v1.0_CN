# 快速启动

## 1. 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 2. 生成本地节点

```bash
dikwp-vita init
```

## 3. 运行确定性演示

```bash
dikwp-vita demo --outdir outputs/demo
```

## 4. 启动本地生命节点

```bash
dikwp-vita serve --ledger data/vitality.db --artifact DIKWP-VITA-MESH --port 8787
```

浏览器打开 `prototype/index.html`。页面打开会先增加本地计数，不会发送网络请求；点击同意后才向 `127.0.0.1:8787` 发送匿名脉冲。

## 5. 把下载转化为复现

```bash
dikwp-vita run-proof --share http://127.0.0.1:8787 --sign
```

## 6. 查看状态和进化提案

```bash
dikwp-vita status --ledger data/vitality.db --artifact DIKWP-VITA-MESH
```

## 7. 联邦复制

节点 A：

```bash
dikwp-vita export --ledger data/vitality.db --node-id node-a --out outputs/node-a-bundle.json
```

节点 B：

```bash
dikwp-vita import outputs/node-a-bundle.json --ledger data/node-b.db
```

事件按 `event_id` 去重，两个节点最终可获得同一 Merkle root。

## 8. Docker 一键部署

```bash
cp .env.example .env
docker compose up -d --build
```

打开 `http://127.0.0.1:8000`。完整生产部署说明见 `deployment/DEPLOYMENT_RUNBOOK_CN.md`。

## 9. 隐私与来源配置

公共部署必须把真实页面 Origin 写入 `VITA_ALLOWED_ORIGINS`。Collector 默认关闭 HTTP 访问日志；只有运行 `dikwp-vita serve --access-log ...` 时才会显式开启。

## 10. 镜像站点每次访问的无身份聚合

```bash
dikwp-vita aggregate-log \
  --log data/nginx/vita_minimal.log \
  --state data/access_offset.json \
  --event-type page_access \
  --path-regex '^/$|^/index\.html$' \
  --share http://127.0.0.1:8787
```

该命令只读取不含 IP 等身份字段的最小化日志，并只处理自上次运行后的新增字节。
