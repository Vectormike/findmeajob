<script lang="ts">
	import { agent } from '#lib/agents.ts';
	import { ago, initials } from '#lib/format.ts';
	import type { Item } from '#lib/thread.ts';
	import AgentAvatar from '../AgentAvatar.svelte';
	import Badge from '../Badge.svelte';

	let { item, caseId, onprep }: { item: Item; caseId: string; onprep: () => void } = $props();
	let open = $state(false);
</script>

{#if item.kind === 'mail'}
	<div class="msg in">
		<div class="who row">
			<span class="person">{initials(item.mail.from)}</span>
			<b>{item.mail.from.replace(/<.*>/, '').trim() || item.mail.from_email}</b>
			<span class="faint small">{ago(item.at)}</span>
			<Badge value={item.mail.category} />
		</div>
		<div class="bubble">
			<p><b>{item.mail.subject}</b></p>
			<p class="muted">{item.mail.summary}</p>
			{#if open}<pre>{item.mail.body}</pre>{/if}
			<button class="link small" onclick={() => (open = !open)}>{open ? 'Hide email' : 'Show email'}</button>
		</div>
	</div>
{:else if item.kind === 'sent'}
	<div class="msg out">
		<div class="who row"><span class="faint small">{ago(item.at)}</span><b>You, via Chaser</b><AgentAvatar name="chaser" size={24} /></div>
		<div class="bubble dark">
			<p class="small faint-light">To {item.to} · Re: {item.subject}</p>
			<pre>{item.body}</pre>
		</div>
	</div>
{:else}
	<div class="msg out">
		<div class="who row">
			<span class="faint small">{ago(item.at)}</span>
			<b>{agent(item.agent).title}</b>
			<AgentAvatar name={item.agent} size={24} />
		</div>
		<div class="bubble agent" class:red={item.tone === 'red'}>
			<p><b>{item.title}</b></p>
			{#if item.body}<p>{item.body}</p>{/if}
			{#if item.bullets?.length}
				<ul>{#each item.bullets as line (line)}<li>{line}</li>{/each}</ul>
			{/if}
			{#if item.action === 'cv'}
				<a class="link small" href="/api/cases/{caseId}/cv.pdf" target="_blank">Open tailored CV PDF</a>
			{:else if item.action === 'prep'}
				<button class="link small" onclick={onprep}>Open interview prep</button>
			{/if}
		</div>
	</div>
{/if}

<style>
	.msg {
		display: flex;
		flex-direction: column;
		gap: 6px;
		max-width: 78%;
	}
	.msg.out {
		align-self: flex-end;
		align-items: flex-end;
	}
	.who {
		gap: 8px;
	}
	.person {
		display: grid;
		place-items: center;
		width: 24px;
		height: 24px;
		border-radius: 50%;
		background: #e6e9ef;
		font-size: 10px;
		font-weight: 600;
	}
	.bubble {
		padding: 10px 14px;
		border-radius: 12px;
		background: var(--soft);
		border: 1px solid var(--line);
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin-left: 32px;
	}
	.out .bubble {
		margin: 0 32px 0 0;
	}
	.bubble.agent {
		background: var(--panel);
	}
	.bubble.red {
		background: var(--red-bg);
		border-color: #f7caca;
	}
	.bubble.dark {
		background: #3a4256;
		border-color: #3a4256;
		color: #fff;
	}
	.faint-light {
		color: #c5cad6;
	}
	ul {
		margin: 2px 0 0;
		padding-left: 18px;
	}
	pre {
		white-space: pre-wrap;
		font: inherit;
		margin: 4px 0 0;
		max-height: 320px;
		overflow: auto;
	}
	.link {
		align-self: flex-start;
		border: none;
		background: none;
		padding: 0;
		color: var(--blue);
		cursor: pointer;
	}
</style>
