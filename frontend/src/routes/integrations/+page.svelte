<script lang="ts">
	import { AudioLines, BadgeCheck, CircleAlert, Globe, Mail, Sparkles } from '@lucide/svelte';
	import type { Component } from 'svelte';
	import { untrack } from 'svelte';
	import { api, type Integration } from '#lib/api.ts';
	import AgentAvatar from '#lib/components/AgentAvatar.svelte';
	import FilterColumn from '#lib/components/FilterColumn.svelte';
	import { ago } from '#lib/format.ts';
	import { live } from '#lib/live.svelte.ts';

	const LOOK: Record<string, { icon: Component; color: string; setup: string }> = {
		gmail: { icon: Mail, color: '#ea4335', setup: 'Run `uv run findmeajob gmail-auth` to connect Gmail.' },
		readai: { icon: AudioLines, color: '#7c3aed', setup: 'Set READAI_WEBHOOK_SECRET and point Read AI at /webhooks/readai/<secret>.' },
		chrome: { icon: Globe, color: '#1a73e8', setup: 'Used the first time Clerk fills a form.' },
		xai: { icon: Sparkles, color: '#111827', setup: 'Drop XAI_API_KEY in .env and restart. then the agents can lock in.' }
	};

	let cards = $state<Integration[]>([]);
	let group = $state('all');
	let open = $state<string | null>(null);

	$effect(() => {
		void live.tick;
		untrack(async () => (cards = await api.integrations()));
	});

	const health = (c: Integration) => (!c.status ? 'unused' : c.status.ok ? 'connected' : 'error');
	const counts = $derived([
		{ key: 'all', label: 'All', count: cards.length },
		{ key: 'connected', label: 'Connected', count: cards.filter((c) => health(c) === 'connected').length },
		{ key: 'error', label: 'Error', count: cards.filter((c) => health(c) === 'error').length, tone: 'red' as const },
		{ key: 'unused', label: 'Not used yet', count: cards.filter((c) => health(c) === 'unused').length }
	]);
	const shown = $derived(cards.filter((c) => group === 'all' || health(c) === group));
</script>

<div class="layout">
	<FilterColumn title="Overview" items={counts} bind:active={group} />
	<section class="main">
		<h1>Integrations</h1>
		<div class="grid">
			{#each shown as card (card.key)}
				{@const look = LOOK[card.key]}
				<article class="card tile">
					<div class="row between">
						<span class="row">
							<span class="brand" style="--c: {look.color}"><look.icon size={16} /></span>
							<b>{card.name}</b>
						</span>
						{#if health(card) === 'connected'}<BadgeCheck size={18} class="ok" />
						{:else if health(card) === 'error'}<CircleAlert size={18} class="bad" />{/if}
					</div>
					<p class="muted">{card.job}</p>
					{#if open === card.key}
						<div class="more small">
							{#if card.status}
								<p class:error-text={!card.status.ok}>{card.status.detail || 'Connected'} · {ago(card.status.at)}</p>
							{/if}
							{#if health(card) !== 'connected'}<p class="muted">{look.setup}</p>{/if}
						</div>
					{/if}
					<div class="row between foot">
						<span class="row users">
							{#each card.agents.slice(0, 5) as name (name)}<AgentAvatar {name} size={22} />{/each}
							{#if card.agents.length > 5}<span class="small faint">+{card.agents.length - 5}</span>{/if}
						</span>
						<button class="btn small" onclick={() => (open = open === card.key ? null : card.key)}>
							{open === card.key ? 'Hide details' : 'View details'}
						</button>
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
	.brand {
		display: grid;
		place-items: center;
		width: 28px;
		height: 28px;
		border-radius: 8px;
		color: var(--c);
		background: color-mix(in srgb, var(--c) 10%, white);
	}
	.tile :global(.ok) {
		color: var(--green);
	}
	.tile :global(.bad) {
		color: var(--red);
	}
	.more {
		padding: 8px 10px;
		border-radius: 8px;
		background: var(--soft);
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.foot {
		margin-top: auto;
	}
	.users {
		gap: 4px;
	}
</style>
