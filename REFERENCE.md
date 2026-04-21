# MedScheduler — Project Reference

**File:** `medscheduler_refactored.py` (single-file Python/Tkinter desktop app)
**Dependency:** `openpyxl` (Excel export only)
**Run:** `python3 medscheduler_refactored.py`

---

## Data Model

### Doctor
```python
@dataclass
class Doctor:
    id: int
    name: str
    spec: str          # specialty label, e.g. "Team 1 Morning" or "Not specified"
    team: str          # "T1" | "T2" | "T3"
    initials: str = "" # user-supplied short code; auto-generated for exports if blank
    first_duty_day: int = 1  # day-of-month to start (1 = no stagger, 2+ = custom)
```

### LeaveBlock
```python
@dataclass
class LeaveBlock:
    id: int; pid: int; f: str; t: str  # f/t are "YYYY-MM-DD" strings
```

### SpecialtyBlock
```python
@dataclass
class SpecialtyBlock:
    id: int; code: str; f: str; t: str  # blocks a specialty code for a date range
```

### ManualAssignment
```python
@dataclass
class ManualAssignment:
    id: int; pid: int; code: str; day: int  # hard-pinned physician+duty+day triple
```

### Assignment store
`self.asgn: Dict[str, str]` — flat dict keyed `"{pid}|{year}|{month_0indexed}|{day}"` → shift code.
`month` is **0-indexed** (January = 0, December = 11) throughout the engine and app.

---

## Shift Codes

| Code | Label | Hours |
|------|-------|-------|
| T1 | Team 1 Morning | 8 |
| T2 | Team 2 Morning | 8 |
| T3 | Team 3 Morning | 8 |
| CAHM | Cardiology / Hematology | 8 |
| GI | Gastroenterology | 8 |
| NE | Neurology | 8 |
| NP | Nephrology | 8 |
| NENP | Neurology + Nephrology (combined escape) | 8 |
| PU | Pulmonology | 8 |
| DC | Daycare Clinic | 8 |
| DM | 16hr Duty – Male Side | 16 |
| DF | 16hr Duty – Female Side | 16 |
| PC | Post-Call Off | 0 |
| O | Day Off | 0 |
| L | Annual Leave | 0 |
| R | Random Off Day | 0 |
| _ | Blank (unassigned) | 0 |

**Key sets:**
- `TEAMS = ["T1", "T2", "T3"]`
- `SUBS = ["CAHM", "GI", "NE", "NP", "PU"]`
- `MORNING_K = TEAMS + SUBS + ["NENP"]`
- `DUTY_SET = {"DM", "DF"}`
- `OFF_SET = {"PC", "O", "L", "R"}`
- `MANUAL_ASSIGN_CODES = ["T1","T2","T3","PU","CAHM","NE","NP","GI","DC","DM","DF"]`

---

## Scheduling Engine — Phase Order

`auto_schedule(docs, base_asgn, leaves, spec_blocks, y, m)` returns `{"a": asgn_dict, "pairs": [...]}`.

### Phase 0 — First Duty Day stamp
- Runs **before** all other phases.
- For each physician with `first_duty_day > 1`, stamps days `1 … fdd-1` as `"O"`.
- These days are also added to `hb` (hard-blocked) in Phase 2 so Phase 4/5 never place DC/DM/DF before the physician's requested start.

### Phase 1 — Leave stamp
- Iterates `LeaveBlock` list; stamps `"L"` on all covered days.

### Phase 2 — Hard-blocked day sets
- Builds `hb: Dict[int, set]` — days with `"L"` or `"R"`, plus FDD-blocked days.
- Builds `pinned: Dict[int, set]` — days where `base_asgn` already has a non-blank, non-off code (user pre-sets). Pinned days are added to `hb` and `unavail`.
- Builds `pref_spec: Dict[int, Optional[str]]` — preferred morning specialty per physician.

### Phase 3 — Calendar weeks
- Splits the month into Sun-Sat calendar weeks.
- Each week: `{"start", "end", "wdays": [weekday nums], "wends": [weekend nums]}`.

### Phase 4 — Daycare rotation
- Picks one physician per week (fewest DC weeks → fewest duties → id).
- Assigns `"DC"` on Mon–Fri, `"O"` on weekends.
- Skips days that already have another physician on DC (pinned protection).
- Enforces 6-consecutive-day limit within DC blocks.
- After each DC week: assigns one `DM` or `DF` post-DC duty on the next available weekday.

### Phase 5 — Daily 16-hour duty coverage
- For each day: ensures one `DM` and one `DF` physician.
- Candidates sorted by fewest duties → fewest hours → id (fairness).
- `assign_duty(pid, d, side)`: stamps DM/DF and 3 mandatory `PC` days after.
  - Refuses if it would violate 6-day streak limit.
  - Refuses if total hours would exceed **168h** hard ceiling.
  - Refuses if any of the 3 PC days would fall on a pinned day.
  - Never overwrites pinned days with `PC`.

