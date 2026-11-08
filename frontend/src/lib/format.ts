export function ago(stamp: string | number | undefined): string {
	if (!stamp) return '';
	const seconds = Math.floor((Date.now() - new Date(stamp).getTime()) / 1000);
	for (const [unit, size] of [['d', 86400], ['h', 3600], ['m', 60]] as const) {
		if (seconds >= size) return `${Math.floor(seconds / size)}${unit} ago`;
	}
	return 'just now';
}

export function label(value: string | undefined): string {
	if (!value) return '';
	const text = value.replaceAll('_', ' ');
	return text[0].toUpperCase() + text.slice(1);
}

export function initials(name: string): string {
	const words = name.replace(/<.*>/, '').trim().split(/\s+/).filter(Boolean);
	return (words.length > 1 ? words[0][0] + words[1][0] : (words[0] ?? '?').slice(0, 2)).toUpperCase();
}

export function count(n: number, word: string): string {
	return `${n} ${word}${n === 1 ? '' : 's'}`;
}

const TONES: Record<string, string> = {
	applied: 'green',
	acknowledged: 'green',
	acknowledgment: 'green',
	sent: 'green',
	opening: 'blue',
	interview: 'blue',
	interview_invite: 'blue',
	scheduling: 'blue',
	offer: 'violet',
	in_conversation: 'amber',
	recruiter_reply: 'amber',
	debriefed: 'amber',
	feedback: 'amber',
	blocked: 'red',
	rejected: 'red',
	rejection: 'red',
	error: 'red'
};

export function tone(value: string | undefined): string {
	return TONES[value ?? ''] ?? 'gray';
}
