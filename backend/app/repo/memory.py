"""In-memory repository and media store for tests and key-free local development."""
import copy
import threading

from app.repo.base import Doc


class InMemoryRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.cases: dict[str, Doc] = {}
        self.docs: dict[tuple[str, str, str], Doc] = {}
        self.daily: dict[tuple[str, str], int] = {}
        self.audit: list[Doc] = []
        self.eval_runs: list[Doc] = []

    def create_case(self, case: Doc) -> None:
        with self._lock:
            self.cases[case["id"]] = copy.deepcopy(case)

    def get_case(self, case_id: str) -> Doc | None:
        with self._lock:
            c = self.cases.get(case_id)
            return copy.deepcopy(c) if c else None

    def update_case(self, case_id: str, fields: Doc) -> None:
        with self._lock:
            if case_id in self.cases:
                self.cases[case_id].update(copy.deepcopy(fields))

    def list_cases(self, owner_uid: str) -> list[Doc]:
        with self._lock:
            found = [c for c in self.cases.values() if c.get("ownerUid") == owner_uid]
            return sorted(copy.deepcopy(found), key=lambda c: c.get("updatedAt", ""), reverse=True)

    def delete_case(self, case_id: str) -> None:
        with self._lock:
            self.cases.pop(case_id, None)
            for key in [k for k in self.docs if k[0] == case_id]:
                del self.docs[key]

    def put_doc(self, case_id: str, collection: str, doc_id: str, data: Doc) -> None:
        with self._lock:
            self.docs[(case_id, collection, doc_id)] = copy.deepcopy(data)

    def get_doc(self, case_id: str, collection: str, doc_id: str) -> Doc | None:
        with self._lock:
            d = self.docs.get((case_id, collection, doc_id))
            return copy.deepcopy(d) if d else None

    def list_docs(self, case_id: str, collection: str) -> list[Doc]:
        with self._lock:
            keys = sorted(k for k in self.docs if k[0] == case_id and k[1] == collection)
            return [copy.deepcopy(self.docs[k]) for k in keys]

    def incr_daily_cases(self, uid: str, day: str) -> int:
        with self._lock:
            self.daily[(uid, day)] = self.daily.get((uid, day), 0) + 1
            return self.daily[(uid, day)]

    def incr_global_daily_cases(self, day: str) -> int:
        return self.incr_daily_cases("__global__", day)

    def add_audit(self, entry: Doc) -> None:
        with self._lock:
            self.audit.append(copy.deepcopy(entry))

    def put_eval_run(self, run: Doc) -> None:
        with self._lock:
            self.eval_runs.append(copy.deepcopy(run))


class InMemoryMediaStore:
    def __init__(self) -> None:
        self._blobs: dict[str, tuple[bytes, str]] = {}

    def put(self, case_id: str, name: str, data: bytes, mime: str) -> str:
        path = f"{case_id}/{name}"
        self._blobs[path] = (data, mime)
        return path

    def get(self, path: str) -> bytes:
        return self._blobs[path][0]

    def delete_case(self, case_id: str) -> None:
        for path in [p for p in self._blobs if p.startswith(f"{case_id}/")]:
            del self._blobs[path]
