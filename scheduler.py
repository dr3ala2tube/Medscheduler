"""
MedScheduler – Rule-based scheduling engine (pure Python, no UI dependencies).
Extracted from medscheduler_refactored.py for use in the web backend.
"""
from __future__ import annotations

import calendar
import random as _rnd
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

MONTHS = ["January","February","March","April","May","June",
          "July","August","September","October","November","December"]
DN     = ["Su","Mo","Tu","We","Th","Fr","Sa"]
TEAMS  = ["T1","T2","T3"]
SUBS   = ["CAHM","GI","NE","NP","PU"]
MORNING_K = TEAMS + SUBS + ["NENP"]
DUTY_SET  = {"DM","DF"}
OFF_SET   = {"PC","O","L","R"}

SHIFTS = {
    "T1":   {"label":"Team 1 Morning",           "short":"T1",    "h":8},
    "T2":   {"label":"Team 2 Morning",           "short":"T2",    "h":8},
    "T3":   {"label":"Team 3 Morning",           "short":"T3",    "h":8},
    "CAHM": {"label":"Cardiology / Hematology",  "short":"CA/HM", "h":8},
    "GI":   {"label":"Gastroenterology",         "short":"GI",    "h":8},
    "NE":   {"label":"Neurology",                "short":"NE",    "h":8},
    "NP":   {"label":"Nephrology",               "short":"NP",    "h":8},
    "NENP": {"label":"Neurology + Nephrology",   "short":"NE/NP", "h":8},
    "PU":   {"label":"Pulmonology",              "short":"PU",    "h":8},
    "DC":   {"label":"Daycare Clinic",           "short":"DC",    "h":8},
    "DM":   {"label":"16hr Duty – Male Side",    "short":"DM",    "h":16},
    "DF":   {"label":"16hr Duty – Female Side",  "short":"DF",    "h":16},
    "PC":   {"label":"Post-Call Off",            "short":"PC",    "h":0},
    "O":    {"label":"Day Off",                  "short":"O",     "h":0},
    "L":    {"label":"Annual Leave",             "short":"L",     "h":0},
    "R":    {"label":"Random Off Day",           "short":"R",     "h":0},
    "_":    {"label":"—",                        "short":"",      "h":0},
}

COLOR_MAP = {
    "T1":"DBEAFE","T2":"CCFBF1","T3":"EDE9FE",
    "CAHM":"FFE4E6","GI":"FFEDD5","NE":"F3E8FF",
    "NP":"CFFAFE","NENP":"C7D7F9","PU":"E0F2FE",
    "DC":"FEF3C7","DM":"FEF9C3","DF":"FCE7F3",
    "PC":"EDE9FE","O":"F3F4F6","L":"D1FAE5",
    "R":"FEE2E2","_":"FFFFFF",
}

SPEC_OPTIONS = ["Not specified"] + [SHIFTS[k]["label"] for k in ["T1","T2","T3","CAHM","GI","NE","NP","PU"]]
MANUAL_ASSIGN_CODES = ["T1","T2","T3","PU","CAHM","NE","NP","GI","DC","DM","DF"]
BLOCKABLE_SPECIALTIES = MORNING_K + ["DC"]


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


def p2(n: int) -> str:
    return str(n).zfill(2)

def dim(y: int, m: int) -> int:
    return calendar.monthrange(y, m + 1)[1]

def ds(y: int, m: int, d: int) -> str:
    return f"{y}-{p2(m+1)}-{p2(d)}"

def day_of_week(y: int, m: int, d: int) -> int:
    py = date(y, m+1, d).weekday()
    return (py+1) % 7

def is_we(y: int, m: int, d: int) -> bool:
    return day_of_week(y, m, d) in (0, 6)

def is_wd(y: int, m: int, d: int) -> bool:
    return not is_we(y, m, d)

def specialty_code_from_label(label: str) -> Optional[str]:
    for code, meta in SHIFTS.items():
        if meta["label"] == label:
            return code
    return None


