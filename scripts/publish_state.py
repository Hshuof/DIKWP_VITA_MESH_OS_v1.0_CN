from pathlib import Path
import json, sys
from dikwp_vita.engine import VitalityEngine
from dikwp_vita.ledger import VitalityLedger

ledger_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
with VitalityLedger(ledger_path) as db:
    state = VitalityEngine().compute_state(db, "DIKWP-VITA-MESH")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
