# PROJECT_MAP.md

Last updated: 2026-06-10 — M1–M4 complete and live (web merged to `main`, deployed on Render `medscheduler-5io6.onrender.com`; desktop updated with workspace support). **FEATURE CYCLE 2 COMPLETE AND LIVE (M5–M10, deployed 2026-06-10):** legacy-import prompt removed, email verification for new signups, invitation accept/decline/leave with per-user notifications panel, UI alignment fixes. Rules v2 (invites + notifications) published in Firebase Console.

## [TECH_STACK]

- Python 3.11 / Flask 3.0.3, gunicorn 22.0.0, openpyxl 3.1.2 (web/requirements.txt, pinned)
- Frontend: single-page vanilla JS in web/templates/index.html, Firebase JS SDK 10.7.1 (compat, CDN)
- Auth: Firebase Authentication (email/password), ID tokens verified server-side via identitytoolkit REST
- Storage: Firebase Firestore, accessed via REST (urllib, no SDK) using the **user's own ID token** — Firestore security rules are the actual access-control enforcement layer
- Deployment: Render.com (Procfile/gunicorn), project `medscheduler-e0853`
- No new dependencies required for this change

## [SYSTEM_FLOW]

1. User signs in → frontend obtains ID token → `GET /api/workspaces`
2. Backend ensures `workspaces/{uid}` meta doc exists (auto-create on first login), queries workspaces shared with the user
3. Workspace switcher: "My Schedule" + shared workspaces; `/api/data?ws={wsId}` reads/writes `workspaces/{wsId}/data/schedule`
4. Firestore rules enforce access (owner or accepted member)
5. Owner manages sharing via Share modal → `POST /api/workspaces/members`
6. New users start with an empty schedule (legacy-import prompt REMOVED in M5)
7. (Cycle 2) New signups must verify email; invitations require accept; members can leave; owners get notifications

## [ARCHITECTURE]

### Firestore data model
```
workspaces/{ownerUid}                      ← workspace meta/ACL doc
  owner_uid:   string  (== document id)
  owner_email: string  (lowercase)
  members:     array<string>  (lowercase emails of ACCEPTED members; owner NOT included)

workspaces/{ownerUid}/data/schedule       ← schedule payload

shared/schedule                            ← legacy doc; kept in Firestore as untouched backup,
                                             unreachable after M5 rules (no block grants access)
```

Additions implemented in M7 (rules live since M10):
```
workspaces/{ownerUid}.invites              ← array<string>, pending invitation emails (accepted → moved to members)

notifications/{recipientUid}/items/{autoId}
  type:        invite_accepted | invite_declined | member_left
  actor_email: string (lowercase, must equal the writer's token email)
  ws_id:       string
  created:     string (ISO 8601)
  read:        bool
```

### Firestore security rules
`web/firestore.rules` is the deployed text (published to Firebase Console at M10, 2026-06-10): invitee get/list via `invites`, diff-validated self-service accept/decline/leave transitions, owner identity fields frozen, `notifications/{uid}/items` block per D9, legacy `shared/schedule` block removed.

