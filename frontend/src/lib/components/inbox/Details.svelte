<script lang="ts">
	import { Download, FileText, Sparkles, X } from '@lucide/svelte';
	import { agent } from '#lib/agents.ts';
	import { api, type CaseDetail } from '#lib/api.ts';
	import { ago, count, label } from '#lib/format.ts';
	import { prefersReducedMotion } from 'svelte/motion';
	import { fly } from 'svelte/transition';
	import Badge from '../Badge.svelte';

	let {
		detail,
		onchange,
		onclose
	}: { detail: CaseDetail; onchange: (next: CaseDetail) => void; onclose: () => void } = $props();
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

<aside class="col" transition:fly={{ x: 40, duration: prefersReducedMotion.current ? 0 : 220 }}>
	<div class="drawer-head row">
		<div class="tabs">
			<button class:on={tab === 'details'} onclick={() => (tab = 'details')}>Case details</button>
			<button class:on={tab === 'debrief'} onclick={() => (tab = 'debrief')}>Debrief {c.debriefs.length ? `(${c.debriefs.length})` : ''}</button>
		</div>
		<button class="icon-btn" onclick={onclose} title="Close details"><X size={15} /></button>
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
			<p class="section-label">Judge's verdict</p>
			<div class="card box">
				<div class="row between">
					<span class="row"><Sparkles size={14} /> <b>Fit</b></span>
					<Badge value={c.fit.recommendation === 'skip' ? 'rejected' : 'applied'} text={label(c.fit.recommendation)} />
				</div>
				<div class="tally">
					<span><b>{c.fit.must_haves_covered?.length ?? 0}</b> covered</span>
					<span class:miss={c.fit.must_haves_missing?.length}><b>{c.fit.must_haves_missing?.length ?? 0}</b> missing</span>
					<span class:miss={c.fit.red_flags?.length}><b>{c.fit.red_flags?.length ?? 0}</b> red flags</span>
				</div>
				<p class="small faint">Full reasoning is in the thread.</p>
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
		flex: 1;
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
	.drawer-head {
		align-items: stretch;
	}
	.drawer-head .icon-btn {
		height: auto;
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
	.tally {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 6px;
	}
	.tally span {
		padding: 6px 8px;
		border-radius: 8px;
		background: var(--soft);
		font-size: 12px;
		color: var(--muted);
		text-align: center;
	}
	.tally b {
		display: block;
		font-size: 16px;
		color: var(--text);
	}
	.tally .miss b {
		color: var(--red);
	}
</style>
