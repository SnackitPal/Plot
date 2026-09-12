"""
Culture Shock & Relocation Radar Engine for PLOT: The Cultural Atlas.

Calculates multi-dimensional cultural friction between a user's 5D coordinates
and 15 empirically modeled Global City Centroids across:
1. Work Autonomy
2. Punctuality Strictness
3. Relational Integration
4. Capital Freedom
5. Civic Trust

Emits normalized Cultural Shock Index (CSI 0-100%), ranked divergence dimensions,
and field-tested behavioral survival protocols for travelers and expats.
"""

import math
from typing import Dict, List, Tuple, Any, Optional

from atlas.algorithms.compass import (
    DIMENSIONS,
    GLOBAL_CITY_CENTROIDS,
    calculate_normalized_euclidean_distance,
    compute_user_vector,
)

# City-specific hyper-local survival keys & cultural codes
CITY_LOCAL_CODES: Dict[str, Dict[str, Any]] = {
    "tokyo": {
        "local_maxim": "和を以て貴しと為す (Harmony is to be valued above all)",
        "golden_rule": "Meishi (business card) protocol: Receive cards with both hands, bow slightly, and keep the card resting respectfully on the conference table during negotiations. Never scribble notes on it.",
        "transit_code": "Train etiquette is absolute: Zero phone conversations, backpacks carried on your chest or overhead, and strict adherence to carriage queue lines.",
    },
    "berlin": {
        "local_maxim": "Feierabend ist heilig (The end-of-workday boundary is sacred)",
        "golden_rule": "Directness is respect: Germans separate the person from the critique. Brutally frank feedback in meetings is not an insult; it is the standard path to technical excellence.",
        "transit_code": "Pedestrian signals are law: Never cross on a red ampelmännchen even at 3:00 AM on an empty street, especially in the presence of children.",
    },
    "reykjavik": {
        "local_maxim": "Þetta reddast (It will all work out in the end)",
        "golden_rule": "Total egalitarianism: Iceland operates without honorifics or rigid hierarchy. Everyone, including prime ministers, is addressed by their first name.",
        "transit_code": "Communal geothermal pool etiquette: Thorough soap shower without swimwear before entering public hot tubs is non-negotiable hygiene law.",
    },
    "new_york": {
        "local_maxim": "Time is the only non-renewable asset",
        "golden_rule": "Speed is politeness: Walk briskly on sidewalks, have your subway card or order ready before reaching the counter, and get directly to the core point in email.",
        "transit_code": "Keep right on escalators: Blocking the passing lane during rush hour will earn immediate vocal correction from commuters.",
    },
    "sao_paulo": {
        "local_maxim": "Calor humano e jogo de cintura (Warmth and agile adaptability)",
        "golden_rule": "Relationship before business: Never jump straight to contract clauses. Shared long lunches and genuine inquiries about personal well-being are mandatory prerequisites to trust.",
        "transit_code": "Street vigilance: Keep smartphones tucked away in crowded avenues like Paulista and prefer verified app rides late at night.",
    },
    "singapore": {
        "local_maxim": "Efficiency, harmony, and flawless execution",
        "golden_rule": "Hawker center 'chope' code: A packet of tissue or an umbrella left on a hawker center table claims that seat. Respect the claim unconditionally.",
        "transit_code": "Immaculate public transit: Eating, drinking, or chewing gum on the MRT carries immediate fines and genuine social stigma.",
    },
    "zurich": {
        "local_maxim": "Pünktlichkeit und Diskretion (Punctuality and quiet discretion)",
        "golden_rule": "The 5-minute pre-arrival rule: Arriving at 09:00 for a 09:00 appointment means you are already late. Arrive at 08:55. Conscientiousness is the bedrock of Swiss life.",
        "transit_code": "Ruhezeit (quiet hours): Loud music, vacuuming, or running laundry after 22:00 or on Sundays triggers swift neighbor interventions.",
    },
    "london": {
        "local_maxim": "Understatement and unspoken irony",
        "golden_rule": "Decode indirect language: 'That is very brave' means 'That is suicidal'; 'I would quietly suggest' means 'Do this immediately'.",
        "transit_code": "The Tube queue and pub rounds: Never push in a queue, and always pay your round at the pub without calculating individual pence.",
    },
    "seoul": {
        "local_maxim": "빨리빨리 (Palli-palli: Speed, dynamism, and grit)",
        "golden_rule": "Hoeshik hierarchy: In team dinners, turn your head away when drinking in front of elders or managers, and pour drinks with both hands.",
        "transit_code": "Subway courtesy seats: The designated seats for elderly and pregnant commuters remain vacant even in crush-capacity trains.",
    },
    "amsterdam": {
        "local_maxim": "Doe maar gewoon, dan doe je al gek genoeg (Just act normal, that's crazy enough)",
        "golden_rule": "The Polder consensus: Flat hierarchy where interns openly critique founders. Candor is considered kindness, and sugarcoating is seen as manipulative.",
        "transit_code": "Bike lane supremacy: Pedestrians walking in designated reddish cycle paths will be furiously bell-chimed. Keep strictly to sidewalks.",
    },
    "mumbai": {
        "local_maxim": "Jugaad and boundless hospitality (Creative resourcefulness)",
        "golden_rule": "Chai diplomacy: Every transaction begins with a shared cup of tea and relational inquiry. Rushing an exchange signals coldness.",
        "transit_code": "Local train solidarity: Boarding and alighting local trains requires communal rhythm and mutual non-verbal coordination.",
    },
    "nairobi": {
        "local_maxim": "Harambee (Let us pull together as one)",
        "golden_rule": "Communal obligation: Financial and personal boundaries are permeable. Supporting extended family through life events via M-Pesa is deeply respected.",
        "transit_code": "Matatu culture: Public minibuses operate with vibrant soundscapes; greeting conductors politely establishes immediate rapport.",
    },
    "sydney": {
        "local_maxim": "No worries, mate (Egalitarian fairness)",
        "golden_rule": "The Tall Poppy test: Never brag about wealth, titles, or status. Self-deprecating humor and treating everyone from cleaner to CEO identically is mandatory.",
        "transit_code": "Beach and bush safety: Swim strictly between the red and yellow flags, and leave zero footprint in nature reserves.",
    },
    "madrid": {
        "local_maxim": "Vivir y convivir (Living fully in company)",
        "golden_rule": "The sacred Sobremesa: Conversations after lunch or dinner last longer than the meal itself. Rushing off immediately after paying is considered rude.",
        "transit_code": "Nocturnal schedule: Dinner before 21:30 is virtually non-existent; adapt your biological clock to late afternoon siesta and midnight terrace life.",
    },
    "cairo": {
        "local_maxim": "الكرم والشهامة (Generosity and dignified chivalry)",
        "golden_rule": "The hospitality obligation: When offered tea, coffee, or food, declining too quickly can wound host dignity. Accept with gratitude.",
        "transit_code": "Negotiation and respect: Friendly greetings and asking about the driver's health make city navigation smooth and affectionate.",
    },
}

