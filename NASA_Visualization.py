import asyncio
import base64
from datetime import datetime
import json
import math
import random
import urllib.error
import urllib.request
from nicegui import ui

# ---------------------------------------------------------
# MISSION SCENARIO PRESETS & PEER CREW ROSTER
# ---------------------------------------------------------
PRESETS = {
    "Nominal Orbit": {
        "delta_trt": 12.0, "iop": 16, "sleep_hrs": 7.4, "pvt_drift": 3,
        "ijv_flow": "Forward (Normal)", "hgb": 13.8, "hr": 64, "spo2": 98, "ppco2": 2.1,
        "urine_ca": 205, "urine_vol": 1.8, "potassium": 4.2,
        "exercise_pct": 95, "rad_msv": 42,
        "vit_d": 48, "vit_b12": 540, "ferritin": 68, "magnesium": 2.0, "sodium": 140,
        "cycle_mode": "Natural Cycle (Active)", "cycle_day": 10,
        "estradiol": 145, "progesterone": 1.2, "flow_status": "None / Dry",
        "menstrual_symptom": "None",
    },
    "Early SANS Watch": {
        "delta_trt": 36.0, "iop": 22, "sleep_hrs": 6.1, "pvt_drift": 12,
        "ijv_flow": "Stagnant / Oscillating", "hgb": 12.4, "hr": 72, "spo2": 96, "ppco2": 3.3,
        "urine_ca": 265, "urine_vol": 1.4, "potassium": 4.0,
        "exercise_pct": 88, "rad_msv": 75,
        "vit_d": 24, "vit_b12": 310, "ferritin": 26, "magnesium": 1.8, "sodium": 146,
        "cycle_mode": "Natural Cycle (Active)", "cycle_day": 21,
        "estradiol": 110, "progesterone": 11.5, "flow_status": "None / Dry",
        "menstrual_symptom": "Mild Fluid Retention / Bloating",
    },
    "Critical Alert": {
        "delta_trt": 58.0, "iop": 26, "sleep_hrs": 5.0, "pvt_drift": 24,
        "ijv_flow": "Reversed / Thrombus", "hgb": 10.6, "hr": 112, "spo2": 91, "ppco2": 4.7,
        "urine_ca": 330, "urine_vol": 1.1, "potassium": 3.3,
        "exercise_pct": 55, "rad_msv": 260,
        "vit_d": 16, "vit_b12": 195, "ferritin": 11, "magnesium": 1.4, "sodium": 150,
        "cycle_mode": "Natural Cycle (Active)", "cycle_day": 3,
        "estradiol": 22, "progesterone": 0.4, "flow_status": "Heavy / Menorrhagia",
        "menstrual_symptom": "Moderate Cramps & Fatigue",
    },
}

PEER_CREW = [
    {
        "id": "maya",
        "name": "Dr. Maya Lin",
        "role": "Flight Engineer",
        "gender": "Female",
        "readiness": 94,
        "ared": 96,
        "sleep": 7.6,
        "hydration": 2.2,
        "vit_d": 52,
        "streak": 18,
        "xp": 1890,
        "status": "NOMINAL",
    },
    {
        "id": "samira",
        "name": "Lt. Samira Patel",
        "role": "Mission Specialist",
        "gender": "Female",
        "readiness": 89,
        "ared": 91,
        "sleep": 7.1,
        "hydration": 1.9,
        "vit_d": 41,
        "streak": 15,
        "xp": 1640,
        "status": "NOMINAL",
    },
    {
        "id": "alexei",
        "name": "Maj. Alexei Volkov",
        "role": "Command Pilot",
        "gender": "Male",
        "readiness": 81,
        "ared": 84,
        "sleep": 6.4,
        "hydration": 1.6,
        "vit_d": 29,
        "streak": 9,
        "xp": 1310,
        "status": "WATCH",
    },
]

state = {
    "selected_system": "Renal & Metabolic",
    "gender": "Female",
    "gemini_api_key": "",
    "ai_response": "",
    "ai_last_prompt": "Auto-Synthesis",
    "xp": 1420,
    "streak_days": 12,
    "completed_quests": [],
    "compare_metric": "readiness",
    **PRESETS["Early SANS Watch"],
    "cycle_log": [
        {
            "mission_day": "FD-42",
            "cycle_day": 19,
            "phase": "Luteal Phase",
            "mode": "Natural Cycle (Active)",
            "flow": "None / Dry",
            "hormones": "E2: 125 pg/mL | P4: 12.8 ng/mL",
            "notes": "Nominal luteal temp +0.3°C",
        },
        {
            "mission_day": "FD-43",
            "cycle_day": 20,
            "phase": "Luteal Phase",
            "mode": "Natural Cycle (Active)",
            "flow": "None / Dry",
            "hormones": "E2: 118 pg/mL | P4: 12.1 ng/mL",
            "notes": "ARED workout completed (90%)",
        },
    ],
}


def get_active_astronaut_name():
    return "Cmdr. Elena Vance" if state["gender"] == "Female" else "Capt. Liam Vance"


# ---------------------------------------------------------
# VITAMINS, MINERALS & ELECTROLYTES COMPARISON ENGINE
# ---------------------------------------------------------
def evaluate_nutrients():
    is_female = state["gender"] == "Female"
    ferritin_low, ferritin_high, ferritin_max = (15.0, 150.0, 200.0) if is_female else (30.0, 300.0, 380.0)

    specs = [
        {
            "key": "vit_d",
            "name": "Vitamin D (25-OH)",
            "role": "Bone & Immunity",
            "val": float(state["vit_d"]),
            "unit": "ng/mL",
            "norm_low": 30.0,
            "norm_high": 80.0,
            "crit_low": 20.0,
            "crit_high": 100.0,
            "scale_min": 0.0,
            "scale_max": 110.0,
            "fmt": "{:.0f}",
            "low_tip": "Take Vitamin D3 (2,000 IU/day) to counter zero-UV bone resorption.",
            "high_tip": "Pause Vitamin D3 supplement; monitor serum & urinary calcium.",
        },
        {
            "key": "vit_b12",
            "name": "Vitamin B12",
            "role": "RBC & SANS Nerve",
            "val": float(state["vit_b12"]),
            "unit": "pg/mL",
            "norm_low": 250.0,
            "norm_high": 900.0,
            "crit_low": 180.0,
            "crit_high": 1050.0,
            "scale_min": 100.0,
            "scale_max": 1100.0,
            "fmt": "{:.0f}",
            "low_tip": "Supplement B12 + folate to support RBCs & one-carbon SANS protection.",
            "high_tip": "Reduce B-complex dosing; recheck on next blood panel.",
        },
        {
            "key": "ferritin",
            "name": f"Ferritin ({state['gender']} Iron)",
            "role": "Hgb & Oxygen Stores",
            "val": float(state["ferritin"]),
            "unit": "ng/mL",
            "norm_low": ferritin_low,
            "norm_high": ferritin_high,
            "crit_low": 10.0 if is_female else 20.0,
            "crit_high": 200.0 if is_female else 350.0,
            "scale_min": 0.0,
            "scale_max": ferritin_max,
            "fmt": "{:.0f}",
            "low_tip": "Administer heme-iron + Vitamin C to rebuild ferritin & hemoglobin.",
            "high_tip": "Avoid iron-fortified rations to limit microgravity oxidative stress.",
        },
        {
            "key": "magnesium",
            "name": "Magnesium (Mg²⁺)",
            "role": "Muscle & Stone Guard",
            "val": float(state["magnesium"]),
            "unit": "mg/dL",
            "norm_low": 1.7,
            "norm_high": 2.3,
            "crit_low": 1.4,
            "crit_high": 2.6,
            "scale_min": 1.0,
            "scale_max": 3.0,
            "fmt": "{:.1f}",
            "low_tip": "Give oral magnesium citrate to prevent arrhythmias & renal stones.",
            "high_tip": "Review supplement intake & monitor neuromuscular reflexes.",
        },
        {
            "key": "potassium",
            "name": "Potassium (K⁺)",
            "role": "Cardiac & Fluid",
            "val": float(state["potassium"]),
            "unit": "mmol/L",
            "norm_low": 3.5,
            "norm_high": 5.0,
            "crit_low": 3.2,
            "crit_high": 5.4,
            "scale_min": 2.5,
            "scale_max": 6.2,
            "fmt": "{:.1f}",
            "low_tip": "Administer potassium citrate & electrolyte hydration pouch.",
            "high_tip": "Restrict K+ intake & run 12-lead ECG immediately.",
        },
        {
            "key": "sodium",
            "name": "Sodium (Na⁺)",
            "role": "Fluid Shift & Bone",
            "val": float(state["sodium"]),
            "unit": "mmol/L",
            "norm_low": 135.0,
            "norm_high": 145.0,
            "crit_low": 130.0,
            "crit_high": 149.0,
            "scale_min": 125.0,
            "scale_max": 155.0,
            "fmt": "{:.0f}",
            "low_tip": "Provide isotonic electrolyte broth; evaluate fluid balance.",
            "high_tip": "Drink >2.5 L/day water & switch to low-sodium space rations.",
        },
    ]

    evaluated = []
    for s in specs:
        v = s["val"]
        if v < s["crit_low"]:
            st, color, tip = "CRIT LOW", "#FF1744", s["low_tip"]
        elif v < s["norm_low"]:
            st, color, tip = "LOW", "#FFC400", s["low_tip"]
        elif v > s["crit_high"]:
            st, color, tip = "CRIT HIGH", "#FF1744", s["high_tip"]
        elif v > s["norm_high"]:
            st, color, tip = "HIGH", "#FFC400", s["high_tip"]
        else:
            st, color, tip = "OPTIMAL", "#00E676", ""

        span = s["scale_max"] - s["scale_min"]
        band_left = round(((s["norm_low"] - s["scale_min"]) / span) * 100.0, 1)
        band_width = round(((s["norm_high"] - s["norm_low"]) / span) * 100.0, 1)
        marker_pct = max(2.0, min(98.0, round(((v - s["scale_min"]) / span) * 100.0, 1)))

        evaluated.append({
            **s,
            "status": st,
            "color": color,
            "tip": tip,
            "band_left": band_left,
            "band_width": band_width,
            "marker_pct": marker_pct,
        })
    return evaluated


def render_vitamin_comparison_card():
    nutrients = evaluate_nutrients()
    out_of_range = [n for n in nutrients if n["status"] != "OPTIMAL"]

    with ui.card().classes("w-full bg-slate-900 border border-emerald-500/40 p-4"):
        with ui.row().classes("w-full justify-between items-center flex-wrap gap-2"):
            with ui.row().classes("items-center gap-2"):
                ui.label("💊 Vitamins, Minerals & Electrolytes Comparison").classes("text-base font-bold text-emerald-300")
                if out_of_range:
                    ui.badge(f"{len(out_of_range)} OUT OF RANGE", color="warning").classes("text-[10px]")
                else:
                    ui.badge("ALL OPTIMAL", color="positive").classes("text-[10px]")

            with ui.row().classes("items-center gap-3 text-[11px] text-slate-400"):
                with ui.row().classes("items-center gap-1"):
                    ui.element("div").classes("w-3 h-2.5 bg-emerald-500/35 border-x border-emerald-400")
                    ui.label("Normal Range")
                with ui.row().classes("items-center gap-1"):
                    ui.element("div").classes("w-2.5 h-2.5 rounded-full bg-sky-400 border border-white")
                    ui.label("Your Level")

        with ui.element("div").classes("w-full grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 mt-2"):
            for n in nutrients:
                val_str = n["fmt"].format(n["val"])
                norm_str = f"{n['fmt'].format(n['norm_low'])}–{n['fmt'].format(n['norm_high'])} {n['unit']}"
                badge_col = "positive" if n["status"] == "OPTIMAL" else ("negative" if "CRIT" in n["status"] else "warning")

                with ui.column().classes("w-full gap-1"):
                    with ui.row().classes("w-full justify-between items-center"):
                        with ui.row().classes("items-baseline gap-1.5"):
                            ui.label(n["name"]).classes("text-xs font-bold text-slate-100")
                            ui.label(f"• {n['role']}").classes("text-[10px] text-slate-400")
                        with ui.row().classes("items-center gap-1.5"):
                            ui.label(f"{val_str} {n['unit']}").classes("text-xs font-mono font-bold").style(
                                f"color: {n['color']};"
                            )
                            ui.badge(n["status"], color=badge_col).classes("text-[9px] px-1.5 py-0")

                    with ui.element("div").classes(
                        "w-full h-3.5 bg-slate-950 border border-slate-800 rounded-full relative my-0.5"
                    ):
                        ui.element("div").classes(
                            "h-full bg-emerald-500/30 border-x-2 border-emerald-400/90 absolute top-0"
                        ).style(f"left: {n['band_left']}%; width: {n['band_width']}%;")

                        ui.element("div").classes(
                            "w-3 h-4.5 -top-0.5 rounded-sm border border-white shadow-md absolute transition-all duration-300"
                        ).style(
                            f"left: calc({n['marker_pct']}% - 6px); background-color: {n['color']}; "
                            f"box-shadow: 0 0 8px {n['color']};"
                        )

                    with ui.row().classes("w-full justify-between text-[10px] text-slate-400 font-mono"):
                        ui.label(f"Low ({n['fmt'].format(n['scale_min'])})")
                        ui.label(f"Normal: {norm_str}").classes("text-emerald-300/90")
                        ui.label(f"High ({n['fmt'].format(n['scale_max'])})")

        if out_of_range:
            ui.separator().classes("my-2")
            with ui.column().classes("w-full gap-1 bg-slate-950/80 border border-amber-500/30 rounded-lg p-2.5"):
                ui.label("⚡ Recommended Micronutrient & Hydration Adjustments:").classes(
                    "text-xs font-bold text-amber-300"
                )
                for n in out_of_range:
                    ui.label(f"• {n['name']} ({n['status']}): {n['tip']}").classes("text-xs text-slate-200")


