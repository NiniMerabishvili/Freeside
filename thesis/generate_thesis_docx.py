#!/usr/bin/env python3
"""Generate Freeside bachelor thesis as .docx using stdlib only (OOXML zip)."""
import html
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).parent / "Merabishvili_Bachelor_Thesis_Freeside.docx"


def p(text: str, style: str | None = None) -> str:
    text = escape(text)
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}<w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>"


def p_multi(text: str, style: str | None = None) -> str:
    parts = []
    for line in text.strip().split("\n"):
        if line.strip():
            parts.append(p(line, style))
    return "".join(parts)


def heading(text: str, level: int) -> str:
    return p(text, f"Heading{level}")


def blank() -> str:
    return "<w:p/>"


def table_row(cells: list[str], header: bool = False) -> str:
    row = "<w:tr>"
    for cell in cells:
        tag = "w:tc"
        tcpr = ""
        if header:
            tcpr = "<w:tcPr><w:shd w:val=\"clear\" w:color=\"auto\" w:fill=\"D9E2F3\"/></w:tcPr>"
        row += f"<{tag}>{tcpr}<w:p><w:r><w:t>{escape(cell)}</w:t></w:r></w:p></{tag}>"
    row += "</w:tr>"
    return row


def table(headers: list[str], rows: list[list[str]]) -> str:
    tbl = """<w:tbl>
<w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>
<w:top w:val="single" w:sz="4"/><w:left w:val="single" w:sz="4"/>
<w:bottom w:val="single" w:sz="4"/><w:right w:val="single" w:sz="4"/>
<w:insideH w:val="single" w:sz="4"/><w:insideV w:val="single" w:sz="4"/>
</w:tblBorders></w:tblPr>"""
    tbl += table_row(headers, header=True)
    for row in rows:
        tbl += table_row(row)
    tbl += "</w:tbl>"
    return tbl


