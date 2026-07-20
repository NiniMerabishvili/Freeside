# Screenshot capture guide

Drop PNG screenshots into this folder using the filenames below.
They are referenced by the **Demo** section in the root `README.md`.

| Filename | What to capture |
|----------|-----------------|
| `01-dashboard-overview.png` | Full dashboard: energy panel, task list, Co-Pilot rail |
| `02-energy-checkin.png` | Energy check-in / AI suggestion + confirm slider |
| `03-clcs-routing.png` | Active vs deferred tasks after energy is set |
| `04-copilot-chat.png` | Co-Pilot reply with task suggestions (ideally Georgian or bilingual) |
| `05-project-memory.png` | Project Memory panel with **Retrieved context** + similarity |
| `06-goals-milestones.png` | Goals panel with milestones and progress |
| `07-brain-dump.png` | Brain dump modal with parsed tasks ready to confirm |
| `08-integrations.png` | Settings: Google Calendar + ClickUp connected |

## Tips

- Use a real demo account with energy set and a few ClickUp/calendar tasks synced.
- Prefer light theme, desktop width (~1440px).
- Crop browser chrome if possible; keep the Freeside UI as the focus.
- Export as PNG, not JPEG, for sharp text.

## Quick capture (local)

1. Start backend (`uvicorn main:app --reload --port 8000`) and frontend (`npm run dev`).
2. Sign in → complete energy check-in → open each feature.
3. Save screenshots with the filenames above into this folder.
4. Push — GitHub will render them in the README Demo section.