### Phase 6 — Weekend off guarantee
- Ensures every physician has at least one weekend day off (`PC`, `O`, `L`, `R`, or blank).

### Phase 7 — Morning specialty fill (day-first loop)
- **Pre-stagger:** Physicians without a custom FDD get a random stagger offset (0–5 days). Physicians with `first_duty_day > 1` are excluded (already stamped in Phase 0). Stable seed per year+month.
- **Per-day steps:**
  - Step 0: Update `lock_map` from pre-existing grid entries. DM/DF releases the lock; a morning code confirms/seeds it.
  - Step 1: Gather physicians with blank slots. Enforce 6-day streak and 168h ceiling. Proactive rest for streak=5 physicians (pull in only if needed for coverage).
  - Step 2: Separate `locked_today` vs `free_today`.
  - Step 2.5: Pre-seed `covered_today` from any physician already carrying a morning code today (prevents double-assignment of manually pre-set slots).
  - Step 3: Honor locked physicians → their specialty. Blocked specialty → `"O"` (lock kept). Lock conflict → `redirectable` pool.
  - Step 4: Fill uncovered required slots from `fill_pool = free_today + redirectable`. NENP escape: if supply < demand and both NE+NP uncovered, merge into single NENP slot.
  - Step 5: Remaining physicians → `"O"`.

**Specialty lock rule:** Lock set at first assignment; persists through PC/O/DC/blocked days; released ONLY on DM/DF.

---

## Hard Rules (never violated)

| Rule | Enforcement |
|------|-------------|
| Max 6 consecutive working days | Checked in `assign_duty`, Phase 4, Phase 7 Steps 1 & 4 |
| Max 168h/month | Hard ceiling in `assign_duty` and Phase 7 Step 1; soft cap 160h triggers morning→O conversion |
| DM/DF followed by exactly 3 PC days | `assign_duty` stamps PC days; never overwrites L/R/DM/DF/pinned |
| Leave (L) never overridden | Skipped in all phases |
| Random off (R) never overridden | In `hb`; respected by assign_duty |
| Pinned manual assignments never overwritten | `pinned` dict in Phase 2; checked in assign_duty before PC stamping |
| At least one weekend off per physician | Phase 6 |
| One DM + one DF per day (goal) | Phase 5 (best-effort) |

---

## UI Structure

```
MedSchedulerApp (tk.Tk, 1520×860)
├── Toolbar (top frame)
│   ├── Title label
│   ├── Month nav (◀ / ▶)
│   └── Action buttons: Auto-Schedule | Annual Leave | Block Specialty | Manual Assign | Export Detailed | Export Rota | Clear Month
├── Physician Management (LabelFrame)
│   ├── Row 1: Add physician (Name · Initials · Specialty · Add · Import)
│   ├── Scrollable physician list (Canvas + doc_list_frame, grid layout)
│   │   Columns: [checkbox | Name | Initials | 1st Day | Specialty | Team]
│   ├── Bulk action buttons: Remove Selected | Select All | Deselect All
│   └── Assign Specialty row (doctor combo · specialty combo · Apply)
├── Notebook
│   ├── Schedule tab → ttk.Treeview (physicians × days)
│   │   Columns: [physician | team | hours | d1 | d2 | … | d30/31]
│   │   Double-click cell → CellEditDialog popup
│   └── Summary tab → ttk.Treeview (statistics per physician)
└── Status bar (bottom)
```

### Physician list (doc_list_frame)
- Uses `grid` geometry manager directly on `doc_list_frame`.
- Row 0 = bold header labels; Row 1 = separator; Rows 2+ = data.
- `columnconfigure(ci, minsize=...)` enforces pixel-perfect column widths.
- `_doc_check_vars`, `_doc_initials_vars`, `_doc_fdd_vars` are dicts keyed by `ph.id`.

### Schedule Treeview column math
- Fixed columns: `#1`=physician, `#2`=team, `#3`=hours (3 columns).
- Day columns start at `#4` → `day = int(col[1:]) - 3`.
- Guard: skip clicks on `#1`, `#2`, `#3`.

---

## Dialogs

### ManualAssignDialog
- Add: physician combobox + duty combobox + day spinbox + Add button.
- Validates: (1) no existing assignment on day, (2) no streak >6, (3) ≤168h ceiling.
- Stores as `ManualAssignment` in `self.parent.manual_asgns`.
- Stamps the assignment into `self.parent.asgn` immediately.
- `schedule()` re-stamps all manual assignments after auto_schedule (prevents overwrite).
- Delete: click 🗑 in the list column (column `#4`).

### LeaveDialog
- Date range picker per physician; stores as `LeaveBlock`.
- Stamps `"L"` on covered days immediately; clears on delete.

### SpecialtyBlockDialog
- Date range + specialty combobox; stores as `SpecialtyBlock`.
- Engine reads `spec_blocks` during Phase 7 Step 3/4.

