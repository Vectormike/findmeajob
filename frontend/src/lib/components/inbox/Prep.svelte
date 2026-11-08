<script lang="ts">
	import { ExternalLink } from '@lucide/svelte';
	import type { Case } from '#lib/api.ts';
	import { label } from '#lib/format.ts';

	let { brief }: { brief: NonNullable<Case['brief']> } = $props();
	const sources = $derived(Object.entries(brief.research).filter(([, claims]) => claims.length));
</script>

<div class="prep">
	{#if brief.interview_time}<p class="muted">Interview: <b>{brief.interview_time}</b></p>{/if}
	{#each brief.questions as qa, i (qa.question)}
		<details class="card qa" open={i === 0}>
			<summary>{qa.question}</summary>
			<p>{qa.answer}</p>
			<p class="small faint">Why they ask: {qa.why_asked}</p>
		</details>
	{/each}

	{#if brief.gaps_to_prepare.length}
		<p class="section-label">Prepare for</p>
		<ul>{#each brief.gaps_to_prepare as gap (gap)}<li>{gap}</li>{/each}</ul>
	{/if}
	{#if brief.questions_to_ask_them.length}
		<p class="section-label">Ask them</p>
		<ul>{#each brief.questions_to_ask_them as q (q)}<li>{q}</li>{/each}</ul>
	{/if}

	{#each sources as [section, claims] (section)}
		<p class="section-label">{label(section)}</p>
		{#each claims as claim (claim.text)}
			<p class="claim small">
				{claim.text}
				<a href={claim.source_url} target="_blank" rel="noopener" title={claim.source_url}><ExternalLink size={12} /></a>
			</p>
		{/each}
	{/each}
</div>

<style>
	.prep {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.qa {
		padding: 10px 14px;
	}
	.qa summary {
		cursor: pointer;
		font-weight: 600;
	}
	.qa p {
		margin-top: 6px;
	}
	ul {
		margin: 0;
		padding-left: 18px;
	}
	.claim a {
		color: var(--blue);
		vertical-align: middle;
	}
</style>
