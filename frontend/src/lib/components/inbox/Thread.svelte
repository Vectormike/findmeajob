<script lang="ts">
	import { ExternalLink, RotateCw } from '@lucide/svelte';
	import { agent } from '#lib/agents.ts';
	import { api, type CaseDetail } from '#lib/api.ts';
	import { initials } from '#lib/format.ts';
	import { live } from '#lib/live.svelte.ts';
	import { day, timeline } from '#lib/thread.ts';
	import AgentAvatar from '../AgentAvatar.svelte';
	import Badge from '../Badge.svelte';
	import Bubble from './Bubble.svelte';
	import Composer from './Composer.svelte';
	import Prep from './Prep.svelte';

	let { detail, onchange }: { detail: CaseDetail; onchange: (next: CaseDetail) => void } = $props();
	const c = $derived(detail.case);
	const items = $derived(timeline(c));
	const busy = $derived(live.working[c.case_id]);
	let tab = $state<'thread' | 'prep'>('thread');
	let retrying = $state(false);

	async function retry() {
		retrying = true;
		await api.retry(c.case_id).finally(() => (retrying = false));
	}
</script>

<section class="col">
	<header class="row between">
		<div class="row">
			<span class="logo">{initials(c.posting.company)}</span>
			<div>
				<h1>{c.posting.company}</h1>
				<p class="small muted">{c.posting.title}</p>
			</div>
		</div>
		<div class="row">
			<Badge value={c.stage} />
			{#if c.posting.url}
				<a class="btn small" href={c.posting.url} target="_blank" rel="noopener"><ExternalLink size={13} /> Posting</a>
			{/if}
		</div>
	</header>

	{#if c.brief}
		<div class="tabs">
			<button class:on={tab === 'thread'} onclick={() => (tab = 'thread')}>Thread</button>
			<button class:on={tab === 'prep'} onclick={() => (tab = 'prep')}>Interview prep</button>
		</div>
	{/if}

	<div class="body">
		{#if detail.index.error}
			<div class="alert row between">
				<span><b>{agent(c.last_agent).title} tapped out:</b> {detail.index.error}</span>
				<button class="btn small" onclick={retry} disabled={retrying}><RotateCw size={13} /> Retry</button>
			</div>
		{/if}

		{#if tab === 'prep' && c.brief}
			<Prep brief={c.brief} />
		{:else}
			{#each items as item, i (i)}
				{#if i === 0 || day(item.at) !== day(items[i - 1].at)}
					<p class="divider small faint">{day(item.at)}</p>
				{/if}
				<Bubble {item} caseId={c.case_id} onprep={() => (tab = 'prep')} />
			{/each}
			{#if busy}
				<div class="typing row">
					<AgentAvatar name={busy} size={24} />
					<span class="pulse muted">{agent(busy).title} {agent(busy).doing}…</span>
				</div>
			{/if}
		{/if}
	</div>

	<Composer {detail} {onchange} />
</section>

<style>
	.col {
		display: flex;
		flex-direction: column;
		min-width: 0;
		border-right: 1px solid var(--line);
	}
	header {
		padding: 12px 20px;
		border-bottom: 1px solid var(--line);
	}
	.logo {
		display: grid;
		place-items: center;
		width: 34px;
		height: 34px;
		border-radius: 50%;
		background: var(--gray-bg);
		font-weight: 600;
	}
	.tabs {
		display: flex;
		gap: 4px;
		padding: 8px 20px 0;
	}
	.tabs button {
		border: none;
		background: none;
		padding: 6px 10px;
		border-radius: 8px;
		cursor: pointer;
		color: var(--muted);
	}
	.tabs button.on {
		background: var(--soft);
		color: var(--text);
		font-weight: 500;
	}
	.body {
		flex: 1;
		overflow: auto;
		padding: 16px 20px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	.divider {
		align-self: center;
	}
	.alert {
		padding: 10px 12px;
		border-radius: 10px;
		background: var(--red-bg);
		border: 1px solid #f7caca;
		gap: 12px;
	}
	.typing {
		align-self: flex-end;
	}
</style>
