**Role:** Act as a senior backend engineer.

**Project:** I am building "Freeside," a personal informatics and productivity SaaS for my Bachelor's thesis. Stack: Next.js 14 (frontend), FastAPI (backend), Supabase (hosted PostgreSQL accessed via the supabase-py client — NOT SQLAlchemy ORM).

**Task:** Write complete, production-ready Python code for two files: services/ai.py and routes/copilot.py. These implement two AI features using the **current Google GenAI SDK** (pip install google-genai).

---

**Database access pattern (Supabase Python client — use this everywhere):**

python  
from supabase import create\_client  
supabase \= create\_client(os.getenv("SUPABASE\_URL"), os.getenv("SUPABASE\_SERVICE\_KEY"))  
\# Example query:  
result \= supabase.table("profiles").select("\*").eq("id", user\_id).single().execute()  
profile \= result.data

**Relevant table columns:**

* profiles: id, name, role, productive\_day\_description, peak\_focus\_time, daily\_work\_hours, work\_style, google\_calendar\_connected, xp\_total  
* goals: id, user\_id, title, category, timeframe, is\_active  
* tasks: id, user\_id, title, cognitive\_load\_score (int 1–10), status ('pending'/'completed')  
* energy\_logs: id, user\_id, confirmed\_score (int 1–10), confirmed\_level ('high'/'balanced'/'low'), ai\_suggested\_score, logged\_at

---

**General AI Setup (services/ai.py):**

* Use the new Google GenAI SDK: from google import genai and from google.genai import types  
* Initialize a single global client: client \= genai.Client(api\_key=os.getenv("GEMINI\_API\_KEY"))  
* Use gemini-2.5-flash for Feature 1 (fast, cheap inference)  
* Use gemini-2.5-pro for Feature 2 (complex reasoning, longer context)  
* Wrap all API calls in try/except. On failure, log the error and raise a ValueError with a descriptive message.

---

**Feature 1 — Energy Inference (services/ai.py):**

Write infer\_energy\_from\_calendar(calendar\_summary: dict, user\_profile: dict) \-\> dict.

Inputs from calendar\_summary: event\_count (int), total\_meeting\_minutes (int), back\_to\_back\_count (int), event\_list (str).  
 Inputs from user\_profile: peak\_focus\_time, work\_style, daily\_work\_hours.

Logic: More meetings and back-to-back blocks \= lower energy for deep work.

**Required output — strict JSON, no markdown fences:**

json  
{  
  "suggested\_score": 5,  
  "suggested\_level": "balanced",  
  "reasoning": "Four meetings including two back-to-back blocks leave limited focus time."  
}

Use response\_mime\_type="application/json" in GenerateContentConfig for native structured output. Add a json.loads() fallback with regex stripping of markdown fences if parsing fails. If both fail, return a safe default: {"suggested\_score": 5, "suggested\_level": "balanced", "reasoning": "Unable to analyse calendar — defaulting to balanced."}.

---

**Feature 2 — AI Co-Pilot (services/ai.py and routes/copilot.py):**

Write build\_copilot\_context(user\_id: str) \-\> str that queries Supabase for: user profile, active goals (is\_active=True), today's most recent energy log, top 5 pending tasks ordered by cognitive\_load\_score descending.

The system prompt it returns **must** include:

* The user's productive\_day\_description verbatim  
* Their current confirmed energy level and score  
* Their active goals (title \+ category)  
* Their pending tasks with cognitive load scores

**Hard behavioural rules to embed in the system prompt:**

1. You are a calm, empathetic productivity coach. Never be generic — always reference the user's actual tasks and goals.  
2. If energy level is "low": never suggest tasks with cognitive load \> 4\. Suggest rest, light admin, or a 5-minute task instead.  
3. If asked to break down a task: return exactly 3–5 micro-steps, each under 15 words, numbered.  
4. All other responses: under 150 words. No filler phrases ("Certainly\!", "Great question\!").

**In routes/copilot.py**, write @router.post("/copilot/chat") that:

* Accepts a JSON body: {"user\_id": str, "message": str, "message\_type": str} (message\_type: "user\_initiated" | "micro\_step" | "proactive")  
* Reads the Authorization: Bearer \<jwt\> header and extracts user\_id from it (use jose library to decode — just decode without verification for now, add a TODO comment for production verification)  
* Calls build\_copilot\_context(user\_id), then calls Gemini 2.5 Pro with that as the system instruction and the user message as the user turn  
* Returns {"reply": response\_text}  
* On any AI error: return HTTP 503 with {"detail": "AI service temporarily unavailable"}

---

Write complete files. Include all imports. Add docstrings to every function. Do not include placeholder comments like "\# implement this" — write the full implementation.

