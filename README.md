# findmeajob

A workflow of agents that finds jobs, rewrites your CV for the posting, applies, and tracks each case through the debrief.

## The dashboard

Cases is the board. Pick a region, a career, and an arrangement, then sweep. Scout lists every job with Judge's verdict, the place, and how old the posting is. Worth applying and Needs you narrow the pile. Paste a link when you already have one.

![The Cases board, with Judge's verdict on each job](docs/screenshots/cases.png)

Open a case and the inbox keeps the thread. Scout found it, Judge wrote the fit note, Tailor rewrote the CV, and Clerk submitted.

![A Busha case that Clerk already applied to](docs/screenshots/inbox.png)

### Agents

Judge writes the fit note. Tailor cooks the CV. Clerk submits. Courier reads the mail, Brief prepares the interview, Critic writes the debrief, Chaser drafts the reply, and Archivist files what to remember.

![The nine agents and what each one does](docs/screenshots/agents.png)

### Profile

Drop in a CV. The form fills from it, and every later agent reads that profile.

![Profile, with a CV uploaded and the form filled from it](docs/screenshots/profile.png)

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

## License

[MIT](LICENSE)
