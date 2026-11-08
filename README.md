# findmeajob

A workflow of agents that finds jobs, rewrites your CV for the posting, applies, and tracks each case through the debrief.

## Flow

Start with a CV. Scout opens a case for each listing. Judge keeps or skips it, Tailor rewrites the CV, and Clerk fills the form. The case then stays in the inbox for mail, interview prep, the debrief, and replies you approve.

### Profile

Drop in a CV. The form fills from it, and every later agent reads that profile.

![Profile, with a CV uploaded and the form filled from it](docs/screenshots/profile.png)

### Scout

Pick a region, a career, and an arrangement, then sweep. Each new listing becomes a case.

![Cases, with Scout sweeping and the pile of listings](docs/screenshots/cases.png)

### The agents

Judge writes the fit note. Tailor cooks the CV. Clerk submits. Courier reads the mail, Brief prepares the interview, Critic writes the debrief, Chaser drafts the reply, and Archivist files what to remember.

![The nine agents and what each one does](docs/screenshots/agents.png)

### One case

Scout opens it, Judge says apply or skip, and Tailor lists what changed on the CV. When a recruiter writes back, the thread continues here.

![A Payzeep case from Scout through the tailored CV](docs/screenshots/inbox.png)

### Integrations

Gmail and Read AI feed the inbox. Chrome is how Clerk submits. Grok is the model the agents think with.

![Gmail, Read AI, Chrome, and Grok](docs/screenshots/integrations.png)

## Run

```bash
docker compose up -d
cp .env.example .env
cd frontend && npm install && npm run build && cd ..
uv run findmeajob serve
```

Open http://127.0.0.1:8000. Put `XAI_API_KEY` in `.env` before the agents can think. `.env` stays off git.
