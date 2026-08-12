"""Policy Graph in-memory từ eval/ontology/*.jsonl — 49+ node thì dict thuần là đủ.

Chuyển Neo4j khi độ phủ lớn (quyết định spec 11/08). Bản ghi có lỗi cứng
(errors ≠ []) bị loại ngay từ load — downstream không bao giờ thấy chúng.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import TypeAdapter

from app.ontology.schema import ActorCU, ComplianceUnit, KhaiNiem, PremiseRecord

_CU_ADAPTER: TypeAdapter = TypeAdapter(ComplianceUnit)
_DIEU_RE = re.compile(r"^(.+?#than/dieu_[0-9a-z]+)")


def dieu_prefix(khoa: str) -> str:
    m = _DIEU_RE.match(khoa)
    return m.group(1) if m else khoa


def _doc_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    ra = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            d.pop("fixture", None)
            ra.append(d)
    return ra


class PolicyGraph:
    def __init__(self, cu, premise, khai_niem):
        self.cu: dict[str, ComplianceUnit] = {c.id: c for c in cu}
        self.premise: list[PremiseRecord] = premise
        self.khai_niem: list[KhaiNiem] = khai_niem
        # kề nhau theo tiền tố Điều, hai chiều
        self._theo_dieu: dict[str, list[str]] = {}
        for cid in self.cu:
            self._theo_dieu.setdefault(dieu_prefix(cid), []).append(cid)
        self._ke: dict[str, set[str]] = {cid: set() for cid in self.cu}
        for cid, c in self.cu.items():
            for ref in c.references:
                for dich in self._theo_dieu.get(dieu_prefix(ref), []):
                    if dich != cid:
                        self._ke[cid].add(dich)
                        self._ke[dich].add(cid)

    @classmethod
    def load(cls, thu_muc: Path = Path("eval/ontology")) -> "PolicyGraph":
        cu = [_CU_ADAPTER.validate_python(d) for d in _doc_jsonl(thu_muc / "pred.jsonl")]
        cu = [c for c in cu if c.ok]
        premise = [PremiseRecord.model_validate(d)
                   for d in _doc_jsonl(thu_muc / "premise.jsonl")]
        kn = [KhaiNiem.model_validate(d) for d in _doc_jsonl(thu_muc / "khainiem.jsonl")]
        return cls(cu, premise, kn)

    def cu_cua_dieu(self, so_hieu: str, so_dieu: str):
        return [self.cu[i] for i in self._theo_dieu.get(
            f"{so_hieu}#than/dieu_{so_dieu}", [])]

    def lang_gieng(self, cu_id: str):
        return [self.cu[i] for i in sorted(self._ke.get(cu_id, ()))]

    def closure(self, cu_id: str, sau: int = 2):
        tham: set[str] = {cu_id}
        bien = {cu_id}
        for _ in range(sau):
            bien = {j for i in bien for j in self._ke.get(i, ())} - tham
            tham |= bien
        return [self.cu[i] for i in sorted(tham - {cu_id})]

    def mien_tru_trong(self, ids):
        return [c for i in ids if isinstance(c := self.cu.get(i), ActorCU)
                and c.modality == "mien_tru"]
