<script lang="ts">
	import { CalendarCheck, CircleCheck, Inbox as InboxIcon, MailCheck, Send } from '@lucide/svelte';
	import { agent } from '#lib/agents.ts';
	import { api, type CaseRow, type Inbox } from '#lib/api.ts';
	import { ago, initials } from '#lib/format.ts';
	import { live } from '#lib/live.svelte.ts';
	import Badge from '../Badge.svelte';

	let {
		inbox,
		selected,
		selectedCase,
		filter = $bindable('all'),
		onselect
	}: {
		inbox: Inbox;
		selected: string | null;
		selectedCase: CaseRow | null;
		filter: string;
		onselect: (id: string) => void;
	} = $props();

	const groups = [
		{ key: 'all', label: 'All open', icon: InboxIcon },
		{ key: 'applied', label: 'Applied', icon: Send },
		{ key: 'acknowledged', label: 'Acknowledged', icon: MailCheck },
		{ key: 'interview', label: 'Interview', icon: CalendarCheck },
		{ key: 'debrief', label: 'Debrief', icon: CircleCheck }
	];
	const STAGES: Record<string, string[]> = {
		applied: ['applied'],
		acknowledged: ['acknowledged', 'in_conversation'],
		interview: ['interview'],
		debrief: ['debriefed']
	};
	const shown = $derived(inbox.cases.filter((c) => filter === 'all' || STAGES[filter]?.includes(c.stage)));
	const pinned = $derived(selectedCase && !inbox.cases.some((c) => c.key === selectedCase.key) ? selectedCase : null);
	let target = $state<Record<string, string>>({});
	let note = $state('');

	async function file(key: string) {
		const caseId = target[key] ?? inbox.cases[0]?.key;
		if (!caseId) return;
		note = '';
		await api.assign(key, caseId).catch((e: Error) => (note = e.message));
	}
</script>

{#snippet caseCard(c: CaseRow)}
	{@const busy = live.working[c.key]}
	<button class="case" class:selected={selected === c.key} onclick={() => onselect(c.key)}>
		<div class="row between">
			<span class="row"><span class="logo">{initials(c.company)}</span><b>{c.company}</b></span>
			{#if busy}
				<span class="pulse small working">{agent(busy).title}'s on it</span>
			{:else if c.error}
				<Badge value="error" />
			{:else}
				<Badge value={c.stage} />
			{/if}
		</div>
		<p class="muted title">{c.title}</p>
		<p class="small faint">{ago(c.updated_at)}</p>
	</button>
{/snippet}

<section class="col">
	<div class="row between head"><h1>Inbox</h1></div>
	<ul class="filters">
		{#each groups as g (g.key)}
			<li>
				<button class:on={filter === g.key} onclick={() => (filter = g.key)}>
					<g.icon size={15} />
					<span>{g.label}</span>
					<span class="num">{g.key === 'all' ? inbox.cases.length : inbox.counts[g.key]}</span>
				</button>
			</li>
		{/each}
	</ul>

	{#if inbox.unmatched.length}
		<p class="section-label">Needs you</p>
		{#each inbox.unmatched as item (item.key)}
			<div class="card unmatched">
				<b class="small">{item.event.message?.subject ?? `Notes: ${item.event.notes?.title}`}</b>
				<p class="small muted">{item.event.message?.from ?? item.event.notes?.start_time}</p>
				<div class="row">
					<select bind:value={target[item.key]} class="small">
						{#each inbox.cases as c (c.key)}<option value={c.key}>{c.company} · {c.title}</option>{/each}
					</select>
					<button class="btn small" onclick={() => file(item.key)}>File</button>
					<button class="btn small" onclick={() => api.dismiss(item.key)}>Ignore</button>
				</div>
			</div>
		{/each}
		{#if note}<p class="small error-text">{note}</p>{/if}
	{/if}

	{#if pinned}
		<p class="section-label">Viewing</p>
		<div class="pinned">{@render caseCard(pinned)}</div>
	{/if}

	<p class="section-label">Cases</p>
	<ul class="cases">
		{#each shown as c (c.key)}
			<li>{@render caseCard(c)}</li>
		{:else}
			<li class="empty">{pinned ? 'No other open cases.' : 'No open cases yet. Send Scout from '} {#if !pinned}<a href="/cases"><u>Cases</u></a>.{/if}</li>
		{/each}
	</ul>
</section>

<style>
	.col {
		padding: 16px;
		border-right: 1px solid var(--line);
		overflow: auto;
	}
	.head {
		margin-bottom: 10px;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.filters {
		padding-bottom: 6px;
		border-bottom: 1px solid var(--line);
	}
	.filters button {
		display: flex;
		align-items: center;
		gap: 10px;
		width: 100%;
		padding: 6px 8px;
		border: none;
		border-radius: 8px;
		background: none;
		cursor: pointer;
		color: #374151;
		text-align: left;
	}
	.filters button:hover,
	.filters button.on {
		background: var(--soft);
	}
	.filters span:nth-child(2) {
		flex: 1;
	}
	.num {
		min-width: 20px;
		padding: 0 6px;
		border: 1px solid var(--line);
		border-radius: 6px;
		font-size: 11px;
		text-align: center;
		color: var(--muted);
	}
	.unmatched {
		padding: 10px;
		margin-bottom: 8px;
		display: flex;
		flex-direction: column;
		gap: 6px;
		border-color: #f3d9b1;
		background: #fffaf2;
	}
	.unmatched select {
		flex: 1;
	}
	.cases {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.pinned {
		margin-bottom: 4px;
	}
	.case {
		width: 100%;
		padding: 10px 12px;
		border: 1px solid var(--line);
		border-radius: 10px;
		background: var(--panel);
		text-align: left;
		cursor: pointer;
	}
	.case:hover {
		background: var(--soft);
	}
	.case.selected {
		background: #f1f4fa;
		border-color: #d5deef;
	}
	.title {
		margin: 4px 0 2px;
	}
	.logo {
		display: grid;
		place-items: center;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: var(--gray-bg);
		font-size: 10px;
		font-weight: 600;
	}
	.working {
		color: var(--blue);
	}
</style>