# ---------------------------------------------------------
# GAMIFICATION & CREW COMPARISON HELPERS
# ---------------------------------------------------------
def get_rank_info(xp):
    level = (xp // 250) + 1
    titles = [
        "Orbital Cadet",
        "Flight Specialist",
        "Mission Biomed Officer",
        "Orbital Vanguard",
        "Deep-Space Commander",
        "Artemis Elite",
    ]
    title = titles[min(level - 1, len(titles) - 1)]
    progress_pct = round(((xp % 250) / 250.0) * 100.0, 1)
    next_xp = level * 250
    return level, title, progress_pct, next_xp


def get_crew_roster_comparison(results):
    readiness = compute_readiness_score(results)
    has_red = any(v["status"] == "RED" for v in results.values())
    has_yellow = any(v["status"] == "YELLOW" for v in results.values())
    status_str = "ALERT" if has_red else ("WATCH" if has_yellow else "NOMINAL")

    you_entry = {
        "id": "you",
        "name": f"{get_active_astronaut_name()} (You)",
        "role": "Mission Commander",
        "gender": state["gender"],
        "readiness": readiness,
        "ared": int(state["exercise_pct"]),
        "sleep": round(float(state["sleep_hrs"]), 1),
        "hydration": round(float(state["urine_vol"]), 1),
        "vit_d": int(state["vit_d"]),
        "streak": int(state["streak_days"]),
        "xp": int(state["xp"]),
        "status": status_str,
    }
    full_roster = sorted([you_entry] + PEER_CREW, key=lambda c: c["readiness"], reverse=True)
    for idx, member in enumerate(full_roster, 1):
        member["rank"] = f"#{idx}"
    you_rank = next(i + 1 for i, c in enumerate(full_roster) if c["id"] == "you")
    return full_roster, you_entry, you_rank


def build_daily_quests(results):
    nutrients_out = [n for n in evaluate_nutrients() if n["status"] != "OPTIMAL"]
    quests = [
        {
            "id": "quest_hydrate",
            "icon": "💧",
            "title": "Drink +500 mL Electrolyte Water",
            "desc": f"Target ≥ 1.75 L/d output (Current: {state['urine_vol']:.1f} L/d)",
            "xp": 50,
            "urgent": state["urine_vol"] < 1.75 or state["sodium"] > 145,
        },
        {
            "id": "quest_ared",
            "icon": "🏋️",
            "title": "Complete Daily ARED Squat & Deadlift Set",
            "desc": f"Target ≥ 85% bone-loading compliance (Current: {state['exercise_pct']}%)",
            "xp": 75,
            "urgent": state["exercise_pct"] < 85,
        },
        {
            "id": "quest_vitamins",
            "icon": "💊",
            "title": "Take Vitamin D3, B12 & Iron Protocol",
            "desc": f"{len(nutrients_out)} micronutrient(s) need rebalancing" if nutrients_out else "Maintain optimal vitamin & mineral reserves",
            "xp": 45,
            "urgent": len(nutrients_out) > 0,
        },
        {
            "id": "quest_lbnp",
            "icon": "🩺",
            "title": "Run 30-Min LBNP Fluid Redistribution",
            "desc": "Counters cephalad fluid shift for SANS & jugular flow",
            "xp": 60,
            "urgent": results["Ocular (SANS)"]["status"] != "GREEN" or results["Vascular & Hematology"]["status"] != "GREEN",
        },
    ]
    return sorted(quests, key=lambda q: (q["id"] in state["completed_quests"], not q["urgent"]))


def render_gamification_card(results, refresh_callback):
    level, rank_title, xp_pct, next_xp = get_rank_info(state["xp"])
    quests = build_daily_quests(results)
    done_count = sum(1 for q in quests if q["id"] in state["completed_quests"])
    nutrients_out = [n for n in evaluate_nutrients() if n["status"] != "OPTIMAL"]

    patches = [
        ("💧 Hydration Pro", state["urine_vol"] >= 1.75, "Urine output ≥ 1.75 L/d"),
        ("🏋️ Zero-G Iron", state["exercise_pct"] >= 90, "ARED compliance ≥ 90%"),
        ("💊 Nutrient Optimal", len(nutrients_out) == 0, "All vitamins & electrolytes in green band"),
        ("🛡️ SANS Guardian", results["Ocular (SANS)"]["status"] == "GREEN", "Retinal ΔTRT & IOP within baseline"),
    ]

    def complete_quest(q):
        if q["id"] in state["completed_quests"]:
            return
        state["completed_quests"].append(q["id"])
        state["xp"] += q["xp"]
        if len(state["completed_quests"]) == 1:
            state["streak_days"] += 1

        # Apply realistic physiological feedback from completing the countermeasure
        if q["id"] == "quest_hydrate":
            state["urine_vol"] = round(min(2.6, state["urine_vol"] + 0.3), 1)
            state["sodium"] = max(138, state["sodium"] - 2)
        elif q["id"] == "quest_ared":
            state["exercise_pct"] = min(100, state["exercise_pct"] + 6)
        elif q["id"] == "quest_vitamins":
            state["vit_d"] = min(65, state["vit_d"] + 7)
            state["ferritin"] = min(90, state["ferritin"] + 6)
            state["vit_b12"] = min(650, state["vit_b12"] + 45)
        elif q["id"] == "quest_lbnp":
            state["delta_trt"] = round(max(10.0, state["delta_trt"] - 4.0), 1)
            state["iop"] = max(14, state["iop"] - 1)

        if not state["gemini_api_key"].strip():
            state["ai_response"] = generate_local_ai_insights(evaluate_crew_health(), state["ai_last_prompt"])
        ui.notify(f"+{q['xp']} XP Earned! {q['title']} logged.", type="positive")
        refresh_callback()

    def reset_quests():
        state["completed_quests"] = []
        refresh_callback()

    with ui.card().classes("w-full bg-slate-900 border border-amber-400/40 p-4"):
        with ui.row().classes("w-full justify-between items-center flex-wrap gap-2"):
            with ui.row().classes("items-center gap-2"):
                ui.label("🏅 Mission Readiness Quests & Flight Patches").classes("text-base font-bold text-amber-300")
                ui.badge(f"LVL {level} • {rank_title.upper()}", color="amber").classes("text-[10px] text-slate-950 font-bold")
            with ui.row().classes("items-center gap-2"):
                ui.badge(f"🔥 {state['streak_days']}-DAY STREAK", color="deep-orange").classes("text-[10px]")
                ui.label(f"{state['xp']} / {next_xp} XP").classes("text-xs font-mono text-amber-200 font-bold")

        # XP Level Progress Bar
        with ui.element("div").classes("w-full h-2.5 bg-slate-950 border border-slate-800 rounded-full overflow-hidden my-1.5"):
            ui.element("div").classes(
                "h-full bg-gradient-to-r from-amber-500 via-yellow-400 to-emerald-400 transition-all duration-300"
            ).style(f"width: {xp_pct}%;")

        # Earnable Mission Patches Row
        with ui.row().classes("w-full gap-2 my-1.5 flex-wrap items-center"):
            ui.label("Mission Patches:").classes("text-[11px] text-slate-400 font-semibold")
            for p_label, unlocked, p_tip in patches:
                patch_style = (
                    "bg-emerald-950/90 border border-emerald-400 text-emerald-200 shadow-sm"
                    if unlocked
                    else "bg-slate-950/60 border border-slate-800 text-slate-500 opacity-60"
                )
                with ui.element("div").classes(f"px-2.5 py-0.5 rounded-full text-[11px] font-medium {patch_style}"):
                    ui.label(f"{p_label} {'✓' if unlocked else '🔒'}").tooltip(p_tip)

        ui.separator().classes("my-2")

        with ui.row().classes("w-full justify-between items-center mb-1"):
            ui.label(f"Daily Protocol Checklist ({done_count}/{len(quests)} Completed Today)").classes(
                "text-xs font-semibold text-slate-300"
            )
            if done_count > 0:
                ui.button("Reset Quests", on_click=reset_quests).props("dense flat size=xs color=grey")

        # Interactive Quest Items
        with ui.column().classes("w-full gap-1.5"):
            for q in quests:
                is_done = q["id"] in state["completed_quests"]
                row_bg = (
                    "bg-emerald-950/25 border border-emerald-500/30"
                    if is_done
                    else ("bg-amber-950/25 border border-amber-500/40" if q["urgent"] else "bg-slate-950/80 border border-slate-800")
                )
                with ui.row().classes(f"w-full justify-between items-center rounded-lg px-3 py-2 {row_bg}"):
                    with ui.row().classes("items-center gap-2.5 flex-1"):
                        ui.label(q["icon"]).classes("text-base")
                        with ui.column().classes("gap-0"):
                            with ui.row().classes("items-center gap-1.5"):
                                ui.label(q["title"]).classes(
                                    f"text-xs font-bold {'line-through text-slate-400' if is_done else 'text-slate-100'}"
                                )
                                if q["urgent"] and not is_done:
                                    ui.badge("PRIORITY", color="warning").classes("text-[9px] px-1 py-0")
                            ui.label(q["desc"]).classes("text-[11px] text-slate-400")

                    if is_done:
                        ui.badge(f"✓ +{q['xp']} XP", color="positive").classes("text-[10px] px-2 py-0.5")
                    else:
                        ui.button(
                            f"Complete (+{q['xp']} XP)",
                            on_click=lambda item=q: complete_quest(item),
                        ).props("dense unelevated size=sm color=amber text-color=black").classes("font-bold")


def render_crew_comparison_card(results, refresh_callback):
    roster, you_entry, you_rank = get_crew_roster_comparison(results)

    metric_configs = {
        "readiness": {"label": "Readiness Score", "unit": "%", "max": 100.0, "fmt": "{:.0f}", "good_high": True},
        "hydration": {"label": "Hydration Output", "unit": " L/d", "max": 2.6, "fmt": "{:.1f}", "good_high": True},
        "ared": {"label": "ARED Exercise", "unit": "%", "max": 100.0, "fmt": "{:.0f}", "good_high": True},
        "sleep": {"label": "Sleep Duration", "unit": " hrs", "max": 9.0, "fmt": "{:.1f}", "good_high": True},
        "vit_d": {"label": "Vitamin D (25-OH)", "unit": " ng/mL", "max": 80.0, "fmt": "{:.0f}", "good_high": True},
    }
    m_key = state["compare_metric"] if state["compare_metric"] in metric_configs else "readiness"
    cfg = metric_configs[m_key]

    avg_val = sum(c[m_key] for c in roster) / len(roster)
    avg_pct = max(4.0, min(96.0, round((avg_val / cfg["max"]) * 100.0, 1)))
    you_val = you_entry[m_key]
    delta = you_val - avg_val
    delta_str = f"{'+' if delta >= 0 else ''}{cfg['fmt'].format(delta)}{cfg['unit']} vs Crew Avg"
    delta_color = "positive" if delta >= 0 else "warning"

    with ui.card().classes("w-full bg-slate-900 border border-cyan-500/40 p-4"):
        with ui.row().classes("w-full justify-between items-center flex-wrap gap-2"):
            with ui.row().classes("items-center gap-2"):
                ui.label("👩‍🚀 Crew-4 Peer Telemetry Comparison").classes("text-base font-bold text-cyan-300")
                ui.badge(f"YOUR RANK: #{you_rank} / {len(roster)}", color="cyan").classes("text-[10px] text-slate-950 font-bold")
            ui.badge(delta_str, color=delta_color).classes("text-[10px]")

        # Metric Selector Chips
        with ui.row().classes("w-full gap-1.5 my-2 flex-wrap items-center"):
            ui.label("Compare Metric:").classes("text-[11px] text-slate-400 mr-1")
            for k, m in metric_configs.items():
                is_active = k == m_key
                ui.button(
                    m["label"],
                    on_click=lambda mk=k: (state.update({"compare_metric": mk}), refresh_callback()),
                ).props(
                    f"dense {'unelevated color=cyan text-color=black' if is_active else 'outline color=cyan'} size=sm"
                )

        # Horizontal Bar Comparison Against Crew Average
        with ui.column().classes("w-full gap-2.5 my-1"):
            for member in sorted(roster, key=lambda c: c[m_key], reverse=True):
                is_you = member["id"] == "you"
                val = member[m_key]
                bar_pct = max(4.0, min(100.0, round((val / cfg["max"]) * 100.0, 1)))
                bar_color = (
                    "bg-gradient-to-r from-sky-500 to-cyan-300"
                    if is_you
                    else "bg-slate-600"
                )

                with ui.column().classes("w-full gap-0.5"):
                    with ui.row().classes("w-full justify-between items-center text-xs"):
                        with ui.row().classes("items-center gap-1.5"):
                            ui.label(member["name"]).classes(
                                f"{'font-bold text-cyan-300' if is_you else 'text-slate-200'}"
                            )
                            ui.label(f"({member['role']})").classes("text-[10px] text-slate-400")
                        ui.label(f"{cfg['fmt'].format(val)}{cfg['unit']}").classes(
                            f"font-mono {'font-bold text-cyan-300' if is_you else 'text-slate-300'}"
                        )

                    with ui.element("div").classes(
                        "w-full h-3.5 bg-slate-950 border border-slate-800 rounded-full relative"
                    ):
                        ui.element("div").classes(f"h-full rounded-full transition-all duration-300 {bar_color}").style(
                            f"width: {bar_pct}%;"
                        )
                        # Vertical Dashed Line for Crew Average
                        ui.element("div").classes(
                            "h-5 -top-0.5 border-l-2 border-dashed border-amber-400 absolute"
                        ).style(f"left: {avg_pct}%;").tooltip(
                            f"Crew Average: {cfg['fmt'].format(avg_val)}{cfg['unit']}"
                        )

        with ui.row().classes("w-full justify-between items-center text-[11px] text-slate-400 mt-1"):
            ui.label(f"--- Dashed Amber Line = Crew Mean ({cfg['fmt'].format(avg_val)}{cfg['unit']})")
            ui.label("Live Multi-Crew Sync Active")

        # Full Crew Multi-Metric Leaderboard Table
        ui.table(
            columns=[
                {"name": "rank", "label": "Rank", "field": "rank", "align": "center"},
                {"name": "name", "label": "Astronaut", "field": "name", "align": "left"},
                {"name": "readiness", "label": "Readiness %", "field": "readiness", "align": "center"},
                {"name": "hydration", "label": "Hydration (L)", "field": "hydration", "align": "center"},
                {"name": "ared", "label": "ARED %", "field": "ared", "align": "center"},
                {"name": "sleep", "label": "Sleep (h)", "field": "sleep", "align": "center"},
                {"name": "vit_d", "label": "Vit D", "field": "vit_d", "align": "center"},
                {"name": "streak", "label": "Streak (d)", "field": "streak", "align": "center"},
            ],
            rows=roster,
        ).props("dense flat bordered dark").classes("w-full mt-2 text-xs")


# ---------------------------------------------------------
# VISUAL COUNTERMEASURE ANIMATION LIBRARY (PURE SVG)
# ---------------------------------------------------------
ACTION_META = {
    "HYDRATION": {
        "title": "Drink Water (>2.5 L/day)",
        "subtitle": "Boost oral water & electrolytes to flush calcium & restore plasma volume.",
        "border": "#38BDF8",
    },
    "LBNP": {
        "title": "Apply LBNP / Thigh Cuffs",
        "subtitle": "Run Lower Body Negative Pressure (-25 mmHg) to pull headward fluid down.",
        "border": "#60A5FA",
    },
    "EXERCISE": {
        "title": "ARED Resistive Exercise",
        "subtitle": "Perform daily ARED squats, deadlifts & treadmill harness loading.",
        "border": "#F59E0B",
    },
    "SLEEP_LIGHT": {
        "title": "Recovery Sleep & LED Shift",
        "subtitle": "Enforce 8-hr protected rest & tune cabin blue-enriched LED lighting.",
        "border": "#A855F7",
    },
    "OXYGEN_ECLSS": {
        "title": "Check CO2 Scrubber & O2",
        "subtitle": "Verify ECLSS CO2 removal, increase airflow & administer supplemental O2.",
        "border": "#10B981",
    },
    "SHIELDING": {
        "title": "Enter Storm Shelter",
        "subtitle": "Move to polyethylene/water-shielded module & halt unshielded EVAs.",
        "border": "#F97316",
    },
    "IRON_NUTRITION": {
        "title": "Iron & Vitamin Support",
        "subtitle": "Administer heme-iron, Vitamin D3, B12 & folate for RBC & bone health.",
        "border": "#F43F5E",
    },
    "FLIGHT_SURGEON": {
        "title": "Flight Surgeon & POCUS",
        "subtitle": "Initiate immediate ground consult & onboard ultrasound scan.",
        "border": "#EF4444",
    },
    "NOMINAL": {
        "title": "Nominal • Maintain Routine",
        "subtitle": "All indicators within NASA-STD-3001 limits — continue standard ops.",
        "border": "#00E676",
    },
}


def build_action_svg(action_type):
    if action_type == "HYDRATION":
        return """
        <svg viewBox="0 0 140 105" width="140" height="105" xmlns="http://www.w3.org/2000/svg">
          <rect width="140" height="105" rx="10" fill="#082F49" stroke="#38BDF8" stroke-width="1.5"/>
          <path d="M 70 18 L 70 9 L 82 6" fill="none" stroke="#BAE6FD" stroke-width="2.5" stroke-linecap="round"/>
          <rect x="46" y="18" width="48" height="64" rx="10" fill="#0F172A" stroke="#7DD3FC" stroke-width="2"/>
          <rect x="49" y="42" width="42" height="37" rx="7" fill="#0284C7" opacity="0.9">
            <animate attributeName="y" values="66;30;66" dur="3.0s" repeatCount="indefinite"/>
            <animate attributeName="height" values="13;49;13" dur="3.0s" repeatCount="indefinite"/>
          </rect>
          <ellipse cx="70" cy="42" rx="20" ry="2.8" fill="#38BDF8">
            <animate attributeName="cy" values="66;30;66" dur="3.0s" repeatCount="indefinite"/>
          </ellipse>
          <circle cx="60" cy="70" r="2.2" fill="#E0F2FE">
            <animate attributeName="cy" values="72;34" dur="1.7s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values="1;0" dur="1.7s" repeatCount="indefinite"/>
          </circle>
          <circle cx="78" cy="68" r="1.8" fill="#E0F2FE">
            <animate attributeName="cy" values="70;32" dur="2.2s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values="1;0" dur="2.2s" repeatCount="indefinite"/>
          </circle>
          <text x="70" y="96" text-anchor="middle" fill="#7DD3FC" font-size="9" font-weight="bold" font-family="sans-serif">DRINK WATER +2.5L</text>
        </svg>
        """

    if action_type == "LBNP":
        return """
        <svg viewBox="0 0 140 105" width="140" height="105" xmlns="http://www.w3.org/2000/svg">
          <rect width="140" height="105" rx="10" fill="#0F172A" stroke="#60A5FA" stroke-width="1.5"/>
          <circle cx="70" cy="18" r="7" fill="none" stroke="#93C5FD" stroke-width="1.8"/>
          <line x1="70" y1="25" x2="70" y2="48" stroke="#93C5FD" stroke-width="2.2"/>
          <rect x="52" y="44" width="36" height="38" rx="6" fill="#1E3A8A" fill-opacity="0.55" stroke="#60A5FA" stroke-width="1.8" stroke-dasharray="3,2"/>
          <path d="M 38 26 L 38 72 M 33 66 L 38 73 L 43 66" fill="none" stroke="#38BDF8" stroke-width="2.2" stroke-linecap="round">
            <animateTransform attributeName="transform" type="translate" values="0,-6; 0,6; 0,-6" dur="1.4s" repeatCount="indefinite"/>
          </path>
          <path d="M 102 26 L 102 72 M 97 66 L 102 73 L 107 66" fill="none" stroke="#38BDF8" stroke-width="2.2" stroke-linecap="round">
            <animateTransform attributeName="transform" type="translate" values="0,-6; 0,6; 0,-6" dur="1.4s" repeatCount="indefinite"/>
          </path>
          <text x="70" y="96" text-anchor="middle" fill="#93C5FD" font-size="9" font-weight="bold" font-family="sans-serif">LBNP FLUID SHIFT</text>
        </svg>
        """

    if action_type == "EXERCISE":
        return """
        <svg viewBox="0 0 140 105" width="140" height="105" xmlns="http://www.w3.org/2000/svg">
          <rect width="140" height="105" rx="10" fill="#1C1917" stroke="#F59E0B" stroke-width="1.5"/>
          <g>
            <animateTransform attributeName="transform" type="translate" values="0,12; 0,-12; 0,12" dur="1.8s" repeatCount="indefinite"/>
            <line x1="30" y1="48" x2="110" y2="48" stroke="#FBBF24" stroke-width="3.5" stroke-linecap="round"/>
            <rect x="24" y="36" width="8" height="24" rx="2" fill="#F59E0B"/>
            <rect x="108" y="36" width="8" height="24" rx="2" fill="#F59E0B"/>
            <rect x="17" y="40" width="5" height="16" rx="1.5" fill="#D97706"/>
            <rect x="118" y="40" width="5" height="16" rx="1.5" fill="#D97706"/>
          </g>
          <ellipse cx="70" cy="76" rx="26" ry="4" fill="none" stroke="#F59E0B" stroke-width="1.5">
            <animate attributeName="rx" values="18;34;18" dur="1.8s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values="0.9;0.2;0.9" dur="1.8s" repeatCount="indefinite"/>
          </ellipse>
          <text x="70" y="96" text-anchor="middle" fill="#FCD34D" font-size="9" font-weight="bold" font-family="sans-serif">ARED SQUATS / LOAD</text>
        </svg>
        """

    if action_type == "SLEEP_LIGHT":
        return """
        <svg viewBox="0 0 140 105" width="140" height="105" xmlns="http://www.w3.org/2000/svg">
          <rect width="140" height="105" rx="10" fill="#1E1B4B" stroke="#A855F7" stroke-width="1.5"/>
          <path d="M 56 26 A 22 22 0 1 0 80 62 A 17 17 0 1 1 56 26 Z" fill="#C084FC"/>
          <text x="76" y="48" fill="#E9D5FF" font-size="12" font-weight="bold" font-family="sans-serif">Z
            <animate attributeName="y" values="52;36" dur="2.0s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values="1;0" dur="2.0s" repeatCount="indefinite"/>
          </text>
          <text x="90" y="38" fill="#E9D5FF" font-size="15" font-weight="bold" font-family="sans-serif">Z
            <animate attributeName="y" values="44;24" dur="2.4s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values="1;0" dur="2.4s" repeatCount="indefinite"/>
          </text>
          <text x="70" y="96" text-anchor="middle" fill="#D8B4FE" font-size="9" font-weight="bold" font-family="sans-serif">8-HR SLEEP &amp; LED</text>
        </svg>
        """

    if action_type == "OXYGEN_ECLSS":
        return """
        <svg viewBox="0 0 140 105" width="140" height="105" xmlns="http://www.w3.org/2000/svg">
          <rect width="140" height="105" rx="10" fill="#064E3B" stroke="#10B981" stroke-width="1.5"/>
          <rect x="52" y="24" width="36" height="46" rx="8" fill="#0F172A" stroke="#34D399" stroke-width="2"/>
          <text x="70" y="51" text-anchor="middle" fill="#6EE7B7" font-size="12" font-weight="bold" font-family="sans-serif">O₂</text>
          <circle cx="24" cy="40" r="3.5" fill="#34D399">
            <animate attributeName="cx" values="20;50" dur="1.4s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values="1;0.1" dur="1.4s" repeatCount="indefinite"/>
          </circle>
          <circle cx="24" cy="56" r="3.5" fill="#38BDF8">
            <animate attributeName="cx" values="20;50" dur="1.8s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values="1;0.1" dur="1.8s" repeatCount="indefinite"/>
          </circle>
          <circle cx="96" cy="48" r="3" fill="#FBBF24">
            <animate attributeName="cx" values="90;122" dur="1.6s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values="0.9;0" dur="1.6s" repeatCount="indefinite"/>
          </circle>
          <text x="70" y="96" text-anchor="middle" fill="#6EE7B7" font-size="9" font-weight="bold" font-family="sans-serif">SCRUB CO2 / GIVE O2</text>
        </svg>
        """

    if action_type == "SHIELDING":
        return """
        <svg viewBox="0 0 140 105" width="140" height="105" xmlns="http://www.w3.org/2000/svg">
          <rect width="140" height="105" rx="10" fill="#431407" stroke="#F97316" stroke-width="1.5"/>
          <path d="M 38 72 A 32 34 0 0 1 102 72 Z" fill="#0EA5E9" fill-opacity="0.25" stroke="#38BDF8" stroke-width="2.5"/>
          <circle cx="70" cy="54" r="6" fill="#F8FAFC"/>
          <path d="M 60 70 Q 70 60 80 70" fill="none" stroke="#F8FAFC" stroke-width="2.5"/>
          <line x1="22" y1="14" x2="48" y2="38" stroke="#FB923C" stroke-width="2.2" stroke-dasharray="4,3">
            <animate attributeName="opacity" values="1;0.2;1" dur="0.9s" repeatCount="indefinite"/>
          </line>
          <line x1="118" y1="14" x2="92" y2="38" stroke="#FB923C" stroke-width="2.2" stroke-dasharray="4,3">
            <animate attributeName="opacity" values="0.2;1;0.2" dur="0.9s" repeatCount="indefinite"/>
          </line>
          <text x="70" y="96" text-anchor="middle" fill="#FDBA74" font-size="9" font-weight="bold" font-family="sans-serif">STORM SHELTER</text>
        </svg>
        """

    if action_type == "IRON_NUTRITION":
        return """
        <svg viewBox="0 0 140 105" width="140" height="105" xmlns="http://www.w3.org/2000/svg">
          <rect width="140" height="105" rx="10" fill="#4C0519" stroke="#F43F5E" stroke-width="1.5"/>
          <rect x="44" y="34" width="52" height="22" rx="11" fill="#F43F5E" stroke="#FDA4AF" stroke-width="1.8">
            <animateTransform attributeName="transform" type="rotate" values="-8 70 45; 8 70 45; -8 70 45" dur="2.2s" repeatCount="indefinite"/>
          </rect>
          <text x="70" y="49" text-anchor="middle" fill="#FFF1F2" font-size="9.5" font-weight="bold" font-family="sans-serif">Fe+D3+B12</text>
          <circle cx="32" cy="64" r="5" fill="#FB7185">
            <animate attributeName="r" values="3.5;6;3.5" dur="1.5s" repeatCount="indefinite"/>
          </circle>
          <circle cx="108" cy="64" r="5" fill="#FB7185">
            <animate attributeName="r" values="6;3.5;6" dur="1.5s" repeatCount="indefinite"/>
          </circle>
          <text x="70" y="96" text-anchor="middle" fill="#FDA4AF" font-size="9" font-weight="bold" font-family="sans-serif">IRON &amp; VITAMINS</text>
        </svg>
        """

    if action_type == "FLIGHT_SURGEON":
        return """
        <svg viewBox="0 0 140 105" width="140" height="105" xmlns="http://www.w3.org/2000/svg">
          <rect width="140" height="105" rx="10" fill="#450A0A" stroke="#EF4444" stroke-width="1.5"/>
          <g>
            <animateTransform attributeName="transform" type="scale" values="1;1.14;1" dur="1.0s" repeatCount="indefinite" additive="sum"/>
            <rect x="64" y="24" width="12" height="36" rx="2" fill="#EF4444"/>
            <rect x="52" y="36" width="36" height="12" rx="2" fill="#EF4444"/>
          </g>
          <path d="M 42 26 Q 32 42 42 58" fill="none" stroke="#FCA5A5" stroke-width="2">
            <animate attributeName="opacity" values="0.2;1;0.2" dur="1.2s" repeatCount="indefinite"/>
          </path>
          <path d="M 98 26 Q 108 42 98 58" fill="none" stroke="#FCA5A5" stroke-width="2">
            <animate attributeName="opacity" values="0.2;1;0.2" dur="1.2s" repeatCount="indefinite"/>
          </path>
          <text x="70" y="96" text-anchor="middle" fill="#FCA5A5" font-size="9" font-weight="bold" font-family="sans-serif">SURGEON / POCUS</text>
        </svg>
        """

    return """
    <svg viewBox="0 0 140 105" width="140" height="105" xmlns="http://www.w3.org/2000/svg">
      <rect width="140" height="105" rx="10" fill="#052E16" stroke="#00E676" stroke-width="1.5"/>
      <circle cx="70" cy="45" r="22" fill="none" stroke="#00E676" stroke-width="2" stroke-dasharray="6,4">
        <animateTransform attributeName="transform" type="rotate" from="0 70 45" to="360 70 45" dur="8s" repeatCount="indefinite"/>
      </circle>
      <path d="M 60 45 L 67 52 L 81 37" fill="none" stroke="#4ADE80" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>
      <text x="70" y="96" text-anchor="middle" fill="#86EFAC" font-size="9" font-weight="bold" font-family="sans-serif">NOMINAL • ALL CLEAR</text>
    </svg>
    """


def render_countermeasure_visuals(system_info):
    action_keys = system_info.get("countermeasures", ["NOMINAL"])
    with ui.row().classes("w-full gap-3 mt-2 flex-wrap"):
        for act_key in action_keys:
            meta = ACTION_META.get(act_key, ACTION_META["NOMINAL"])
            with ui.card().classes("flex-1 min-w-56 bg-slate-950/95 p-2.5 items-center").style(
                f"border: 1px solid {meta['border']};"
            ):
                with ui.row().classes("w-full items-center gap-3 no-wrap"):
                    ui.html(build_action_svg(act_key), sanitize=False)
                    with ui.column().classes("flex-1 gap-1"):
                        ui.label("VISUAL ACTION GUIDE").classes("text-[10px] font-bold tracking-wider text-slate-400")
                        ui.label(meta["title"]).classes("text-sm font-bold text-slate-100")
                        ui.label(meta["subtitle"]).classes("text-xs text-slate-300 leading-snug")


# ---------------------------------------------------------
# MENSTRUAL PHASE HELPER
# ---------------------------------------------------------
def get_cycle_phase_info(day, mode):
    if mode != "Natural Cycle (Active)":
        return (
            "Suppressed (Amenorrhea)",
            "Hormonal suppression active — menstrual bleeding paused; monitor for breakthrough spotting & venous stasis.",
            "#A855F7",
        )
    if day <= 5:
        return (
            "Menstrual Phase",
            "Days 1–5: Endometrial shedding; monitor iron/hemoglobin, hydration & hygiene containment.",
            "#F43F5E",
        )
    elif day <= 13:
        return (
            "Follicular Phase",
            "Days 6–13: Rising Estradiol (E2); optimal anaerobic & ARED resistive strength recovery window.",
            "#38BDF8",
        )
    elif day == 14:
        return (
            "Ovulatory Window",
            "Day 14: LH surge & peak Estradiol; slight basal body temperature inflection.",
            "#10B981",
        )
    elif day <= 28:
        return (
            "Luteal Phase",
            "Days 15–28: Elevated Progesterone (P4); +0.3–0.5°C basal core temp rise is normal (not fever).",
            "#F59E0B",
        )
    else:
        return (
            "Delayed / Oligomenorrhea",
            "Cycle > 28 days: Evaluate microgravity HPG-axis suppression or exercise energy deficit.",
            "#EF4444",
        )


# ---------------------------------------------------------
# NASA HRP & NASA-STD-3001 SEX-STRATIFIED TRIAGE ENGINE
# ---------------------------------------------------------
def evaluate_crew_health():
    systems = {}
    is_female = state["gender"] == "Female"

    # 1. Ocular (SANS)
    sans_note = (
        "Female profile: lower severe SANS incidence, but OCT monitoring remains mandatory."
        if is_female
        else "Male profile: elevated incidence/severity of optic disc edema and globe flattening."
    )
    if state["delta_trt"] >= 55 or state["iop"] > 25:
        status, priority = "RED", 3
        action = f"CRITICAL SANS: Retinal thickening ≥ 55 µm or high IOP. Alert Flight Surgeon; initiate LBNP & evaluate acetazolamide. ({sans_note})"
        cm = ["LBNP", "FLIGHT_SURGEON"]
    elif state["delta_trt"] >= 19.4 or state["iop"] > 21:
        status, priority = "YELLOW", 2
        action = f"EARLY SANS WATCH: Mild optic disc edema (+19.4 to +54 µm). Repeat OCT in 7 days & apply Lower Body Negative Pressure (LBNP). ({sans_note})"
        cm = ["LBNP"]
    else:
        status, priority = "GREEN", 1
        action = f"Nominal: Retinal thickness and IOP within pre-flight baseline. ({sans_note})"
        cm = ["NOMINAL"]
    systems["Ocular (SANS)"] = {
        "x": 203, "y": 73, "label_dx": 14, "anchor": "start",
        "status": status, "priority": priority,
        "reading": f"ΔTRT: +{state['delta_trt']:.1f} µm | IOP: {state['iop']} mmHg",
        "normal_ref": "ΔTRT < +19.4 µm | IOP 10–21 mmHg",
        "action": action,
        "countermeasures": cm,
    }

    # 2. Neuro-Cognitive & Circadian
    if state["sleep_hrs"] < 5.5 or state["pvt_drift"] > 20:
        status, priority = "RED", 3
        action = "SEVERE FATIGUE ALERT: High cognitive lapse risk. Defer EVA/docking duties & schedule 8-hr protected recovery sleep."
        cm = ["SLEEP_LIGHT"]
    elif state["sleep_hrs"] < 6.5 or state["pvt_drift"] > 10:
        status, priority = "YELLOW", 2
        action = "CIRCADIAN WATCH: Mild alertness drift. Shift cabin LEDs to blue-enriched daytime spectrum & reduce workload."
        cm = ["SLEEP_LIGHT"]
    else:
        status, priority = "GREEN", 1
        action = "Nominal: Sleep duration and psychomotor vigilance within target."
        cm = ["NOMINAL"]
    systems["Neuro-Cognitive"] = {
        "x": 166, "y": 53, "label_dx": -14, "anchor": "end",
        "status": status, "priority": priority,
        "reading": f"Sleep: {state['sleep_hrs']:.1f} hrs | PVT Drift: +{state['pvt_drift']}%",
        "normal_ref": "Sleep 7.0–8.5 hrs | PVT Drift < 10%",
        "action": action,
        "countermeasures": cm,
    }

    # 3. Vascular & Hematology
    hgb_red = 11.0 if is_female else 12.0
    hgb_yellow = 12.0 if is_female else 13.5
    hgb_ref = "12.0–15.5 g/dL" if is_female else "13.5–17.5 g/dL"

    ijv_sev = 3 if state["ijv_flow"] == "Reversed / Thrombus" else (2 if state["ijv_flow"] == "Stagnant / Oscillating" else 1)
    hgb_sev = 3 if state["hgb"] < hgb_red else (2 if state["hgb"] < hgb_yellow else 1)
    priority = max(ijv_sev, hgb_sev)
    status = {3: "RED", 2: "YELLOW", 1: "GREEN"}[priority]

    notes = []
    cm = []
    if ijv_sev == 3:
        notes.append("CRITICAL VASCULAR: Suspected jugular thrombosis — immediate Flight Surgeon consult & anticoagulation protocol.")
        cm.append("FLIGHT_SURGEON")
    elif ijv_sev == 2:
        notes.append("VENOUS STASIS WATCH: Headward fluid pooling on neck POCUS — repeat scan in 24h & deploy LBNP/thigh cuffs.")
        cm.append("LBNP")

    if hgb_sev == 3:
        notes.append(f"SPACE ANEMIA ALERT: Hemoglobin ({state['hgb']:.1f} g/dL) below {state['gender']} threshold (< {hgb_red} g/dL) — evaluate iron/B12/folate & limit strenuous EVA.")
        cm.append("IRON_NUTRITION")
    elif hgb_sev == 2:
        notes.append(f"HEMATOLOGY WATCH: Hemoglobin ({state['hgb']:.1f} g/dL) below {state['gender']} pre-flight baseline ({hgb_ref}) — monitor red cell mass.")
        cm.append("IRON_NUTRITION")

    if not cm:
        cm = ["NOMINAL"]
    action = " ".join(notes) if notes else f"Nominal: Continuous forward jugular flow and Hemoglobin within {state['gender']} baseline ({hgb_ref})."

    systems["Vascular & Hematology"] = {
        "x": 190, "y": 124, "label_dx": 14, "anchor": "start",
        "status": status, "priority": priority,
        "reading": f"IJV: {state['ijv_flow']} | Hgb: {state['hgb']:.1f} g/dL",
        "normal_ref": f"Forward Flow | Hgb {hgb_ref} ({state['gender']})",
        "action": action,
        "countermeasures": cm,
    }

    # 4. Cardiopulmonary & Cabin Atmosphere
    hr_low = 50 if is_female else 45
    hr_ref = "50–100 bpm" if is_female else "45–100 bpm"
    ortho_note = (
        "Female profile: prioritize pre-reentry fluid loading & lower-body compression garments to prevent orthostatic intolerance."
        if is_female
        else "Male profile: maintain standard aerobic/fluid re-entry countermeasures."
    )

    if state["spo2"] < 90 or state["hr"] > 100 or state["hr"] < hr_low or state["ppco2"] > 4.5:
        status, priority = "RED", 3
        action = f"CARDIOPULMONARY / CO2 ALERT: Check ECLSS CO2 scrubbers, administer supplemental O2, and run 12-lead ECG. ({ortho_note})"
        cm = ["OXYGEN_ECLSS", "FLIGHT_SURGEON"]
    elif state["spo2"] <= 94 or state["ppco2"] > 3.0:
        status, priority = "YELLOW", 2
        action = f"ATMOSPHERE / SPO2 WATCH: Cabin ppCO2 > 3.0 mmHg or mild desaturation. Increase module airflow & monitor headaches. ({ortho_note})"
        cm = ["OXYGEN_ECLSS"]
    else:
        status, priority = "GREEN", 1
        action = f"Nominal: Vitals and cabin ppCO2 within NASA-STD-3001 limits. ({ortho_note})"
        cm = ["NOMINAL"]

    systems["Cardiopulmonary"] = {
        "x": 195, "y": 190, "label_dx": 14, "anchor": "start",
        "status": status, "priority": priority,
        "reading": f"HR: {state['hr']} bpm | SpO2: {state['spo2']}% | ppCO2: {state['ppco2']:.1f} mmHg",
        "normal_ref": f"HR {hr_ref} ({state['gender']}) | SpO2 ≥ 95% | ppCO2 ≤ 3.0",
        "action": action,
        "countermeasures": cm,
    }

    # 5. Renal & Metabolic
    ca_red = 275 if is_female else 300
    ca_yellow = 220 if is_female else 250
    ca_ref = "< 220 mg/d" if is_female else "< 250 mg/d"
    renal_note = (
        "Female profile: lower body-mass calcium cutoff; also screen for microgravity UTI symptoms if urinary output drops."
        if is_female
        else "Male profile: elevated calcium oxalate stone supersaturation risk in microgravity."
    )

    if state["urine_ca"] > ca_red or state["urine_vol"] < 1.2 or not (3.5 <= state["potassium"] <= 5.0):
        status, priority = "RED", 3
        action = f"HIGH RENAL / ELECTROLYTE RISK: Exceeded {state['gender']} threshold. Force hydration > 2.5 L/day, give potassium citrate, & run renal POCUS. ({renal_note})"
        cm = ["HYDRATION", "FLIGHT_SURGEON"]
    elif state["urine_ca"] > ca_yellow or state["urine_vol"] < 1.5:
        status, priority = "YELLOW", 2
        action = f"RENAL CONCENTRATING WATCH: Above {state['gender']} baseline ({ca_ref}). Increase daily water intake target. ({renal_note})"
        cm = ["HYDRATION"]
    else:
        status, priority = "GREEN", 1
        action = f"Nominal: Urinary calcium, hydration volume, and serum potassium balanced for {state['gender']} profile."
        cm = ["NOMINAL"]

    systems["Renal & Metabolic"] = {
        "x": 156, "y": 264, "label_dx": -14, "anchor": "end",
        "status": status, "priority": priority,
        "reading": f"Ca: {state['urine_ca']} mg/d | Vol: {state['urine_vol']:.1f} L | K+: {state['potassium']:.1f} mmol/L",
        "normal_ref": f"Ca {ca_ref} ({state['gender']}) | Vol ≥ 1.75 L | K+ 3.5–5.0",
        "action": action,
        "countermeasures": cm,
    }

    # 6. Radiation Dosimetry
    rad_note = (
        "NASA-STD-3001 600 mSv career cap is calibrated to protect higher female tissue susceptibility (breast, ovarian, lung)."
        if is_female
        else "Tracked against NASA-STD-3001 universal 600 mSv career limit and 250 mSv acute SPE threshold."
    )
    if state["rad_msv"] >= 250:
        status, priority = "RED", 3
        action = f"RADIATION STORM ALERT: Acute limit reached. Relocate crew immediately to polyethylene/water storm shelter. ({rad_note})"
        cm = ["SHIELDING"]
    elif state["rad_msv"] >= 100:
        status, priority = "YELLOW", 2
        action = f"DOSIMETRY WATCH: Elevated cumulative ionizing exposure. Restrict non-critical EVAs during solar particle events. ({rad_note})"
        cm = ["SHIELDING"]
    else:
        status, priority = "GREEN", 1
        action = f"Nominal: Cumulative radiation dose within mission profile. ({rad_note})"
        cm = ["NOMINAL"]

    systems["Radiation Dose"] = {
        "x": 212, "y": 244, "label_dx": 14, "anchor": "start",
        "status": status, "priority": priority,
        "reading": f"Cumulative Dose: {state['rad_msv']} mSv",
        "normal_ref": "< 100 mSv nominal | < 250 mSv acute limit",
        "action": action,
        "countermeasures": cm,
    }

    # 7. Endocrine & Menstrual (Female) OR Endocrine HPG Axis (Male)
    if is_female:
        phase_name, phase_desc, _ = get_cycle_phase_info(state["cycle_day"], state["cycle_mode"])
        is_natural = state["cycle_mode"] == "Natural Cycle (Active)"
        m_alerts = []
        m_sev = 1
        cm = []

        if state["flow_status"] == "Heavy / Menorrhagia":
            m_sev = 3
            m_alerts.append(
                f"HEAVY BLEEDING ALERT: Menorrhagia on Day {state['cycle_day']} increases space anemia & iron depletion risk (Hgb: {state['hgb']:.1f} g/dL) — boost hydration, start iron & consult Flight Surgeon."
            )
            cm.extend(["HYDRATION", "IRON_NUTRITION"])
        elif not is_natural and state["flow_status"] in ("Light / Spotting", "Moderate (Normal)"):
            m_sev = max(m_sev, 2)
            m_alerts.append(
                f"BREAKTHROUGH BLEEDING WATCH: Unscheduled bleeding under {state['cycle_mode']} — verify pill/IUD adherence & waste containment."
            )
            cm.append("FLIGHT_SURGEON")

        if is_natural and state["estradiol"] < 30:
            m_sev = max(m_sev, 2)
            m_alerts.append(
                f"HYPO-ESTROGENIC WATCH: Low Estradiol ({state['estradiol']} pg/mL) from microgravity/exercise energy deficit accelerates bone density loss — review caloric intake & ARED load."
            )
            if "IRON_NUTRITION" not in cm:
                cm.append("IRON_NUTRITION")
            cm.append("EXERCISE")

        if is_natural and state["cycle_day"] > 28:
            m_sev = max(m_sev, 2)
            m_alerts.append(
                f"CYCLE DELAY WATCH: Day {state['cycle_day']} (> 28 days) — evaluate HPG-axis suppression or caloric deficit."
            )
            if "IRON_NUTRITION" not in cm:
                cm.append("IRON_NUTRITION")

        if state["cycle_mode"] == "Hormonal Suppression (COC)" and state["ijv_flow"] != "Forward (Normal)":
            m_sev = max(m_sev, 2)
            m_alerts.append(
                "THROMBOSIS CROSS-CHECK: Estrogen-containing COC combined with stagnant IJV flow — elevate VTE monitoring & LBNP schedule."
            )
            cm.append("LBNP")

        if not cm:
            cm = ["NOMINAL"]

        status = {3: "RED", 2: "YELLOW", 1: "GREEN"}[m_sev]
        action = " ".join(m_alerts) if m_alerts else f"Nominal ({phase_name}): {phase_desc}"

        systems["Endocrine & Menstrual"] = {
            "x": 180, "y": 308, "label_dx": 14, "anchor": "start",
            "status": status, "priority": m_sev,
            "reading": (
                f"Day {state['cycle_day']} ({phase_name.split()[0]}) | "
                f"E2: {state['estradiol']} pg/mL | P4: {state['progesterone']:.1f} ng/mL"
            ),
            "normal_ref": "Cycle 21–28d | E2 30–300 pg/mL (or Suppressed)",
            "action": action,
            "countermeasures": cm[:2],
        }
    else:
        systems["Endocrine (HPG)"] = {
            "x": 180, "y": 308, "label_dx": 14, "anchor": "start",
            "status": "GREEN", "priority": 1,
            "reading": "HPG Axis & Cortisol: Nominal Male Baseline",
            "normal_ref": "Nominal Spaceflight HPG & Energy Balance",
            "action": "Nominal: Male hypothalamic-pituitary-gonadal axis within expected mission parameters.",
            "countermeasures": ["NOMINAL"],
        }

    # 8. Musculoskeletal
    if state["exercise_pct"] < 60:
        status, priority = "RED", 3
        action = "DECONDITIONING ALERT: Critical resistive loading deficit. High bone mineral loss risk; restore daily ARED protocol."
        cm = ["EXERCISE"]
    elif state["exercise_pct"] < 85:
        status, priority = "YELLOW", 2
        action = "EXERCISE COMPLIANCE WATCH: Increase ARED squats/deadlifts and treadmill harness load."
        cm = ["EXERCISE"]
    else:
        status, priority = "GREEN", 1
        action = "Nominal: Resistive and aerobic bone/muscle countermeasure targets met."
        cm = ["NOMINAL"]

    systems["Musculoskeletal"] = {
        "x": 146, "y": 410, "label_dx": -14, "anchor": "end",
        "status": status, "priority": priority,
        "reading": f"ARED Exercise Compliance: {state['exercise_pct']}%",
        "normal_ref": "≥ 85% Weekly Countermeasure Target",
        "action": action,
        "countermeasures": cm,
    }

    return systems


# ---------------------------------------------------------
# AI FLIGHT SURGEON COPILOT (AEGIS-MED AI)
# ---------------------------------------------------------
def compute_readiness_score(results):
    score = 100
    for info in results.values():
        if info["status"] == "RED":
            score -= 18
        elif info["status"] == "YELLOW":
            score -= 7
    for n in evaluate_nutrients():
        if "CRIT" in n["status"]:
            score -= 5
        elif n["status"] != "OPTIMAL":
            score -= 2
    return max(5, min(100, score))


def generate_local_ai_insights(results, prompt="Auto-Synthesis"):
    readiness = compute_readiness_score(results)
    red_sys = [k for k, v in results.items() if v["status"] == "RED"]
    yellow_sys = [k for k, v in results.items() if v["status"] == "YELLOW"]
    low_or_high_nutrients = [n for n in evaluate_nutrients() if n["status"] != "OPTIMAL"]
    roster, you_entry, you_rank = get_crew_roster_comparison(results)
    crew_avg = round(sum(c["readiness"] for c in roster) / len(roster), 1)
    is_female = state["gender"] == "Female"

    syndromes = []
    if state["delta_trt"] >= 19.4 and (state["ijv_flow"] != "Forward (Normal)" or state["vit_b12"] < 250):
        syndromes.append(
            "• **Cephalad Fluid & One-Carbon SANS Axis:** Optic disc thickening (+{:.1f} µm) with {} (B12: {:.0f} pg/mL) elevates SANS progression risk — deploy LBNP (-25 mmHg) and B-vitamin/folate support.".format(
                state["delta_trt"], state["ijv_flow"], state["vit_b12"]
            )
        )
    if state["urine_ca"] > (220 if is_female else 250) and (state["vit_d"] < 30 or state["sodium"] > 145 or state["exercise_pct"] < 85):
        syndromes.append(
            "• **Bone–Renal Calcium Unloading Axis:** Hypercalciuria ({} mg/d) paired with Vitamin D at {:.0f} ng/mL and Sodium at {:.0f} mmol/L accelerates bone demineralization and kidney stone risk — supplement D3 (2,000 IU/d), hydrate >2.5 L/d, and cut sodium.".format(
                state["urine_ca"], state["vit_d"], state["sodium"]
            )
        )
    if (is_female and state["flow_status"] == "Heavy / Menorrhagia") or state["hgb"] < 12.0 or state["ferritin"] < (15 if is_female else 30):
        syndromes.append(
            "• **Space Anemia & Iron Reserve Synergy:** Hemoglobin ({:.1f} g/dL) and Ferritin ({:.0f} ng/mL) indicate depleted iron stores — administer heme-iron + Vitamin C and monitor fatigue.".format(
                state["hgb"], state["ferritin"]
            )
        )
    if state["ppco2"] > 3.0 and (state["sleep_hrs"] < 6.5 or state["pvt_drift"] > 10):
        syndromes.append(
            "• **Hypercapnic Cognitive Cascade:** Elevated cabin ppCO2 ({:.1f} mmHg) compounds sleep debt ({:.1f} hrs), accelerating PVT drift (+{}%).".format(
                state["ppco2"], state["sleep_hrs"], state["pvt_drift"]
            )
        )

    q = prompt.lower()

    if "crew" in q or "peer" in q or "compare" in q or "benchmark" in q:
        top_peer = roster[0]
        diff = round(readiness - crew_avg, 1)
        return (
            f"👩‍🚀 **CREW-4 PEER BENCHMARK ({get_active_astronaut_name().upper()} — RANK #{you_rank} OF {len(roster)})**\n"
            f"• **Readiness vs. Crew Mean:** Your Readiness is **{readiness}%** vs. Crew Mean **{crew_avg}%** (`{'+' if diff >= 0 else ''}{diff}%`).\n"
            f"• **Top Crew Performer:** **{top_peer['name']}** leads at **{top_peer['readiness']}%** Readiness (`{top_peer['hydration']} L/d` hydration, `{top_peer['ared']}%` ARED, `{top_peer['vit_d']} ng/mL` Vit D).\n"
            f"• **Fastest Way to Climb Rank:** Complete your active Hydration (+50 XP) and Vitamin D3/Iron (+45 XP) protocol quests to close the gap."
        )

    if "eva" in q or "spacewalk" in q or "clearance" in q:
        if red_sys:
            verdict = f"🚫 **EVA CLEARANCE: NO-GO (Readiness {readiness}/100)** — Critical threshold breaches in **{', '.join(red_sys)}** disqualify the crewmember from extravehicular activity until stabilized."
        elif len(yellow_sys) >= 2:
            verdict = f"⚠️ **EVA CLEARANCE: CONDITIONAL / RESTRICTED (Readiness {readiness}/100)** — Multiple watch flags (**{', '.join(yellow_sys)}**). Limit EVA duration to < 4 hours and enforce pre-breathe hydration."
        else:
            verdict = f"✅ **EVA CLEARANCE: GO (Readiness {readiness}/100)** — Cardiopulmonary, neuro-cognitive, and ocular parameters support full 6-hour EVA operations."
        return f"{verdict}\n\n**Key Physiological Drivers:**\n" + ("\n".join(syndromes) if syndromes else "• All cross-system physiological couplings are currently balanced.")

    if "brief" in q or "sitrep" in q or "surgeon" in q:
        nut_str = ", ".join(f"{n['name']} ({n['status']})" for n in low_or_high_nutrients) if low_or_high_nutrients else "All Optimal"
        return (
            f"📋 **FLIGHT SURGEON SITREP ({get_active_astronaut_name().upper()} | READINESS: {readiness}/100 | CREW RANK #{you_rank})**\n"
            f"• **Critical Alerts ({len(red_sys)}):** {', '.join(red_sys) if red_sys else 'None'}\n"
            f"• **Active Watch Items ({len(yellow_sys)}):** {', '.join(yellow_sys) if yellow_sys else 'None'}\n"
            f"• **Vitamins & Electrolytes:** {nut_str}\n\n"
            f"**Cross-System Synthesis:**\n" + ("\n".join(syndromes) if syndromes else "• No multi-organ decompensation patterns detected.")
        )

    if "menstrual" in q or "hormone" in q or "cycle" in q or "period" in q:
        if not is_female:
            return "ℹ️ Current active profile is **Male**. Switch Crew Physiological Profile to **Female** in the sidebar to inspect menstrual cycle phase synchronization, Estradiol/Progesterone bone protection, and iron-ferritin tracking."
        phase_name, phase_desc, _ = get_cycle_phase_info(state["cycle_day"], state["cycle_mode"])
        return (
            f"🌸 **ENDOCRINE & CYCLE INSIGHT — {phase_name.upper()} (DAY {state['cycle_day']})**\n"
            f"• **Hormone Profile:** Estradiol (E2) = `{state['estradiol']} pg/mL`, Progesterone (P4) = `{state['progesterone']:.1f} ng/mL` ({state['cycle_mode']}).\n"
            f"• **Clinical Interpretation:** {phase_desc}\n"
            f"• **Countermeasure Guidance:** {'Prioritize heavy ARED resistive loading during follicular/ovulatory estrogen peaks.' if state['cycle_day'] <= 14 else 'Account for +0.3–0.5°C progesterone basal thermogenesis when evaluating cabin thermal comfort and hydration.'}"
        )

    header = f"🧠 **Aegis-Med Autonomous Synthesis — {get_active_astronaut_name()} (Readiness: {readiness}/100 • Rank #{you_rank}/{len(roster)})**\n"
    if not syndromes and not low_or_high_nutrients:
        body = (
            "• **Multi-System & Nutritional Stability:** All organ systems, vitamins, and electrolytes are inside NASA-STD-3001 optimal bounds.\n"
            f"• **Primary Focus:** Maintain {state['exercise_pct']}% ARED resistive compliance and ≥ 2.0 L/day fluid intake."
        )
    else:
        body = "**Detected Cross-System & Nutritional Interactions:**\n" + (
            "\n".join(syndromes)
            if syndromes
            else "• Out-of-range micronutrients detected: " + ", ".join(f"{n['name']} ({n['status']})" for n in low_or_high_nutrients)
        )

    if prompt and prompt != "Auto-Synthesis":
        body += f"\n\n**Response to your query (*\"{prompt}\"*):** Prioritize correcting **{red_sys[0] if red_sys else (yellow_sys[0] if yellow_sys else 'out-of-range micronutrients')}** first to stabilize downstream vitals."

    return header + body


async def call_gemini_or_local(prompt_text):
    results = evaluate_crew_health()
    api_key = state["gemini_api_key"].strip()
    if not api_key:
        return generate_local_ai_insights(results, prompt_text)

    roster, _, you_rank = get_crew_roster_comparison(results)
    summary_payload = {
        "astronaut": get_active_astronaut_name(),
        "profile": state["gender"],
        "readiness_score": compute_readiness_score(results),
        "crew_rank": f"#{you_rank}/{len(roster)}",
        "telemetry": {k: v for k, v in state.items() if k not in ("gemini_api_key", "ai_response", "cycle_log")},
        "triage_statuses": {k: {"status": v["status"], "reading": v["reading"]} for k, v in results.items()},
        "vitamins_minerals": {n["name"]: {"val": n["val"], "unit": n["unit"], "status": n["status"]} for n in evaluate_nutrients()},
        "peer_crew": roster,
    }
    system_instruction = (
        "You are Aegis-Med, an autonomous NASA Flight Surgeon AI assistant for deep-space missions. "
        "Analyze the astronaut's live telemetry, vitamin panel, and peer crew comparison using NASA-STD-3001 principles. "
        "Be concise, specific, and actionable (3-5 bullet points max)."
    )
    full_prompt = f"{system_instruction}\n\nLive Crew Telemetry:\n{json.dumps(summary_payload)}\n\nUser Question: {prompt_text}"

    def _post_request():
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        req_body = json.dumps({"contents": [{"parts": [{"text": full_prompt}]}]}).encode("utf-8")
        req = urllib.request.Request(url, data=req_body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]

    try:
        return await asyncio.to_thread(_post_request)
    except Exception as exc:
        fallback = generate_local_ai_insights(results, prompt_text)
        return f"*(Live Gemini API unreachable: {exc} — showing built-in Aegis-Med Clinical Engine)*\n\n{fallback}"


# ---------------------------------------------------------
# FACIAL EXPRESSION & ANIMATED SVG BODY GENERATOR
# ---------------------------------------------------------
def get_facial_state(results):
    statuses = [v["status"] for v in results.values()]
    has_red = "RED" in statuses
    has_yellow = "YELLOW" in statuses
    is_fatigued = state["sleep_hrs"] < 6.5 or state["pvt_drift"] > 10
    is_respiratory_strain = state["ppco2"] > 3.5 or state["spo2"] <= 94

    if has_red or is_respiratory_strain:
        return "CRITICAL", "Distressed / High Strain", "#FF1744"
    elif is_fatigued:
        return "FATIGUED", "Fatigued / Circadian Deficit", "#FFC400"
    elif has_yellow:
        return "WATCH", "Focused / Mild Watch", "#FFC400"
    else:
        return "OPTIMAL", "Alert & Nominal", "#00E676"


def build_face_svg(mood, accent):
    if mood == "CRITICAL":
        return """
        <g id="face-critical">
          <line x1="163" y1="42" x2="175" y2="46" stroke="#FF1744" stroke-width="2.2" stroke-linecap="round" />
          <line x1="197" y1="42" x2="185" y2="46" stroke="#FF1744" stroke-width="2.2" stroke-linecap="round" />
          <circle cx="170" cy="52" r="3.4" fill="#F8FAFC" />
          <circle cx="170" cy="52" r="1.6" fill="#0F172A" />
          <circle cx="190" cy="52" r="3.4" fill="#F8FAFC" />
          <circle cx="190" cy="52" r="1.6" fill="#0F172A" />
          <path d="M 172 69 Q 180 62 188 69 Q 180 67 172 69 Z" fill="#FF1744" stroke="#FF1744" stroke-width="1.4" />
          <circle cx="155" cy="48" r="3" fill="#FF1744">
            <animate attributeName="r" values="2;4.5;2" dur="0.9s" repeatCount="indefinite" />
          </circle>
        </g>
        """
    elif mood == "FATIGUED":
        return """
        <g id="face-fatigued">
          <line x1="164" y1="46" x2="175" y2="47" stroke="#CBD5E1" stroke-width="1.8" stroke-linecap="round" />
          <line x1="196" y1="46" x2="185" y2="47" stroke="#CBD5E1" stroke-width="1.8" stroke-linecap="round" />
          <path d="M 165 52 Q 170 55 175 52" fill="none" stroke="#E2E8F0" stroke-width="2" stroke-linecap="round" />
          <path d="M 185 52 Q 190 55 195 52" fill="none" stroke="#E2E8F0" stroke-width="2" stroke-linecap="round" />
          <path d="M 166 56 Q 170 58 174 56" fill="none" stroke="#94A3B8" stroke-width="1" />
          <path d="M 186 56 Q 190 58 194 56" fill="none" stroke="#94A3B8" stroke-width="1" />
          <ellipse cx="180" cy="67" rx="4.5" ry="2.5" fill="none" stroke="#FFC400" stroke-width="1.6" />
        </g>
        """
    elif mood == "WATCH":
        return """
        <g id="face-watch">
          <line x1="164" y1="44" x2="175" y2="46" stroke="#FFC400" stroke-width="2" stroke-linecap="round" />
          <line x1="196" y1="44" x2="185" y2="46" stroke="#FFC400" stroke-width="2" stroke-linecap="round" />
          <circle cx="170" cy="52" r="2.7" fill="#F8FAFC" />
          <circle cx="190" cy="52" r="2.7" fill="#F8FAFC" />
          <path d="M 173 67 Q 180 65 187 67" fill="none" stroke="#FFC400" stroke-width="1.8" stroke-linecap="round" />
          <path d="M 157 46 Q 154 51 157 53 Q 160 51 157 46 Z" fill="#38BDF8" opacity="0.85" />
        </g>
        """
    else:
        return f"""
        <g id="face-optimal">
          <path d="M 164 45 Q 170 42 175 45" fill="none" stroke="{accent}" stroke-width="1.8" stroke-linecap="round" />
          <path d="M 185 45 Q 190 42 196 45" fill="none" stroke="{accent}" stroke-width="1.8" stroke-linecap="round" />
          <circle cx="170" cy="52" r="2.8" fill="#F8FAFC" />
          <circle cx="171" cy="51" r="1.0" fill="#38BDF8" />
          <circle cx="190" cy="52" r="2.8" fill="#F8FAFC" />
          <circle cx="191" cy="51" r="1.0" fill="#38BDF8" />
          <path d="M 173 65 Q 180 71 187 65" fill="none" stroke="#00E676" stroke-width="2" stroke-linecap="round" />
        </g>
        """


def blank_svg_source(width, height):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"></svg>'
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def build_body_svg(results, width=480, height=720):
    color_map = {"GREEN": "#00E676", "YELLOW": "#FFC400", "RED": "#FF1744"}
    accent = "#F472B6" if state["gender"] == "Female" else "#38BDF8"
    accent_fill = "rgba(244, 114, 182, 0.12)" if state["gender"] == "Female" else "rgba(56, 189, 248, 0.12)"

    mood, mood_label, mood_color = get_facial_state(results)
    beat_dur = round(60.0 / max(35, state["hr"]), 2)

    if state["ijv_flow"] == "Forward (Normal)":
        flow_anim = '<animate attributeName="cy" values="110;154" dur="1.4s" repeatCount="indefinite" />'
        flow_color = "#00E676"
    elif state["ijv_flow"] == "Stagnant / Oscillating":
        flow_anim = '<animate attributeName="cy" values="118;128;118" dur="1.8s" repeatCount="indefinite" />'
        flow_color = "#FFC400"
    else:
        flow_anim = '<animate attributeName="r" values="2;5;2" dur="0.7s" repeatCount="indefinite" />'
        flow_color = "#FF1744"

    nodes_svg = []
    for name, info in results.items():
        c = color_map[info["status"]]
        x, y = info["x"], info["y"]
        anchor = info.get("anchor", "start")
        is_selected = name == state["selected_system"]

        if info["status"] == "RED":
            nodes_svg.append(
                f'<circle cx="{x}" cy="{y}" r="10" fill="none" stroke="{c}" stroke-width="2">'
                f'  <animate attributeName="r" values="8;22" dur="1.1s" repeatCount="indefinite" />'
                f'  <animate attributeName="opacity" values="0.9;0" dur="1.1s" repeatCount="indefinite" />'
                f'</circle>'
                f'<circle cx="{x}" cy="{y}" r="18" fill="{c}" fill-opacity="0.22" />'
            )
        elif info["status"] == "YELLOW":
            nodes_svg.append(
                f'<circle cx="{x}" cy="{y}" r="10" fill="none" stroke="{c}" stroke-width="1.5">'
                f'  <animate attributeName="r" values="8;19" dur="2.1s" repeatCount="indefinite" />'
                f'  <animate attributeName="opacity" values="0.8;0" dur="2.1s" repeatCount="indefinite" />'
                f'</circle>'
                f'<circle cx="{x}" cy="{y}" r="16" fill="{c}" fill-opacity="0.18" />'
            )

        if is_selected:
            nodes_svg.append(
                f'<circle cx="{x}" cy="{y}" r="14" fill="none" stroke="{accent}" stroke-width="2" stroke-dasharray="4,3">'
                f'  <animateTransform attributeName="transform" type="rotate" from="0 {x} {y}" to="360 {x} {y}" dur="7s" repeatCount="indefinite" />'
                f'</circle>'
            )

        nodes_svg.append(
            f'<g style="cursor:pointer">'
            f'  <title>{name} [{info["status"]}]: {info["reading"]}</title>'
            f'  <circle cx="{x}" cy="{y}" r="7.5" fill="{c}" stroke="#0F172A" stroke-width="2" />'
            f'  <text x="{x + info["label_dx"]}" y="{y + 4}" text-anchor="{anchor}" fill="#E2E8F0" font-size="11.2" '
            f'        font-family="sans-serif" font-weight="{"bold" if is_selected else "normal"}">{name}</text>'
            f'</g>'
        )

    return f"""
    <svg viewBox="0 0 360 540" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="scanGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="{accent}" stop-opacity="0" />
          <stop offset="50%" stop-color="{accent}" stop-opacity="0.26" />
          <stop offset="100%" stop-color="{accent}" stop-opacity="0" />
        </linearGradient>
      </defs>

      <rect width="360" height="540" rx="12" fill="#0B1120" />

      <!-- Dedicated Top HUD Header Zone -->
      <text x="14" y="18" fill="{accent}" font-size="10.2" font-family="sans-serif" font-weight="bold">
        {get_active_astronaut_name().upper()} ({state["gender"].upper()})
      </text>
      <text x="346" y="18" text-anchor="end" fill="#94A3B8" font-size="10" font-family="monospace">
        HR: {state["hr"]} BPM
      </text>
      <text x="14" y="32" fill="{mood_color}" font-size="9.5" font-family="sans-serif">
        FACE: {mood_label.upper()}
      </text>
      <line x1="14" y1="40" x2="346" y2="40" stroke="#1E293B" stroke-width="1" />

      <!-- Center Vertical Axis -->
      <line x1="180" y1="42" x2="180" y2="515" stroke="#1E293B" stroke-width="1" stroke-dasharray="4,4" />

      <!-- Biometric Scanner Sweep -->
      <rect x="35" y="42" width="290" height="18" fill="url(#scanGrad)">
        <animate attributeName="y" values="42;492;42" dur="6.5s" repeatCount="indefinite" />
      </rect>

      <!-- Head & Dynamic Facial Expression -->
      <circle cx="180" cy="76" r="32" fill="{accent_fill}" stroke="{accent}" stroke-width="1.8" />
      <g transform="translate(0, 22)">
        {build_face_svg(mood, accent)}
      </g>

      <!-- Torso, Arms & Legs Silhouette -->
      <path d="M 166 108 L 164 128 L 106 144 L 74 290 L 94 294 L 122 180 L 130 258
               L 122 298 L 128 504 L 156 504 L 180 318 L 204 504 L 232 504 L 238 298
               L 230 258 L 238 180 L 266 294 L 286 290 L 254 144 L 196 128 L 194 108 Z"
            fill="{accent_fill}" stroke="{accent}" stroke-width="1.8" stroke-linejoin="round" />

      <!-- Animated Jugular Vein Flow Conduit -->
      <line x1="187" y1="108" x2="187" y2="158" stroke="{flow_color}" stroke-width="2" stroke-opacity="0.45" />
      <circle cx="187" cy="118" r="2.8" fill="{flow_color}">
        {flow_anim}
      </circle>

      <!-- BPM-Synchronized Pulsing Heart -->
      <g transform="translate(0, 22)">
        <path d="M 184 175 C 184 175 174 168 174 162 C 174 158.5 177 156 180 156 C 182 156 183.5 157.2 184 158.8 C 184.5 157.2 186 156 188 156 C 191 156 194 158.5 194 162 C 194 168 184 175 184 175 Z"
              fill="#FF1744" fill-opacity="0.8" stroke="#FDA4AF" stroke-width="1">
          <animate attributeName="fill-opacity" values="0.95;0.35;0.95" dur="{beat_dur}s" repeatCount="indefinite" />
        </path>
      </g>

      <!-- Interactive System Nodes -->
      {''.join(nodes_svg)}

      <text x="14" y="528" fill="#64748B" font-size="9.5" font-family="monospace">
        CLICK ANY NODE TO VIEW ANIMATED TREATMENT PLAN
      </text>
    </svg>
    """


def handle_body_click(e, width, refresh_callback):
    results = evaluate_crew_health()
    closest_sys = None
    min_dist = 34.0
    scale = width / 360.0
    for name, info in results.items():
        dist = math.hypot((e.image_x / scale) - info["x"], (e.image_y / scale) - info["y"])
        if dist < min_dist:
            min_dist = dist
            closest_sys = name
    if closest_sys:
        state["selected_system"] = closest_sys
        refresh_callback()


# ---------------------------------------------------------
# PAGE 1: MAIN MISSION CONTROL DASHBOARD (/)
# ---------------------------------------------------------
@ui.page("/")
def main_page():
    if not state["ai_response"]:
        state["ai_response"] = generate_local_ai_insights(evaluate_crew_health(), "Auto-Synthesis")

    def refresh_all():
        telemetry_panel.refresh()
        popup_panel.refresh()

    # Full-Screen Pop-Up Dialog
    with ui.dialog().props("maximized") as popup_dialog, ui.card().classes(
        "w-full h-full bg-slate-950 text-slate-100 p-6"
    ):
        with ui.row().classes("w-full justify-between items-center border-b border-slate-800 pb-3 mb-4"):
            with ui.row().classes("items-center gap-3"):
                ui.label("🩺 CrewMed — Projected Anatomical & Treatment View").classes("text-xl font-bold text-sky-400")
                ui.badge("LIVE SYNC", color="info")
            ui.button("Close Pop-Up", icon="close", on_click=popup_dialog.close).props("outline color=sky")

        @ui.refreshable
        def popup_panel():
            results = evaluate_crew_health()
            active_key = state["selected_system"] if state["selected_system"] in results else list(results.keys())[0]
            sel = results[active_key]
            badge_color = {"GREEN": "positive", "YELLOW": "warning", "RED": "negative"}[sel["status"]]

            with ui.row().classes("w-full justify-center items-start gap-10 flex-wrap"):
                ui.interactive_image(
                    source=blank_svg_source(560, 840),
                    size=(560, 840),
                    content=build_body_svg(results, width=560, height=840),
                    on_mouse=lambda e: handle_body_click(e, 560, refresh_all),
                    sanitize=False,
                ).style("width: 560px; height: 840px; min-width: 560px;")

                with ui.column().classes("w-[460px] gap-4 mt-4"):
                    with ui.card().classes("w-full bg-slate-900 border-2 border-sky-500/50 p-5"):
                        with ui.row().classes("w-full justify-between items-center"):
                            ui.label(active_key).classes("text-xl font-bold text-sky-300")
                            ui.badge(sel["status"], color=badge_color).classes("text-sm px-3 py-1")
                        ui.label(f"Crewmember: {get_active_astronaut_name()} ({state['gender']})").classes(
                            "text-xs font-semibold text-pink-300 mt-1"
                        )
                        ui.label(f"Reading: {sel['reading']}").classes("text-base font-mono text-slate-100 mt-2")
                        ui.label(f"Reference: {sel['normal_ref']}").classes("text-xs text-slate-400 mt-1")
                        ui.separator().classes("my-3")
                        ui.label(sel["action"]).classes("text-sm text-slate-200")
                        render_countermeasure_visuals(sel)

                    ui.label("Click any organ node on the figure to switch systems.").classes("text-xs text-slate-400")

        popup_panel()

    # Main Dashboard Content
    @ui.refreshable
    def telemetry_panel():
        results = evaluate_crew_health()
        sorted_systems = sorted(results.items(), key=lambda x: x[1]["priority"], reverse=True)
        total_sys = len(results)
        readiness = compute_readiness_score(results)
        _, mood_label, _ = get_facial_state(results)
        roster, _, you_rank = get_crew_roster_comparison(results)
        level, _, _, _ = get_rank_info(state["xp"])

        red_n = sum(1 for v in results.values() if v["status"] == "RED")
        yellow_n = sum(1 for v in results.values() if v["status"] == "YELLOW")
        green_n = sum(1 for v in results.values() if v["status"] == "GREEN")

        with ui.row().classes("w-full gap-3 mb-2 flex-wrap"):
            with ui.card().classes("flex-1 min-w-36 bg-slate-900 border border-emerald-500/40 p-3"):
                ui.label("NOMINAL SYSTEMS").classes("text-xs text-slate-400")
                ui.label(f"🟢 {green_n} / {total_sys}").classes("text-2xl font-bold text-emerald-400")
            with ui.card().classes("flex-1 min-w-36 bg-slate-900 border border-amber-500/40 p-3"):
                ui.label("WATCH / ACTION").classes("text-xs text-slate-400")
                ui.label(f"🟡 {yellow_n} / {total_sys}").classes("text-2xl font-bold text-amber-400")
            with ui.card().classes("flex-1 min-w-36 bg-slate-900 border border-rose-500/40 p-3"):
                ui.label("SURGEON ALERT").classes("text-xs text-slate-400")
                ui.label(f"🔴 {red_n} / {total_sys}").classes("text-2xl font-bold text-rose-400")
            with ui.card().classes("flex-1 min-w-36 bg-slate-900 border border-sky-500/40 p-3"):
                ui.label("READINESS & CREW RANK").classes("text-xs text-slate-400")
                ui.label(f"🚀 {readiness}% (#{you_rank}/{len(roster)})").classes("text-2xl font-bold text-sky-400")
            with ui.card().classes("flex-1 min-w-36 bg-slate-900 border border-amber-400/40 p-3"):
                ui.label("STREAK & FLIGHT XP").classes("text-xs text-slate-400")
                ui.label(f"🔥 {state['streak_days']}d • Lvl {level}").classes("text-2xl font-bold text-amber-300")

        with ui.row().classes("w-full gap-6 items-start flex-wrap"):
            # Left Card: Animated Human Diagram (480 x 720) + Projection Buttons
            with ui.card().classes("bg-slate-900 border border-slate-800 p-4 items-center"):
                with ui.row().classes("w-full justify-between items-center mb-1"):
                    ui.label("Interactive Biometric Map").classes("text-base font-semibold text-sky-400")
                    with ui.row().classes("gap-2"):
                        ui.button(
                            "Pop-Up",
                            icon="open_in_full",
                            on_click=popup_dialog.open,
                        ).props("dense outline size=sm color=sky")
                        ui.button(
                            "New Tab",
                            icon="open_in_new",
                            on_click=lambda: ui.navigate.to("/projector", new_tab=True),
                        ).props("dense outline size=sm color=sky")

                ui.label(f"{get_active_astronaut_name()} • Expression: {mood_label}").classes(
                    "text-xs text-slate-400 mb-2"
                )
                ui.interactive_image(
                    source=blank_svg_source(480, 720),
                    size=(480, 720),
                    content=build_body_svg(results, width=480, height=720),
                    on_mouse=lambda e: handle_body_click(e, 480, refresh_all),
                    sanitize=False,
                ).style("width: 480px; height: 720px; min-width: 480px;")

            # Right Column: Selected Inspector + Gamified Quests + Vitamins + Crew Comparison + AI + Menstrual + Queue
            with ui.column().classes("flex-1 min-w-80 gap-3"):
                # 1. Selected Organ System Inspector + Animated Visual Treatment Plan
                active_key = state["selected_system"] if state["selected_system"] in results else list(results.keys())[0]
                sel = results[active_key]
                badge_color = {"GREEN": "positive", "YELLOW": "warning", "RED": "negative"}[sel["status"]]

                with ui.card().classes("w-full bg-slate-900 border-2 border-sky-500/50 p-4"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(f"Selected Region: {active_key}").classes("text-lg font-bold text-sky-300")
                        ui.badge(sel["status"], color=badge_color).classes("text-sm px-3 py-1")
                    ui.label(f"Current Reading: {sel['reading']}").classes("text-sm font-mono text-slate-200 mt-1")
                    ui.label(f"Reference Limit: {sel['normal_ref']}").classes("text-xs text-slate-400")
                    ui.separator().classes("my-2")
                    ui.label(sel["action"]).classes("text-sm text-slate-100")

                    render_countermeasure_visuals(sel)

                # 2. Gamified Mission Readiness Quests & Earnable Flight Patches
                render_gamification_card(results, refresh_all)

                # 3. Crew-4 Peer Telemetry Comparison Card
                render_crew_comparison_card(results, refresh_all)

                # 4. Vitamins, Minerals & Electrolytes Comparison Bar Panel
                render_vitamin_comparison_card()

                # 5. AI Flight Surgeon Copilot Card
                with ui.card().classes("w-full bg-slate-900 border-2 border-indigo-500/50 p-4"):
                    with ui.row().classes("w-full justify-between items-center"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label("🤖 Aegis-Med AI Flight Surgeon Agent").classes("text-base font-bold text-indigo-300")
                            ui.badge(
                                "GEMINI LIVE" if state["gemini_api_key"].strip() else "CLINICAL ENGINE",
                                color="indigo",
                            ).classes("text-[10px]")

                        async def run_ai_query(prompt_str):
                            state["ai_last_prompt"] = prompt_str
                            state["ai_response"] = "⏳ *Analyzing multi-system telemetry, crew benchmarks, and NASA-STD-3001 limits...*"
                            telemetry_panel.refresh()
                            state["ai_response"] = await call_gemini_or_local(prompt_str)
                            telemetry_panel.refresh()

                        ui.button(
                            "Re-Analyze",
                            icon="auto_awesome",
                            on_click=lambda: run_ai_query("Auto-Synthesis"),
                        ).props("dense outline size=sm color=indigo")

                    with ui.row().classes("w-full gap-1.5 my-2 flex-wrap"):
                        for chip_label, chip_prompt in [
                            ("Multi-System Risks", "Auto-Synthesis"),
                            ("Crew Peer Benchmark", "Compare my metrics to other crew members"),
                            ("EVA Clearance Check", "Evaluate EVA spacewalk clearance"),
                            ("Flight Surgeon Sitrep", "Generate Flight Surgeon sitrep"),
                            ("Cycle & Hormone Insight", "Analyze menstrual cycle and hormone impact"),
                        ]:
                            ui.button(
                                chip_label,
                                on_click=lambda p=chip_prompt: run_ai_query(p),
                            ).props("dense unelevated size=sm color=indigo-9 text-color=indigo-2")

                    with ui.card().classes("w-full bg-slate-950/90 border border-indigo-500/30 p-3"):
                        ui.markdown(state["ai_response"]).classes("text-xs text-slate-200 leading-relaxed")

                    with ui.row().classes("w-full gap-2 mt-2 items-center"):
                        user_q = ui.input(
                            placeholder="Ask Aegis-Med (e.g., 'How do I compare to the crew?' or 'How to reach #1?')..."
                        ).props("dense outlined dark").classes("flex-1")

                        async def submit_custom_q():
                            if user_q.value and user_q.value.strip():
                                q_text = user_q.value.strip()
                                user_q.value = ""
                                await run_ai_query(q_text)

                        user_q.on("keydown.enter", submit_custom_q)
                        ui.button("Ask AI", icon="send", on_click=submit_custom_q).props("dense color=indigo size=sm")

                    with ui.expansion("Optional: Connect Live Gemini API Key", icon="vpn_key").classes(
                        "w-full text-xs text-slate-400 mt-1"
                    ):
                        ui.input(
                            label="Gemini API Key (leave blank for built-in offline clinical reasoning)",
                            password=True,
                            password_toggle_button=True,
                            value=state["gemini_api_key"],
                            on_change=lambda e: state.update({"gemini_api_key": e.value}),
                        ).props("dense outlined dark").classes("w-full")

                # 6. Dedicated Menstrual Cycle & Endocrine Tracker Panel (Female Profile)
                if state["gender"] == "Female":
                    phase_name, phase_desc, _ = get_cycle_phase_info(state["cycle_day"], state["cycle_mode"])
                    with ui.card().classes("w-full bg-slate-900 border border-pink-500/40 p-4"):
                        with ui.row().classes("w-full justify-between items-center"):
                            ui.label("🌸 In-Flight Menstrual & Endocrine Tracker").classes("text-base font-bold text-pink-300")
                            ui.badge(f"Day {state['cycle_day']} • {phase_name}", color="pink").classes("text-xs")

                        if state["cycle_mode"] == "Natural Cycle (Active)":
                            with ui.row().classes("w-full gap-0.5 my-2 items-center"):
                                for d in range(1, 29):
                                    if d <= 5:
                                        seg_color = "#F43F5E"
                                    elif d <= 13:
                                        seg_color = "#38BDF8"
                                    elif d == 14:
                                        seg_color = "#10B981"
                                    else:
                                        seg_color = "#F59E0B"
                                    is_today = d == min(state["cycle_day"], 28)
                                    opacity = "1.0" if is_today else "0.35"
                                    border = "2px solid white" if is_today else "none"
                                    ui.element("div").style(
                                        f"flex: 1; height: 10px; background-color: {seg_color}; "
                                        f"opacity: {opacity}; border-radius: 2px; border: {border};"
                                    )
                            ui.label(
                                "Pink: Menstrual (1–5) | Blue: Follicular (6–13) | Green: Ovulation (14) | Amber: Luteal (15–28)"
                            ).classes("text-[11px] text-slate-400")
                        else:
                            ui.label(f"Suppression Protocol: {state['cycle_mode']}").classes("text-xs text-purple-300 my-1")

                        with ui.row().classes("w-full gap-4 mt-2 text-xs text-slate-200 font-mono"):
                            ui.label(f"Estradiol (E2): {state['estradiol']} pg/mL")
                            ui.label(f"Progesterone (P4): {state['progesterone']:.1f} ng/mL")
                            ui.label(f"Flow: {state['flow_status']}")

                        ui.label(f"Symptom/Note: {state['menstrual_symptom']} — {phase_desc}").classes(
                            "text-xs text-slate-300 mt-1"
                        )

                        def log_cycle_entry():
                            state["cycle_log"].insert(
                                0,
                                {
                                    "mission_day": f"FD-{44 + len(state['cycle_log']) - 2}",
                                    "cycle_day": state["cycle_day"],
                                    "phase": phase_name,
                                    "mode": state["cycle_mode"],
                                    "flow": state["flow_status"],
                                    "hormones": f"E2: {state['estradiol']} pg/mL | P4: {state['progesterone']:.1f} ng/mL",
                                    "notes": f"{state['menstrual_symptom']} ({datetime.now().strftime('%H:%M')})",
                                },
                            )
                            state["xp"] += 25
                            ui.notify("+25 XP • Cycle entry logged to crew medical record", type="positive")
                            refresh_all()

                        with ui.row().classes("w-full justify-between items-center mt-2"):
                            ui.button(
                                "Log Today's Cycle Entry (+25 XP)",
                                icon="add_circle",
                                on_click=log_cycle_entry,
                            ).props("dense outline size=sm color=pink")
                            ui.label(f"{len(state['cycle_log'])} entries logged").classes("text-xs text-slate-400")

                        ui.table(
                            columns=[
                                {"name": "mission_day", "label": "Mission", "field": "mission_day", "align": "left"},
                                {"name": "cycle_day", "label": "Day", "field": "cycle_day", "align": "center"},
                                {"name": "phase", "label": "Phase", "field": "phase", "align": "left"},
                                {"name": "flow", "label": "Flow", "field": "flow", "align": "left"},
                                {"name": "hormones", "label": "Hormones", "field": "hormones", "align": "left"},
                                {"name": "notes", "label": "Notes", "field": "notes", "align": "left"},
                            ],
                            rows=state["cycle_log"][:4],
                        ).props("dense flat bordered dark").classes("w-full mt-2 text-xs")

                # 7. Prioritized Crew Triage Queue
                ui.label("Prioritized Crew Triage Queue (Click any card to view animated action)").classes(
                    "text-base font-semibold text-slate-200 mt-2"
                )
                for sys_name, info in sorted_systems:
                    border_cls = {
                        "RED": "border-l-4 border-rose-500 bg-rose-950/30",
                        "YELLOW": "border-l-4 border-amber-400 bg-amber-950/20",
                        "GREEN": "border-l-4 border-emerald-500 bg-slate-900/80",
                    }[info["status"]]
                    primary_cm = info["countermeasures"][0]
                    cm_label = ACTION_META[primary_cm]["title"]

                    def select_card(name=sys_name):
                        state["selected_system"] = name
                        refresh_all()

                    with ui.card().classes(f"w-full p-3 cursor-pointer hover:brightness-110 {border_cls}").on(
                        "click", select_card
                    ):
                        with ui.row().classes("w-full justify-between items-center"):
                            ui.label(sys_name).classes("font-semibold text-sm")
                            with ui.row().classes("items-center gap-2"):
                                ui.badge(f"▶ {cm_label}", color="sky" if info["status"] != "GREEN" else "positive").props("outline")
                                ui.label(info["reading"]).classes("text-xs font-mono text-slate-300")
                        ui.label(info["action"]).classes("text-xs text-slate-300 mt-1")

    # Header
    with ui.header().classes("bg-slate-950 border-b border-slate-800 px-6 py-3 items-center justify-between"):
        with ui.row().classes("items-center gap-3"):
            ui.label("🩺 CrewMed").classes("text-xl font-bold text-sky-400")
            ui.label("Autonomous Spaceflight Crew Health & Triage System").classes("text-sm text-slate-400")

        def tick_telemetry():
            state["hr"] = max(42, min(135, state["hr"] + random.choice([-1, 0, 1])))
            state["spo2"] = max(86, min(100, state["spo2"] + random.choice([0, 0, -1, 1])))
            state["ppco2"] = round(max(0.8, min(5.8, state["ppco2"] + random.choice([-0.1, 0.0, 0.1]))), 1)
            state["rad_msv"] = round(state["rad_msv"] + 0.2, 1)
            hr_slider.value = state["hr"]
            spo2_slider.value = state["spo2"]
            ppco2_slider.value = state["ppco2"]
            rad_slider.value = state["rad_msv"]
            if not state["gemini_api_key"].strip():
                state["ai_response"] = generate_local_ai_insights(evaluate_crew_health(), state["ai_last_prompt"])
            refresh_all()

        sim_timer = ui.timer(1.5, tick_telemetry, active=False)
        ui.switch("Live ISS/Orion Telemetry Stream").bind_value_to(sim_timer, "active").classes("text-sky-300")

    # Left Sidebar Controls
    with ui.left_drawer(value=True).classes("bg-slate-950 border-r border-slate-800 p-4"):
        def update_val(key, val):
            state[key] = val
            if not state["gemini_api_key"].strip():
                state["ai_response"] = generate_local_ai_insights(evaluate_crew_health(), state["ai_last_prompt"])
            refresh_all()

        def switch_gender(new_gender):
            state["gender"] = new_gender
            if new_gender == "Male" and state["selected_system"] == "Endocrine & Menstrual":
                state["selected_system"] = "Endocrine (HPG)"
            elif new_gender == "Female" and state["selected_system"] == "Endocrine (HPG)":
                state["selected_system"] = "Endocrine & Menstrual"
            menstrual_sidebar_box.set_visibility(new_gender == "Female")
            if not state["gemini_api_key"].strip():
                state["ai_response"] = generate_local_ai_insights(evaluate_crew_health(), state["ai_last_prompt"])
            refresh_all()

        ui.label("1. Crew Physiological Profile").classes("text-sm font-bold text-sky-400 uppercase tracking-wider")
        ui.radio(
            ["Female", "Male"],
            value=state["gender"],
            on_change=lambda e: switch_gender(e.value),
        ).props("inline color=pink").classes("my-1")

        ui.separator().classes("my-3")
        ui.label("2. Mission Presets").classes("text-sm font-bold text-sky-400 uppercase tracking-wider")

        def apply_preset(preset_name):
            state.update(PRESETS[preset_name])
            trt_slider.value = state["delta_trt"]
            iop_slider.value = state["iop"]
            sleep_slider.value = state["sleep_hrs"]
            pvt_slider.value = state["pvt_drift"]
            ijv_select.value = state["ijv_flow"]
            hgb_slider.value = state["hgb"]
            hr_slider.value = state["hr"]
            spo2_slider.value = state["spo2"]
            ppco2_slider.value = state["ppco2"]
            ca_slider.value = state["urine_ca"]
            vol_slider.value = state["urine_vol"]
            k_slider.value = state["potassium"]
            ex_slider.value = state["exercise_pct"]
            rad_slider.value = state["rad_msv"]
            vit_d_slider.value = state["vit_d"]
            vit_b12_slider.value = state["vit_b12"]
            ferritin_slider.value = state["ferritin"]
            mg_slider.value = state["magnesium"]
            na_slider.value = state["sodium"]
            cycle_mode_select.value = state["cycle_mode"]
            cycle_day_slider.value = state["cycle_day"]
            e2_slider.value = state["estradiol"]
            p4_slider.value = state["progesterone"]
            flow_select.value = state["flow_status"]
            symptom_select.value = state["menstrual_symptom"]
            if not state["gemini_api_key"].strip():
                state["ai_response"] = generate_local_ai_insights(evaluate_crew_health(), "Auto-Synthesis")
            refresh_all()

        with ui.row().classes("w-full gap-1 my-2"):
            for p_name in PRESETS:
                ui.button(p_name.split()[0], on_click=lambda n=p_name: apply_preset(n)).props("dense outline size=sm")

        # Dedicated Menstrual Cycle Sidebar Section
        with ui.column().classes("w-full") as menstrual_sidebar_box:
            ui.separator().classes("my-3")
            ui.label("3. Menstrual & Hormone Tracking").classes("text-sm font-bold text-pink-400 uppercase tracking-wider mb-1")

            cycle_mode_select = ui.select(
                ["Natural Cycle (Active)", "Hormonal Suppression (COC)", "Hormonal IUD (LNG-IUD)"],
                label="Cycle Management Mode",
                value=state["cycle_mode"],
                on_change=lambda e: update_val("cycle_mode", e.value),
            ).classes("w-full my-1")

            ui.label("Cycle Day (1–35)").classes("text-xs text-slate-400")
            cycle_day_slider = ui.slider(min=1, max=35, step=1, value=state["cycle_day"], on_change=lambda e: update_val("cycle_day", e.value)).props("label color=pink")

            ui.label("Estradiol E2 (pg/mL)").classes("text-xs text-slate-400")
            e2_slider = ui.slider(min=10, max=350, step=5, value=state["estradiol"], on_change=lambda e: update_val("estradiol", e.value)).props("label color=pink")

            ui.label("Progesterone P4 (ng/mL)").classes("text-xs text-slate-400")
            p4_slider = ui.slider(min=0.2, max=25.0, step=0.2, value=state["progesterone"], on_change=lambda e: update_val("progesterone", e.value)).props("label color=pink")

            flow_select = ui.select(
                ["None / Dry", "Light / Spotting", "Moderate (Normal)", "Heavy / Menorrhagia"],
                label="Flow / Bleeding Status",
                value=state["flow_status"],
                on_change=lambda e: update_val("flow_status", e.value),
            ).classes("w-full my-1")

            symptom_select = ui.select(
                ["None", "Mild Fluid Retention / Bloating", "Moderate Cramps & Fatigue", "Headache / Mood Shift"],
                label="Reported Symptom",
                value=state["menstrual_symptom"],
                on_change=lambda e: update_val("menstrual_symptom", e.value),
            ).classes("w-full my-1")

        menstrual_sidebar_box.set_visibility(state["gender"] == "Female")

        ui.separator().classes("my-3")
        ui.label("4. Vitamins & Electrolytes Panel").classes("text-sm font-bold text-emerald-400 uppercase tracking-wider mb-2")

        ui.label("Vitamin D 25-OH (ng/mL) [Normal: 30–80]").classes("text-xs text-slate-400")
        vit_d_slider = ui.slider(min=5, max=105, step=1, value=state["vit_d"], on_change=lambda e: update_val("vit_d", e.value)).props("label color=emerald")

        ui.label("Vitamin B12 (pg/mL) [Normal: 250–900]").classes("text-xs text-slate-400")
        vit_b12_slider = ui.slider(min=120, max=1080, step=10, value=state["vit_b12"], on_change=lambda e: update_val("vit_b12", e.value)).props("label color=emerald")

        ui.label("Ferritin Iron Stores (ng/mL)").classes("text-xs text-slate-400")
        ferritin_slider = ui.slider(min=5, max=360, step=1, value=state["ferritin"], on_change=lambda e: update_val("ferritin", e.value)).props("label color=emerald")

        ui.label("Magnesium Mg²⁺ (mg/dL) [Normal: 1.7–2.3]").classes("text-xs text-slate-400")
        mg_slider = ui.slider(min=1.1, max=2.9, step=0.1, value=state["magnesium"], on_change=lambda e: update_val("magnesium", e.value)).props("label color=emerald")

        ui.label("Sodium Na⁺ (mmol/L) [Normal: 135–145]").classes("text-xs text-slate-400")
        na_slider = ui.slider(min=126, max=154, step=1, value=state["sodium"], on_change=lambda e: update_val("sodium", e.value)).props("label color=emerald")

        ui.separator().classes("my-3")
        ui.label("5. Point-of-Care Exam Inputs").classes("text-sm font-bold text-sky-400 uppercase tracking-wider mb-2")

        ui.label("ΔTRT Retinal Thickness (µm)").classes("text-xs text-slate-400")
        trt_slider = ui.slider(min=0, max=80, step=0.5, value=state["delta_trt"], on_change=lambda e: update_val("delta_trt", e.value)).props("label")

        ui.label("Intraocular Pressure (mmHg)").classes("text-xs text-slate-400")
        iop_slider = ui.slider(min=8, max=35, step=1, value=state["iop"], on_change=lambda e: update_val("iop", e.value)).props("label")

        ui.label("Sleep Duration (hrs/night)").classes("text-xs text-slate-400")
        sleep_slider = ui.slider(min=3.0, max=9.5, step=0.1, value=state["sleep_hrs"], on_change=lambda e: update_val("sleep_hrs", e.value)).props("label")

        ui.label("PVT Reaction Time Drift (%)").classes("text-xs text-slate-400")
        pvt_slider = ui.slider(min=0, max=40, step=1, value=state["pvt_drift"], on_change=lambda e: update_val("pvt_drift", e.value)).props("label")

        ijv_select = ui.select(
            ["Forward (Normal)", "Stagnant / Oscillating", "Reversed / Thrombus"],
            label="Internal Jugular Vein Flow",
            value=state["ijv_flow"],
            on_change=lambda e: update_val("ijv_flow", e.value),
        ).classes("w-full my-2")

        ui.label("Hemoglobin (g/dL)").classes("text-xs text-slate-400")
        hgb_slider = ui.slider(min=9.0, max=18.0, step=0.1, value=state["hgb"], on_change=lambda e: update_val("hgb", e.value)).props("label")

        ui.label("Heart Rate (bpm)").classes("text-xs text-slate-400")
        hr_slider = ui.slider(min=35, max=140, step=1, value=state["hr"], on_change=lambda e: update_val("hr", e.value)).props("label")

        ui.label("SpO2 (%)").classes("text-xs text-slate-400")
        spo2_slider = ui.slider(min=82, max=100, step=1, value=state["spo2"], on_change=lambda e: update_val("spo2", e.value)).props("label")

        ui.label("Cabin ppCO2 (mmHg)").classes("text-xs text-slate-400")
        ppco2_slider = ui.slider(min=0.5, max=6.0, step=0.1, value=state["ppco2"], on_change=lambda e: update_val("ppco2", e.value)).props("label")

        ui.label("24-Hr Urinary Calcium (mg/d)").classes("text-xs text-slate-400")
        ca_slider = ui.slider(min=100, max=450, step=5, value=state["urine_ca"], on_change=lambda e: update_val("urine_ca", e.value)).props("label")

        ui.label("Daily Urine Output (L/day)").classes("text-xs text-slate-400")
        vol_slider = ui.slider(min=0.5, max=3.0, step=0.1, value=state["urine_vol"], on_change=lambda e: update_val("urine_vol", e.value)).props("label")

        ui.label("Serum Potassium K+ (mmol/L)").classes("text-xs text-slate-400")
        k_slider = ui.slider(min=2.8, max=6.0, step=0.1, value=state["potassium"], on_change=lambda e: update_val("potassium", e.value)).props("label")

        ui.label("ARED Exercise Compliance (%)").classes("text-xs text-slate-400")
        ex_slider = ui.slider(min=0, max=100, step=1, value=state["exercise_pct"], on_change=lambda e: update_val("exercise_pct", e.value)).props("label")

        ui.label("Cumulative Radiation (mSv)").classes("text-xs text-slate-400")
        rad_slider = ui.slider(min=0, max=400, step=1, value=state["rad_msv"], on_change=lambda e: update_val("rad_msv", e.value)).props("label")

    with ui.column().classes("w-full p-4"):
        telemetry_panel()


# ---------------------------------------------------------
# PAGE 2: DEDICATED PROJECTOR TAB (/projector)
# ---------------------------------------------------------
@ui.page("/projector")
def projector_page():
    @ui.refreshable
    def projected_view():
        results = evaluate_crew_health()
        active_key = state["selected_system"] if state["selected_system"] in results else list(results.keys())[0]
        sel = results[active_key]
        badge_color = {"GREEN": "positive", "YELLOW": "warning", "RED": "negative"}[sel["status"]]
        _, mood_label, _ = get_facial_state(results)

        with ui.row().classes("w-full justify-center items-start gap-10 p-6 flex-wrap"):
            ui.interactive_image(
                source=blank_svg_source(560, 840),
                size=(560, 840),
                content=build_body_svg(results, width=560, height=840),
                on_mouse=lambda e: handle_body_click(e, 560, projected_view.refresh),
                sanitize=False,
            ).style("width: 560px; height: 840px; min-width: 560px;")

            with ui.column().classes("w-[520px] gap-4 mt-4"):
                ui.label("🩺 CrewMed Live Telemetry Projection").classes("text-2xl font-bold text-sky-400")
                ui.label(f"{get_active_astronaut_name()} ({state['gender']}) • Expression: {mood_label}").classes(
                    "text-xs text-slate-400"
                )

                with ui.card().classes("w-full bg-slate-900 border-2 border-sky-500/50 p-5"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(active_key).classes("text-xl font-bold text-sky-300")
                        ui.badge(sel["status"], color=badge_color).classes("text-sm px-3 py-1")
                    ui.label(f"Crewmember: {get_active_astronaut_name()}").classes("text-xs font-semibold text-pink-300 mt-1")
                    ui.label(f"Reading: {sel['reading']}").classes("text-base font-mono text-slate-100 mt-2")
                    ui.label(f"Reference: {sel['normal_ref']}").classes("text-xs text-slate-400 mt-1")
                    ui.separator().classes("my-3")
                    ui.label(sel["action"]).classes("text-sm text-slate-200")
                    render_countermeasure_visuals(sel)

                render_gamification_card(results, projected_view.refresh)
                render_crew_comparison_card(results, projected_view.refresh)
                render_vitamin_comparison_card()

    projected_view()
    ui.timer(1.0, projected_view.refresh)


ui.run(title="CrewMed | Autonomous Crew Health Triage", dark=True)