<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import { api, type CaseDetail, type Inbox } from '#lib/api.ts';
	import CaseList from '#lib/components/inbox/CaseList.svelte';
	import Details from '#lib/components/inbox/Details.svelte';
	import Thread from '#lib/components/inbox/Thread.svelte';
	import { live } from '#lib/live.svelte.ts';

	let inbox = $state<Inbox>({ cases: [], counts: {}, unmatched: [] });
	let detail = $state<CaseDetail | null>(null);
	let filter = $state('all');
	const selected = $derived(page.url.searchParams.get('case') ?? inbox.cases[0]?.key ?? null);

	$effect(() => {
		void live.tick;
		untrack(async () => (inbox = await api.inbox()));
	});

	$effect(() => {
		void live.tick;
		const id = selected;
		if (!id) return;
		untrack(async () => {
			const next = await api.case(id).catch(() => null);
			if (id === selected) detail = next;
		});
	});

	function select(id: string) {
		goto(`/inbox?case=${id}`, { reset: false });
	}
</script>

<div class="inbox">
	<CaseList {inbox} {selected} bind:filter onselect={select} />
	{#if detail && detail.case.case_id === selected}
		{#key detail.case.case_id}
			<Thread {detail} onchange={(next) => (detail = next)} />
			<Details {detail} onchange={(next) => (detail = next)} />
		{/key}
	{:else}
		<div class="placeholder empty">{selected ? 'Loading case…' : 'Select a case to see its thread.'}</div>
	{/if}
</div>

<style>
	.inbox {
		display: grid;
		grid-template-columns: 290px minmax(0, 1fr) 320px;
		grid-template-rows: minmax(0, 1fr);
		height: 100%;
	}
	.inbox > :global(*) {
		min-height: 0;
	}
	.placeholder {
		grid-column: span 2;
		align-self: center;
	}
	@media (max-width: 1180px) {
		.inbox {
			grid-template-columns: 250px minmax(0, 1fr);
			grid-template-rows: calc(100vh - 52px) auto;
			overflow: auto;
			height: auto;
		}
		.inbox :global(aside.col) {
			grid-column: 2;
			border-top: 1px solid var(--line);
		}
	}
</style>
