# PROJECT_MAP.md

Last updated: 2026-06-10 — **M1 + M2 + M3 complete** (branch `feature/private-workspaces`). M4 (live two-account verification) pending. Firestore rules NOT yet deployed — deploy rules + code together, then run M4.

## [TECH_STACK]

- Python 3.11 / Flask 3.0.3, gunicorn 22.0.0, openpyxl 3.1.2 (web/requirements.txt, pinned)
- Frontend: single-page vanilla JS in web/templates/index.html, Firebase JS SDK 10.7.1 (compat, CDN)
- Auth: Firebase Authentication (email/password), ID tokens verified server-side via identitytoolkit REST
- Storage: Firebase Firestore, accessed via REST (urllib, no SDK) using the **user's own ID token** — Firestore security rules are the actual access-control enforcement layer
- Deployment: Render.com (Procfile/gunicorn), project `medscheduler-e0853`
- No new dependencies required for this change

## [SYSTEM_FLOW]

### Current (problem)
1. User signs in → frontend obtains ID token
2. All `/api/data` GET/POST read/write **one** Firestore doc: `shared/schedule`
3. Firestore rules allow any authenticated user → **every account sees and edits the same schedule**

### Target
1. User signs in → frontend calls `GET /api/workspaces`
2. Backend ensures `workspaces/{uid}` meta doc exists (auto-create on first login), runs a Firestore query for workspaces whose `members` array contains the user's email
3. Frontend shows workspace switcher: "My Schedule" + any shared-with-me workspaces
4. `/api/data?ws={wsId}` reads/writes `workspaces/{wsId}/data/schedule`; Firestore rules permit access only to the owner (`uid == wsId`) or invited members (email in meta doc `members`)
5. Owner manages invites via a Share modal → `POST /api/workspaces/members` (add/remove email) → PATCH on meta doc, rules restrict to owner
6. Legacy `shared/schedule` becomes read-only (rules); a one-time "Import previous shared data" action copies it into the user's own workspace when the workspace is empty

## [ARCHITECTURE]

### Firestore data model (new)
```
workspaces/{ownerUid}                      ← workspace meta/ACL doc
  owner_uid:   string  (== document id)
  owner_email: string  (lowercase)
  members:     array<string>  (lowercase emails of invited users; owner NOT included)

workspaces/{ownerUid}/data/schedule       ← schedule payload (same shape as legacy shared/schedule)

shared/schedule                            ← legacy doc, kept untouched as backup; rules → read-only
```

