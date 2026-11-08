import type { Case, Mail } from './api.ts';
import { count } from './format.ts';

export type AgentItem = {
	kind: 'agent';
	at: number;
	agent: string;
	title: string;
	body?: string;
	bullets?: string[];
	action?: 'cv' | 'prep';
	tone?: 'red';
};
export type MailItem = { kind: 'mail'; at: number; mail: Mail };
export type SentItem = { kind: 'sent'; at: number; to: string; subject: string; body: string };
export type Item = AgentItem | MailItem | SentItem;

const INVITES = ['interview_invite', 'scheduling'];

export function timeline(c: Case): Item[] {
	const applied = c.application?.at ? Date.parse(c.application.at) : Date.now();
	const items: Item[] = [];
	const where = [c.filters.skill, c.filters.region, c.filters.arrangement].filter(Boolean).join(' · ');
	items.push({
		kind: 'agent',
		at: applied - 3000,
		agent: 'scout',
		title: 'Opened this case',
		body: `Found ${c.posting.title} at ${c.posting.company}${c.posting.source ? ` on ${c.posting.source}` : ''}${where ? ` for ${where}` : ''}.`
	});
	if (c.fit) {
		items.push({
			kind: 'agent',
			at: applied - 2000,
			agent: 'judge',
			title: `Fit note: ${c.fit.recommendation}`,
			body: c.fit.reason,
			bullets: [
				...(c.fit.must_haves_missing ?? []).map((m) => `Missing: ${m}`),
				...(c.fit.red_flags ?? []).map((f) => `Red flag: ${f}`)
			]
		});
	}
	if (c.cv) {
		items.push({
			kind: 'agent',
			at: applied - 1000,
			agent: 'tailor',
			title: 'Tailored your CV',
			body: `${count(c.cv.changes.length, 'change')} for ${count(c.cv.requirements.length, 'requirement')}.`,
			bullets: c.cv.gaps.map((g) => `Gap: ${g}`),
			action: 'cv'
		});
	}
	if (c.application) {
		const a = c.application;
		items.push(
			a.blocked
				? { kind: 'agent', at: applied, agent: 'clerk', title: "couldn't apply", body: a.blocked, tone: 'red' }
				: {
						kind: 'agent',
						at: applied,
						agent: 'clerk',
						title: 'Applied',
						body: `Answered ${a.answers?.length ?? 0} questions and uploaded the CV.${a.salary ? ` Asked ${a.salary.currency} ${a.salary.figure.toLocaleString()} per ${a.salary.period}.` : ''}`
					}
		);
	}
	for (const mail of c.mail) items.push({ kind: 'mail', at: mail.internal_ms, mail });
	const invite = c.mail.find((m) => INVITES.includes(m.category));
	if (c.brief && invite) {
		items.push({
			kind: 'agent',
			at: invite.internal_ms + 1,
			agent: 'brief',
			title: 'Prepared your interview brief',
			body: `${c.brief.questions.length} questions answered, starting with "Tell me about yourself".`,
			action: 'prep'
		});
	}
	for (const d of c.debriefs) {
		items.push({ kind: 'agent', at: Date.parse(d.at), agent: 'critic', title: `Debrief from ${d.source}`, bullets: d.could_be_better });
	}
	for (const s of c.sent) items.push({ kind: 'sent', at: Date.parse(s.at), to: s.to, subject: s.subject, body: s.body });
	return items.sort((x, y) => x.at - y.at);
}

export function day(at: number): string {
	return new Date(at).toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}
