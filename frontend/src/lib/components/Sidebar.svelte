<script lang="ts">
	import { page } from '$app/state';
	import { Blocks, Bot, Briefcase, ChevronDown, Inbox, UserRound } from '@lucide/svelte';
	import { agent } from '#lib/agents.ts';
	import { live } from '#lib/live.svelte.ts';
	import AgentAvatar from './AgentAvatar.svelte';

	const manage = [
		{ href: '/cases', label: 'Cases', icon: Briefcase },
		{ href: '/agents', label: 'Agents', icon: Bot },
		{ href: '/profile', label: 'Profile', icon: UserRound },
		{ href: '/integrations', label: 'Integrations', icon: Blocks }
	];
	const busy = $derived(Object.entries(live.working));
	const active = (href: string) => page.url.pathname.startsWith(href);
</script>

<aside>
	<div class="workspace">
		<span class="logo">f</span>
		<b>findmeajob</b>
		<ChevronDown size={14} class="faint" />
	</div>

	<nav>
		<a href="/inbox" class:active={active('/inbox')}><Inbox size={16} /> Inbox</a>
		<p class="section-label">Manage</p>
		{#each manage as item (item.href)}
			<a href={item.href} class:active={active(item.href)}><item.icon size={16} /> {item.label}</a>
		{/each}
	</nav>

	<div class="live card">
		<div class="row between">
			<b>{busy.length ? 'Agents at work' : 'All quiet'}</b>
			<span class="dot" class:on={live.connected} title={live.connected ? 'Live' : 'Reconnecting'}></span>
		</div>
		{#each busy as [caseId, name] (caseId + name)}
			<a class="row job" href={caseId ? `/inbox?case=${caseId}` : '/cases'}>
				<AgentAvatar {name} size={22} />
				<span class="small pulse">{agent(name).title} {agent(name).doing}</span>
			</a>
		{:else}
			<p class="small muted">agents pull up here when they're on a case.</p>
		{/each}
	</div>
</aside>

<style>
	aside {
		display: flex;
		flex-direction: column;
		width: 216px;
		flex-shrink: 0;
		padding: 14px 12px;
		background: linear-gradient(180deg, #eef2f8 0%, #f4f3f6 55%, #fbefe7 100%);
		border-right: 1px solid var(--line);
	}
	.workspace {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 4px 6px 14px;
		border-bottom: 1px solid var(--line);
	}
	.logo {
		display: grid;
		place-items: center;
		width: 24px;
		height: 24px;
		border-radius: 7px;
		background: var(--accent);
		color: #fff;
		font-weight: 700;
	}
	nav {
		display: flex;
		flex-direction: column;
		gap: 2px;
		margin-top: 12px;
	}
	nav a {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 7px 10px;
		border-radius: 9px;
		color: #374151;
	}
	nav a:hover {
		background: rgb(255 255 255 / 60%);
	}
	nav a.active {
		background: #dfe6f2;
		color: var(--text);
		font-weight: 500;
	}
	nav .section-label {
		padding: 0 10px;
		margin: 14px 0 4px;
	}
	.live {
		margin-top: auto;
		padding: 12px;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.job {
		align-items: flex-start;
	}
	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--faint);
	}
	.dot.on {
		background: var(--green);
		box-shadow: 0 0 0 3px var(--green-bg);
	}
</style>
