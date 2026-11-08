<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { Link, Radar } from '@lucide/svelte';
	import { untrack } from 'svelte';
	import { agent } from '#lib/agents.ts';
	import { api, type CaseRow, type Status } from '#lib/api.ts';
	import Badge from '#lib/components/Badge.svelte';
	import FilterColumn from '#lib/components/FilterColumn.svelte';
	import { CAREERS, FIELDS } from '#lib/careers.ts';
	import { ago, label } from '#lib/format.ts';
	import { live } from '#lib/live.svelte.ts';

	const OPEN = ['applied', 'acknowledged', 'in_conversation', 'interview', 'debriefed', 'offer'];
	const GROUPS: Record<string, (c: CaseRow) => boolean> = {
		all: () => true,
		open: (c) => OPEN.includes(c.stage),
		blocked: (c) => c.stage === 'blocked' || Boolean(c.error),
		skipped: (c) => c.stage === 'skipped',
		closed: (c) => ['closed', 'rejected'].includes(c.stage)
	};

	let cases = $state<CaseRow[]>([]);
	let scout = $state<Status | null>(null);
	let arrangements = $state<string[]>(['any']);
	let regions = $state<{ name: string; countries: string[] }[]>([]);
	let group = $state('all');
	let query = $state(page.url.searchParams.get('q') ?? '');
	let region = $state('Germany');
	let field = $state('Tech');
	let career = $state(CAREERS.Tech[0]);
	let arrangement = $state('any');
	let url = $state('');
	let note = $state('');
	let busy = $state(false);
	let since = $state('');
	let fresh = $state<Record<string, boolean>>({});
	let stagger = $state<Record<string, number>>({});
	let runOnly = $state(false);
	let runIds = $state<Record<string, boolean>>({});
	let loaded = false;
	let sweepVersion = 0;
	const known = new Set<string>();
	const revealed = new Set<string>();
	const scoutColor = agent('scout').color;

	function reveal(key: string, place: number) {
		if (revealed.has(key)) return;
		revealed.add(key);
		runIds[key] = true;
		fresh[key] = true;
		stagger[key] = place;
		const version = sweepVersion;
		setTimeout(() => {
			if (version !== sweepVersion) return;
			delete fresh[key];
			delete stagger[key];
		}, 1700 + place * 420);
	}

	function notice(rows: CaseRow[]) {
		if (!loaded) {
			for (const row of rows) known.add(row.key);
			loaded = true;
			return;
		}
		const available = new Set(rows.map((row) => row.key));
		if (runOnly) {
			for (const key of live.discovered) {
				if (available.has(key)) reveal(key, revealed.size);
			}
		}
		for (const row of rows) {
			if (known.has(row.key)) continue;
			known.add(row.key);
			if (runOnly) reveal(row.key, revealed.size);
			else {
				fresh[row.key] = true;
				setTimeout(() => delete fresh[row.key], 1700);
			}
		}
	}

	$effect(() => {
		query = page.url.searchParams.get('q') ?? '';
	});

	$effect(() => {
		void live.tick;
		untrack(async () => {
			const data = await api.cases();
			const initial = !loaded;
			notice(data.cases);
			({ cases, scout, arrangements, regions } = data);
			if (initial && data.scout?.run_id) {
				runIds = Object.fromEntries((data.scout.case_ids ?? []).map((key) => [key, true]));
				runOnly = true;
			}
		});
	});

	const needle = $derived(query.trim().toLowerCase());
	const listed = $derived(runOnly ? cases.filter((c) => runIds[c.key]) : cases);
	const shown = $derived(
		listed.filter((c) => GROUPS[group](c) && (!needle || Object.values(c).join(' ').toLowerCase().includes(needle)))
	);
	const counts = $derived(Object.keys(GROUPS).map((key) => ({ key, label: label(key), count: listed.filter(GROUPS[key]).length })));
	const sweeping = $derived(busy || '' in live.working);
	const careers = $derived(CAREERS[field]);

	$effect(() => {
		if (!careers.includes(career)) career = careers[0];
	});

	$effect(() => {
		if (busy && scout && scout.at !== since) {
			busy = false;
			note = scout.detail;
		}
	});

	async function sweep(event: SubmitEvent) {
		event.preventDefault();
		since = scout?.at ?? '';
		for (const row of cases) known.add(row.key);
		loaded = true;
		sweepVersion += 1;
		revealed.clear();
		live.beginScout();
		runIds = {};
		fresh = {};
		stagger = {};
		runOnly = true;
		busy = true;
		note = `table's clear. scout's hunting ${career} in ${region}.`;
		await api.scout(region, career, arrangement).catch((error: Error) => {
			busy = false;
			note = error.message;
		});
	}

	async function add(event: SubmitEvent) {
		event.preventDefault();
		await api.addPosting(url);
		note = "opening that one. judge's up next.";
		url = '';
	}
