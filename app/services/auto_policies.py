# app/services/auto_policies.py
"""
The two Supervity Auto policies the call agent uses, shown read-only on the Auto Policies page.

This is a copy of the policies in Supervity Auto (Production, workspace Auto_cc_Training). The
live policies are authored and published in Auto. The page shows when this copy was last
synced and warns when it is older than STALE_AFTER_DAYS.

To refresh after a change in Auto: update the values below and SYNCED_AT, then rebuild.
Compare each policy's "updated_at" with the "Updated" time shown in Auto to know if it changed.
Nothing here is executed by the Command Centre.
"""

from datetime import date

# Date this copy was last checked against Supervity Auto (both policies unchanged since their updated_at).
SYNCED_AT = "2026-11-11"
STALE_AFTER_DAYS = 14
SOURCE = "Supervity Auto, Production, workspace Auto_cc_Training"

_NO_AGENT = "Read only the lines starting with [Customer]. Ignore [Agent] and [Unknown] lines. Judge what was said, never tone. "

LEAD_SCORE = {
    "policy_id": "01a1bf87-6742-739f-9fb5-17c67819caa1",
    "name": "ORL Lead Score Policy - Phani",
    "agent": "Lead Score",
    "description": (
        "Customer purchase-intent band 0 to 5 for ORL (Oberoi Realty) calls. Eight yes/no AI Judgments "
        "read the customer's lines; a first-match table returns a numeric band and label. A mismatch caps "
        "the band at 2; an unclear customer side gives 0. Reason and evidence are produced by the Lead "
        "Score operator."
    ),
    "workspace": "Auto_cc_Training",
    "version": 2,
    "published": True,
    "updated_at": "2026-11-09T09:14:54.973Z",
    "url": "https://auto.supervity.ai/u/policies?policy=01a1bf87-6742-739f-9fb5-17c67819caa1",
    "inputs": ["transcript"],
    "outputs": [
        {"field": "band", "values": ["0", "1", "2", "3", "4", "5"]},
        {
            "field": "label",
            "values": [
                "0 No usable conversation",
                "1 No purchase intent",
                "2 Weak interest",
                "3 Medium intent",
                "4 High intent",
                "5 Immediate intent",
            ],
        },
    ],
    "judgments": [
        {
            "name": "usable_conversation",
            "answers": ["yes", "no"],
            "rubric": _NO_AGENT
            + "Answer yes if there is a usable conversation: the customer actually speaks about a property enquiry or gives any buying signal, even in a very short call (a buying signal in 20 seconds counts as usable). Answer no if the call is a voicemail, silence, mute, hung up, a wrong number or random question unrelated to property (for example asking where the mall is), the transcript is exactly [NO SPEECH DETECTED], or there are no [Customer] lines at all (the customer side is unclear). A short call is not automatically no.",
        },
        {
            "name": "not_interested",
            "answers": ["yes", "no"],
            "rubric": _NO_AGENT
            + 'Answer yes if the customer clearly says they have no purchase intent: "not interested", already purchased a flat, "don\'t call me", "I never made this enquiry", or similar, and has not changed their mind later in the call. If the customer changes their mind, the latest statement wins. Answer no otherwise, including when the customer only seems hesitant or says nothing about interest.',
        },
        {
            "name": "visit_confirmed_or_dated",
            "answers": ["yes", "no"],
            "rubric": _NO_AGENT
            + 'Answer yes if the customer requests, confirms or proposes a site visit WITH a date or time (for example "Can I come Saturday at 11?" or "Yes, Sunday works"), or the customer discusses booking a unit. If only the agent suggests a visit or a date and the customer does not accept it, answer no. If the customer wants to visit but has not fixed any date or time, answer no. Never use a date the customer did not say. If the customer later withdraws the visit, the latest statement wins.',
        },
        {
            "name": "visit_wanted_no_date",
            "answers": ["yes", "no"],
            "rubric": _NO_AGENT
            + 'Answer yes if the customer says they want to visit the site or office but has NOT fixed any date or time (for example "I\'d like to visit, I\'ll tell you the date later"). Answer no if the customer gave a date or time, if only the agent suggested a visit and the customer did not accept, or if the customer did not talk about visiting.',
        },
        {
            "name": "gave_requirements_budget_timeline",
            "answers": ["yes", "no"],
            "rubric": _NO_AGENT
            + "Answer yes only if the customer themselves stated their requirements (for example configuration such as 2 BHK or 3 BHK, or location), AND their budget, AND when they want to buy or move. Never infer or assume a budget, date, size or location the customer did not say. If any of the three is missing from the customer's own words, answer no.",
        },
        {
            "name": "genuine_interest_specific_property",
            "answers": ["yes", "no"],
            "rubric": _NO_AGENT
            + 'Answer yes if the customer shows genuine interest in a specific property: asks several relevant questions about it (area, price, possession, amenities), says price, location and possession are okay, or says they need to discuss with family before deciding. A vague "okay", "hmm" or "will see" does not count as genuine interest. Answer no if the customer shows only general or no interest.',
        },
        {
            "name": "mismatch",
            "answers": ["yes", "no"],
            "rubric": _NO_AGENT
            + 'Answer yes if at any point the customer says what is on offer does not fit them on budget (too expensive, above budget), configuration (wrong size or BHK), location (wrong area) or timeline (possession too late or too early). Going ahead with a visit or asking for details does NOT resolve the mismatch. Answer no only if the customer never raised such a problem, or later explicitly says the problem is resolved (for example "okay, the price works for me"). Never infer a mismatch the customer did not say.',
        },
        {
            "name": "weak_signal",
            "answers": ["yes", "no"],
            "rubric": _NO_AGENT
            + 'Answer yes if the customer gives only a weak signal: just browsing, "send details on WhatsApp" on its own, "I\'ll let you know", "will see", or a vague "okay" with nothing specific. Answer no if the customer gives no such signal.',
        },
    ],
    "rules_title": "Decision table (first match wins)",
    "rules": [
        "If not_interested is yes, the band is 1 (No purchase intent).",
        "If usable_conversation is no or unsure, the band is 0 (No usable conversation).",
        "If mismatch is yes, the band is 2 (Weak interest).",
        "If visit_confirmed_or_dated is yes, the band is 5 (Immediate intent).",
        "If visit_wanted_no_date is yes and gave_requirements_budget_timeline is yes, the band is 4 (High intent).",
        "If genuine_interest_specific_property is yes, the band is 3 (Medium intent).",
        "If weak_signal is yes, the band is 2 (Weak interest).",
        "If any other judgment is unsure, or nothing above matches, the band is 2 (Weak interest).",
    ],
}