def auto_schedule(docs, base_asgn, leaves, spec_blocks, y, m):
    if len(docs) < 3:
        return {"err": "Need at least 3 physicians (one per IM team)."}
    td = dim(y, m)
    a  = dict(base_asgn)

    def ak(pid, d):   return f"{pid}|{y}|{m}|{d}"
    def get(pid, d):  return a.get(ak(pid, d), "_")
    def setv(pid, d, v): a[ak(pid, d)] = v
    def day_str(d):   return ds(y, m, d)

    def is_spec_blocked(code, d):
        cur = day_str(d)
        return any(b.code == code and b.f <= cur <= b.t for b in spec_blocks)

    def calc_h(doc_id):
        return sum(SHIFTS[get(doc_id, d)]["h"] for d in range(1, td+1))

    def consecutive_working_days_before(pid, d):
        streak, x = 0, d - 1
        while x >= 1 and get(pid, x) not in OFF_SET and get(pid, x) != "_":
            streak += 1; x -= 1
        return streak

    def preplaced_working_days_after(pid, d):
        """Count consecutive pre-placed working days starting at d+1.
        DM/DF count as working so the streak check blocks assigning a morning
        immediately before a duty shift (which would create a >6-day run).
        """
        streak, x = 0, d + 1
        while x <= td:
            code = get(pid, x)
            if code in OFF_SET or code == "_": break  # DM/DF are working — don't break on them
            streak += 1; x += 1
        return streak

    # Phase 0 – first duty day stamps
    for ph in docs:
        fdd = int(ph.first_duty_day) if ph.first_duty_day and ph.first_duty_day > 1 else 1
        fdd = min(fdd, td)
        for _d in range(1, fdd):
            if get(ph.id, _d) == "_": setv(ph.id, _d, "O")

    # Phase 1 – leave stamps
    for b in leaves:
        for d in range(1, td+1):
            if b.f <= day_str(d) <= b.t: setv(b.pid, d, "L")

    # Phase 2 – hard-blocked sets
    hb: Dict[int, set] = {}
    for ph in docs:
        hb[ph.id] = set()
        fdd = int(ph.first_duty_day) if ph.first_duty_day and ph.first_duty_day > 1 else 1
        for d in range(1, td+1):
            if get(ph.id, d) in ("L","R"): hb[ph.id].add(d)
            if d < fdd: hb[ph.id].add(d)

    unavail:       Dict[int, set] = {ph.id: set(hb[ph.id]) for ph in docs}
    duty_cnt:      Dict[int, int] = {ph.id: 0 for ph in docs}
    male_side_cnt: Dict[int, int] = {ph.id: 0 for ph in docs}
    dc_wk_cnt:     Dict[int, int] = {ph.id: 0 for ph in docs}

    _pinned_codes = set(SHIFTS.keys()) - {"_","O","L","R","PC"}
    pinned: Dict[int, set] = {ph.id: set() for ph in docs}
    for ph in docs:
        for d in range(1, td+1):
            if get(ph.id, d) in _pinned_codes: pinned[ph.id].add(d)
    for ph in docs:
        hb[ph.id]     |= pinned[ph.id]
        unavail[ph.id] |= pinned[ph.id]

    pref_spec: Dict[int, Optional[str]] = {}
    for i, ph in enumerate(docs):
        if ph.spec == "Not specified":
            pref_spec[ph.id] = None
        else:
            sc = specialty_code_from_label(ph.spec)
            pref_spec[ph.id] = sc if sc and sc in MORNING_K else (ph.team if ph.team in TEAMS else TEAMS[i%3])

    def assign_duty(pid, d, side):
        if consecutive_working_days_before(pid, d) >= 6: return False
        if d > 1 and get(pid, d-1) in MORNING_K and calc_h(pid)+16 > 160: setv(pid, d-1, "O")
        if calc_h(pid)+16 > 168: return False
        for _pc in range(1, 4):
            _pd = d + _pc
            if _pd <= td:
                if _pd in pinned.get(pid, set()): return False
                if get(pid, _pd) == "DC":         return False
        setv(pid, d, side)
        duty_cnt[pid] += 1
        if side == "DM": male_side_cnt[pid] += 1
        unavail[pid].add(d)
        for pc in range(1, 4):
            pd = d + pc
            if pd > td: break
            existing = get(pid, pd)
            if existing in ("L","R","DM","DF","DC"): continue
            if pd in pinned.get(pid, set()):         continue
            setv(pid, pd, "PC")
            unavail[pid].add(pd)
        return True

    # Phase 3 – calendar weeks
    weeks = []
    start_d = 1
    while start_d <= td:
        dw = day_of_week(y, m, start_d)
        days_to_sun = 0 if dw == 0 else 7 - dw
        end_d = min(start_d + days_to_sun, td)
        weeks.append({"start": start_d, "end": end_d,
                      "wdays": [x for x in range(start_d, end_d+1) if is_wd(y,m,x)],
                      "wends": [x for x in range(start_d, end_d+1) if is_we(y,m,x)]})
        start_d = end_d + 1

    # Phase 4 – daycare rotation
    dc_info = []
    for wk in weeks:
        if not wk["wdays"]: continue
        elig = [ph for ph in docs if any(d not in hb[ph.id] for d in wk["wdays"])]
        if not elig:
            dc_info.append({"docId": None, "weekEnd": wk["end"]}); continue
        first_wd = wk["wdays"][0]
        elig.sort(key=lambda ph: (dc_wk_cnt[ph.id],
            sum(1 for _dp in range(max(1,first_wd-3),first_wd) if get(ph.id,_dp) in ("DM","DF")),
            consecutive_working_days_before(ph.id, first_wd), duty_cnt[ph.id], ph.id))
        doc = elig[0]; dc_wk_cnt[doc.id] += 1
        for d in wk["wdays"]:
            if any(get(ph.id,d)=="DC" for ph in docs if ph.id!=doc.id): continue
            if d not in hb[doc.id] and not is_spec_blocked("DC",d):
                if consecutive_working_days_before(doc.id,d) >= 6: setv(doc.id,d,"O")
                else: setv(doc.id,d,"DC")
                unavail[doc.id].add(d)
        for d in wk["wends"]:
            if d not in hb[doc.id] and get(doc.id,d) == "_":
                setv(doc.id,d,"O"); unavail[doc.id].add(d)
        dc_info.append({"docId": doc.id, "weekEnd": wk["end"]})

    for info in dc_info:
        doc_id, week_end = info["docId"], info["weekEnd"]
        if not doc_id: continue
        for d in range(week_end+1, td+1):
            if is_wd(y,m,d) and d not in unavail[doc_id] and get(doc_id,d) == "_":
                if consecutive_working_days_before(doc_id,d) >= 6: continue
                side = "DM" if male_side_cnt[doc_id] <= (duty_cnt[doc_id]-male_side_cnt[doc_id]) else "DF"
                assign_duty(doc_id, d, side); break

    # Phase 4.5 – DC gap-fill
    for _d in range(1, td+1):
        if not is_wd(y,m,_d) or is_spec_blocked("DC",_d): continue
        if any(get(ph.id,_d)=="DC" for ph in docs): continue
        _dc_gap = [ph for ph in docs if get(ph.id,_d)=="_" and _d not in unavail[ph.id]
                   and consecutive_working_days_before(ph.id,_d)<6 and calc_h(ph.id)+8<=168]
        if _dc_gap:
            _dc_gap.sort(key=lambda ph:(dc_wk_cnt[ph.id],duty_cnt[ph.id],calc_h(ph.id),ph.id))
            setv(_dc_gap[0].id,_d,"DC"); unavail[_dc_gap[0].id].add(_d); dc_wk_cnt[_dc_gap[0].id]+=1

    # Phase 5 – daily duty coverage
    pairs = []
    for d in range(1, td+1):
        exist_dm = next((ph for ph in docs if get(ph.id,d)=="DM"), None)
        exist_df = next((ph for ph in docs if get(ph.id,d)=="DF"), None)
        need_dm, need_df = exist_dm is None, exist_df is None
        if not need_dm and not need_df:
            pairs.append({"d":d,"male":exist_dm.id,"female":exist_df.id}); continue
        avail = [(ph,duty_cnt[ph.id],calc_h(ph.id)) for ph in docs
                 if d not in unavail[ph.id] and get(ph.id,d)=="_"
                 and consecutive_working_days_before(ph.id,d)<6]
        avail.sort(key=lambda x:(x[1],x[2],x[0].id))
        just_docs = [x[0] for x in avail]
        m_doc, f_doc = exist_dm, exist_df
        if need_dm and need_df:
            if len(just_docs) >= 2:
                d1,d2 = just_docs[0],just_docs[1]
                if male_side_cnt[d1.id] > (duty_cnt[d1.id]-male_side_cnt[d1.id]): d1,d2=d2,d1
                m_doc,f_doc = d1,d2
            elif len(just_docs)==1: m_doc = just_docs[0]
        elif need_dm and just_docs: m_doc = just_docs[0]
        elif need_df and just_docs: f_doc = just_docs[0]
        assigned_m = assigned_f = None
        if m_doc and need_dm and assign_duty(m_doc.id,d,"DM"): assigned_m=m_doc.id
        if f_doc and need_df and (not assigned_m or f_doc.id!=assigned_m):
            if assign_duty(f_doc.id,d,"DF"): assigned_f=f_doc.id
        pairs.append({"d":d,"male":assigned_m or getattr(exist_dm,"id",None),
                      "female":assigned_f or getattr(exist_df,"id",None)})

    # Phase 5.5 – DM/DF rescue
    for _d in range(1, td+1):
        for _side,_needed in (("DM",not any(get(ph.id,_d)=="DM" for ph in docs)),
                               ("DF",not any(get(ph.id,_d)=="DF" for ph in docs))):
            if not _needed: continue
            _rescue = [ph for ph in docs if get(ph.id,_d) in MORNING_K or get(ph.id,_d)=="_"
                       if consecutive_working_days_before(ph.id,_d)<6 and calc_h(ph.id)+16<=168
                       if all((_d+pc>td or _d+pc not in pinned.get(ph.id,set()))
                              and (_d+pc>td or get(ph.id,_d+pc)!="DC") for pc in range(1,4))]
            if _rescue:
                _rescue.sort(key=lambda ph:(duty_cnt[ph.id],calc_h(ph.id),ph.id))
                _rph=_rescue[0]
                if get(_rph.id,_d) in MORNING_K: setv(_rph.id,_d,"_")
                assign_duty(_rph.id,_d,_side)

    # Phase 5.6 – minimum on-call guarantee (target: ≥ 3 per physician)
    # Scans for physicians below the minimum and tries to assign additional
    # duties without violating streak, hour, or pinned-day constraints.
    MIN_DUTIES = 3
    for ph in docs:
        while duty_cnt[ph.id] < MIN_DUTIES:
            placed = False
            for _d in range(1, td + 1):
                cur = get(ph.id, _d)
                if cur not in ("_",) and cur not in MORNING_K:
                    continue
                if consecutive_working_days_before(ph.id, _d) >= 6:
                    continue
                if calc_h(ph.id) + 16 > 168:
                    break  # no point scanning further days
                _ok = True
                for _pc in range(1, 4):
                    _pd = _d + _pc
                    if _pd <= td:
                        if _pd in pinned.get(ph.id, set()): _ok = False; break
                        if get(ph.id, _pd) == "DC":         _ok = False; break
                if not _ok:
                    continue
                _side = "DM" if male_side_cnt[ph.id] <= (duty_cnt[ph.id] - male_side_cnt[ph.id]) else "DF"
                if cur in MORNING_K: setv(ph.id, _d, "_")
                if assign_duty(ph.id, _d, _side):
                    placed = True; break
                else:
                    if cur in MORNING_K: setv(ph.id, _d, cur)  # restore on reject
            if not placed:
                break  # cannot reach minimum without violating hard constraints

    # Phase 6 – happy weekend guarantee (Sat + Sun both off) + single-day fallback
    wkends = [d for d in range(1,td+1) if is_we(y,m,d)]
    # Build Sat+Sun pairs: Saturday=6, Sunday=0 in day_of_week()
    we_pairs = []
    for _d in range(1, td+1):
        if day_of_week(y, m, _d) == 6 and _d+1 <= td and day_of_week(y, m, _d+1) == 0:
            we_pairs.append((_d, _d+1))
    for ph in docs:
        # First pass: try to guarantee a full Sat+Sun happy weekend.
        # IMPORTANT: blank ("_") slots are NOT confirmed off — Phase 7 will fill them
        # with mornings. Only count confirmed OFF_SET codes here.
        has_happy = any(
            get(ph.id,sat) in OFF_SET and get(ph.id,sun) in OFF_SET
            for sat,sun in we_pairs
        )
        if not has_happy:
            # Try to protect a free Sat+Sun pair by stamping "O" BEFORE Phase 7 runs.
            # Phase 7 will then see those days as off and assign coverage to others.
            for sat,sun in we_pairs:
                sc,uc = get(ph.id,sat), get(ph.id,sun)
                # "Free" means not locked by duty/leave/DC; blank or existing morning can be cleared
                sat_free = sc not in DUTY_SET and sc not in ("L","R","DC")
                sun_free = uc not in DUTY_SET and uc not in ("L","R","DC")
                if sat_free and sun_free:
                    if sc not in OFF_SET: setv(ph.id, sat, "O")
                    if uc not in OFF_SET: setv(ph.id, sun, "O")
                    break
        # Fallback: guarantee at least one single weekend day off (don't count "_" as off)
        if not any(get(ph.id,d) in OFF_SET for d in wkends):
            for w in wkends:
                if get(ph.id,w) not in DUTY_SET and get(ph.id,w) not in ("L","R","DC"):
                    setv(ph.id,w,"O"); break

    # Phase 7 – morning specialty fill
    spec_usage: Dict[str,int] = {code:0 for code in MORNING_K}
    for _d in range(1,td+1):
        for _ph in docs:
            _code=get(_ph.id,_d)
            if _code in MORNING_K: spec_usage[_code]+=1

    lock_map: Dict[int,Optional[str]] = {ph.id:None for ph in docs}

    _rng = _rnd.Random(y*1000+(m+1)*31)
    _default_docs = [ph for ph in docs if not (ph.first_duty_day and ph.first_duty_day>1)]
    _shuffled = list(_default_docs); _rng.shuffle(_shuffled)
    _slots_per_day = len(SUBS)+len(TEAMS); _first_group = _slots_per_day+4; _stagger_max=5
    for _gi,_ph in enumerate(_shuffled):
        _offset = 0 if _gi<_first_group else min((_gi-_first_group)//_slots_per_day+1,_stagger_max)
        for _sd in range(1,_offset+1):
            if get(_ph.id,_sd)=="_": setv(_ph.id,_sd,"O")

    for d in range(1, td+1):
        for ph in docs:
            code=get(ph.id,d)
            if code in DUTY_SET: lock_map[ph.id]=None
            elif code in MORNING_K: lock_map[ph.id]=code

        to_assign=[]; can_rest_early=[]
        for ph in docs:
            if get(ph.id,d)!="_": continue
            if calc_h(ph.id)+8>168: setv(ph.id,d,"O"); continue
            backward=consecutive_working_days_before(ph.id,d)
            if backward>=6: setv(ph.id,d,"O"); continue
            forward=preplaced_working_days_after(ph.id,d)
            if backward+1+forward>6: setv(ph.id,d,"O"); continue
            (can_rest_early if backward>=5 else to_assign).append(ph)

        needed=len(SUBS)+len(TEAMS); shortfall=max(0,needed-len(to_assign))
        if shortfall>0 and can_rest_early:
            can_rest_early.sort(key=lambda ph:(duty_cnt[ph.id],calc_h(ph.id),ph.id))
            to_assign.extend(can_rest_early[:shortfall])
            for ph in can_rest_early[shortfall:]: setv(ph.id,d,"O")
        else:
            for ph in can_rest_early: setv(ph.id,d,"O")

        locked_today=[(ph,lock_map[ph.id]) for ph in to_assign if lock_map[ph.id] is not None]
        free_today=[ph for ph in to_assign if lock_map[ph.id] is None]

        covered_today:Dict[str,int]={}
        for _ph in docs:
            _code=get(_ph.id,d)
            if _code in MORNING_K:
                covered_today[_code]=_ph.id
                if _code=="NENP": covered_today["NE"]=_ph.id; covered_today["NP"]=_ph.id

        redirectable=[]
        for ph,lock in locked_today:
            if lock=="NENP":
                ne_bl=is_spec_blocked("NE",d); np_bl=is_spec_blocked("NP",d)
                ne_op="NE" not in covered_today; np_op="NP" not in covered_today
                if ne_bl and np_bl: setv(ph.id,d,"O")
                elif ne_op and np_op and not ne_bl and not np_bl:
                    setv(ph.id,d,"NENP"); covered_today["NE"]=ph.id; covered_today["NP"]=ph.id
                    spec_usage["NE"]+=1; spec_usage["NP"]+=1
                elif ne_op and not ne_bl:
                    setv(ph.id,d,"NE"); lock_map[ph.id]="NE"
                    covered_today["NE"]=ph.id; spec_usage["NE"]+=1
                elif np_op and not np_bl:
                    setv(ph.id,d,"NP"); lock_map[ph.id]="NP"
                    covered_today["NP"]=ph.id; spec_usage["NP"]+=1
                else: redirectable.append(ph)
            elif is_spec_blocked(lock,d): setv(ph.id,d,"O")
            elif lock not in covered_today:
                setv(ph.id,d,lock); spec_usage[lock]+=1; covered_today[lock]=ph.id
            else: redirectable.append(ph)

        required_order=[s for s in (SUBS+TEAMS) if s not in covered_today and not is_spec_blocked(s,d)]
        fill_pool=free_today+redirectable
        fill_pool.sort(key=lambda ph:(duty_cnt[ph.id],calc_h(ph.id),ph.id))
        if len(fill_pool)<len(required_order) and "NE" in required_order and "NP" in required_order:
            required_order.remove("NE"); required_order.remove("NP"); required_order.insert(0,"NENP")

        for spec in required_order:
            if not fill_pool: break
            if spec=="NENP":
                best_idx=next((i for i,ph in enumerate(fill_pool) if pref_spec.get(ph.id) in ("NE","NP")),None)
            else:
                best_idx=next((i for i,ph in enumerate(fill_pool) if pref_spec.get(ph.id)==spec),None)
            if best_idx is None: best_idx=0
            ph=fill_pool.pop(best_idx)
            if spec=="NENP":
                setv(ph.id,d,"NENP"); lock_map[ph.id]="NENP"
                spec_usage["NE"]+=1; spec_usage["NP"]+=1
                covered_today["NE"]=ph.id; covered_today["NP"]=ph.id
            else:
                setv(ph.id,d,spec); lock_map[ph.id]=spec
                spec_usage[spec]+=1; covered_today[spec]=ph.id

        for ph in fill_pool: setv(ph.id,d,"O")

    # Phase 7.5 – team-round rescue
    for _d in range(1,td+1):
        for _team in ("T1","T2","T3"):
            if any(get(ph.id,_d)==_team for ph in docs): continue
            _subs_pool=[ph for ph in docs if get(ph.id,_d) in SUBS]
            if not _subs_pool: continue
            _subs_pool.sort(key=lambda ph:(0 if pref_spec.get(ph.id)==_team else 1,-calc_h(ph.id),ph.id))
            _rph=_subs_pool[0]; setv(_rph.id,_d,_team); lock_map[_rph.id]=_team

    # Phase 8 – Minimum hours enforcement (≥ 160 h per month)
    #
    # Hard rule: every physician must work at least 160 h per month.
    # The only legitimate reasons to fall below 160 h are:
    #   • Annual leave (L) – immovable, counts as zero working hours.
    #   • Random off day (R) – immovable, counts as zero working hours.
    #   • Manually assigned off day (O) that was pinned by the user.
    #
    # For any physician still below 160 h, plain "O" days that are not
    # hard-blocked (L/R/FDD) and not user-pinned are converted into 8-hour
    # morning shifts until the floor is reached or no eligible O days remain.
    #
    # Constraints respected:
    #   • Hard 168 h ceiling is never exceeded.
    #   • 6-consecutive-day limit is never violated.
    #   • L, R, PC, and user-pinned days are never touched.
    for ph in docs:
        if calc_h(ph.id) >= 160:
            continue
        convertible = sorted(
            d for d in range(1, td + 1)
            if get(ph.id, d) == "O"
            and d not in hb[ph.id]
            and d not in pinned[ph.id]
        )
        for d in convertible:
            if calc_h(ph.id) >= 160:
                break
            if calc_h(ph.id) + 8 > 168:
                break
            streak_before = consecutive_working_days_before(ph.id, d)
            streak_after  = preplaced_working_days_after(ph.id, d)
            if streak_before + 1 + streak_after > 6:
                continue
            best_code = pref_spec.get(ph.id) or ph.team
            if best_code not in MORNING_K:
                best_code = ph.team
            if is_spec_blocked(best_code, d):
                best_code = ph.team if ph.team in MORNING_K else "T1"
            setv(ph.id, d, best_code)

    return {"a": a, "pairs": pairs}


def compute_summary(docs, asgn, yr, mo):
    """Compute per-physician statistics for the given month."""
    td = dim(yr, mo)
    rows = []
    for ph in docs:
        def get(d): return asgn.get(f"{ph.id}|{yr}|{mo}|{d}", "_")
        h8=h16=calls=daycare=postcall=off=leave=random=blocked=0
        we_off=0
        for d in range(1, td+1):
            code=get(d)
            h=SHIFTS.get(code,{}).get("h",0)
            if h==8:  h8+=8
            if h==16: h16+=16; calls+=1
            if code=="DC": daycare+=1
            if code=="PC": postcall+=1
            if code in ("O","R"): off+=1
            if code=="L": leave+=1
            if code=="R": random+=1
            if code=="_": blocked+=1
            if is_we(yr,mo,d) and code in OFF_SET: we_off+=1
        rows.append({"name":ph.name,"team":ph.team,"initials":ph.initials,
                     "h8":h8,"h16":h16,"total":h8+h16,"calls":calls,
                     "daycare":daycare,"postcall":postcall,"off":off,
                     "leave":leave,"random":random,"blocked":blocked,
                     "weekend_off":we_off})
    return rows
