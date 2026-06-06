"""
MedScheduler - Rule-based scheduling engine (pure Python, no UI dependencies).
"""
from __future__ import annotations
import calendar
import random as _rnd
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

OFF_SET = {"PC", "O", "L", "R"}
MONTHS = ["January","February","March","April","May","June",
          "July","August","September","October","November","December"]
DN = ["Su","Mo","Tu","We","Th","Fr","Sa"]


@dataclass
class ShiftEntry:
    code: str
    label: str
    short: str
    color: str
    hours: int
    shift_type: str  # "team" | "specialty" | "duty" | "clinic"
    enabled: bool = True  # False = excluded from schedule rotation


@dataclass
class ShiftConfig:
    teams: List[ShiftEntry]
    specialties: List[ShiftEntry]
    duties: List[ShiftEntry]
    # clinics: configurable list of clinic entries (replaces single fixed DC).
    # An empty list means no clinic rotation.
    clinics: List[ShiftEntry] = field(default_factory=lambda: [
        ShiftEntry("DC", "GP Clinic", "DC", "FEF3C7", 8, "clinic")
    ])

    def team_codes(self):
        return [e.code for e in self.teams]

    def specialty_codes(self):
        return [e.code for e in self.specialties]

    def duty_codes(self):
        return [e.code for e in self.duties]

    def clinic_codes(self):
        return [e.code for e in self.clinics if e.enabled]

    def duty_set(self):
        return {e.code for e in self.duties}

    def clinic_set(self):
        return {e.code for e in self.clinics if e.enabled}

    def morning_k(self):
        codes = self.team_codes() + self.specialty_codes()
        sc = self.specialty_codes()
        if "NE" in sc and "NP" in sc:
            codes.append("NENP")
        return codes

    def to_shifts_dict(self):
        result = {}
        for e in self.teams + self.specialties + self.duties + self.clinics:
            result[e.code] = {"label": e.label, "short": e.short, "h": e.hours}
        sc = self.specialty_codes()
        if "NE" in sc and "NP" in sc:
            ne_h = next((e.hours for e in self.specialties if e.code == "NE"), 8)
            result["NENP"] = {"label": "Neurology + Nephrology", "short": "NE/NP", "h": ne_h}
        result["PC"] = {"label": "Post-Call Off",  "short": "PC", "h": 0}
        result["O"]  = {"label": "Day Off",        "short": "O",  "h": 0}
        result["L"]  = {"label": "Annual Leave",   "short": "L",  "h": 0}
        result["R"]  = {"label": "Random Off Day", "short": "R",  "h": 0}
        result["_"]  = {"label": "-",              "short": "",   "h": 0}
        return result

    def to_color_map(self):
        result = {}
        for e in self.teams + self.specialties + self.duties + self.clinics:
            result[e.code] = e.color
        sc = self.specialty_codes()
        if "NE" in sc and "NP" in sc:
            result["NENP"] = "C7D7F9"
        result["PC"] = "EDE9FE"
        result["O"]  = "F3F4F6"
        result["L"]  = "D1FAE5"
        result["R"]  = "FEE2E2"
        result["_"]  = "FFFFFF"
        return result

    def code_hours(self):
        h = {}
        for e in self.teams + self.specialties + self.duties + self.clinics:
            h[e.code] = e.hours
        sc = self.specialty_codes()
        if "NE" in sc and "NP" in sc:
            h["NENP"] = next((e.hours for e in self.specialties if e.code == "NE"), 8)
        return h

    def spec_options(self):
        return ["Not specified"] + [e.label for e in self.teams] + [e.label for e in self.specialties]

    def manual_assign_codes(self):
        codes = self.team_codes()
        sc = self.specialty_codes()
        for code in sc:
            if code not in ("NE", "NP"):
                codes.append(code)
        if "NE" in sc and "NP" in sc:
            codes += ["NE", "NP", "NENP"]
        elif "NE" in sc:
            codes.append("NE")
        elif "NP" in sc:
            codes.append("NP")
        codes += self.clinic_codes()
        codes += self.duty_codes()
        return codes

    def blockable_specialties(self):
        return self.morning_k() + self.clinic_codes()


