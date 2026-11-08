import {
	Archive,
	BookOpen,
	Gavel,
	Mail,
	MessageSquareReply,
	Microscope,
	PenLine,
	Radar,
	Scissors
} from '@lucide/svelte';
import type { Component } from 'svelte';

export type AgentMeta = { title: string; icon: Component; color: string; doing: string };

export const AGENTS: Record<string, AgentMeta> = {
	scout: { title: 'Scout', icon: Radar, color: '#2563eb', doing: "is out hunting" },
	judge: { title: 'Judge', icon: Gavel, color: '#7c3aed', doing: 'is clocking the fit' },
	tailor: { title: 'Tailor', icon: Scissors, color: '#db2777', doing: 'is cooking the CV' },
	clerk: { title: 'Clerk', icon: PenLine, color: '#ea580c', doing: 'is in the form' },
	courier: { title: 'Courier', icon: Mail, color: '#0891b2', doing: 'is reading the mail' },
	brief: { title: 'Brief', icon: BookOpen, color: '#16a34a', doing: 'is studying the interview' },
	critic: { title: 'Critic', icon: Microscope, color: '#ca8a04', doing: 'is writing the debrief' },
	chaser: { title: 'Chaser', icon: MessageSquareReply, color: '#4f46e5', doing: 'is drafting the reply' },
	archivist: { title: 'Archivist', icon: Archive, color: '#57534e', doing: 'is filing the lesson' }
};

export function agent(name: string | undefined): AgentMeta {
	return AGENTS[name ?? ''] ?? { title: name ?? 'Agent', icon: Archive, color: '#57534e', doing: 'is working' };
}
