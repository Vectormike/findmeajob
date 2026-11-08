<script lang="ts">
	import { Download, FileText, Sparkles } from '@lucide/svelte';
	import { agent } from '#lib/agents.ts';
	import { api, type CaseDetail } from '#lib/api.ts';
	import { ago, count, label } from '#lib/format.ts';
	import Badge from '../Badge.svelte';

	let { detail, onchange }: { detail: CaseDetail; onchange: (next: CaseDetail) => void } = $props();
	const c = $derived(detail.case);
	let tab = $state<'details' | 'debrief'>('details');

	const info = $derived([
		['Company', c.posting.company],
		['Role', c.posting.title],
		['Region', c.filters.region || c.posting.location || '—'],
		['Career', c.filters.skill || '—'],
		['Arrangement', label(c.filters.arrangement) || '—'],
		['Last agent', agent(c.last_agent).title],
		['Updated', ago(detail.index.updated_at)]
	]);

	function sections(d: CaseDetail['case']['debriefs'][number]): [string, string[]][] {
		const all: [string, string[]][] = [
			['Landed', d.landed],
			['Thin', d.thin],
			['Unused answers', d.unused_answers],
			['Could be better', d.could_be_better]
		];
		return all.filter(([, lines]) => lines.length);
	}

	async function close() {
		if (confirm('Close this case? Agents stop working on it.')) onchange(await api.close(c.case_id));
	}
</script>

<aside class="col">
	<div class="tabs">
		<button class:on={tab === 'details'} onclick={() => (tab = 'details')}>Case details</button>
		<button class:on={tab === 'debrief'} onclick={() => (tab = 'debrief')}>Debrief {c.debriefs.length ? `(${c.debriefs.length})` : ''}</button>
	</div>

	{#if tab === 'details'}
		<p class="section-label">Information</p>
		<dl>
			{#each info as [key, value] (key)}<dt>{key}</dt><dd>{value}</dd>{/each}
		</dl>

		{#if c.cv}
			<p class="section-label">Tailored CV</p>
			<div class="card box">
				<div class="row between">
					<span class="row"><FileText size={15} /> <b>{count(c.cv.changes.length, 'change')}</b></span>
					<span class="row">
						<a class="btn small" href="/api/cases/{c.case_id}/{c.cv.has_pdf ? 'cv.pdf' : 'cv'}" target="_blank">
							{c.cv.has_pdf ? 'View PDF' : 'View CV'}
						</a>
						{#if c.cv.has_pdf}<a class="icon-btn" href="/api/cases/{c.case_id}/cv.pdf?download=true" title="Download PDF"><Download size={14} /></a>{/if}
					</span>
				</div>
				<ul class="small">
					{#each c.cv.changes as change (change.change)}
						<li>{change.change} <span class="faint">({change.requirement}{change.source === 'profile' ? ', from profile' : ''})</span></li>
					{/each}
				</ul>
				{#if c.cv.gaps.length}<p class="small"><b>Gaps:</b> {c.cv.gaps.join(', ')}</p>{/if}
			</div>
		{/if}

		{#if c.application?.salary}
			{@const s = c.application.salary}
			<p class="section-label">Salary asked</p>
			<div class="card box row between">
				<span class="small muted">Range {s.low.toLocaleString()}–{s.high.toLocaleString()} per {s.period}</span>
				<b class="money">{s.currency} {s.figure.toLocaleString()}</b>
			</div>
			<p class="small">{#each s.sources as url, i (url)}<a class="src" href={url} target="_blank" rel="noopener">Source {i + 1}</a> {/each}</p>
		{/if}

		{#if c.fit}
			<p class="section-label">Judge's insight</p>
			<div class="card box">
				<p class="row"><Sparkles size={14} /> <b>Fit note</b></p>
				<p class="small">{c.fit.reason}</p>
				{#if c.fit.must_haves_covered?.length}<p class="small muted">Covers: {c.fit.must_haves_covered.join(', ')}</p>{/if}
				<p class="small row">Verdict: <Badge value={c.fit.recommendation === 'skip' ? 'rejected' : 'applied'} text={label(c.fit.recommendation)} /></p>
			</div>
		{/if}

		{#if detail.waiting}<button class="btn close" onclick={close}>Close case</button>{/if}
	{:else}
		{#each [...c.debriefs].reverse() as d (d.at)}
			<p class="section-label">From {d.source} · {ago(d.at)}</p>
			{#each sections(d) as [title, lines] (title)}
				<div class="card box">
					<b class="small">{title}</b>
					<ul class="small">{#each lines as line (line)}<li>{line}</li>{/each}</ul>
				</div>
			{/each}
		{:else}
			<p class="empty">Critic writes a debrief after each interview, from Read AI notes or feedback mail.</p>
		{/each}
	{/if}
</aside>

<style>
	.col {
		padding: 12px 16px 16px;
		overflow: auto;
		display: flex;
		flex-direction: column;
	}
	.tabs {
		display: flex;
		gap: 4px;
		padding: 3px;
		background: var(--soft);
		border-radius: 10px;
	}
	.tabs button {
		flex: 1;
		border: none;
		background: none;
		padding: 5px;
		border-radius: 8px;
		cursor: pointer;
		color: var(--muted);
	}
	.tabs button.on {
		background: var(--panel);
		color: var(--text);
		font-weight: 500;
		box-shadow: 0 1px 2px rgb(16 24 40 / 8%);
	}
	dl {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 10px 12px;
		margin: 0;
	}
	dt {
		color: var(--muted);
	}
	dd {
		margin: 0;
		text-align: right;
		font-weight: 500;
	}
	.box {
		padding: 10px 12px;
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin-bottom: 8px;
	}
	ul {
		margin: 0;
		padding-left: 16px;
	}
	.money {
		font-size: 16px;
	}
	.src {
		color: var(--blue);
	}
	.close {
		margin-top: 16px;
		justify-content: center;
	}
</style>