DEFAULT_SHIFT_CONFIG = ShiftConfig(
    teams=[
        ShiftEntry("T1","Team 1 Morning","T1","DBEAFE",8,"team"),
        ShiftEntry("T2","Team 2 Morning","T2","CCFBF1",8,"team"),
        ShiftEntry("T3","Team 3 Morning","T3","EDE9FE",8,"team"),
    ],
    specialties=[
        ShiftEntry("CAHM","Cardiology / Hematology","CA/HM","FFE4E6",8,"specialty"),
        ShiftEntry("GI","Gastroenterology","GI","FFEDD5",8,"specialty"),
        ShiftEntry("NE","Neurology","NE","F3E8FF",8,"specialty"),
        ShiftEntry("NP","Nephrology","NP","CFFAFE",8,"specialty"),
        ShiftEntry("PU","Pulmonology","PU","E0F2FE",8,"specialty"),
    ],
    duties=[
        ShiftEntry("DM","16hr Duty - Male Side","DM","FEF9C3",16,"duty"),
        ShiftEntry("DF","16hr Duty - Female Side","DF","FCE7F3",16,"duty"),
    ],
    # clinics defaults to [ShiftEntry("DC","GP Clinic","DC","FEF3C7",8,"clinic")]
)

# Legacy constants for backward compat
TEAMS  = DEFAULT_SHIFT_CONFIG.team_codes()
SUBS   = DEFAULT_SHIFT_CONFIG.specialty_codes()
MORNING_K = DEFAULT_SHIFT_CONFIG.morning_k()
DUTY_SET  = DEFAULT_SHIFT_CONFIG.duty_set()
SHIFTS    = DEFAULT_SHIFT_CONFIG.to_shifts_dict()
COLOR_MAP = DEFAULT_SHIFT_CONFIG.to_color_map()
SPEC_OPTIONS          = DEFAULT_SHIFT_CONFIG.spec_options()
MANUAL_ASSIGN_CODES   = DEFAULT_SHIFT_CONFIG.manual_assign_codes()
BLOCKABLE_SPECIALTIES = DEFAULT_SHIFT_CONFIG.blockable_specialties()


@dataclass
class ScheduleRules:
    max_consecutive_days: int = 6
    post_call_days:       int = 3
    min_duties:           int = 3
    max_duties:           int = 0   # 0 = uncapped
    min_hours:            int = 160
    max_hours:            int = 168
    duty_shift_hours:     int = 16
    morning_shift_hours:  int = 8
    enforce_weekend_off:  bool = True

DEFAULT_RULES = ScheduleRules()


@dataclass
class Doctor:
    id: int
    name: str
    spec: str
    team: str
    initials: str = ""
    first_duty_day: int = 1

@dataclass
class LeaveBlock:
    id: int
    pid: int
    f: str
    t: str

@dataclass
class SpecialtyBlock:
    id: int
    code: str
    f: str
    t: str

@dataclass
class ManualAssignment:
    id: int
    pid: int
    code: str
    day: int


def p2(n):
    return str(n).zfill(2)

def dim(y, m):
    return calendar.monthrange(y, m + 1)[1]

def ds(y, m, d):
    return f"{y}-{p2(m+1)}-{p2(d)}"

def day_of_week(y, m, d):
    return (date(y, m+1, d).weekday() + 1) % 7

def is_we(y, m, d):
    return day_of_week(y, m, d) in (0, 6)

def is_wd(y, m, d):
    return not is_we(y, m, d)

def specialty_code_from_label(label, cfg=None):
    cfg = cfg or DEFAULT_SHIFT_CONFIG
    for e in cfg.teams + cfg.specialties:
        if e.label == label:
            return e.code
    return None


