# Privacy Constitution / 隐私宪章

DIKWP-VITA Mesh deliberately separates **local vitality** from **public network vitality**.

1. Opening the offline dashboard always increments a local counter in the browser. No network request is required.
2. A public pulse is sent only after explicit opt-in. Consent can be withdrawn in the dashboard.
3. The reference collector does not store raw IP addresses, user-agent strings, cookies, names, email addresses or exact location.
4. Anonymous pulses use a locally generated, daily rotating pseudonymous token and are capped by event type.
5. High-value contributions should be submitted as signed public evidence, GitHub issues, reproducible runs or pull requests.
6. Deployers must disable or document reverse-proxy access logs if they claim privacy-equivalent behavior.
7. No pulse may be used to infer personal value, personality, political preference, medical status or legal identity.

8. Anonymous browser `node_id` values rotate daily; the collector must not use reverse-proxy logs to reconstruct a persistent identity.
9. The reference CLI disables HTTP access logs by default. Enabling `--access-log` changes the privacy posture and must be disclosed.
10. Public ledger payloads are capped at 16 KiB; operators should additionally configure proxy-level rate and body-size limits.

11. A controlled mirror may use the optional minimal access adapter. Its reference Nginx format records only UTC timestamp, method, URI and status; it excludes IP, cookies, user-agent and referrer, and raw logs are never uploaded to the vitality collector.