# Generic protocol templates across 5 dimensions
DIMENSIONAL_PROTOCOLS: Dict[str, Dict[str, Any]] = {
    "punctuality": {
        "name": "Punctuality & Chronemics",
        "icon": "🕒",
        "high_dest": {
            "title": "The Zero-Minute Buffer & Elevator Rule",
            "friction": "Destination enforces absolute monochronic precision.",
            "protocol": "Arriving at the exact scheduled minute is considered late. Aim to be seated 5 minutes prior. Blaming transit or traffic is viewed as a failure of foresight.",
        },
        "low_dest": {
            "title": "The Relational Elasticity Principle",
            "friction": "Destination operates on fluid, relationship-first time.",
            "protocol": "Arriving on the exact dot for private dinners may catch hosts unprepared. A 20–40 minute arrival window is standard. Prioritize the ongoing human connection over clock rigidities.",
        },
    },
    "autonomy": {
        "name": "Work Autonomy & Hierarchy",
        "icon": "💼",
        "high_dest": {
            "title": "Egalitarian Direct Candor",
            "friction": "Destination expects individual sovereignty and flat-hierarchy pushback.",
            "protocol": "Do not wait for hierarchical approval. Challenge ideas directly in open meetings and present your own solutions. Hesitation or deference is mistaken for lack of competence.",
        },
        "low_dest": {
            "title": "Nemawashi & Collective Face Preservation",
            "friction": "Destination values team harmony and formal seniority deference.",
            "protocol": "Never openly contradict a superior in front of the group. Build consensus beforehand via informal 1-on-1 conversations ('Nemawashi'). Frame critique as collaborative inquiry.",
        },
    },
    "boundary": {
        "name": "Relational Boundaries & Intimacy",
        "icon": "🤝",
        "high_dest": {
            "title": "The Warm Hospitable Check Grab",
            "friction": "Destination prizes permeable, familial warmth across all ties.",
            "protocol": "Itemizing restaurant bills to individual cents signals emotional detachment. Vigorously competing to cover the check is normal camaraderie. Expect colleagues to invite you into their homes.",
        },
        "low_dest": {
            "title": "The Sacred Independent Perimeter",
            "friction": "Destination maintains strict separation between professional and private life.",
            "protocol": "Work ends sharply at 5:00 PM. Do not ask intrusive questions about marriage or family life without explicit invitation. Splitting checks down to the cent is respected as clean independence.",
        },
    },
    "freedom": {
        "name": "Capital Freedom & Enterprise",
        "icon": "⚡",
        "high_dest": {
            "title": "High-Velocity Reinvention Appetite",
            "friction": "Destination celebrates rapid exits, self-employment, and aggressive career mobility.",
            "protocol": "Sticking to an uninspiring role out of loyalty is seen as complacency. Bold pivots, side ventures, and negotiation of equity or time sovereignty are openly applauded.",
        },
        "low_dest": {
            "title": "Conscientious Institutional Stewardship",
            "friction": "Destination honors tenure, duty, and long-term organizational stewardship.",
            "protocol": "Rapid job-hopping triggers skepticism regarding reliability. Demonstrating multi-year commitment, team loyalty, and thorough handoffs builds deep social capital.",
        },
    },
    "trust": {
        "name": "Civic Trust & Stranger Dynamics",
        "icon": "🛡️",
        "high_dest": {
            "title": "The Unattended Laptop Test",
            "friction": "Destination runs on immaculate generalized public trust.",
            "protocol": "Civic spaces operate as communal living rooms. Leaving personal items to hold a seat is customary. Obey unwritten rules of queueing, sorting trash, and quietude without reminder.",
        },
        "low_dest": {
            "title": "Situational Vigilance & In-Group Vetting",
            "friction": "Destination relies on interpersonal networks rather than abstract civic trust.",
            "protocol": "Formal institutional promises carry less weight than a warm personal introduction. Keep belongings secure in crowded hubs, verify details independently, and cultivate strong local guides.",
        },
    },
}