def auto_schedule(docs, base_asgn, leaves, spec_blocks, y, m,
                  rules=None, shift_config=None):
    if rules is None:        rules = ScheduleRules()
    if shift_config is None: shift_config = DEFAULT_SHIFT_CONFIG
    if len(docs) < 3:
        return {"err": "Need at least 3 physicians (one per IM team)."}

    TEAMS_L      = shift_config.team_codes()
    SUBS_L       = shift_config.specialty_codes()
    DUTY_CODES   = shift_config.duty_codes()
    DUTY_SET_L   = shift_config.duty_set()
    MK_L         = shift_config.morning_k()
    CLINIC_CODES = shift_config.clinic_codes()
    CLINIC_SET   = shift_config.clinic_set()
    _ch          = shift_config.code_hours()
    has_nenp     = "NE" in SUBS_L and "NP" in SUBS_L

    td = dim(y, m)
    a  = dict(base_asgn)

    def ak(pid, d):      return f"{pid}|{y}|{m}|{d}"
    def get(pid, d):     return a.get(ak(pid, d), "_")
    def setv(pid, d, v): a[ak(pid, d)] = v
    def day_str(d):      return ds(y, m, d)

    def is_spec_blocked(code, d):
        cur = day_str(d)
        return any(b.code == code and b.f <= cur <= b.t for b in spec_blocks)

    def calc_h(doc_id):
        return sum(_ch.get(get(doc_id, d), 0) for d in range(1, td + 1))

    def consec_before(pid, d):
        streak, x = 0, d - 1
        while x >= 1 and get(pid, x) not in OFF_SET and get(pid, x) != "_":
            streak += 1; x -= 1
        return streak

    def preplaced_after(pid, d):
        streak, x = 0, d + 1
        while x <= td:
            code = get(pid, x)
            if code in OFF_SET or code == "_": break
            streak += 1; x += 1
        return streak

    # Phase 0 - first duty day
    for ph in docs:
        fdd = int(ph.first_duty_day) if ph.first_duty_day and ph.first_duty_day > 1 else 1
        fdd = min(fdd, td)
        for _d in range(1, fdd):
            if get(ph.id, _d) == "_": setv(ph.id, _d, "O")

    # Phase 1 - leave stamps
    for b in leaves:
        for d in range(1, td + 1):
            if b.f <= day_str(d) <= b.t: setv(b.pid, d, "L")

    # Phase 2 - hard blocks
    hb = {}
    for ph in docs:
        hb[ph.id] = set()
        fdd = int(ph.first_duty_day) if ph.first_duty_day and ph.first_duty_day > 1 else 1
        for d in range(1, td + 1):
            if get(ph.id, d) in ("L", "R"): hb[ph.id].add(d)
            if d < fdd: hb[ph.id].add(d)

    unavail        = {ph.id: set(hb[ph.id]) for ph in docs}
    duty_cnt       = {ph.id: 0 for ph in docs}
    duty_type_cnt  = {ph.id: {dc: 0 for dc in DUTY_CODES} for ph in docs}
    dc_wk_cnt      = {ph.id: 0 for ph in docs}  # total clinic weeks assigned

    _pinned_codes = {e.code for e in shift_config.teams + shift_config.specialties + shift_config.duties}
    _pinned_codes |= CLINIC_SET
    if has_nenp: _pinned_codes.add("NENP")

    pinned = {ph.id: set() for ph in docs}
    for ph in docs:
        for d in range(1, td + 1):
            if get(ph.id, d) in _pinned_codes: pinned[ph.id].add(d)
    for ph in docs:
        hb[ph.id]      |= pinned[ph.id]
        unavail[ph.id] |= pinned[ph.id]

    pref_spec = {}
    for i, ph in enumerate(docs):
        if ph.spec == "Not specified":
            pref_spec[ph.id] = None
        else:
            sc_code = specialty_code_from_label(ph.spec, shift_config)
            pref_spec[ph.id] = (
                sc_code if sc_code and sc_code in MK_L
                else (ph.team if ph.team in TEAMS_L else TEAMS_L[i % len(TEAMS_L)])
            )

    pc_range = range(1, rules.post_call_days + 1)

    def pick_duty(pid):
        return min(DUTY_CODES, key=lambda dc: (duty_type_cnt[pid].get(dc, 0), dc))

    def assign_duty(pid, d, side):
        if consec_before(pid, d) >= rules.max_consecutive_days: return False
        if rules.max_duties > 0 and duty_cnt[pid] >= rules.max_duties: return False
        duty_h = _ch.get(side, 16)
        if d > 1 and get(pid, d-1) in MK_L and calc_h(pid) + duty_h > rules.min_hours:
            setv(pid, d-1, "O")
        if calc_h(pid) + duty_h > rules.max_hours: return False
        for _pc in pc_range:
            _pd = d + _pc
            if _pd <= td:
                if _pd in pinned.get(pid, set()): return False
                if get(pid, _pd) in CLINIC_SET:   return False
        setv(pid, d, side)
        duty_cnt[pid] += 1
        duty_type_cnt[pid][side] = duty_type_cnt[pid].get(side, 0) + 1
        unavail[pid].add(d)
        for pc in pc_range:
            pd = d + pc
            if pd > td: break
            existing = get(pid, pd)
            if existing in ("L","R") or existing in DUTY_SET_L or existing in CLINIC_SET: continue
            if pd in pinned.get(pid, set()): continue
            setv(pid, pd, "PC")
            unavail[pid].add(pd)
        return True

    # Phase 3 - calendar weeks
    weeks = []
    start_d = 1
    while start_d <= td:
        dw = day_of_week(y, m, start_d)
        days_to_sun = 0 if dw == 0 else 7 - dw
        end_d = min(start_d + days_to_sun, td)
        weeks.append({
            "start": start_d, "end": end_d,
            "wdays": [x for x in range(start_d, end_d+1) if is_wd(y,m,x)],
            "wends": [x for x in range(start_d, end_d+1) if is_we(y,m,x)],
        })
        start_d = end_d + 1

    # Phase 4 - clinic rotation (one physician per clinic per week)
    clinic_wk_info_list = []  # (doc_id, week_end) pairs for post-clinic duty assignment

    for cc in CLINIC_CODES:
        for wk in weeks:
            if not wk["wdays"]: continue
            elig = [ph for ph in docs if any(d not in hb[ph.id] for d in wk["wdays"])]
            if not elig: continue
            first_wd = wk["wdays"][0]
            elig.sort(key=lambda ph: (
                dc_wk_cnt[ph.id],
                sum(1 for _dp in range(max(1,first_wd-3),first_wd) if get(ph.id,_dp) in DUTY_SET_L),
                consec_before(ph.id, first_wd), duty_cnt[ph.id], ph.id,
            ))
            # Prefer a doctor not already on another clinic this week
            doc = None
            for candidate in elig:
                if not any(get(candidate.id, d) in CLINIC_SET for d in wk["wdays"]):
                    doc = candidate; break
            if doc is None:
                doc = elig[0]

            dc_wk_cnt[doc.id] += 1
            for d in wk["wdays"]:
                if any(get(ph.id,d)==cc for ph in docs if ph.id!=doc.id): continue
                if d not in hb[doc.id] and not is_spec_blocked(cc,d):
                    if consec_before(doc.id,d) >= rules.max_consecutive_days:
                        setv(doc.id,d,"O")
                    else:
                        setv(doc.id,d,cc)
                    unavail[doc.id].add(d)
            for d in wk["wends"]:
                if d not in hb[doc.id] and get(doc.id,d)=="_":
                    setv(doc.id,d,"O"); unavail[doc.id].add(d)
            clinic_wk_info_list.append((doc.id, wk["end"]))

    # Give each clinic-week doctor a duty the following week
    for doc_id, week_end in clinic_wk_info_list:
        for d in range(week_end+1, td+1):
            if is_wd(y,m,d) and d not in unavail[doc_id] and get(doc_id,d)=="_":
                if consec_before(doc_id,d) >= rules.max_consecutive_days: continue
                assign_duty(doc_id, d, pick_duty(doc_id)); break

    # Phase 4.5 - clinic gap-fill (one per clinic per weekday)
    for cc in CLINIC_CODES:
        for _d in range(1, td+1):
            if not is_wd(y,m,_d) or is_spec_blocked(cc,_d): continue
            if any(get(ph.id,_d)==cc for ph in docs): continue
            _gap = [ph for ph in docs
                    if get(ph.id,_d)=="_" and _d not in unavail[ph.id]
                    and consec_before(ph.id,_d) < rules.max_consecutive_days
                    and calc_h(ph.id) + _ch.get(cc,8) <= rules.max_hours]
            if _gap:
                _gap.sort(key=lambda ph:(dc_wk_cnt[ph.id],duty_cnt[ph.id],calc_h(ph.id),ph.id))
                setv(_gap[0].id,_d,cc); unavail[_gap[0].id].add(_d); dc_wk_cnt[_gap[0].id]+=1

    # Phase 5 - daily duty coverage (N duty types)
    pairs = []
    for d in range(1, td+1):
        duty_cov = {}
        for dc in DUTY_CODES:
            found = next((ph for ph in docs if get(ph.id,d)==dc), None)
            duty_cov[dc] = found.id if found else None

        missing = [dc for dc,pid in duty_cov.items() if pid is None]
        if not missing:
            pairs.append({"d":d, **duty_cov}); continue

        avail = [ph for ph in docs
                 if d not in unavail[ph.id] and get(ph.id,d)=="_"
                 and consec_before(ph.id,d) < rules.max_consecutive_days
                 and (rules.max_duties <= 0 or duty_cnt[ph.id] < rules.max_duties)]
        avail.sort(key=lambda ph:(duty_cnt[ph.id],calc_h(ph.id),ph.id))

        assigned_today = set()
        for duty_code in missing:
            candidates = [ph for ph in avail if ph.id not in assigned_today]
            if not candidates: continue
            candidates.sort(key=lambda ph:(
                duty_type_cnt[ph.id].get(duty_code,0),
                duty_cnt[ph.id], calc_h(ph.id), ph.id))
            chosen = candidates[0]
            if assign_duty(chosen.id, d, duty_code):
                duty_cov[duty_code] = chosen.id
                assigned_today.add(chosen.id)
        pairs.append({"d":d, **duty_cov})

    # Phase 5.5 - duty rescue
    for _d in range(1, td+1):
        for duty_code in DUTY_CODES:
            if any(get(ph.id,_d)==duty_code for ph in docs): continue
            _rescue = [ph for ph in docs
                       if (get(ph.id,_d) in MK_L or get(ph.id,_d)=="_")
                       and consec_before(ph.id,_d) < rules.max_consecutive_days
                       and calc_h(ph.id)+_ch.get(duty_code,16) <= rules.max_hours
                       and (rules.max_duties <= 0 or duty_cnt[ph.id] < rules.max_duties)
                       and all((_d+pc>td or _d+pc not in pinned.get(ph.id,set()))
                               and (_d+pc>td or get(ph.id,_d+pc) not in CLINIC_SET)
                               for pc in pc_range)]
            if _rescue:
                _rescue.sort(key=lambda ph:(
                    duty_type_cnt[ph.id].get(duty_code,0),
                    duty_cnt[ph.id], calc_h(ph.id), ph.id))
                _rph = _rescue[0]
                if get(_rph.id,_d) in MK_L: setv(_rph.id,_d,"_")
                assign_duty(_rph.id,_d,duty_code)

    # Phase 5.6 - minimum duties
    for ph in docs:
        while duty_cnt[ph.id] < rules.min_duties:
            placed = False
            for _d in range(1, td+1):
                cur = get(ph.id,_d)
                if cur not in ("_",) and cur not in MK_L: continue
                if consec_before(ph.id,_d) >= rules.max_consecutive_days: continue
                side = pick_duty(ph.id)
                if calc_h(ph.id)+_ch.get(side,16) > rules.max_hours: break
                if rules.max_duties > 0 and duty_cnt[ph.id] >= rules.max_duties: break
                _ok = True
                for _pc in pc_range:
                    _pd = _d+_pc
                    if _pd<=td:
                        if _pd in pinned.get(ph.id,set()): _ok=False; break
                        if get(ph.id,_pd) in CLINIC_SET:   _ok=False; break
                if not _ok: continue
                if cur in MK_L: setv(ph.id,_d,"_")
                if assign_duty(ph.id,_d,side):
                    placed=True; break
                else:
                    if cur in MK_L: setv(ph.id,_d,cur)
            if not placed: break

    # Phase 6 - weekend guarantee
    if rules.enforce_weekend_off:
        wkends = [d for d in range(1,td+1) if is_we(y,m,d)]
        we_pairs = []
        for _d in range(1,td+1):
            if day_of_week(y,m,_d)==6 and _d+1<=td and day_of_week(y,m,_d+1)==0:
                we_pairs.append((_d,_d+1))
        for ph in docs:
            has_happy = any(
                get(ph.id,sat) in OFF_SET and get(ph.id,sun) in OFF_SET
                for sat,sun in we_pairs)
            if not has_happy:
                for sat,sun in we_pairs:
                    sc_s,uc = get(ph.id,sat),get(ph.id,sun)
                    sat_free = sc_s not in DUTY_SET_L and sc_s not in ("L","R") and sc_s not in CLINIC_SET
                    sun_free = uc   not in DUTY_SET_L and uc   not in ("L","R") and uc   not in CLINIC_SET
                    if sat_free and sun_free:
                        if sc_s not in OFF_SET: setv(ph.id,sat,"O")
                        if uc   not in OFF_SET: setv(ph.id,sun,"O")
                        break
            if not any(get(ph.id,d) in OFF_SET for d in wkends):
                for w in wkends:
                    if get(ph.id,w) not in DUTY_SET_L and get(ph.id,w) not in ("L","R") and get(ph.id,w) not in CLINIC_SET:
                        setv(ph.id,w,"O"); break

    # Phase 7 - morning specialty fill
    lock_map = {ph.id: None for ph in docs}
    _rng = _rnd.Random(y*1000+(m+1)*31)
    _default_docs = [ph for ph in docs if not (ph.first_duty_day and ph.first_duty_day>1)]
    _shuffled = list(_default_docs); _rng.shuffle(_shuffled)
    _slots_per_day = len(SUBS_L)+len(TEAMS_L)
    _first_group = _slots_per_day+4; _stagger_max = 5
    for _gi,_ph in enumerate(_shuffled):
        _offset = 0 if _gi<_first_group else min((_gi-_first_group)//_slots_per_day+1,_stagger_max)
        for _sd in range(1,_offset+1):
            if get(_ph.id,_sd)=="_": setv(_ph.id,_sd,"O")

    morning_h_rep = _ch.get(TEAMS_L[0], 8) if TEAMS_L else 8

    for d in range(1,td+1):
        for ph in docs:
            code = get(ph.id,d)
            if code in DUTY_SET_L:  lock_map[ph.id] = None
            elif code in MK_L:      lock_map[ph.id] = code

        to_assign=[]; can_rest_early=[]
        for ph in docs:
            if get(ph.id,d)!="_": continue
            if calc_h(ph.id)+morning_h_rep > rules.max_hours:
                setv(ph.id,d,"O"); continue
            backward = consec_before(ph.id,d)
            if backward >= rules.max_consecutive_days:
                setv(ph.id,d,"O"); continue
            forward = preplaced_after(ph.id,d)
            if backward+1+forward > rules.max_consecutive_days:
                setv(ph.id,d,"O"); continue
            (can_rest_early if backward >= rules.max_consecutive_days-1 else to_assign).append(ph)

        needed = len(SUBS_L)+len(TEAMS_L)
        shortfall = max(0,needed-len(to_assign))
        if shortfall>0 and can_rest_early:
            can_rest_early.sort(key=lambda ph:(duty_cnt[ph.id],calc_h(ph.id),ph.id))
            to_assign.extend(can_rest_early[:shortfall])
            for ph in can_rest_early[shortfall:]: setv(ph.id,d,"O")
        else:
            for ph in can_rest_early: setv(ph.id,d,"O")

        locked_today = [(ph,lock_map[ph.id]) for ph in to_assign if lock_map[ph.id] is not None]
        free_today   = [ph for ph in to_assign if lock_map[ph.id] is None]

        covered_today = {}
        for _ph in docs:
            _code = get(_ph.id,d)
            if _code in MK_L:
                covered_today[_code] = _ph.id
                if _code=="NENP":
                    covered_today["NE"]=_ph.id; covered_today["NP"]=_ph.id

        redirectable = []
        for ph,lock in locked_today:
            if lock=="NENP" and has_nenp:
                ne_bl=is_spec_blocked("NE",d); np_bl=is_spec_blocked("NP",d)
                ne_op="NE" not in covered_today; np_op="NP" not in covered_today
                if ne_bl and np_bl: setv(ph.id,d,"O")
                elif ne_op and np_op and not ne_bl and not np_bl:
                    setv(ph.id,d,"NENP"); covered_today["NE"]=ph.id; covered_today["NP"]=ph.id
                elif ne_op and not ne_bl:
                    setv(ph.id,d,"NE"); lock_map[ph.id]="NE"; covered_today["NE"]=ph.id
                elif np_op and not np_bl:
                    setv(ph.id,d,"NP"); lock_map[ph.id]="NP"; covered_today["NP"]=ph.id
                else: redirectable.append(ph)
            elif is_spec_blocked(lock,d): setv(ph.id,d,"O")
            elif lock not in covered_today:
                setv(ph.id,d,lock); covered_today[lock]=ph.id
            else: redirectable.append(ph)

        # Teams come first so T1/T2/T3 are always filled when doctors are available;
        # specialties are filled with whatever remains.
        required_order = [s for s in (TEAMS_L+SUBS_L)
                          if s not in covered_today and not is_spec_blocked(s,d)]
        fill_pool = free_today+redirectable
        fill_pool.sort(key=lambda ph:(duty_cnt[ph.id],calc_h(ph.id),ph.id))

        if (has_nenp and len(fill_pool)<len(required_order)
                and "NE" in required_order and "NP" in required_order):
            required_order.remove("NE"); required_order.remove("NP")
            # Insert NENP after the last team slot so teams stay at front
            insert_pos = next((i for i,s in enumerate(required_order) if s not in TEAMS_L),
                              len(required_order))
            required_order.insert(insert_pos,"NENP")

        for spec in required_order:
            if not fill_pool: break
            if spec=="NENP":
                best_idx = next((i for i,ph in enumerate(fill_pool)
                                 if pref_spec.get(ph.id) in ("NE","NP")), None)
            else:
                best_idx = next((i for i,ph in enumerate(fill_pool)
                                 if pref_spec.get(ph.id)==spec), None)
            if best_idx is None: best_idx=0
            ph = fill_pool.pop(best_idx)
            if spec=="NENP":
                setv(ph.id,d,"NENP"); lock_map[ph.id]="NENP"
                covered_today["NE"]=ph.id; covered_today["NP"]=ph.id
            else:
                setv(ph.id,d,spec); lock_map[ph.id]=spec; covered_today[spec]=ph.id

        for ph in fill_pool: setv(ph.id,d,"O")

    # Phase 7.5 - team rescue
    # With teams-first ordering in Phase 7, this fires only on genuine shortage days.
    # Priority: (1) redirect a specialty doctor, (2) un-O any doctor not hard-blocked.
    for _d in range(1,td+1):
        for _team in TEAMS_L:
            if any(get(ph.id,_d)==_team for ph in docs): continue
            # Try 1: steal from a specialty slot (specialty can be re-covered elsewhere)
            _pool = [ph for ph in docs if get(ph.id,_d) in SUBS_L]
            if not _pool:
                # Try 2: any doctor on "O" who is not hard-blocked and not over max-consecutive
                _pool = [ph for ph in docs
                         if get(ph.id,_d) == "O"
                         and _d not in hb[ph.id]
                         and consec_before(ph.id,_d) < rules.max_consecutive_days
                         and preplaced_after(ph.id,_d) == 0]  # no pre-assigned days right after
            if not _pool: continue
            _pool.sort(key=lambda ph:(0 if pref_spec.get(ph.id)==_team else 1,-calc_h(ph.id),ph.id))
            setv(_pool[0].id,_d,_team); lock_map[_pool[0].id]=_team

    # Phase 8 - minimum hours
    for ph in docs:
        if calc_h(ph.id) >= rules.min_hours: continue
        convertible = sorted(d for d in range(1,td+1)
                             if get(ph.id,d)=="O"
                             and d not in hb[ph.id] and d not in pinned[ph.id])
        for d in convertible:
            if calc_h(ph.id) >= rules.min_hours: break
            mh = _ch.get(pref_spec.get(ph.id) or ph.team, 8)
            if calc_h(ph.id)+mh > rules.max_hours: break
            if consec_before(ph.id,d)+1+preplaced_after(ph.id,d) > rules.max_consecutive_days:
                continue
            best = pref_spec.get(ph.id) or ph.team
            if best not in MK_L:
                best = ph.team if ph.team in TEAMS_L else TEAMS_L[0]
            if is_spec_blocked(best,d):
                best = TEAMS_L[0]
            setv(ph.id,d,best)

    return {"a": a, "pairs": pairs}


def compute_summary(docs, asgn, yr, mo, rules=None, shift_config=None):
    if rules is None:        rules = ScheduleRules()
    if shift_config is None: shift_config = DEFAULT_SHIFT_CONFIG
    DUTY_SET_L   = shift_config.duty_set()
    CLINIC_SET_L = shift_config.clinic_set()
    _ch          = shift_config.code_hours()
    td = dim(yr, mo)
    rows = []
    for ph in docs:
        _pid = ph.id
        def get(d): return asgn.get(f"{_pid}|{yr}|{mo}|{d}", "_")
        h8=h16=calls=daycare=postcall=off=leave=random=blocked=we_off=0
        for d in range(1,td+1):
            code=get(d); h=_ch.get(code,0)
            if code in DUTY_SET_L:   h16+=h; calls+=1
            elif h>0:                h8+=h
            if code in CLINIC_SET_L: daycare+=1
            if code=="PC":           postcall+=1
            if code in ("O","R"):    off+=1
            if code=="L":            leave+=1
            if code=="R":            random+=1
            if code=="_":            blocked+=1
            if is_we(yr,mo,d) and code in OFF_SET: we_off+=1
        rows.append({"name":ph.name,"team":ph.team,"initials":ph.initials,
                     "h8":h8,"h16":h16,"total":h8+h16,"calls":calls,
                     "daycare":daycare,"postcall":postcall,"off":off,
                     "leave":leave,"random":random,"blocked":blocked,
                     "weekend_off":we_off})
    return rows
