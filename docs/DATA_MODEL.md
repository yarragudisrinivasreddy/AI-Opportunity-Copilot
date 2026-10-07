# Data model (as implemented)

Firestore collections; the in-memory repository mirrors the same shape. Case ids are random 16-hex strings.

```text
cases/{caseId}
  id, ownerUid, status, vertical, isSample(false), description (cleaned), descriptionFlagged,
  frameCount, notAiExplanation, createdAt, updatedAt
  media/{000..}        frameIndex, sanitizedPath, kind(image|frame),
                       privacy{facesBlurred, piiRedactionApplied, piiRegionsMasked, summary}, createdAt
  process/{001..}      version, data(Process), confirmedByUser, userEdits[], createdAt
  answers/{fieldKey}   fieldKey, question, answer, source("user"), createdAt
  opportunities/{o1..} Opportunity + selected
  briefs/{b1..}        id, oppId, version, data(Brief), createdAt
  proposals/{providerId} id, providerId, simulated:true, structured(Proposal), rawText, createdAt
  evaluations/{e1..}   id, data(Evaluation), createdAt
auditLogs/{auto}       actorUid, action, caseId, ts, meta (no PII)
rateLimits/{uid_date}  caseCount, updatedAt
evalRuns/{auto}        suite, commit, model, metrics   (never write fake-LLM runs)
```

Notes: `rawText` of proposals is untrusted; render as text only (React escapes it; never use `dangerouslySetInnerHTML`). Index: `cases(ownerUid asc, updatedAt desc)` is in `firestore.indexes.json`. Client access to Firestore is denied by rules; all reads/writes go through the API.
