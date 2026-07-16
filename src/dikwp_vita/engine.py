from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .crypto import verify_packet
from .ledger import VitalityLedger
from .models import EvolutionProposal, PulsePacket, VitalityDimensions, VitalityState


DEFAULT_WEIGHTS = {
    "page_access": {"base": 0.04, "energy": 0.45, "diversity": 0.10, "continuity": 0.05},
    "release_download": {"base": 0.10, "energy": 0.45, "reproduction": 0.20, "continuity": 0.10},
    "clone": {"base": 0.14, "energy": 0.30, "reproduction": 0.30, "diversity": 0.10},
    "star": {"base": 0.08, "energy": 0.35, "trust": 0.08},
    "fork": {"base": 0.22, "reproduction": 0.40, "diversity": 0.10, "adaptation": 0.08},
    "run_proof": {"base": 0.55, "reproduction": 0.25, "trust": 0.35, "information": 0.15},
    "feedback": {"base": 0.65, "information": 0.40, "adaptation": 0.20, "diversity": 0.10},
    "contradiction": {"base": 0.95, "information": 0.35, "trust": 0.25, "adaptation": 0.25},
    "issue_evidence": {"base": 1.10, "information": 0.35, "trust": 0.20, "adaptation": 0.25},
    "pr_merged": {"base": 2.20, "adaptation": 0.40, "continuity": 0.20, "trust": 0.15},
    "citation": {"base": 2.80, "trust": 0.40, "reproduction": 0.20, "information": 0.10},
    "mirror_heartbeat": {"base": 1.80, "continuity": 0.40, "reproduction": 0.30, "diversity": 0.15},
    "maintainer_release": {"base": 4.00, "continuity": 0.45, "governance": 0.25, "adaptation": 0.20},
    "resource_contribution": {"base": 1.20, "energy": 0.50, "continuity": 0.10},
    "translation": {"base": 1.60, "diversity": 0.35, "information": 0.20, "reproduction": 0.15},
    "adoption": {"base": 4.50, "reproduction": 0.35, "trust": 0.30, "continuity": 0.15},
}

SATURATION = {
    "energy": 22.0,
    "information": 12.0,
    "reproduction": 12.0,
    "continuity": 10.0,
    "governance": 6.0,
    "diversity": 9.0,
    "adaptation": 10.0,
    "trust": 12.0,
}

ANONYMOUS_DAILY_CAPS = {
    "page_access": 24,
    "release_download": 1000000,
    "clone": 20,
    "run_proof": 4,
    "feedback": 6,
}