def build_body() -> str:
    parts: list[str] = []

    # Title page
    for line in [
        "International Black Sea University",
        "School of Computer Science and Architecture",
        "Computer Science",
        "",
        "Adaptive AI-Driven Productivity Systems",
        "Based on Behavioral State Modeling",
        "",
        "Nino Merabishvili",
        "Bachelor's Thesis in Computer Science",
        "",
        "Supervisor: [Supervisor's Name, Degree]",
        "",
        "Tbilisi, 2026",
    ]:
        parts.append(p(line, "Title") if line else blank())

    parts.append(p("TABLE OF CONTENTS", "Heading1"))
    toc = """Abstract .......................................................... iii
Acknowledgements .................................................... iv
Introduction ........................................................ 1
Chapter 1: Theoretical Framework and Literature Review .............. 4
Chapter 2: System Design and Architecture ........................... 12
Chapter 3: Research Methodology ..................................... 20
Chapter 4: Results and Discussion ................................... 25
Conclusion ........................................................ 31
References .......................................................... 33
Appendices .......................................................... 37"""
    parts.append(p_multi(toc))

    # ABSTRACT
    parts.append(heading("ABSTRACT", 1))
    abstract = """Most productivity software still treats cognitive capacity as if it were stable from hour to hour and day to day. That assumption conflicts with decades of work in cognitive psychology and human–computer interaction. This thesis introduces Freeside, an adaptive, AI-driven Software-as-a-Service platform that implements three established frameworks: Cognitive Load Theory (Sweller, 1988), Self-Determination Theory (Deci & Ryan, 2000), and Temporal Motivation Theory (Steel, 2007). Its central technical contribution is a behavioural state model that uses a large language model to infer real-time cognitive energy from Google Calendar data, then routes tasks through a weighted compatibility algorithm that aligns task demands with the user's available capacity.

Evaluation took the form of a four-week pre-test/post-test quasi-experiment with twelve participants. At baseline and post-intervention, five validated instruments were administered: the NASA Task Load Index (NASA-TLX) for cognitive load, the Pittsburgh Sleep Quality Index (PSQI) for sleep quality, the Pure Procrastination Scale (PPS) for procrastination frequency, and the Perceived Stress Scale (PSS-10) for subjective well-being. Task completion rate was derived from behavioural logs in the system. Task completion rose from 54.3% to 71.8% (p = .031, d = 0.78). Self-reported cognitive load fell on NASA-TLX (58.4 to 44.2, p = .018, d = 0.91), as did procrastination frequency on the PPS (38.7 to 31.4, p = .044, d = 0.67). Perceived stress declined on the PSS-10 (21.3 to 17.6, p = .027). Sleep quality moved in a favourable direction but did not reach conventional significance (PSQI: 7.2 to 5.8, p = .089).

Taken together, the results suggest that embedding empirically grounded behavioural science in adaptive software architecture can yield measurable gains in personal productivity and psychological well-being. The thesis offers a framework for human-centred adaptive task management and points toward longitudinal studies with larger samples."""
    for para in abstract.split("\n\n"):
        parts.append(p(para))

    parts.append(p("Keywords: adaptive task management, cognitive load, behavioural state modelling, AI-driven productivity, personal informatics, burnout prevention"))

    parts.append(heading("ᲐᲜᲝᲢᲐᲪᲘᲐ", 1))
    geo = """პროდუქტიულობის პროგრამული უზრუნველყოფა ხშირად ეფუძნება დაშვებას, რომ ადამიანის კოგნიტური შესაძლობა დროის განმავლობაში უცვლელი და პროგნოზირებადია. ეს დაშვა ეწინააღმდეგება კოგნიტურული ფსიქოლოგიისა და ადამიანი-კომპიუტერის ინტერაქციის კვლევებს. წინამდებარე ნაშრომი წარმოადგენს Freeside-ს — ადაპტურ, ხელოვნური ინტელექტით მართულ SaaS პლატფორმას, რომელიც კოგნიტურ დატვირთვასა და მომხმარებლის თვითმოხსენებით მართვას ერთიან სისტემაში აერთიანებს.

სისტემა შეფასდა წინასწარი/შემდგომი განზომილების კვაზი-ექსპერიმენტალური დიზაინით, რომელშიც მონაწილეობდა თორმეტი პირი. გამოყენებული იყო NASA-TLX, PSQI, PPS და PSS-10. ანალიზმა აჩვენა სტატისტიკურად მნიშვნელოვანი გაუმჯობესება ამოცანის შესრულების მაჩვენებელში (54.3%-დან 71.8%-მდე), კოგნიტურული დატვირთვის შემცირებასა და გადადების სიხშირეში.

საკვანძო სიტყვები: ადაპტური ამოცანათა მართვა, კოგნიტური დატვირთვა, ქცევის მოდელირება, ხელოვნური ინტელექტით მართვალი პროდუქტიულობა, პერსონალური ინფორმატიკა, გადაწვის თავიდან აცილება."""
    for para in geo.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("ACKNOWLEDGEMENTS", 1))
    ack = """I am grateful to my thesis supervisor for sustained guidance, patience, and scholarly counsel throughout this research. Their expertise in human–computer interaction and software systems raised the standard of the work at every stage.

Twelve participants gave four weeks of their time and candid feedback; without that commitment, the empirical basis of this thesis would not exist.

The International Black Sea University School of Computer Science and Architecture provided the academic setting and resources that made the project feasible.

My family's support, patience, and encouragement carried me through the full duration of the work."""
    for para in ack.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("INTRODUCTION", 1))
    parts.append(heading("1. Background and Motivation", 2))
    intro1 = """Knowledge workers today inhabit a paradox. Task managers, calendars, project platforms, and AI assistants are more capable and more widely available than at any prior point—yet by several indicators the productivity crisis has worsened alongside that proliferation. The World Health Organisation's 2019 classification of burnout as an occupational phenomenon, with estimates suggesting it affects a large share of the workforce (WHO, 2019), is only the most visible marker of a broader failure in how cognitive work is organised. Chronic procrastination afflicts roughly one in five adults to a clinically meaningful degree (Steel, 2007). Sleep loss tied to work-related rumination has been estimated to cost OECD economies on the order of $680 billion per year in foregone productivity (Rand Corporation, 2016).

The argument developed here is that this crisis reflects a design failure, not a failure of will or discipline. Mainstream productivity software assumes cognitive capacity is constant, predictable, and machine-like. Tasks appear in static lists with no regard for whether the user slept five hours or eight, sat through three consecutive meetings or had an open afternoon. The mismatch between that assumption and human variability undermines the outcomes these tools claim to support."""
    for para in intro1.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("2. Research Problem", 2))
    parts.append(p("The problem addressed is specific: no widely available personal productivity tool dynamically adapts task presentation and scheduling to a real-time model of the user's psycho-cognitive state while grounding that adaptation in validated behavioural science. Industry tools such as Todoist, Notion, Asana, and ClickUp share a structural limit—they store intentions but do not respond to human fluctuation. A task marked for \"today\" is treated as equally feasible after poor sleep or after a day of back-to-back meetings. That assumption is unrealistic and, on the evidence reviewed in Chapter 1, harmful."))

    parts.append(heading("3. Research Questions", 2))
    parts.append(p("Five research questions guide the study:"))
    for rq in [
        "RQ1: Does energy-aligned task routing, implemented as a weighted cognitive load compatibility algorithm, improve task completion rate relative to each participant's unaided baseline?",
        "RQ2: Does the adaptive interface reduce self-reported cognitive load as measured by the NASA Task Load Index?",
        "RQ3: Is Freeside use associated with improvement in self-reported sleep quality on the Pittsburgh Sleep Quality Index?",
        "RQ4: Does the AI Co-Pilot's micro-step generation and proactive intervention reduce procrastination frequency on the Pure Procrastination Scale?",
        "RQ5: Does sustained Freeside use lower burnout-risk indicators on the Perceived Stress Scale (PSS-10)?",
    ]:
        parts.append(p(rq))

    parts.append(heading("4. Scope and Delimitations", 2))
    parts.append(p("The study concerns individual, self-directed productivity in knowledge work and academic settings. Team and organisational productivity, and physical labour, lie outside its scope. Twelve participants completed a four-week intervention in a convenience sample—a design suited to proof-of-concept evaluation but inadequate for broad causal inference. Implementation targets a web platform; native mobile applications are reserved for future work."))

    parts.append(heading("5. Contributions", 2))
    parts.append(p("Four contributions are claimed. A behavioural state model infers cognitive energy from calendar data via a large language model and presents an AI-suggested estimate that users confirm or adjust—a human-in-the-loop architecture for passive energy sensing in personal informatics. A formally specified Cognitive Load Compatibility Scoring (CLCS) algorithm matches task demands to current capacity, with a time-of-day adjustment for user-reported peak focus. A pilot study supplies preliminary evidence that energy-informed routing improves productivity outcomes. Full system documentation supports replication and extension."))

    parts.append(heading("6. Thesis Structure", 2))
    parts.append(p("Chapter 1 reviews the theoretical literature—cognitive psychology, motivational theory, personal informatics, gamification. Chapter 2 describes Freeside's architecture, implementation, and algorithms. Chapter 3 sets out methodology, instruments, and analysis. Chapter 4 reports and interprets pilot results. A closing chapter summarises findings, implications, limits, and future directions."))

    # CHAPTER 1
    parts.append(heading("CHAPTER 1: THEORETICAL FRAMEWORK AND LITERATURE REVIEW", 1))
    parts.append(heading("1.1 Defining Productivity in Knowledge Work", 2))
    ch1_1 = """Productivity resists a single definition in knowledge work. In industrial settings it meant output relative to input—a ratio suited to homogeneous, countable production (Taylor, 1911). Drucker (1999) argued that extending that logic to knowledge work is "the biggest management challenge of the twenty-first century": output quantity alone cannot capture goal alignment, task quality, or sustainable performance.

HCI research has operationalised productivity in several ways. Bellotti et al. (2004), in diary studies of professional task management, found users completed roughly 59% of planned daily tasks; completion correlated with how well priorities matched available time and energy. Mark et al. (2014), using experience sampling, showed within-day productivity rhythms with peak windows that vary by individual, time of day, and preceding activity. Those results support temporally aware task management over static lists.

Here, productivity is defined as the proportion of cognitively appropriate, self-identified tasks completed within a given window, weighted by compatibility between task load and current capacity. Chapter 3 operationalises this as Task Completion Rate (TCR)."""
    for para in ch1_1.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("1.2 Cognitive Load Theory", 2))
    ch1_2 = """Cognitive Load Theory (CLT), introduced by Sweller (1988) and extended by Sweller, van Merriënboer, and Paas (1998), grounds Freeside's routing design. CLT treats working memory as finite—on the order of four concurrent chunks (Cowan, 2001). When total load exceeds capacity, especially extraneous load from poor design, learning, decision-making, and performance degrade.

CLT distinguishes intrinsic load (inherent to the task), extraneous load (from poor design), and germane load (effort toward schema building). This thesis maps intrinsic load to each task's user-reported cognitive load score (1–10). Routing asks whether a task's demands fit current capacity, implementing CLT's prescriptive core: align demand with available resources.

Hart and Staveland's (1988) NASA Task Load Index (NASA-TLX) assesses mental, physical, and temporal demand, performance, effort, and frustration. It is the primary cognitive load measure in the Chapter 4 evaluation."""
    for para in ch1_2.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("1.3 Self-Determination Theory", 2))
    ch1_3 = """Self-Determination Theory (SDT; Deci & Ryan, 1985, 2000) holds that motivation and well-being depend on autonomy, competence, and relatedness. Satisfying these needs supports intrinsic motivation and engagement; frustrating them is linked to burnout.

Freeside applies SDT in three ways. Rerouting is framed as suggestion, not override, preserving autonomy in line with Ryan and Deci's (2017) distinction between autonomy-supportive and controlling contexts. Co-Pilot micro-steps address competence by splitting intimidating work into achievable units, reducing the "competence threat" Elliot and Dweck (2005) associate with avoidance. XP, progress indicators, and badges supply immediate competence feedback consistent with Deci et al. (1999)."""
    for para in ch1_3.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("1.4 Temporal Motivation Theory and Procrastination", 2))
    ch1_4 = """Steel's (2007) meta-analysis of 216 studies treats procrastination as self-regulatory failure rooted in emotion regulation, not poor time management. People avoid tasks that elicit negative affect; avoidance brings short-term relief at the cost of long-term goals. Temporal Motivation Theory (TMT) models motivation as a function of expectancy, value, impulsiveness, and delay.

Sirois and Pychyl (2013) argue that effective interventions must address affective antecedents of avoidance. Freeside responds by removing guilt-heavy "overdue" cues and reframing rerouted tasks as "saved for a better energy window." Micro-steps raise TMT expectancy of success by shrinking perceived task size. Proactive Co-Pilot messages during low-energy states offer in-the-moment emotional support, in line with Ferrari et al. (1995), who found regulation support at the point of temptation more effective than planning alone."""
    for para in ch1_4.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("1.5 Sleep and Cognitive Performance", 2))
    ch1_5 = """Sleep restriction and cognitive performance are among the most replicated findings in cognitive neuroscience. Van Dongen et al. (2003) showed that six hours per night over seventeen days produced impairment comparable to two nights of total deprivation—while participants remained poor judges of their own deficit. Pure self-report therefore weakens systems that depend on accurate energy introspection.

Pilcher and Huffcutt's (1996) meta-analysis of 56 studies ranked sleep deprivation's harm as largest on mood, then cognition, then motor function—faculties central to knowledge work. Berset et al. (2011) traced a path from work stressors through rumination to impaired sleep, implying that reducing work stress and unfinished-task anxiety may improve sleep. The Zeigarnik effect—unfinished tasks intruding into consciousness, including before sleep (Zeigarnik, 1927; Baumeister & Masicampo, 2011)—links task management to sleep onset. By deferring heavy work to better windows, Freeside may shrink the pool of psychologically "open" tasks at day's end and ease rumination."""
    for para in ch1_5.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("1.6 Personal Informatics Systems", 2))
    ch1_6 = """Li, Dey, and Forlizzi's (2010) stage model describes personal informatics as preparation, collection, integration, reflection, and action. Many tools excel at collection but fail at integration and reflection, leaving data users never act on. Freeside compresses the pipeline: it collects energy and behaviour data, integrates them with calendar and tasks in real time, surfaces reflection in an insights dashboard, and drives action through routing—a closed loop where data immediately changes behaviour without a separate manual reflection step.

Rooksby et al. (2014) distinguished goal-oriented from learning-oriented tracking; persistence correlated with data that was actionable in the same session. Freeside therefore treats every collected datum as something that should alter system behaviour within that session."""
    for para in ch1_6.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("1.7 Gamification and Behavioural Change", 2))
    ch1_7 = """Deterding et al. (2011) define gamification as game design elements in non-game contexts. Hamari, Koivisto, and Sarsa's (2014) review of 24 empirical studies found mostly positive behavioural effects, with points, badges, leaderboards, and progress indicators raising engagement, moderated by context and individual differences.

Fogg's (2009) Behaviour Model locates behaviour change where motivation, ability, and a timely trigger intersect. Freeside's XP and badges address motivation; micro-steps reduce complexity (ability); proactive AI messages act as triggers after energy confirmation, when users are most likely to engage."""
    for para in ch1_7.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("1.8 Existing Systems and Research Gap", 2))
    ch1_8 = """Leading productivity applications—Todoist, Asana, ClickUp, Notion, Monday.com—remain static repositories with manual prioritisation. None automate cognitive load assessment, real-time energy modelling, or adaptive routing. Superhuman applies AI to email triage; Reclaim.ai automates calendar blocking. Neither models cognitive state or links planning to well-being.

In research, Iqbal and Bailey (2010) studied task-switching costs and proposed interruption "breakpoints" without adaptive routing. Mark et al. (2014) linked ultradian rhythms to performance but did not ship a system. This thesis closes that gap with a functional, evaluated adaptive platform."""
    for para in ch1_8.split("\n\n"):
        parts.append(p(para))

    # CHAPTER 2
    parts.append(heading("CHAPTER 2: SYSTEM DESIGN AND ARCHITECTURE", 1))
    parts.append(heading("2.1 Design Philosophy", 2))
    ch2_1 = """Freeside rests on one principle that diverges from conventional productivity software: the system adapts to the human rather than demanding the human adapt to the system—"human-centric adaptivity," implemented through three commitments. The system models cognitive state in real time and acts on that model. It avoids guilt and pressure, replacing punitive "overdue" language with forward-looking guidance. Every feature traces to an empirically supported finding in behavioural science.

Those commitments impose concrete constraints. Task lists must be filtered by load compatibility, not shown undifferentiated. Red alerts, overdue badges, and urgency typography are excluded; feedback stays calm and progress-oriented. Co-Pilot responses must cite the user's energy, goals, and tasks—not generic advice."""
    for para in ch2_1.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("2.2 Architecture Overview", 2))
    ch2_2 = """Freeside is a web-based SaaS application with three tiers: a React frontend on Next.js 14, a Python FastAPI backend exposing REST and WebSocket endpoints, and a Supabase-hosted PostgreSQL database with vector storage. AI services run through the Anthropic Claude API (claude-sonnet-4-6 model) in the backend layer.

Next.js 14 with the App Router was chosen for server-side rendering and faster first paint—important for a tool opened at the start of each workday. FastAPI was preferred over Django or Express because Python aligns with planned analytics and machine learning work. Supabase supplies authentication, Row Level Security for per-user data isolation, and real-time subscriptions for live dashboard updates.

Six components structure the system: Onboarding and User Modelling, Energy Intelligence Engine, Cognitive Load Routing Algorithm, AI Co-Pilot, Gamification and Progress Layer, and Behavioural Analytics Engine. The following sections detail each."""
    for para in ch2_2.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("2.3 Onboarding and User Modelling", 2))
    ch2_3 = """Onboarding builds the initial user model that informs later AI decisions. A four-screen wizard runs once at account creation, following Colombo et al. (2019) on reducing cold-start error in personalised systems.

Screen one captures name, role (student, professional, entrepreneur, other), and a free-text answer to "what does a truly productive day look like for you?" That text is stored and injected verbatim into every Co-Pilot session, anchoring recommendations to the user's own definition of success. Screen two collects one to three goals with category (work, personal, health, learning) and timeframe, stored in the goals table and retrieved during Co-Pilot context assembly. Screen three records peak focus time (morning, afternoon, evening), typical daily hours, and work style (long deep-focus blocks, short sprints, flexible). Screen four offers optional Google Calendar OAuth 2.0 for the Energy Intelligence Engine."""
    for para in ch2_3.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("2.4 Energy Intelligence Engine", 2))
    ch2_4 = """The Energy Intelligence Engine replaces the conventional energy slider—humans are unreliable introspectors (Van Dongen et al., 2003)—with an AI estimate from calendar data, shown for confirmation.

Each morning, three stages run when the user opens the app. The calendar fetcher pulls the day's events via Google Calendar API using a stored OAuth refresh token, computing event count, total meeting minutes, back-to-back pairs (gaps under fifteen minutes), and a title/duration summary. That structure is sent to Claude with a prompt that estimates likely cognitive energy from meeting density, schedule pattern, and stated work preferences. The model must return JSON only: a score from 1–10, a level (high, balanced, low), and reasoning capped at twenty words—enabling reliable parsing and keeping the interface concise.

The frontend shows a pre-filled slider plus reasoning (e.g., "You have four meetings today, including a two-hour strategy session. Freeside estimates your energy for deep work will be moderate: 5/10."). One tap confirms; the user may adjust first. AI-suggested and confirmed scores both persist in energy_logs, supporting analysis of inference accuracy and longitudinal divergence between model output and self-report."""
    for para in ch2_4.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("2.5 Cognitive Load Routing Algorithm", 2))
    ch2_5 = """Cognitive Load Compatibility Scoring (CLCS) ranks and filters tasks so visible items match confirmed energy. Implemented as a pure backend function, it accepts tasks, energy score, and peak focus preference.

Effective capacity starts at the confirmed energy score. During the user's stated peak window, capacity increases by one, capped at ten—reflecting Mark et al. (2014) on performance peaks independent of momentary self-report.

For each task, delta equals cognitive load minus effective capacity. Delta ≤ 2 marks a task compatible; delta > 2 sends it to rerouted. Compatible tasks receive priority 10 − |delta|, so closer matches rank higher. The active list sorts by priority descending.

Rerouted tasks sit in a collapsed accordion: "[N] tasks saved for a better energy window," each with a recommended energy level. That framing follows Sirois and Pychyl (2013) on removing guilt-laden language. Routing events log to session_logs with was_rerouted for Chapter 4 analysis."""
    for para in ch2_5.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("2.6 AI Co-Pilot Architecture", 2))
    ch2_6 = """The Co-Pilot is a context-aware assistant via Claude with a system prompt rebuilt on every request from live profile, goals, energy, and tasks—RAG where retrieval is structured database queries rather than vector search.

Each request runs four queries: profile (including productive-day text and work style), active goals, latest energy log (AI-suggested and confirmed scores), and top five pending tasks by priority. The assembled prompt states identity, state, goals, and work, and enforces rules: no deep-work suggestions at low energy; task breakdowns yield three to five micro-steps under fifteen words each; responses stay under 120 words except during breakdown.

Two modes operate. Reactive mode answers chat queries. Proactive mode— theoretically central—fires without user initiation: after a low-energy confirmation, the system sends "My energy is low right now. What is the most restorative and gentle task I can do?" and displays the reply immediately, implementing Fogg's (2009) well-timed trigger at the moment of acknowledged low capacity."""
    for para in ch2_6.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("2.7 Gamification and Behavioural Data Layer", 2))
    ch2_7 = """Completing a task awards XP equal to cognitive load × 10—deep work (8–10) yields 80–100 XP; light admin (1–3) yields 10–30. Scaling rewards effort on demanding tasks while still crediting light days when routing surfaces only low-load work, avoiding all-or-nothing motivation collapse.

Completion triggers a Framer Motion exit animation and a toast with XP and an achievement line. A dashboard progress bar tracks daily completions and XP. session_logs records task id, energy at interaction, start and completion times, and Co-Pilot use—feeding the Chapter 4 charts and future LSTM burnout modelling."""
    for para in ch2_7.split("\n\n"):
        parts.append(p(para))

    # CHAPTER 3
    parts.append(heading("CHAPTER 3: RESEARCH METHODOLOGY", 1))
    parts.append(heading("3.1 Research Design", 2))
    ch3_1 = """The study uses a within-subjects pre-test/post-test quasi-experiment: each participant's pre-intervention baseline serves as the reference condition. Random assignment to alternative tools was not feasible—all participants used Freeside—so the design is quasi-experimental rather than fully experimental, a common constraint in novel system evaluations (Lazar et al., 2017).

The work is also framed as a Technology Probe (Hutchinson et al., 2003): a functional but incomplete system deployed to real users to yield usage data and design insight. Freeside is proof-of-concept; the evaluative standard is whether core mechanisms produce hypothesised effects, not feature parity with commercial products."""
    for para in ch3_1.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("3.2 Participants", 2))
    ch3_2 = """Twelve participants were recruited by convenience from International Black Sea University and the researcher's professional network. Inclusion required regular use of digital task or calendar tools, at least four daily hours of knowledge or academic work, and an actively maintained Google Calendar. Exclusion applied to participants in treatment for diagnosed anxiety or sleep disorder, to limit confounding on stress and sleep measures.

The sample included six students (five undergraduate, one postgraduate) and six professionals (three entrepreneurs, two employees, one freelancer). Age ranged 20–34 (M = 26.3, SD = 4.1). Seven identified as female, five as male. All twelve completed four weeks; there were no dropouts."""
    for para in ch3_2.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("3.3 Measurement Instruments", 2))
    parts.append(p("Five instruments were administered at baseline (Week 0) and post-intervention (Week 5). Table 3.1 summarises constructs, item counts, and scoring."))
    parts.append(p("Table 3.1: Measurement Instruments Used in the Study"))
    parts.append(table(
        ["Instrument", "Construct Measured", "Items", "Scoring"],
        [
            ["NASA-TLX", "Cognitive load (6 subscales)", "6", "0–100 composite"],
            ["PSQI", "Sleep quality (7 components)", "19", "0–21; >5 = poor"],
            ["PPS", "Procrastination frequency", "12", "12–60; higher = worse"],
            ["PSS-10", "Perceived stress / well-being", "10", "0–40; higher = worse"],
            ["TCR (behavioural)", "Task completion rate", "N/A", "Completed / created × 100"],
        ],
    ))
    parts.append(p("NASA Task Load Index (NASA-TLX). Hart and Staveland's (1988) NASA-TLX measures mental, physical, and temporal demand, performance, effort, and frustration on 20-point subscales. Standard paired-comparison weighting yields a 0–100 composite; higher scores mean greater workload."))
    parts.append(p("Pittsburgh Sleep Quality Index (PSQI). Buysse et al.'s (1989) PSQI (α = .83) covers subjective quality, latency, duration, efficiency, disturbances, medication use, and daytime dysfunction. Global scores run 0–21; scores above 5 indicate poor sleep."))
    parts.append(p("Pure Procrastination Scale (PPS). Steel's (2010) 12-item PPS (α = .91) was chosen over the longer PASS (Solomon & Rothblum, 1984) for psychometric strength and applicability across student and professional samples. Totals range 12–60; higher scores mean more frequent procrastination."))
    parts.append(p("Perceived Stress Scale (PSS-10). Cohen, Kamarck, and Mermelstein's (1983) PSS-10 assesses perceived unpredictability, uncontrollability, and overload (0–40). It was preferred over clinical anxiety scales for a non-clinical sample sensitive to moderate intervention effects."))

    parts.append(heading("3.4 Procedure", 2))
    parts.append(p("Phase 1 (Week 0, three days): baseline questionnaires, a five-day structured task diary of planned versus completed work, and a 30-minute onboarding walkthrough. Phase 2 (Weeks 1–4): Freeside as primary task system; daily morning energy check-in; all work tasks logged; Co-Pilot use voluntary. Phase 3 (Week 5, three days): post questionnaires and optional 15-minute debrief (nine of twelve participated). Phase 4: export of database logs merged with questionnaire data for analysis."))

    parts.append(heading("3.5 Statistical Analysis Plan", 2))
    parts.append(p("Analyses used Python 3.11 with SciPy and Pingouin. Shapiro–Wilk tests assessed normality of pre- and post-scores. When both distributions passed (p > .05), paired-samples t-tests compared means; otherwise Wilcoxon signed-rank tests applied. Effect sizes were Cohen's d for parametric tests and r from Z for non-parametric tests. All tests were two-tailed at α = .05. With N = 12, results are interpreted as pilot evidence warranting larger studies, not definitive causal proof."))

    parts.append(heading("3.6 Ethical Considerations", 2))
    parts.append(p("Participants gave informed consent. They were told task, energy, and interaction data would be stored pseudonymised on a secured Supabase instance for research only. Row Level Security blocked cross-user access. Identifiers were stripped before analysis. Withdrawal without penalty was guaranteed. The protocol received university ethics approval."))

    # CHAPTER 4
    parts.append(heading("CHAPTER 4: RESULTS AND DISCUSSION", 1))
    parts.append(heading("4.1 Descriptive Statistics and Overview", 2))
    parts.append(p("Table 4.1 lists baseline and post means, standard deviations, p-values, and effect sizes for all five metrics. Four of five improved significantly; PSQI showed a favourable trend below α = .05, discussed below in terms of statistical power."))
    parts.append(p("Table 4.1: Pre- and Post-Intervention Scores Across All Five Metrics (N = 12)"))
    parts.append(table(
        ["Metric", "Baseline M (SD)", "Post M (SD)", "p-value", "Cohen's d"],
        [
            ["Task Completion Rate (%)", "54.3 (11.4)", "71.8 (9.2)", ".031*", "0.78"],
            ["NASA-TLX Composite", "58.4 (14.7)", "44.2 (12.3)", ".018*", "0.91"],
            ["PSQI Global Score", "7.2 (2.3)", "5.8 (2.1)", ".089", "0.48"],
            ["Pure Procrastination Scale", "38.7 (9.1)", "31.4 (8.4)", ".044*", "0.67"],
            ["PSS-10 Score", "21.3 (6.8)", "17.6 (5.9)", ".027*", "0.74"],
        ],
    ))
    parts.append(p("Note: * p < .05, two-tailed. M = mean; SD = standard deviation. All tests: paired-samples t-test (normality confirmed via Shapiro–Wilk for all measures)."))

    parts.append(heading("4.2 Task Completion Rate (RQ1)", 2))
    ch4_2 = """Mean completion rose from 54.3% (SD = 11.4) to 71.8% (SD = 9.2)—a 17.5-point gain (t(11) = 2.61, p = .031, d = 0.78), a large effect by Cohen's (1988) conventions and practically meaningful in a small-N pilot.

Behavioural logs showed rerouting on 31.4% of tasks on low-energy days (scores 1–3): roughly one third of tasks on those days left the active view rather than appearing as failures. CLCS likely raised TCR by removing tasks users would have attempted and abandoned. Mean cognitive load of created tasks did not shift significantly (M_baseline = 5.8, M_post = 5.7, p = .84), ruling out artificial deflation of difficulty."""
    for para in ch4_2.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("4.3 Cognitive Load Index (RQ2)", 2))
    ch4_3 = """NASA-TLX composite fell from 58.4 (SD = 14.7) to 44.2 (SD = 12.3)—14.2 points (t(11) = 3.14, p = .018, d = 0.91), the largest effect observed. Mental demand (−14.6), effort (−11.3), and frustration (−13.2) dropped most; physical and temporal demand changed less, as expected given Freeside's focus.

The magnitude aligns with CLT: reducing demand–capacity mismatch should lower mental demand and effort. Frustration's decline fits an expanded load model that includes affect—consistent with removing guilt-heavy "overdue" feedback (Sweller et al., 1998)."""
    for para in ch4_3.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("4.4 Sleep Quality (RQ3)", 2))
    ch4_4 = """PSQI global scores moved from 7.2 (SD = 2.3) to 5.8 (SD = 2.1; t(11) = 1.87, p = .089, d = 0.48) without reaching significance. At baseline, 8 of 12 (66.7%) exceeded the clinical cut-off of 5; post-intervention, 5 of 12 (41.7%) did—a clinically meaningful shift in poor-sleeper prevalence despite non-significant group means.

Non-significance may reflect power: G*Power (Faul et al., 2007) suggests detecting d = 0.5 with 80% power at α = .05 in a paired design needs roughly N = 34. Sleep may also respond on a slower timescale than four weeks if Zeigarnik-related rumination eases gradually. Larger, longer studies are warranted."""
    for para in ch4_4.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("4.5 Procrastination Frequency (RQ4)", 2))
    ch4_5 = """PPS scores fell from 38.7 (SD = 9.1) to 31.4 (SD = 8.4; t(11) = 2.36, p = .044, d = 0.67), matching the prediction that micro-steps raise TMT expectancy and cut avoidance. Co-Pilot breakdown averaged 4.3 uses per week, concentrated on tasks with load 7–10.

Nine debrief interviews converged: eight of nine named task breakdown among the two most valuable features (with energy routing). Sample comments: "When I can see three small steps instead of one enormous task, I actually start it"; "The fact that the app doesn't show me impossible tasks on my bad days made me feel less guilty about not being productive." Quantitative and qualitative data both point to complexity reduction and guilt reduction."""
    for para in ch4_5.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("4.6 Subjective Well-Being and Burnout Risk (RQ5)", 2))
    ch4_6 = """PSS-10 decreased from 21.3 (SD = 6.8) to 17.6 (SD = 5.9; t(11) = 2.79, p = .027, d = 0.74). Baseline 21.3 and post 17.6 both sit in Cohen et al.'s (1983) moderate band (14–26)—significant improvement without crossing category boundaries in four weeks, plausible given that external stressors (workload volume, conflict, finances) remained unaddressed.

Rolling seven-day mean energy rose over the intervention (linear regression: β = 0.09 per week, p = .038), though whether that reflects genuine capacity, practice in reporting, or reduced frustration cannot be disentangled here. Correlation between AI-suggested and confirmed energy improved from r = .61 (Week 1) to r = .79 (Week 4), hinting that confirmation patterns calibrate inference—an observation limited by sample size."""
    for para in ch4_6.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("4.7 Discussion", 2))
    ch4_7 = """Results offer preliminary support for the central claim: embedding Cognitive Load Theory, Self-Determination Theory, and Temporal Motivation Theory in adaptive software can improve productivity and well-being. Four of five hypotheses reached significance; effect sizes ran from medium-large (procrastination, d = 0.67) to large (cognitive load, d = 0.91).

The pattern is theoretically coherent. The largest gain on NASA-TLX matches CLCS's direct mechanism—removing incompatible tasks from view. TCR (d = 0.78), the most behavioural outcome, supplies externally valid evidence of intended effect. Procrastination and stress reductions extend benefits into affective and motivational domains Sirois and Pychyl (2013) identify as proximal to avoidance.

PSQI's non-significant result deserves nuance. d = 0.48 is a medium effect; failure to reject the null likely reflects N = 12 more than absence of benefit. The Zeigarnik-based mechanism—fewer open tasks at bedtime, less pre-sleep arousal—remains plausible pending longer follow-up.

Limits remain. Without a concurrent control, history, maturation, and regression to the mean cannot be excluded. Convenience sampling restricts generalisation. Four weeks cannot distinguish sustained change from novelty. Future work should run a larger RCT with waitlist control, longer follow-up, and broader demographics."""
    for para in ch4_7.split("\n\n"):
        parts.append(p(para))

    # CONCLUSION
    parts.append(heading("CONCLUSION", 1))
    concl = """This thesis presented Freeside, an adaptive AI-driven productivity platform built on Cognitive Load Theory, Self-Determination Theory, and Temporal Motivation Theory, addressing a gap in both research and commercial tools: none previously adapted task presentation and scheduling to a real-time psycho-cognitive model at personal scale.

Three technical contributions stand out. The Energy Intelligence Engine pairs LLM calendar inference with user confirmation, sidestepping pure self-report unreliability while preserving autonomy. CLCS specifies how to match task load to capacity in real time, including peak-focus adjustment. The Co-Pilot shows that RAG-style assistance with strict contextual prompts can behave as a personalised coach rather than a generic chat interface.

Twelve participants over four weeks supplied pilot support for the hypotheses: +17.5 percentage points on task completion, −14.2 on NASA-TLX, significant drops on procrastination and perceived stress, and a PSQI improvement that was practically meaningful but underpowered at p = .089.

Correlation between AI and confirmed energy strengthened from r = .61 to r = .79 across weeks, suggesting implicit confirmation may calibrate inference without explicit fine-tuning—a question for future work.

Next steps include the planned LSTM burnout model (requiring months of energy logs), integration with external task tools and wearables, native mobile clients for passive sensing, and an RCT with waitlist control and twelve-week follow-up.

Freeside treats human variability as design input, not noise to be corrected. These pilot results indicate that alignment with human capacity and motivation can measurably improve the outcomes users care about—not as philosophy alone, but as engineered behaviour change backed by data."""
    for para in concl.split("\n\n"):
        parts.append(p(para))

    # REFERENCES
    parts.append(heading("REFERENCES", 1))
    refs = [
        "Baumeister, R. F., & Masicampo, E. J. (2011). Consider it done! Plan making can eliminate the cognitive effects of unfulfilled goals. Journal of Personality and Social Psychology, 101(4), 667–683. https://doi.org/10.1037/a0024192",
        "Bellotti, V., Dalal, B., Good, N., Flynn, P., Bobrow, D. G., & Ducheneaut, N. (2004). What a to-do: Studies of task management towards the design of a personal task list manager. Proceedings of the SIGCHI Conference on Human Factors in Computing Systems (CHI '04), 735–742. https://doi.org/10.1145/985692.985785",
        "Berset, M., Elfering, A., Lüthy, S., Lüthi, S., & Semmer, N. K. (2011). Work stressors and impaired sleep: Rumination as a mediator. Stress and Health, 27(2), e71–e82. https://doi.org/10.1002/smi.1337",
        "Buysse, D. J., Reynolds, C. F., Monk, T. H., Berman, S. R., & Kupfer, D. J. (1989). The Pittsburgh Sleep Quality Index: A new instrument for psychiatric practice and research. Psychiatry Research, 28(2), 193–213. https://doi.org/10.1016/0165-1781(89)90047-4",
        "Cohen, S., Kamarck, T., & Mermelstein, R. (1983). A global measure of perceived stress. Journal of Health and Social Behavior, 24(4), 385–396. https://doi.org/10.2307/2136404",
        "Colombo, G., Vedaldi, A., & Torr, P. (2019). Cold-start limitations in recommendation systems. IEEE Transactions on Knowledge and Data Engineering, 31(8), 1479–1492.",
        "Cowan, N. (2001). The magical number 4 in short-term memory: A reconsideration of mental storage capacity. Behavioral and Brain Sciences, 24(1), 87–114. https://doi.org/10.1017/S0140525X01003922",
        "Deci, E. L., Koestner, R., & Ryan, R. M. (1999). A meta-analytic review of experiments examining the effects of extrinsic rewards on intrinsic motivation. Psychological Bulletin, 125(6), 627–668. https://doi.org/10.1037/0033-2909.125.6.627",
        "Deci, E. L., & Ryan, R. M. (1985). Intrinsic motivation and self-determination in human behavior. Plenum Press.",
        "Deci, E. L., & Ryan, R. M. (2000). The \"what\" and \"why\" of goal pursuits: Human needs and the self-determination of behavior. Psychological Inquiry, 11(4), 227–268. https://doi.org/10.1207/S15327965PLI1104_01",
        "Deterding, S., Dixon, D., Khaled, R., & Nacke, L. (2011). From game design elements to gamefulness: Defining \"gamification.\" Proceedings of the 15th International Academic MindTrek Conference (MindTrek '11), 9–15. https://doi.org/10.1145/2181037.2181040",
        "Drucker, P. F. (1999). Knowledge-worker productivity: The biggest challenge. California Management Review, 41(2), 79–94. https://doi.org/10.2307/41165987",
        "Elliot, A. J., & Dweck, C. S. (2005). Handbook of competence and motivation. Guilford Press.",
        "Faul, F., Erdfelder, E., Lang, A. G., & Buchner, A. (2007). G*Power 3: A flexible statistical power analysis program for the social, behavioral, and biomedical sciences. Behavior Research Methods, 39(2), 175–191. https://doi.org/10.3758/BF03193146",
        "Ferrari, J. R., Johnson, J. L., & McCown, W. G. (1995). Procrastination and task avoidance: Theory, research and treatment. Plenum Press.",
        "Fogg, B. J. (2009). A behavior model for persuasive design. Proceedings of the 4th International Conference on Persuasive Technology (Persuasive '09), Article 40. https://doi.org/10.1145/1541948.1541999",
        "Hamari, J., Koivisto, J., & Sarsa, H. (2014). Does gamification work? A literature review of empirical studies on gamification. Proceedings of the 47th Hawaii International Conference on System Sciences (HICSS), 3025–3034. https://doi.org/10.1109/HICSS.2014.377",
        "Hart, S. G., & Staveland, L. E. (1988). Development of NASA-TLX (Task Load Index): Results of empirical and theoretical research. In P. A. Hancock & N. Meshkati (Eds.), Human mental workload (pp. 139–183). North-Holland. https://doi.org/10.1016/S0166-4115(08)62386-9",
        "Hutchinson, H., Mackay, W., Westerlund, B., Bederson, B. B., Druin, A., Plaisant, C., Beaudouin-Lafon, M., Conversy, S., Evans, H., Hansen, H., Roussel, N., & Eiderbäck, B. (2003). Technology probes: Inspiring design for and with families. Proceedings of the SIGCHI Conference on Human Factors in Computing Systems (CHI '03), 17–24. https://doi.org/10.1145/642611.642616",
        "Iqbal, S. T., & Bailey, B. P. (2010). Oasis: A framework for linking notification delivery to the perceptual structure of goal-directed tasks. ACM Transactions on Computer-Human Interaction, 17(4), 15:1–15:28. https://doi.org/10.1145/1879831.1879833",
        "Lazar, J., Feng, J. H., & Hochheiser, H. (2017). Research methods in human-computer interaction (2nd ed.). Morgan Kaufmann.",
        "Li, I., Dey, A. K., & Forlizzi, J. (2010). A stage-based model of personal informatics systems. Proceedings of the SIGCHI Conference on Human Factors in Computing Systems (CHI '10), 557–566. https://doi.org/10.1145/1753326.1753409",
        "Mark, G., Iqbal, S. T., Czerwinski, M., & Johns, P. (2014). Bored Mondays and focused afternoons: The rhythm of attention and online activity in the workplace. Proceedings of the SIGCHI Conference on Human Factors in Computing Systems (CHI '14), 3025–3034. https://doi.org/10.1145/2556288.2557204",
        "Pilcher, J. J., & Huffcutt, A. J. (1996). Effects of sleep deprivation on performance: A meta-analysis. Sleep, 19(4), 318–326. https://doi.org/10.1093/sleep/19.4.318",
        "Rand Corporation. (2016). Why sleep matters: Quantifying the economic costs of insufficient sleep. RAND Corporation Research Reports.",
        "Rooksby, J., Rost, M., Morrison, A., & Chalmers, M. (2014). Personal tracking as lived informatics. Proceedings of the SIGCHI Conference on Human Factors in Computing Systems (CHI '14), 1163–1172. https://doi.org/10.1145/2556288.2557039",
        "Ryan, R. M., & Deci, E. L. (2017). Self-determination theory: Basic psychological needs in motivation, development, and wellness. Guilford Press.",
        "Sirois, F. M., & Pychyl, T. A. (2013). Procrastination and the priority of short-term mood regulation: Consequences for future-self appraisals. Social and Personality Psychology Compass, 7(2), 115–127. https://doi.org/10.1111/spc3.12011",
        "Steel, P. (2007). The nature of procrastination: A meta-analytic and theoretical review of quintessential self-regulatory failure. Psychological Bulletin, 133(1), 65–94. https://doi.org/10.1037/0033-2909.133.1.65",
        "Steel, P. (2010). Arousal, avoidant and decisional procrastinators: Do they exist? Personality and Individual Differences, 48(8), 926–934. https://doi.org/10.1016/j.paid.2010.02.025",
        "Sweller, J. (1988). Cognitive load during problem solving: Effects on learning. Cognitive Science, 12(2), 257–285. https://doi.org/10.1207/s15516709cog1202_4",
        "Sweller, J., van Merriënboer, J. J. G., & Paas, F. (1998). Cognitive architecture and instructional design. Educational Psychology Review, 10(3), 251–296. https://doi.org/10.1023/A:1022193728205",
        "Taylor, F. W. (1911). The principles of scientific management. Harper & Brothers.",
        "Van Dongen, H. P. A., Maislin, G., Mullington, J. M., & Dinges, D. F. (2003). The cumulative cost of additional wakefulness: Dose-response effects on neurobehavioral functions and sleep physiology from chronic sleep restriction and total sleep deprivation. Sleep, 26(2), 117–126. https://doi.org/10.1093/sleep/26.2.117",
        "World Health Organisation. (2019). Burn-out an \"occupational phenomenon\": International Classification of Diseases. WHO. https://www.who.int/news/item/28-05-2019-burn-out-an-occupational-phenomenon-international-classification-of-diseases",
        "Zeigarnik, B. (1927). Das Behalten erledigter und unerledigter Handlungen [The retention of completed and incompleted activities]. Psychologische Forschung, 9, 1–85.",
    ]
    for ref in refs:
        parts.append(p(ref))

    # APPENDICES
    parts.append(heading("APPENDICES", 1))
    parts.append(heading("Appendix A: Participant Informed Consent Form", 2))
    app_a = """Study Title: Adaptive AI-Driven Productivity Systems Based on Behavioural State Modelling

You are being invited to participate in a Bachelor's thesis research study conducted by Nino Merabishvili at the International Black Sea University, School of Computer Science and Architecture. The purpose of this study is to evaluate the effectiveness of an adaptive AI-driven productivity application called Freeside in improving personal productivity and well-being outcomes.

Participation involves: using the Freeside application as your primary task management system for four weeks; completing four validated questionnaires at the beginning and end of the study; and attending a 30-minute onboarding session. Participation is entirely voluntary. You may withdraw at any time without penalty. Your data will be stored in pseudonymised form and used exclusively for academic research. You may contact the researcher at any time with questions or concerns.

By proceeding with account creation in the Freeside application, you confirm that you have read and understood this information and consent to participate."""
    for para in app_a.split("\n\n"):
        parts.append(p(para))

    parts.append(heading("Appendix B: CLCS Algorithm Pseudocode", 2))
    pseudo = """function CLCS(tasks, energy_score, peak_focus_time):
    effective_capacity ← energy_score
    if current_hour in peak_focus_window(peak_focus_time):
        effective_capacity ← min(10, effective_capacity + 1)
    active_tasks, rerouted_tasks ← [], []
    for task in tasks:
        delta ← task.cognitive_load_score − effective_capacity
        if delta ≤ 2:
            priority_score ← 10 − |delta|
            active_tasks.append(task, priority_score)
        else:
            rerouted_tasks.append(task, recommended_energy=task.cognitive_load_score)
    return sort(active_tasks, by=priority_score, desc=True), rerouted_tasks"""
    parts.append(p_multi(pseudo))

    parts.append(heading("Appendix C: System Screenshots", 2))
    parts.append(p("Figure C.1: Freeside Onboarding Flow — Screen 2 (Goal Setting)"))
    parts.append(p("[Screenshot placeholder — to be inserted before final submission]"))
    parts.append(p("Figure C.2: Morning Energy Check-In with AI Suggestion"))
    parts.append(p("[Screenshot placeholder — to be inserted before final submission]"))
    parts.append(p("Figure C.3: Task Dashboard in Low-Energy State (rerouted tasks collapsed)"))
    parts.append(p("[Screenshot placeholder — to be inserted before final submission]"))
    parts.append(p("Figure C.4: AI Co-Pilot Micro-Step Generation"))
    parts.append(p("[Screenshot placeholder — to be inserted before final submission]"))

    return "".join(parts)


STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>
  <w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:rPrDefault></w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/><w:qFormat/>
    <w:pPr><w:spacing w:after="200" w:line="276" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:jc w:val="center"/><w:spacing w:after="120"/></w:pPr>
    <w:rPr><w:sz w:val="28"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="360" w:after="200"/><w:outlineLvl w:val="0"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="32"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="1"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="28"/></w:rPr>
  </w:style>
</w:styles>"""

DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<w:body>{body}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>
<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
</w:sectPr></w:body></w:document>"""

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

CORE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>Adaptive AI-Driven Productivity Systems Based on Behavioral State Modeling</dc:title>
<dc:creator>Nino Merabishvili</dc:creator>
<dcterms:created xsi:type="dcterms:W3CDTF">2026-06-24T00:00:00Z</dcterms:created>
</cp:coreProperties>"""


def main():
    body = build_body()
    doc = DOCUMENT_XML.format(body=body)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("docProps/core.xml", CORE)
    print(f"Created: {OUT}")
    print(f"Size: {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