CALL_AUDIT = {
    "policy_id": "01a1bf82-f5a7-739a-b29e-089f14a53088",
    "name": "ORL Call Audit Policy-Phani",
    "agent": "Call Audit",
    "description": (
        "Sales agent audit for ORL (Oberoi Realty) calls: Politeness, Information and Query solved, each "
        'scored 1 to 5 from AI Judgments. Not-sure answers return "unsure" and the operator decides how to '
        "handle them. The no-speech case and the score percent are handled in the operator."
    ),
    "workspace": "Auto_cc_Training",
    "version": 2,
    "published": True,
    "updated_at": "2026-11-09T09:16:06.476Z",
    "url": "https://auto.supervity.ai/u/policies?policy=01a1bf82-f5a7-739a-b29e-089f14a53088",
    "inputs": ["transcript"],
    "outputs": [
        {"field": "politeness_score", "values": ["1", "2", "3", "4", "5", "unsure"]},
        {"field": "information_score", "values": ["1", "2", "3", "4", "5", "unsure"]},
        {"field": "query_score", "values": ["1", "2", "3", "4", "5", "unsure"]},
    ],
    "judgments": [
        {
            "name": "politeness_judgment",
            "answers": ["excellent", "good", "average", "below_average", "poor"],
            "rubric": "Judge only the lines starting with [Agent]. Ignore [Customer] and [Unknown] lines. Check three things in the agent's own words: a greeting, the company name, and the agent's own name; also check the tone. excellent (5): greeting, company name and own name all present, friendly tone throughout. good (4): exactly one of greeting, company name or own name is missing, tone friendly. average (3): two of the three are missing, or the tone is flat. below_average (2): none of the three present, or noticeably curt and hurried, but not rude. poor (1): rude, dismissive or mocking. If there are no [Agent] lines, answer unsure.",
        },
        {
            "name": "information_judgment",
            "answers": ["consistent", "minor_gaps", "partial", "mostly_missing", "incorrect"],
            "rubric": "Judge the information the agent gave (location, project, pricing, possession, configuration), using the customer's questions for context. You cannot check facts against a source, so judge completeness and consistency only. consistent (5): everything the customer asked was given, specific and consistent. minor_gaps (4): everything important was given, one minor detail vague. partial (3): some asked items given, others vague or missing; also when the agent does not have the information but promises a concrete follow-up (a callback or a message) and says nothing wrong. mostly_missing (2): little useful information, mostly vague or evasive, nothing wrong said. incorrect (1): a flat refusal with no follow-up, different figures for the same item, or the agent contradicts itself. If the customer asked for no information and the agent gave none, answer unsure.",
        },
        {
            "name": "query_judgment",
            "answers": [
                "fully_answered",
                "mostly_answered",
                "partly_answered",
                "callback_promised",
                "barely_answered",
                "not_answered",
            ],
            "rubric": "Was the customer's question answered? Use the customer's and the agent's lines. fully_answered (5): every question answered clearly and consistently. mostly_answered (4): the main question answered, a minor part left open. partly_answered (3): part answered, or deferred with a concrete follow-up. callback_promised (3): the agent only promises a callback or follow-up and gives no answer now. barely_answered (2): the agent tried but gave little of use. not_answered (1): the question was ignored or left unanswered. If the agent contradicts itself on the answer (for example two different figures for the same item), it is not fully answered: use partly_answered at most. If the customer asked no question, judge whether the purpose of the call was met.",
        },
    ],
    "rules_title": "Score tables",
    "rules": [
        "Politeness: excellent is 5, good is 4, average is 3, below_average is 2, poor is 1, unsure is unsure.",
        "Information: consistent is 5, minor_gaps is 4, partial is 3, mostly_missing is 2, incorrect is 1, unsure is unsure.",
        "Query solved: fully_answered is 5, mostly_answered is 4, partly_answered and callback_promised are 3, barely_answered is 2, not_answered is 1, unsure is unsure.",
    ],
}

AUTO_POLICIES = [LEAD_SCORE, CALL_AUDIT]


def snapshot_info(today: date | None = None) -> dict:
    """When the copy was synced, how old it is, and whether it is old enough to warn about."""
    age = ((today or date.today()) - date.fromisoformat(SYNCED_AT)).days
    return {
        "synced_at": SYNCED_AT,
        "source": SOURCE,
        "age_days": max(0, age),
        "stale": age > STALE_AFTER_DAYS,
        "stale_after_days": STALE_AFTER_DAYS,
    }
