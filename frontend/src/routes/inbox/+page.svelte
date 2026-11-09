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
	let detailsOpen = $state(false);
	const selected = $derived(page.url.searchParams.get('case') ?? inbox.cases[0]?.key ?? null);
	const selectedCase = $derived(detail && selected ? { ...detail.index, key: selected } : null);

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
		detailsOpen = false;
		goto(`/inbox?case=${id}`, { reset: false });
	}
</script>

<div class="inbox" class:details-open={detailsOpen}>
	<CaseList {inbox} {selected} {selectedCase} bind:filter onselect={select} />
	{#if detail && detail.case.case_id === selected}
		{#key detail.case.case_id}
			<Thread {detail} onchange={(next) => (detail = next)} ondetails={() => (detailsOpen = true)} />
			{#if detailsOpen}
				<Details {detail} onchange={(next) => (detail = next)} onclose={() => (detailsOpen = false)} />
			{/if}
		{/key}
	{:else}
		<div class="placeholder empty">{selected ? 'Loading case…' : 'Select a case to see its thread.'}</div>
	{/if}
</div>

<style>
	.inbox {
		display: grid;
		grid-template-columns: 280px minmax(0, 1fr) 0px;
		grid-template-rows: minmax(0, 1fr);
		height: 100%;
		position: relative;
		overflow: hidden;
		transition: grid-template-columns 220ms ease;
	}
	@media (prefers-reduced-motion: reduce) {
		.inbox {
			transition: none;
		}
	}
	.inbox.details-open {
		grid-template-columns: 280px minmax(0, 1fr) 340px;
	}
	.inbox > :global(*) {
		min-height: 0;
	}
	.placeholder {
		grid-column: span 2;
		align-self: center;
	}
	@media (max-width: 1180px) {
		.inbox,
		.inbox.details-open {
			grid-template-columns: 250px minmax(0, 1fr);
		}
		.inbox :global(aside.col) {
			position: absolute;
			z-index: 4;
			inset: 0 0 0 auto;
			width: min(370px, 100%);
			background: var(--panel);
			border-left: 1px solid var(--line);
			box-shadow: -12px 0 32px rgb(16 24 40 / 12%);
		}
	}
</style>