class VitalityEngine:
    def __init__(self, weights: Dict | None = None, governance_baseline: float = 0.58):
        self.weights = weights or DEFAULT_WEIGHTS
        self.governance_baseline = governance_baseline

    @classmethod
    def from_config(cls, path: str | Path) -> "VitalityEngine":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data.get("event_weights"), data.get("governance_baseline", 0.58))

    def accepted_weight(self, packet: PulsePacket, ledger: VitalityLedger) -> float:
        cfg = self.weights.get(packet.event_type.value)
        if not cfg:
            raise ValueError(f"unsupported event type: {packet.event_type}")
        if packet.consent_scope == "local":
            raise ValueError("local-only pulses must not be persisted in the public ledger")
        if packet.day_token:
            cap = ANONYMOUS_DAILY_CAPS.get(packet.event_type.value, 50)
            used = ledger.count_for_day_token(packet.day_token, packet.event_type.value)
            if used >= cap:
                raise ValueError("daily pseudonymous pulse cap reached")
            count = min(packet.count, cap - used)
        else:
            count = packet.count
        base = float(cfg.get("base", 0.1))
        # Repeated low-cost events grow logarithmically; signed and proof-bearing events retain more weight.
        scale = math.log1p(max(count, 1))
        if packet.event_type.value in {"page_access", "release_download", "star"}:
            scale = math.log1p(max(count, 1)) / math.log(2)
        verification_factor = 1.20 if verify_packet(packet) else 1.0
        if packet.payload.get("proof_valid") is True:
            verification_factor += 0.25
        return round(base * scale * verification_factor, 8)

    @staticmethod
    def _saturate(raw: float, scale: float) -> float:
        return max(0.0, min(1.0, 1.0 - math.exp(-raw / max(scale, 1e-9))))

    def compute_state(self, ledger: VitalityLedger, artifact_id: str) -> VitalityState:
        events = ledger.all_events(artifact_id)
        raw = defaultdict(float)
        type_counts = Counter()
        nodes = set()
        verified_count = 0
        for event in events:
            cfg = self.weights.get(event["event_type"], {})
            weight = float(event["accepted_weight"])
            count = int(event["count"])
            type_counts[event["event_type"]] += count
            nodes.add(event["node_id"])
            verified_count += int(event["verified"])
            for dimension in SATURATION:
                raw[dimension] += weight * float(cfg.get(dimension, 0.0))
        # Governance is partly a constitutional property, not merely popularity.
        raw["governance"] += -math.log(max(1e-9, 1.0 - self.governance_baseline)) * SATURATION["governance"]
        # Node diversity is explicit and cannot be inflated only by event volume.
        raw["diversity"] += math.log1p(len(nodes)) * 1.2
        dims = {k: self._saturate(raw[k], SATURATION[k]) for k in SATURATION}
        values = [max(0.02, dims[k]) for k in SATURATION]
        geometric = math.exp(sum(math.log(v) for v in values) / len(values))
        integrity_gate = min(1.0, 0.45 + 0.55 * dims["trust"])
        vitality = round(100 * geometric * integrity_gate, 2)
        stage = self.life_stage(vitality, len(nodes), type_counts)
        residual = []
        if dims["trust"] < 0.45:
            residual.append("可验证复现、引用或签名事件不足；生命力可能被表面访问量放大。")
        if dims["diversity"] < 0.40:
            residual.append("节点和使用场景过于集中；尚未形成真正分布式谱系。")
        if dims["continuity"] < 0.45:
            residual.append("发布、维护者与镜像心跳不足；存在单点失活风险。")
        if type_counts.get("page_access", 0) > 20 * max(1, type_counts.get("run_proof", 0)):
            residual.append("访问量显著高于复现量；需要把注意力转化为运行证据。")
        return VitalityState(
            artifact_id=artifact_id,
            event_count=len(events),
            verified_event_count=verified_count,
            unique_nodes=len(nodes),
            merkle_root=ledger.merkle_root(artifact_id),
            dimensions=VitalityDimensions(**{k: round(v, 4) for k, v in dims.items()}),
            vitality_score=vitality,
            life_stage=stage,
            event_type_counts=dict(type_counts),
            residual_risks=residual,
        )

    @staticmethod
    def life_stage(score: float, unique_nodes: int, counts: Counter) -> str:
        if score < 15:
            return "L0 Seed / 种子"
        if score < 30:
            return "L1 Sprout / 萌芽"
        if score < 48:
            return "L2 Organism / 单体生命"
        if score < 65:
            return "L3 Colony / 协作群落"
        if score < 80:
            return "L4 Ecosystem / 开源生态"
        if unique_nodes >= 8 and counts.get("mirror_heartbeat", 0) >= 3:
            return "L5 Distributed Lineage / 分布式谱系"
        return "L4+ Commons / 公共生命体"

    def proposals(self, state: VitalityState) -> List[EvolutionProposal]:
        dims = state.dimensions.model_dump()
        proposals: List[EvolutionProposal] = []
        templates = {
            "information": (
                "把访问转化为语义营养",
                ["在首页增加一分钟微贡献：使用场景、错误或反例三选一", "发布结构化 ClaimGene / Contradiction 表单", "每月公开吸收与拒绝的反馈差分"],
                ["至少 20 条去重反馈", "至少 5 条进入 Issue 或文档修订", "公布未采纳理由"],
            ),
            "reproduction": (
                "启动一键复现与环境多样性挑战",
                ["提供 `dikwp-vita run-proof`", "冻结基准哈希与预期结果", "邀请三种操作系统和两个独立团队运行"],
                ["独立 run-proof >= 10", "至少 3 种环境", "失败结果被保留"],
            ),
            "continuity": (
                "建立非创始维护与镜像连续性",
                ["发布正式 Release", "指定两名非创始 steward", "部署三个镜像节点并每周心跳"],
                ["非创始维护者完成一次发布", "镜像连续在线 30 天", "恢复演练通过"],
            ),
            "diversity": (
                "扩展语言、地区与场景多样性",
                ["发布英文入口和术语表", "征集教育、医疗、治理之外的新场景", "建立跨地域镜像"],
                ["新增 3 个语言或地区节点", "新增 5 个异质场景", "重复事件权重下降"],
            ),
            "adaptation": (
                "把反馈闭环为版本化进化",
                ["每季度生成 EvolutionProposal", "所有规则变更通过 PR 与差分测试", "保留被否决提案"],
                ["至少 2 个提案被验证", "发布变更前后指标", "可回滚"],
            ),
            "trust": (
                "强化证据与防刷机制",
                ["要求高权重事件签名或 proof", "公开 Merkle root", "设置反刷审计和异常事件隔离"],
                ["签名/验证事件占比提升", "第三方复核通过", "异常事件不进入主分数"],
            ),
            "energy": (
                "建立维护资源和算力补给池",
                ["把赞助、算力、维护小时建成 ResourceContribution", "为关键 Issue 设置资源预算", "季度公开资源流向"],
                ["维护预算覆盖 6 个月", "至少 3 类资源来源", "不存在单一资助方控制"],
            ),
            "governance": (
                "完成公共生命宪章与多签治理",
                ["冻结 Purpose Constitution", "建立权限矩阵和紧急暂停", "关键规则由多签维护者批准"],
                ["治理文件版本化", "关键操作两人以上批准", "申诉与退出机制可用"],
            ),
        }
        for dim, value in sorted(dims.items(), key=lambda x: x[1]):
            if value >= 0.62:
                continue
            title, actions, evidence = templates[dim]
            pid = sha256(f"{state.artifact_id}|{dim}|{state.merkle_root}".encode()).hexdigest()[:16]
            priority = "critical" if value < 0.25 else "high" if value < 0.4 else "medium"
            proposals.append(
                EvolutionProposal(
                    proposal_id=f"EVO-{pid.upper()}",
                    priority=priority,
                    target_dimension=dim,
                    title=title,
                    rationale=f"当前 {dim} 维度为 {value:.2f}，低于公共数字生命建议阈值 0.62。",
                    actions=actions,
                    success_evidence=evidence,
                    kill_conditions=["无法证明改动带来净改善", "引入隐蔽追踪或不可撤销权限", "破坏既有复现结果"],
                )
            )
        return proposals[:5]