def calculate_culture_shock(
    user_vector: Dict[str, float],
    destination_id: str,
) -> Dict[str, Any]:
    """
    Computes 5D cultural friction, Cultural Shock Index (CSI),
    dimensional divergences, and actionable survival protocols.
    """
    dest = next((c for c in GLOBAL_CITY_CENTROIDS if c["city_id"] == destination_id), None)
    if not dest:
        dest = GLOBAL_CITY_CENTROIDS[0]

    dim_keys = [d["key"] for d in DIMENSIONS]
    u_vals = [user_vector.get(k, 0.5) for k in dim_keys]
    d_vals = dest["vector"]

    deltas = []
    divergence_items = []
    for i, k in enumerate(dim_keys):
        u_k = u_vals[i]
        d_k = d_vals[i]
        delta_k = round(u_k - d_k, 4)
        abs_delta = round(abs(delta_k), 4)
        deltas.append(delta_k)

        dim_meta = DIMENSIONS[i]
        divergence_items.append({
            "key": k,
            "label": dim_meta["label"],
            "user_val": u_k,
            "dest_val": d_k,
            "delta": delta_k,
            "abs_delta": abs_delta,
            "friction_level": "acute" if abs_delta >= 0.40 else ("moderate" if abs_delta >= 0.20 else "low"),
            "color": dim_meta["color"],
        })

    divergence_items.sort(key=lambda x: x["abs_delta"], reverse=True)

    mean_sq_dist = sum(d ** 2 for d in deltas) / len(deltas)
    csi_raw = math.sqrt(mean_sq_dist) * 100.0
    csi_pct = min(100, max(0, round(csi_raw)))

    if csi_pct < 25:
        severity = "low"
        verdict = "Low Friction • Natural Cultural Alignment"
        verdict_summary = f"Your daily worldview is in natural harmony with {dest['city_name']}. The social rhythms, boundaries, and working norms will feel largely intuitive."
        badge_bg = "#DCFCE7"
        badge_text = "#14532D"
    elif csi_pct < 50:
        severity = "moderate"
        verdict = "Noticeable Nuance • Conscious Code-Switching Required"
        verdict_summary = f"You will navigate {dest['city_name']} smoothly with awareness. Notable friction points exist in {divergence_items[0]['label']} and {divergence_items[1]['label']}."
        badge_bg = "#FEF3C7"
        badge_text = "#92400E"
    else:
        severity = "acute"
        verdict = "Acute Culture Shock • Inverted Social Operating System"
        verdict_summary = f"{dest['city_name']} operates on fundamentally inverted assumptions from your worldview. Expect major surprises in {divergence_items[0]['label']} and {divergence_items[1]['label']}."
        badge_bg = "#FEE2E2"
        badge_text = "#991B1B"

    protocol_cards = []
    for item in divergence_items[:3]:
        dim_key = item["key"]
        delta_val = item["delta"]
        proto_group = DIMENSIONAL_PROTOCOLS.get(dim_key, {})
        if not proto_group:
            continue

        template = proto_group["high_dest"] if delta_val < 0 else proto_group["low_dest"]

        protocol_cards.append({
            "dimension_key": dim_key,
            "dimension_label": proto_group.get("name", item["label"]),
            "icon": proto_group.get("icon", "🧭"),
            "title": template["title"],
            "friction_context": template["friction"],
            "actionable_rule": template["protocol"],
            "user_score": int(round(item["user_val"] * 100)),
            "dest_score": int(round(item["dest_val"] * 100)),
            "abs_delta_pct": int(round(item["abs_delta"] * 100)),
            "severity": item["friction_level"],
        })

    local_info = CITY_LOCAL_CODES.get(dest["city_id"], {
        "local_maxim": dest["tagline"],
        "golden_rule": dest["narrative"],
        "transit_code": "Observe local customs with quiet respect and curiosity.",
    })

    return {
        "destination": {
            "city_id": dest["city_id"],
            "city_name": dest["city_name"],
            "country": dest["country"],
            "flag": dest["flag"],
            "tagline": dest["tagline"],
            "narrative": dest["narrative"],
            "vector": dest["vector"],
            "local_maxim": local_info["local_maxim"],
            "golden_rule": local_info["golden_rule"],
            "transit_code": local_info["transit_code"],
        },
        "csi_pct": csi_pct,
        "severity": severity,
        "verdict": verdict,
        "verdict_summary": verdict_summary,
        "badge_bg": badge_bg,
        "badge_text": badge_text,
        "divergences": divergence_items,
        "protocol_cards": protocol_cards,
        "user_vector": {k: u_vals[i] for i, k in enumerate(dim_keys)},
    }