</script>

<div class="layout">
	<FilterColumn title="Overview" items={counts} bind:active={group} />

	<section class="main">
		<h1>Cases</h1>
		<div class="forms">
			<form class="card form scout" class:scanning={sweeping} onsubmit={sweep}>
				<p class="row">
					<span class="radar" class:on={sweeping}>
						<Radar size={15} />
						{#if sweeping}<span class="ring"></span><span class="ring late"></span>{/if}
					</span>
					<b>{sweeping ? "Scout's locked in" : 'Send Scout'}</b>
				</p>
				<div class="controls">
					<select bind:value={region} aria-label="Region">
						<optgroup label="Continents">
							{#each regions as group (group.name)}<option value={group.name}>{group.name}</option>{/each}
						</optgroup>
						{#each regions as group (group.name)}
							<optgroup label={group.name}>
								{#each group.countries as country (country)}<option value={country}>{country}</option>{/each}
							</optgroup>
						{/each}
					</select>
					<select bind:value={field} aria-label="Field">{#each FIELDS as name (name)}<option>{name}</option>{/each}</select>
					<select bind:value={career} aria-label="Career">{#each careers as name (name)}<option>{name}</option>{/each}</select>
					<select bind:value={arrangement} aria-label="Arrangement">{#each arrangements as a (a)}<option value={a}>{label(a)}</option>{/each}</select>
					<button class="btn primary" disabled={sweeping}>{sweeping ? 'Locked in…' : 'Sweep'}</button>
				</div>
				{#if scout}<p class="small" class:error-text={!scout.ok} class:muted={scout.ok}>last sweep {ago(scout.at)}: {scout.detail}</p>{/if}
			</form>
			<form class="card form" onsubmit={add}>
				<p class="row"><Link size={15} /> <b>Got a link?</b></p>
				<div class="row">
					<input type="url" bind:value={url} placeholder="https://…" required />
					<button class="btn">Open it</button>
				</div>
			</form>
		</div>
		{#if note}<p class="small muted">{note}</p>{/if}

		<div class="card table" style:--scout={scoutColor}>
			<div class="row between">
				<input class="filter" bind:value={query} placeholder="filter the pile…" />
				{#if scout?.run_id}
					<div class="run-switch">
						<span>{runOnly ? 'Latest sweep' : 'All history'}</span>
						<button type="button" class="btn small" onclick={() => (runOnly = !runOnly)}>
							{runOnly ? 'All history' : 'Latest sweep'}
						</button>
					</div>
				{/if}
			</div>
			<div class="sheet-scroll">
				<div class="sheet">
					<div class="cols head">
						<span>Company</span><span>Role</span><span>Region</span><span>Career</span><span>Arrangement</span><span>Stage</span><span>Last agent</span><span>Updated</span>
					</div>
					{#each shown as c (c.key)}
						<div class="slot" class:arrive={fresh[c.key]} style:--d={`${(stagger[c.key] ?? 0) * 420}ms`}>
							<div class="clip">
							<button type="button" class="cols job" onclick={() => goto(`/inbox?case=${c.key}`)}>
								<span><b>{c.company}</b></span>
								<span>{c.title}</span>
								<span>{c.region || '—'}</span>
								<span>{c.skill || '—'}</span>
								<span>{label(c.arrangement) || '—'}</span>
								<span>
									{#if live.working[c.key]}<span class="pulse small working" style:color={agent(live.working[c.key]).color}>{agent(live.working[c.key]).title}'s on it</span>
									{:else if c.error}<Badge value="error" />
									{:else}<Badge value={c.stage} />{/if}
								</span>
								<span>{agent(c.last_agent).title}</span>
								<span class="faint">{ago(c.updated_at)}</span>
							</button>
							</div>
						</div>
					{:else}
						<p class="empty">{sweeping ? "any second now. they'll slide in." : runOnly ? 'this sweep came back dry.' : cases.length ? 'nothing in here matches.' : 'no cases yet. hit sweep and let scout cook.'}</p>
					{/each}
				</div>
			</div>
		</div>
	</section>
</div>

<style>
	.layout {
		display: grid;
		grid-template-columns: 200px minmax(0, 1fr);
		height: 100%;
		min-height: 0;
		overflow: hidden;
	}
	.main {
		padding: 16px 20px;
		display: flex;
		flex-direction: column;
		gap: 12px;
		min-height: 0;
		overflow: hidden;
	}
	.forms {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
		gap: 12px;
	}
	.form {
		padding: 14px;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.controls select {
		flex: 1 1 140px;
	}
	.table {
		padding: 12px;
		display: flex;
		flex: 1;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
	}
	.filter {
		flex: 1;
		min-width: 0;
	}
	.run-switch {
		display: flex;
		align-items: center;
		gap: 8px;
		color: var(--muted);
		font-size: 12px;
		white-space: nowrap;
	}
	.sheet {
		min-width: 820px;
	}
	.sheet-scroll {
		flex: 1;
		min-height: 0;
		margin-top: 8px;
		overflow: auto;
		overscroll-behavior: contain;
		scrollbar-gutter: stable;
	}
	.cols {
		display: grid;
		grid-template-columns: 1.15fr 1.45fr 0.85fr 1.05fr 0.95fr 0.95fr 0.8fr 0.7fr;
		align-items: center;
		column-gap: 10px;
		width: 100%;
		text-align: left;
	}
	.cols > span {
		min-width: 0;
	}
	.head {
		position: sticky;
		top: 0;
		z-index: 1;
		padding: 8px 14px;
		background: var(--panel);
		color: var(--muted);
		font-size: 12px;
		font-weight: 500;
		border-bottom: 1px solid var(--line);
	}
	.slot {
		display: grid;
		grid-template-rows: 1fr;
	}
	.slot.arrive {
		animation: unfold 1.35s cubic-bezier(0.22, 1, 0.36, 1) both;
		animation-delay: var(--d, 0ms);
	}
	.clip {
		overflow: hidden;
		min-height: 0;
	}
	.job {
		border: 0;
		border-bottom: 1px solid var(--line);
		border-radius: 0;
		background: transparent;
		box-shadow: none;
		padding: 11px 14px;
		cursor: pointer;
		position: relative;
	}
	.job:hover {
		background: var(--soft);
	}
	.slot.arrive .job {
		animation: rise 1.35s cubic-bezier(0.22, 1, 0.36, 1) both;
		animation-delay: var(--d, 0ms);
	}
	.slot.arrive .job::before {
		content: '';
		position: absolute;
		left: 0;
		top: 10px;
		bottom: 10px;
		width: 2px;
		border-radius: 2px;
		background: var(--scout);
		transform-origin: center top;
		animation: mark 1.6s cubic-bezier(0.22, 1, 0.36, 1) both;
		animation-delay: var(--d, 0ms);
	}
	@keyframes unfold {
		from { grid-template-rows: 0fr; }
		to { grid-template-rows: 1fr; }
	}
	@keyframes rise {
		from { opacity: 0; transform: translateY(16px); }
		to { opacity: 1; transform: none; }
	}
	@keyframes mark {
		0% { transform: scaleY(0); opacity: 0; }
		40% { transform: scaleY(1); opacity: 1; }
		100% { transform: scaleY(1); opacity: 0; }
	}
	.working {
		color: var(--blue);
	}
	.scout.scanning {
		position: relative;
		overflow: hidden;
	}
	.scout.scanning::after {
		content: '';
		position: absolute;
		left: 0;
		right: 0;
		height: 42%;
		background: linear-gradient(180deg, transparent, rgb(47 91 211 / 16%), transparent);
		animation: scan 1.8s ease-in-out infinite;
		pointer-events: none;
	}
	.radar {
		position: relative;
		display: grid;
		place-items: center;
		width: 22px;
		height: 22px;
		color: var(--blue);
	}
	.radar.on :global(svg) {
		animation: spin 2.8s linear infinite;
	}
	.ring {
		position: absolute;
		inset: 2px;
		border: 1.5px solid var(--blue);
		border-radius: 50%;
		animation: ping 1.8s ease-out infinite;
	}
	.ring.late {
		animation-delay: 0.7s;
	}
	@keyframes scan {
		from { top: -40%; }
		to { top: 100%; }
	}
	@keyframes spin {
		to { transform: rotate(360deg); }
	}
	@keyframes ping {
		from { transform: scale(0.7); opacity: 0.55; }
		to { transform: scale(2.4); opacity: 0; }
	}
	@media (prefers-reduced-motion: reduce) {
		.scout.scanning::after,
		.radar.on :global(svg),
		.ring,
		.slot.arrive,
		.slot.arrive .job,
		.slot.arrive .job::before {
			animation: none;
		}
	}
</style>