### Firestore security rules (target — deployed manually in Firebase Console)
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    match /workspaces/{wsId} {
      // Owner creates own meta doc
      allow create: if request.auth != null
                    && request.auth.uid == wsId
                    && request.resource.data.owner_uid == request.auth.uid;
      // Owner or invited member can read meta
      allow get: if request.auth != null
                 && (request.auth.uid == wsId
                     || request.auth.token.email in resource.data.members);
      // Query "workspaces shared with me" (array-contains my email)
      allow list: if request.auth != null
                  && request.auth.token.email in resource.data.members;
      // Only owner edits membership / deletes workspace
      allow update, delete: if request.auth != null && request.auth.uid == wsId;

      match /data/schedule {
        allow read, write: if request.auth != null
          && (request.auth.uid == wsId
              || request.auth.token.email in
                 get(/databases/$(database)/documents/workspaces/$(wsId)).data.members);
      }
    }

    // Legacy doc: read-only during migration window, then remove this block
    match /shared/schedule {
      allow read: if request.auth != null;
      allow write: if false;
    }
  }
}
```

### Backend (web/app.py) — modified/added routes
| Route | Method | Change |
|---|---|---|
| `/api/workspaces` | GET | NEW — ensure own meta doc, return `{own, shared:[{id, owner_email}]}` via Firestore runQuery (members array-contains email) |
| `/api/workspaces/members` | POST | NEW — owner adds/removes a member email (PATCH meta doc, `updateMask=members`); rules enforce owner-only |
| `/api/data` | GET/POST | MODIFIED — accepts `?ws={wsId}` (default: caller's uid); path `workspaces/{ws}/data/schedule` |
| `/api/data/import-legacy` | POST | NEW — copies legacy `shared/schedule` into caller's own workspace (only if own workspace data is empty); legacy doc untouched |
| `/api/schedule`, `/api/summary`, `/api/export/*` | POST | UNCHANGED (stateless — operate on posted payload) |

All Firestore calls keep the existing pattern: user's ID token, urllib REST, `_py_to_fs`/`_fs_to_py`. Enforcement lives in Firestore rules, not in Flask — Flask never holds elevated credentials.

### Frontend (web/templates/index.html) — changes
- `S.wsId` state (default = own uid), `S.workspaces` list
- Workspace switcher in header row 1 (next to user badge): "My Schedule" + "<owner_email>'s schedule" entries; switching reloads data
- Share modal (owner only): member email list, add input, remove buttons → `/api/workspaces/members`
- Read-only indicator not needed (members have full edit); show "Shared by <owner_email>" badge when viewing another's workspace
- On first load with empty own workspace: offer "Import previous shared data" (calls `/api/data/import-legacy`)
- `loadData()/btn-save/btn-load` pass `?ws=${S.wsId}`

### Desktop app (medscheduler_refactored.py / firebase_service.py)
- OUT OF SCOPE this change. It still points at `shared/schedule`, which becomes read-only → desktop saves will fail with a permission error until updated. Tracked in [ORPHANS].

## [DECISIONS]

- **D1 — Workspace id = owner uid (one workspace per user).** Context: requirement is "his scheduling page" per user. Simplest id scheme, no collision handling, no workspace-creation UI. Tradeoff: a user cannot own multiple workspaces (acceptable; revisit only if requested).
- **D2 — Invite = add email to `members` array; no invite tokens/emails sent.** Invited user simply sees the workspace on next login (or after signup with that email). Tradeoff: no accept/decline step; owner can add anyone's email. Acceptable for a small trusted team; avoids email-sending infrastructure.
- **D3 — Members get full edit; owner-only membership management.** Matches current collaborative usage (user's selection). Roles (viewer/editor) deliberately excluded — would expand rules complexity without a stated need.
- **D4 — Enforcement in Firestore rules, not Flask.** The backend already uses the caller's ID token for Firestore; keeping this means no service-account secret to manage and no trust placed in the Flask layer. Rules text is version-controlled here and in PROJECT_STATE.md; deployed manually via Firebase Console (rules history allows rollback).
- **D5 — Migration: legacy `shared/schedule` left untouched (backup), made read-only by rules; explicit user-triggered import into own workspace.** Chosen over silent auto-migration to keep the action visible and reversible. Note: any previously-authorized user can import a copy — acceptable since they already had full access to that data.
- **D6 — Emails stored/compared lowercase.** Firebase normalizes token emails to lowercase; backend lowercases on write to avoid case-mismatch lockouts.

## [MILESTONES]

- **M1 — Backend + rules — DONE 2026-06-10** (branch: `feature/private-workspaces`)
  - app.py: workspace helpers, `FsError`, url-parametrized `fs_load/fs_save`, `fs_query_shared_workspaces`; routes `GET /api/workspaces`, `POST /api/workspaces/members`, ws-scoped `GET/POST /api/data?ws=`, `POST /api/data/import-legacy`
  - `web/firestore.rules` written (manual deploy via Firebase Console; NOT yet deployed)
  - Verified V2 against mocked Firestore: 8 scenario groups (meta auto-create + email lowercasing, empty load, save/reload, invite add/self-reject/bad-input/duplicate, member discovery via query + cross-workspace load, member removal, import-legacy 409/404/success with legacy untouched, 403 passthrough). Rules-level enforcement test pending deployment (part of M4 matrix)
- **M2 — Frontend workspace plumbing — DONE 2026-06-10**
  - index.html: `S.wsId`/`S.workspaces` state, `initWorkspaces()` on login, `wsQuery()` on all 4 data load/save call sites, `maybeOfferLegacyImport()` (one-time prompt for empty own workspace; declines and no-legacy remembered via localStorage flag `msched_legacy_import_dismissed`)
  - Verified: node --check on extracted inline JS, Flask render test confirms all hooks + complete document. Live two-account check deferred to M4 (needs rules deploy)
- **M3 — Sharing UI — DONE 2026-06-10**
  - index.html: workspace switcher `#ws-select` in header row 1 (hidden unless ≥1 shared workspace), `#ws-badge` "Shared by <owner>" chip, `👥 Share` button in row 2, Share modal (invite by email / remove, wired to POST /api/workspaces/members), `renderWsSwitcher/updateWsBadge/renderShareList/shareAction`
  - Verified: node --check on inline JS, all 10 new element ids present, Flask render test complete-document check. Live pass criteria (A invites B → B edits; A removes B → access lost) moved to M4 matrix
- **M4 — Verification + docs (V2)**
  - End-to-end manual test matrix with two accounts (own/shared/revoked/unauthenticated)
  - Update PROJECT_STATE.md (rules, data paths, access-control section); update [ORPHANS]
  - Pass: full matrix green; PROJECT_STATE.md current

**Rollback procedure (required before M1 deploy):** restore previous Firestore rules from Firebase Console rules history (or paste the old rules text preserved in PROJECT_STATE.md); revert the feature branch (no main merge until approval); legacy `shared/schedule` doc is never modified or deleted, so pre-change behavior returns fully once old rules are restored and the old code is redeployed.

## [ORPHANS]

- Desktop app (`medscheduler_refactored.py`, `firebase_service.py`) still targets `