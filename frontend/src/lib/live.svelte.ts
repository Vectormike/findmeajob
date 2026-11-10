export type LiveEvent = {
	kind: 'working' | 'case' | 'discovered' | 'status' | 'unmatched' | 'profile' | 'captcha';
	case_id?: string;
	agent?: string;
	stage?: string;
	name?: string;
	detail?: string;
	error?: string;
	waiting?: boolean;
};

const KINDS: LiveEvent['kind'][] = ['working', 'case', 'discovered', 'status', 'unmatched', 'profile', 'captcha'];
const SETTLE_MS = 150;

class Live {
	connected = $state(false);
	working = $state<Record<string, string>>({});
	discovered = $state<string[]>([]);
	captcha = $state<Record<string, boolean>>({});
	tick = $state(0);
	#timer: ReturnType<typeof setTimeout> | undefined;

	start() {
		const source = new EventSource('/api/events');
		source.onopen = () => (this.connected = true);
		source.onerror = () => (this.connected = false);
		for (const kind of KINDS) {
			source.addEventListener(kind, (message) => this.#take(JSON.parse(message.data)));
		}
		return () => source.close();
	}

	#take(event: LiveEvent) {
		const caseId = event.case_id ?? '';
		if (event.kind === 'working' && event.agent) this.working[caseId] = event.agent;
		if (event.kind === 'discovered' && caseId) this.discovered = [...this.discovered, caseId];
		if (event.kind === 'case') delete this.working[caseId];
		if (event.kind === 'captcha') this.captcha[caseId] = !!event.waiting;
		if (event.kind === 'status' && event.name === 'scout') delete this.working[''];
		clearTimeout(this.#timer);
		this.#timer = setTimeout(() => this.tick++, SETTLE_MS);
	}

	beginScout() {
		this.discovered = [];
	}
}

export const live = new Live();
