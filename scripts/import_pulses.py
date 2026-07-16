from pathlib import Path
import json, sys
from dikwp_vita.engine import VitalityEngine
from dikwp_vita.ledger import VitalityLedger
from dikwp_vita.models import PulsePacket

pulses_path = Path(sys.argv[1])
ledger_path = Path(sys.argv[2])
engine = VitalityEngine()
pulses = json.loads(pulses_path.read_text(encoding="utf-8"))
with VitalityLedger(ledger_path) as db:
    for item in pulses:
        p = PulsePacket.model_validate(item)
        try:
            db.append(p, engine.accepted_weight(p, db))
        except ValueError:
            pass
