<script lang="ts">
	import { untrack } from 'svelte';
	import { agent } from '#lib/agents.ts';
	import { api, type AgentCard } from '#lib/api.ts';
	import AgentAvatar from '#lib/components/AgentAvatar.svelte';
	import FilterColumn from '#lib/components/FilterColumn.svelte';
	import { ago } from '#lib/format.ts';
	import { live } from '#lib/live.svelte.ts';

	let cards = $state<AgentCard[]>([]);
	let group = $state('all');

	$effect(() => {
		void live.tick;
		untrack(async () => (cards = await api.agents()));
	});

	const working = $derived(new Map(Object.entries(live.working).map(([caseId, name]) => [name, caseId])));
	const counts = $derived([
		{ key: 'all', label: 'All agents', count: cards.length },
		{ key: 'working', label: 'Working now', count: cards.filter((c) => working.has(c.name)).length },
		{ key: 'idle', label: 'Idle', count: cards.filter((c) => !working.has(c.name)).length }
	]);
	const shown = $derived(
		cards.filter((c) => group === 'all' || (group === 'working') === working.has(c.name))
	);
</script>

<div class="layout">
	<FilterColumn title="Overview" items={counts} bind:active={group} />
	<section class="main">
		<h1>Agents</h1>
		<div class="grid">
			{#each shown as card (card.name)}
				<article class="card tile">
					<div class="row between">
						<span class="row"><AgentAvatar name={card.name} /> <b>{agent(card.name).title}</b></span>
						{#if working.has(card.name)}
							<span class="state on pulse">Working</span>
						{:else}
							<span class="state">Idle</span>
						{/if}
					</div>
					<p class="muted">{card.job}</p>
					<div class="row between foot">
						{#if card.last}
							<a class="small" href="/inbox?case={card.last.key}">Last: <b>{card.last.company}</b> · {ago(card.last.updated_at)}</a>
						{:else}
							<span class="small faint">No cases yet</span>
						{/if}
						<span class="small faint">{card.count} cases</span>
					</div>
				</article>
			{/each}
		</div>
	</section>
</div>

<style>
	.layout {
		display: grid;
		grid-template-columns: 200px minmax(0, 1fr);
		min-height: 100%;
	}
	.main {
		padding: 16px 20px;
		display: flex;
		flex-direction: column;
		gap: 14px;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
		gap: 14px;
	}
	.tile {
		padding: 14px;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.foot {
		margin-top: auto;
		padding-top: 10px;
		border-top: 1px solid var(--line);
	}
	.state {
		font-size: 11px;
		padding: 1px 8px;
		border-radius: 99px;
		background: var(--gray-bg);
		color: var(--muted);
	}
	.state.on {
		background: var(--blue-bg);
		color: var(--blue);
	}
</style>
