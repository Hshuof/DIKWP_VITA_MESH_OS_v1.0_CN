# 无身份访问/下载聚合适配器

当站点由可控镜像服务器托管时，可以在**不记录 IP、Cookie、User-Agent 或 Referrer**的前提下，让每次成功访问/下载进入公共生命账本。

项目提供的 `deployment/nginx.conf` 只记录四项：UTC 时间、HTTP 方法、URI、状态码。

定时读取新增日志并提交访问增量：

```bash
dikwp-vita aggregate-log \
  --log /var/log/nginx/vita_minimal.log \
  --state data/access_offset.json \
  --event-type page_access \
  --path-regex '^/$|^/index\.html$' \
  --node-id mirror-hainan-web \
  --share https://collector.example.org
```

对镜像 ZIP 下载使用：

```bash
dikwp-vita aggregate-log \
  --log /var/log/nginx/vita_minimal.log \
  --state data/download_offset.json \
  --event-type release_download \
  --path-regex '\.zip$' \
  --node-id mirror-hainan-download \
  --share https://collector.example.org
```

适配器只读取自上次运行后的新增字节，自动处理日志轮换，并按日期生成聚合 PulsePacket。它不会把原始日志上传到 Collector。

部署者仍必须在隐私说明中公开该聚合计数，并设置合理的日志保留期。若不愿保留任何服务器访问记录，可关闭该机制，仅使用浏览器本地生命力与明示同意脉冲。