### CellEditDialog (inline cell editor)
- Triggered by single-click on a day cell in the schedule treeview.
- Shows physician name, day number, day-of-week, current assignment.
- Combobox of all shift codes with labels.
- OK → `setv(pid, day, code)`; Cancel → no change.

---

## App State (MedSchedulerApp.__init__)

| Attribute | Type | Purpose |
|-----------|------|---------|
| `yr` | int | Current year |
| `mo` | int | Current month (0-indexed) |
| `docs` | List[Doctor] | All physicians |
| `asgn` | Dict[str,str] | All assignments (all months) |
| `leaves` | List[LeaveBlock] | All leave blocks |
| `spec_blocks` | List[SpecialtyBlock] | All specialty blocks |
| `manual_asgns` | List[ManualAssignment] | User-pinned assignments |
| `next_doc_id` | int | Auto-increment for Doctor.id |
| `next_leave_id` | int | Auto-increment for LeaveBlock.id |
| `next_spec_block_id` | int | Auto-increment for SpecialtyBlock.id |
| `next_manual_id` | int | Auto-increment for ManualAssignment.id |
| `_doc_check_vars` | dict | {pid: tk.IntVar} checkbox state |
| `_doc_initials_vars` | dict | {pid: tk.StringVar} initials entry |
| `_doc_fdd_vars` | dict | {pid: tk.IntVar} first-duty-day spinbox |

---

## Export Formats

### Export Detailed (.xlsx) — `export_xlsx()`
- One row per day, one column per physician.
- Separate Summary sheet (hours, calls, daycare, post-call, off, leave, random, weekend off).
- Separate Blocked Specialties sheet.
- Shift codes color-coded per `COLOR_MAP`.

### Export Rota (.xlsx) — `export_simplified_xlsx()`
- Hospital rota-board layout: one row per day.
- Morning specialty columns: T1, T2, T3, PUL, CA/HM, NEU, NEPH, GAS, Daycare.
- On-call columns: (Male) / (Female).
- Initials legend column.
- Weekend rows highlighted in amber.
- Header: "First On Call Internal Medicine ROTA / MONTH YEAR".

---

## Key Methods

| Method | Description |
|--------|-------------|
| `schedule()` | Flushes FDD vars → stamps manual asgns → calls `auto_schedule()` → re-stamps manual asgns |
| `refresh_all()` | Calls `refresh_doctor_selector()` + `refresh_schedule()` + `refresh_summary()` |
| `refresh_doctor_list()` | Rebuilds physician list grid (header + data rows in same grid) |
| `refresh_schedule()` | Rebuilds schedule treeview columns and rows |
| `assign_specialty_to_doc()` | Changes `ph.spec`; syncs `ph.team` if T1/T2/T3 selected |
| `_save_fdd(pid, sv)` | Persists first_duty_day spinbox to Doctor object |
| `_flush_fdd_vars()` | Force-saves all FDD spinboxes before scheduling |
| `clear_month()` | Clears all asgn keys for current month + clears manual_asgns |
| `nav_month(delta)` | Moves to previous/next month; calls refresh_all() |
| `import_doctors()` | Parses .txt or .docx file for doctor names; adds missing ones |
| `_generate_initials()` | Produces unique 2-4 char abbreviations for export |
| `edit_schedule_cell(event)` | Double-click handler → CellEditDialog for that physician+day |

---

## Specialty Options (SPEC_OPTIONS)

```python
SPEC_OPTIONS = [
    "Not specified",
    "Team 1 Morning",   # → code T1, syncs ph.team = "T1"
    "Team 2 Morning",   # → code T2, syncs ph.team = "T2"
    "Team 3 Morning",   # → code T3, syncs ph.team = "T3"
    "Cardiology / Hematology",  # → CAHM
    "Gastroenterology",          # → GI
    "Neurology",                 # → NE
    "Nephrology",                # → NP
    "Pulmonology",               # → PU
]
```

`specialty_code_from_label(label)` looks up the code from SHIFTS dict by matching `meta["label"]`.

---

## Known Constraints & Behaviour Notes

- **Thin-pool coverage:** With <20 physicians some morning slots may go uncovered on days where many are on PC or DC. This is expected with low roster sizes, not a bug.
- **NENP escape:** When fill pool is smaller than required slot count AND both NE+NP are uncovered, one physician covers both (coded as "NENP").
- **Lock released only on DM/DF:** A physician's morning specialty lock persists through O, PC, DC, and blocked specialty days. Only a 16h duty resets it.
- **Month is 0-indexed** everywhere in the codebase (January=0, December=11). The `ds()` helper adds 1 when building YYYY-MM-DD strings.
- **Manual assign re-stamp:** `schedule()` stamps manual assignments both BEFORE (so Phase 7 sees them as filled) and AFTER (so PC cascades from nearby duties don't overwrite them).
