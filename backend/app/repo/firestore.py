"""Firestore and Cloud Storage implementations.

UNVERIFIED against live services in the build container. Verify with the Firestore emulator
or a dev project before relying on them (docs/TASKS.md). Only sanitised media is ever stored.
"""
from app.repo.base import Doc


class FirestoreRepository:
    def __init__(self, project: str, database: str = "(default)") -> None:
        from google.cloud import firestore

        self._fs = firestore
        self._db = firestore.Client(project=project, database=database)

    def _case(self, case_id: str):
        return self._db.collection("cases").document(case_id)

    def create_case(self, case: Doc) -> None:
        self._case(case["id"]).set(case)

    def get_case(self, case_id: str) -> Doc | None:
        snap = self._case(case_id).get()
        return snap.to_dict() if snap.exists else None

    def update_case(self, case_id: str, fields: Doc) -> None:
        self._case(case_id).set(fields, merge=True)

    def list_cases(self, owner_uid: str) -> list[Doc]:
        query = (
            self._db.collection("cases")
            .where("ownerUid", "==", owner_uid)
            .order_by("updatedAt", direction=self._fs.Query.DESCENDING)
            .limit(50)
        )
        return [d.to_dict() for d in query.stream()]

    def delete_case(self, case_id: str) -> None:
        ref = self._case(case_id)
        for sub in ref.collections():
            for doc in sub.stream():
                doc.reference.delete()
        ref.delete()

    def put_doc(self, case_id: str, collection: str, doc_id: str, data: Doc) -> None:
        self._case(case_id).collection(collection).document(doc_id).set(data)

    def get_doc(self, case_id: str, collection: str, doc_id: str) -> Doc | None:
        snap = self._case(case_id).collection(collection).document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    def list_docs(self, case_id: str, collection: str) -> list[Doc]:
        docs = self._case(case_id).collection(collection).stream()
        return [d.to_dict() for d in sorted(docs, key=lambda d: d.id)]

    def incr_daily_cases(self, uid: str, day: str) -> int:
        ref = self._db.collection("rateLimits").document(f"{uid}_{day}")
        ref.set({"caseCount": self._fs.Increment(1), "updatedAt": self._fs.SERVER_TIMESTAMP}, merge=True)
        return int(ref.get().to_dict().get("caseCount", 1))

    def add_audit(self, entry: Doc) -> None:
        self._db.collection("auditLogs").add(entry)

    def put_eval_run(self, run: Doc) -> None:
        self._db.collection("evalRuns").add(run)


class GcsMediaStore:
    def __init__(self, bucket: str) -> None:
        from google.cloud import storage

        self._bucket = storage.Client().bucket(bucket)

    def put(self, case_id: str, name: str, data: bytes, mime: str) -> str:
        path = f"{case_id}/{name}"
        self._bucket.blob(path).upload_from_string(data, content_type=mime)
        return path

    def get(self, path: str) -> bytes:
        return self._bucket.blob(path).download_as_bytes()

    def delete_case(self, case_id: str) -> None:
        for blob in self._bucket.list_blobs(prefix=f"{case_id}/"):
            blob.delete()