### Backend (web/app.py) — routes
| Route | Method | Status |
|---|---|---|
| `/api/workspaces` | GET | ensure own meta doc, return `{own, shared:[{id, owner_email}]}` |
| `/api/workspaces/members` | POST | owner adds/removes a member email |
| `/api/data` | GET/POST | `?ws={wsId}` (default: caller's uid) → `workspaces/{ws}/data/schedule` |
| `/api/data/import-legacy` | POST | **REMOVED in M5** (was one-time legacy migration) |
| `/api/schedule`, `/api/summary`, `/api/export/*` | POST | stateless — operate on posted payload |

Implemented in M7: `POST /api/invitations/respond` (accept/decline, notifies owner), `POST /api/workspaces/leave` (notifies owner), `GET /api/notifications` (newest-first, unread count), `POST /api/notifications/read` (ids, best-effort); `GET /api/workspaces` now returns `own.invites` + pending `invites` list; `POST /api/workspaces/members` add→`invites`, remove→both arrays. New helpers: `fs_create`, `fs_patch_fields` (updateMask + exists precondition), `fs_query_notifications`, `_notify` (best-effort, never rolls back the membership change).

All Firestore calls keep the existing pattern: user's ID token, urllib REST, `_py_to_fs`/`_fs_to_py`. Enforcement lives in Firestore rules, not in Flask — Flask never holds elevated credentials.

### Frontend (web/templates/index.html)
- `S.wsId` state (default = own uid), `S.workspaces` `{own, shared, invites}`, `S.notifications`; workspace switcher + "Shared by" badge + 🚪 Leave button (shared ws only) in header row 1
- 🔔 bell + unread badge (user-badge group): notifications modal — pending invites (Accept/Decline) + activity feed; opening marks unread read; 60s poll (`startNotifPolling`/`stopNotifPolling` on login/sign-out) also detects revoked access via `applyWorkspaces()`
- Share modal (owner only): "Awaiting response" (Cancel) + "Members" (Remove) lists → `/api/workspaces/members`
- Email-verification gate: `login-card`/`verify-card` on auth screen (M6)
- Legacy-import prompt and `maybeOfferLegacyImport()` REMOVED in M5 — empty workspace just starts fresh
- `loadData()/btn-save/btn-load` pass `?ws=${S.wsId}`

### Desktop app (medscheduler_refactored.py / firebase_service.py)
- **Updated June 2026** to support workspace model. `firebase_service.py` exports `get_workspaces()` and accepts `workspace_id` in `save_app_data()`/`load_app_data()`. `medscheduler_refactored.py` shows workspace selector dropdown in toolbar and workspace selection dialog after login.

## [DECISIONS]

- **D1 — Workspace id = owner uid (one workspace per user).** Simplest id scheme, no collision handling, no workspace-creation UI. Tradeoff: a user cannot own multiple workspaces (acceptable; revisit only if requested).
- **D2 — Invite = add email to `members` array; no invite tokens/emails sent.** Invited user simply sees the workspace on next login. **(Accept/decline part superseded by D8 in feature cycle 2.)**
- **D3 — Members get full edit; owner-only membership management.** Roles (viewer/editor) deliberately excluded — would expand rules complexity without a stated need.
- **D4 — Enforcement in Firestore rules, not Flask.** Backend uses the caller's ID token for Firestore; no service-account secret, no trust in the Flask layer. Rules deployed manually via Firebase Console (rules history allows rollback).
- **D5 — Migration: legacy `shared/schedule` left untouched (backup).** Import path REMOVED in M5; the doc remains in Firestore but no rules block grants access after the M5 rules are published.
- **D6 — Emails stored/compared lowercase.** Firebase normalizes token emails to lowercase; backend lowercases on write to avoid case-mismatch lockouts.
- **D7 — Email verification enforced for NEW signups only (user decision 2026-06-10).** Enforcement: frontend gate (verify screen after signup / unverified sign-in) + Flask `require_auth` check (`emailVerified` + `createdAt >= VERIFICATION_CUTOFF` from identitytoolkit lookup, which already returns both fields). Firestore rules CANNOT grandfather (token has no creation date), so rules-level verification is skipped. Accepted residual risk: a new unverified account could bypass Flask and hit Firestore REST directly with its own token; revisit with custom claims if this matters later.
- **D8 — Invitation state lives on the workspace meta doc: `invites` (pending) + `members` (accepted).** Existing members are grandfathered as accepted (user decision). Owner adds emails to `invites`; the invited user accepts (move own email invites→members), declines (remove own email from invites), or later leaves (remove own email from members). Firestore rules permit these non-owner updates only as strict self-service diffs (toSet() difference == exactly the caller's own email, affected keys ⊆ {members, invites}); `data/schedule` access stays members-only. No invite tokens/emails sent.
- **D9 — Notifications stored at `notifications/{recipientUid}/items/{autoId}`** with fields `type` (invite_accepted | invite_declined | member_left), `actor_email`, `ws_id`, `created`, `read`. Rules: any authenticated user may CREATE into another user's feed but only with validated fields and `actor_email == request.auth.token.email`; only the recipient can read/list/delete, and update may touch only `read`. Spam-creation risk accepted for a small trusted team. "You were invited" is NOT a stored notification — pending invites are discovered live via the workspaces query (works even when the invitee registers after being invited).
- **D10 — Notifications panel refreshes by 60-second polling** (user decision) plus refresh on login and on panel open. No push infrastructure added.

## [MILESTONES]

- **M1 — Backend + rules — DONE 2026-06-10** (branch: `feature/private-workspaces`)
  - app.py: workspace helpers, `FsError`, url-parametrized `fs_load/fs_save`, `fs_query_shared_workspaces`; routes `GET /api/workspaces`, `POST /api/workspaces/members`, ws-scoped `GET/POST /api/data?ws=`, `POST /api/data/import-legacy`
  - Verified V2 against mocked Firestore: 8 scenario groups. Rules-level enforcement verified live in M4
- **M2 — Frontend workspace plumbing — DONE 2026-06-10**
  - index.html: `S.wsId`/`S.workspaces` state, `initWorkspaces()` on login, `wsQuery()` on all 4 data load/save call sites, `maybeOfferLegacyImport()` one-time prompt
  - Verified: node --check on extracted inline JS, Flask render test, blob-hash commit verification
- **M3 — Sharing UI — DONE 2026-06-10**
  - index.html: workspace switcher `#ws-select`, `#ws-badge` chip, `👥 Share` button, Share modal wired to POST /api/workspaces/members
  - Verified: node --check, element-id checks, Flask render test; live pass criteria confirmed in M4
- **M4 — Verification + docs — DONE 2026-06-10 (V3: live operational verification)**
  - Deployed: merge to main → GitHub → Render; rules published in Firebase Console (old rules in Console rules history = rollback)
  - Live matrix passed (user-confirmed); PROJECT_STATE.md updated

### Feature cycle 2 (branch: `feature/invites-verification`, T4: merge approval required)

- **M5 — Remove first-login legacy-import prompt — IMPLEMENTED 2026-06-10, pending commit verification** (L1/L2)
  - index.html: deleted `maybeOfferLegacyImport()` + its call in `loadData()` (new users start with a fresh empty schedule)
  - app.py: deleted `/api/data/import-legacy` route + `LEGACY_DOC` constant
  - firestore.rules: dropped the legacy `shared/schedule` block (doc itself stays in Firestore untouched as backup); rules go live with M10 publish
  - Pass: new account → empty schedule, no prompt; `node --check`, py_compile, Flask render test
- **M6 — Email verification for new signups — IMPLEMENTED 2026-06-10** (L2, auth change)
  - index.html: after `createUserWithEmailAndPassword` → `sendEmailVerification()` → verify screen (resend + "I've verified" + sign-out); same gate on sign-in when `!user.emailVerified` and `user.metadata.creationTime >= cutoff`
  - app.py: `VERIFICATION_CUTOFF` constant (deploy date, epoch ms); `require_auth` returns 403 `email-not-verified` when `createdAt >= cutoff and not emailVerified`
  - Pass (verified): mocked require_auth matrix — new+unverified 403 `email-not-verified`, new+verified 200, pre-cutoff unverified 200, missing createdAt 200, no token 401; node --check; render test (verify card + cutoff present). Cutoff = 1781049600000 (2026-06-10T00:00:00Z), identical in app.py and index.html. Live email-delivery check deferred to M10 matrix
- **M7 — Invitations backend + rules — IMPLEMENTED 2026-06-10** (L3)
  - app.py: `GET /api/workspaces` also returns `own.invites` + `invites:[{id,owner_email}]` (second runQuery on `invites` array-contains email); `POST /api/workspaces/members` add→`invites`, remove→both arrays; NEW `POST /api/invitations/respond` {ws_id, action} and `POST /api/workspaces/leave` {ws_id} (meta transition + notification doc); NEW `GET /api/notifications` (runQuery, created desc, limit 50) and `POST /api/notifications/read` (PATCH with `updateMask.fieldPaths=read`)
  - firestore.rules: meta get/list extended to invitees; self-service diff-validated update clauses; owner update may not change `owner_uid`/`owner_email`; `notifications/{uid}/items` block per D9
  - Pass (verified): 18/18 mocked-Firestore scenarios (meta auto-create with invites[]; invite add/dup-idempotent/existing-member-400; invitee pending discovery; accept→member+notification; decline; leave; owner revoke; notifications list/unread/mark-read; 400/404 paths incl. own-ws and bad ids). Rules Playground dry-run of accept/decline/leave transitions REQUIRED before M10 publish
- **M8 — Invitations + notifications frontend — IMPLEMENTED 2026-06-10** (L2)
  - index.html: 🔔 bell + unread badge in header row 1; notifications modal (pending invites with Accept/Decline; notification list with mark-read); 60s poll; "Leave workspace" action when viewing a shared workspace (confirm → POST leave → switch to own ws, refresh switcher); Share modal split into Pending / Members lists with Cancel / Remove
  - Pass (verified): node --check, element-id checks, render test (all new ids + endpoints present). Implementation notes: `applyWorkspaces()` preserves the active wsId across refreshes and detects revoked access (poll switches back to My Schedule + reloads); opening the bell marks unread as read (badge clears, highlights persist until close); polling starts on login, stops on sign-out. Live two-account flow deferred to M10 matrix
- **M9 — UI review & alignment fixes — IMPLEMENTED 2026-06-10** (L1)
  - Known issues found during planning: (1) BUG `renderSchedule`: `'#'+S.C.color_map[code]||'fff'` — precedence makes unknown codes render `#undefined`, should be `'#'+(S.C.color_map[code]||'fff')`; (2) hardcoded `hrs>160` red threshold ignores configurable `S.rules.max_hours`; (3) header row 1 crowding on ≤640px once bell is added (audit `ws-switch`/`ws-badge`/bell wrap behavior); (4) systematic pass over modals/header/sidebar at 360px/640px/900px/desktop widths
  - Fixed (before → after): (1) unknown shift codes rendered background `#undefined` → `'#'+(map[code]||'fff')`; (2) grid Hrs column + Summary red threshold hardcoded `>160` → follows configurable `S.rules.max_hours`; (3) `.hdr-row2` used flex-wrap + `overflow:hidden`, silently CLIPPING action buttons at ~901–1150px widths → nowrap + horizontal scroll at all widths; (4) header row 1 could overflow at ≤640px with switcher+Leave+bell → row scrolls, `#ws-select` capped 110px, redundant `#ws-badge` hidden, compact Leave; (5) `.doc-del` was hover-revealed (opacity:0) → always visible on touch widths
  - Pass: node --check, render test; live spot-check at 360/640/900px in M10 matrix
- **M10 — V3 verification + deploy + docs — DONE 2026-06-10 (V3: live operational verification)**
  - Pre-deploy regression: 13/13 passed on branch head 8ef4c20 (auth matrix, invitation lifecycle incl. notifications, render checks); all working-tree blobs == HEAD
  - **DEPLOY ORDER IS CRITICAL: publish Firestore rules FIRST, then merge/deploy code.** New code + old rules breaks login for everyone (the pending-invites runQuery is rejected → GET /api/workspaces 403). New rules + old code is safe (old code never touches `invites`; only gap: legacy-import for brand-new users during the minutes-long window, removed by the code deploy anyway)
  - Deployed: rules published in Firebase Console (old rules in Console history = rollback), then branch merged to main via GitHub PR → Render auto-deploy
  - Live matrix passed (user-confirmed 2026-06-10): new signup blocked until email verified, then empty schedule with no import popup; existing account unaffected; invite → bell badge → accept → workspace in switcher + owner notified; decline + leave both notify owner; revoke detected by poll; UI spot-checks at 360/640/900px clean
  - Rollback: restore prior rules from Console history; revert merge on GitHub (Render redeploys old code); `invites` arrays are additive (old code ignores them); legacy doc untouched; PROJECT_STATE.md update deferred until live matrix passes

**Rollback (cycle 2):** restore previous Firestore rules from Firebase Console rules history; revert the feature branch (no main merge until approval); legacy `shared/schedule` doc is never modified or deleted.

## [ORPHANS]

- Firebase web API key hardcoded in `app.py`/`index.html` and also expected as env var per DEPLOY.md — harmless (web API keys are public identifiers) but inconsistent; consider consolidating to env vars later.
- Open self-signup (`createUserWithEmailAndPassword`) remains enabled; M6 email verification reduces abuse, but an email allowlist remains an optional hardening step.
- Notifications have no retention/purge policy (capped at 50 most-recent per fetch); add cleanup later if volume grows.
- Desktop app (`firebase_service.py`/`medscheduler_refactored.py`) will NOT gain invite-respond/notifications UI in this cycle; pending invites are simply not shown there. Members who accepted via web work normally on desktop. Follow-up if desktop parity is wanted.
