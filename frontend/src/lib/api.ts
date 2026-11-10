export type Status = {
	key: string;
	ok: boolean;
	detail: string;
	at: string;
	run_id?: string;
	case_ids?: string[];
};

export type CaseRow = {
	key: string;
	company: string;
	title: string;
	url: string;
	region: string;
	skill: string;
	arrangement: string;
	location?: string;
	salary?: string;
	posted_at?: string;
	remote?: boolean;
	source?: string;
	fit?: string;
	stage: string;
	last_agent: string;
	updated_at: string;
	error?: string;
	captcha?: boolean;
};

export type LiveAction =
	| { kind: 'click'; x: number; y: number }
	| { kind: 'type'; text: string }
	| { kind: 'key'; key: string }
	| { kind: 'scroll'; dy: number };

export type Mail = {
	id: string;
	thread_id: string;
	from: string;
	from_email: string;
	subject: string;
	date: string;
	internal_ms: number;
	body: string;
	category: string;
	summary: string;
	needs_answer: boolean;
	interview_time: string;
};

export type Claim = { text: string; source_url: string };

export type FitArea = { verdict: string; covered: string[]; missing: string[] };

export type Case = {
	case_id: string;
	stage: string;
	last_agent?: string;
	filters: { region?: string; skill?: string; arrangement?: string };
	posting: { title: string; company: string; url: string; location?: string; source?: string; salary?: string };
	fit?: {
		recommendation: string;
		reason: string;
		must_haves_covered?: string[];
		must_haves_missing?: string[];
		technical?: FitArea;
		behavioural?: FitArea;
		seniority?: string;
		location_and_pay?: string;
		red_flags?: string[];
	};
	cv?: {
		requirements: string[];
		changes: { change: string; requirement: string; source: string }[];
		gaps: string[];
		has_pdf: boolean;
	};
	application?: {
		url: string;
		at: string;
		blocked?: string;
		missing?: (MissingFact | string)[];
		answers?: { field_id: string; value: string; source: string }[];
		fields?: { id: string; label: string }[];
		steps?: {
			number: number;
			fields: { id: string; label: string }[];
			answers: { field_id: string; value: string; source: string }[];
			outcome: string;
			errors: string[];
		}[];
		salary?: { low: number; high: number; figure: number; currency: string; period: string; sources: string[] };
		confirmation?: { url: string; confirmed: string };
	};
	mail: Mail[];
	brief?: {
		research: Record<string, Claim[]>;
		questions: { question: string; answer: string; why_asked: string }[];
		gaps_to_prepare: string[];
		questions_to_ask_them: string[];
		interview_time: string;
	};
	debriefs: {
		source: string;
		at: string;
		landed: string[];
		thin: string[];
		unused_answers: string[];
		could_be_better: string[];
		lessons: string[];
	}[];
	draft?: { kind: string; to: string; subject: string; body: string; error?: string } | null;
	sent: { to: string; subject: string; body: string; at: string }[];
};

export type CaseDetail = { case: Case; index: CaseRow; waiting: boolean; retryable: string[]; captcha: boolean };

export type Unmatched = {
	key: string;
	at: string;
	event: { type: 'mail' | 'notes'; message?: Mail; notes?: { title: string; start_time: string } };
};

export type Inbox = { cases: CaseRow[]; counts: Record<string, number>; unmatched: Unmatched[] };

export type Story = { title: string; text: string };

export type FormFact = { question: string; answer: string; job?: string };

export type MissingFact = { question: string; options: string[] };

export type Profile = {
	name: string;
	email: string;
	phone: string;
	location: string;
	links: string;
	titles: string;
	skills: string[];
	work_authorization: string;
	skip_companies: string[];
	stories: Story[];
	form_facts: FormFact[];
	master_cv: string;
	master_cv_file: string;
};

export type MemoryEntry = { key: string; kind: 'lesson' | 'story'; text: string; status: string; case_id: string };

export type AgentCard = { name: string; job: string; count: number; last: CaseRow | null };

export type Integration = {
	key: string;
	name: string;
	job: string;
	agents: string[];
	configured: boolean;
	active: boolean;
	status: Status | null;
};

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
	const json = body !== undefined && !(body instanceof Blob);
	const response = await fetch(`/api${path}`, {
		method,
		headers: json ? { 'Content-Type': 'application/json' } : undefined,
		body: json ? JSON.stringify(body) : (body as Blob | undefined)
	});
	if (!response.ok) {
		const detail = await response.json().catch(() => ({}));
		throw new Error(typeof detail.detail === 'string' ? detail.detail : `something broke (${response.status}). try again.`);
	}
	return response.json();
}

export const api = {
	inbox: () => request<Inbox>('GET', '/inbox'),
	cases: () =>
		request<{
			cases: CaseRow[];
			scout: Status | null;
			arrangements: string[];
			regions: { name: string; countries: string[] }[];
		}>('GET', '/cases'),
	case: (id: string) => request<CaseDetail>('GET', `/cases/${id}`),
	scout: (region: string, skill: string, arrangement: string) =>
		request('POST', '/scout', { region, skill, arrangement, title_only: true }),
	addPosting: (url: string) => request('POST', '/cases', { url }),
	approve: (id: string, body: string) => request<CaseDetail>('POST', `/cases/${id}/approve`, { body }),
	discard: (id: string) => request<CaseDetail>('POST', `/cases/${id}/discard`),
	close: (id: string) => request<CaseDetail>('POST', `/cases/${id}/close`),
	retry: (id: string) => request('POST', `/cases/${id}/retry`),
	retryAgent: (id: string, agent: string) => request('POST', `/cases/${id}/retry/${agent}`),
	addFacts: (id: string, facts: FormFact[]) => request('POST', `/cases/${id}/facts`, { facts }),
	liveAct: (id: string, action: LiveAction) => request('POST', `/cases/${id}/live`, action),
	assign: (key: string, caseId: string) => request('POST', `/unmatched/${key}/assign`, { case_id: caseId }),
	dismiss: (key: string) => request('DELETE', `/unmatched/${key}`),
	agents: () => request<AgentCard[]>('GET', '/agents'),
	profile: () => request<{ profile: Profile; memory: MemoryEntry[] }>('GET', '/profile'),
	saveProfile: (profile: Profile) => request<{ profile: Profile; memory: MemoryEntry[] }>('PUT', '/profile', profile),
	uploadCv: (file: File) =>
		request<{ profile: Profile; memory: MemoryEntry[] }>('PUT', `/profile/cv?name=${encodeURIComponent(file.name)}`, file),
	decide: (key: string, decision: 'accepted' | 'dismissed') =>
		request<{ profile: Profile; memory: MemoryEntry[] }>('POST', `/profile/memory/${key}/${decision}`),
	integrations: () => request<Integration[]>('GET', '/integrations'),
	testIntegration: (key: string) => request<{ status: string; detail: string }>('POST', `/integrations/${key}/test`),
	connectGmail: () => request<{ status: string; detail: string }>('POST', '/integrations/gmail/connect')
};