def generate_personalized_dossier(
    user_vector: Dict[str, float],
    total_votes: int = 5,
    archetype_title: str = "THE AUTONOMOUS COSMOPOLITAN",
) -> Dict[str, Any]:
    """
    Synthesizes a deep personalized cultural DNA reading across three life arenas:
    1. Career & High-Stakes Ambition
    2. Friendship, Intimacy & Boundaries
    3. Conflict, Stress & Trust Under Pressure
    """
    autonomy = user_vector.get("autonomy", 0.5)
    punctuality = user_vector.get("punctuality", 0.5)
    boundary = user_vector.get("boundary", 0.5)
    freedom = user_vector.get("freedom", 0.5)
    trust = user_vector.get("trust", 0.5)

    if autonomy >= 0.65 and freedom >= 0.60:
        career_title = "The Sovereign Operator"
        career_analysis = "You view corporate ladders as optional rather than mandatory. Your primary career currency is time sovereignty and exit leverage. You perform best in high-ownership, asynchronous, merit-driven environments where results matter far more than seat time."
        career_trap = "Risk of prematurely exiting promising collaborative teams out of impatience with necessary governance protocols."
    elif autonomy <= 0.40 and punctuality >= 0.60:
        career_title = "The Institutional Anchor"
        career_analysis = "You thrive within clear chains of command, structured processes, and mutual conscientiousness. You build long-term institutional value and excel at turning complex ambiguities into dependable, repeatable workflows."
        career_trap = "Risk of staying in bureaucratic environments past their expiration date out of sheer institutional loyalty."
    else:
        career_title = "The Pragmatic Enterprise Synthesizer"
        career_analysis = "You skillfully balance personal career agility with team alignment. You know when to push for independence and when to compromise to ship large initiatives."
        career_trap = "Can occasionally exhaust yourself attempting to satisfy both bureaucratic demands and personal creative projects."

    if boundary >= 0.65 and punctuality <= 0.45:
        relational_title = "The Warm Permeable Weaver"
        relational_analysis = "You treat friendships like extended family. You do not count favors, you do not calculate minutes, and you are always available when an emergency strikes. Your social life is fluid, warm, and deeply bonded."
        relational_trap = "Can feel wounded by friends who practice rigid calendar timeboxing or transactional boundaries."
    elif boundary <= 0.40:
        relational_title = "The Clean Perimeter Architect"
        relational_analysis = "You maintain clean, healthy firewalls between your work, your close confidants, and acquaintances. You value clarity, mutual respect of personal space, and prompt communication."
        relational_trap = "May be misread as distant or reserved by cultures that equate intimacy with lack of boundaries."
    else:
        relational_title = "The Balanced Cosmopolitan Ally"
        relational_analysis = "You offer dependable, warm loyalty while respecting mutual personal schedules and privacy. You navigate diverse social circles with ease and tact."
        relational_trap = "Balancing commitments across disparate social circles can create calendar strain."

    if trust >= 0.70:
        conflict_title = "The Civic Restorer"
        conflict_analysis = "When friction occurs, your instinct is to assume good faith and appeal to shared principles or transparent dialogue. You expect institutions and people to honor commitments."
        conflict_trap = "Can be taken off-guard by bad-faith actors or hyper-competitive zero-sum negotiation tactics."
    elif trust <= 0.40:
        conflict_title = "The Vigilant Realist"
        conflict_analysis = "Under stress, you immediately inspect the underlying incentives and secure your downside. You believe trust must be earned through repeated, verifiable actions rather than spoken promises."
        conflict_trap = "May delay forming mutually beneficial alliances due to excessive vetting barriers."
    else:
        conflict_title = "The Pragmatic Arbitrator"
        conflict_analysis = "You evaluate conflict contextually. You seek win-win solutions where possible, but maintain clear boundaries and fallback positions if bad faith is detected."
        conflict_trap = "Can expend heavy cognitive energy mediating disputes between ideological hardliners."

    return {
        "archetype_title": archetype_title,
        "calibration_basis": f"Synthesized from {total_votes} empirical dilemma decisions across 6 sociological axes.",
        "arenas": [
            {
                "arena": "High-Stakes Career & Ambition",
                "icon": "💼",
                "archetype_role": career_title,
                "analysis": career_analysis,
                "watch_out": career_trap,
            },
            {
                "arena": "Friendship, Intimacy & Boundaries",
                "icon": "🤝",
                "archetype_role": relational_title,
                "analysis": relational_analysis,
                "watch_out": relational_trap,
            },
            {
                "arena": "Stress, Conflict & Trust Instinct",
                "icon": "⚡",
                "archetype_role": conflict_title,
                "analysis": conflict_analysis,
                "watch_out": conflict_trap,
            },
        ],
    }
