<script lang="ts">
	import { page } from '$app/state';
	import { Link, Radar } from '@lucide/svelte';
	import { untrack } from 'svelte';
	import { api, type CaseRow, type Status } from '#lib/api.ts';
	import ScoutTable from '#lib/components/ScoutTable.svelte';
	import { CAREERS, FIELDS } from '#lib/careers.ts';
	import { ago, label } from '#lib/format.ts';
	import { live } from '#lib/live.svelte.ts';

	let cases = $state<CaseRow[]>([]);
	let scout = $state<Status | null>(null);
	let arrangements = $state<string[]>(['any']);
	let regions = $state<{ name: string; countries: string[] }[]>([]);
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
			}
		});
	});

	const needle = $derived(query.trim().toLowerCase());
	const listed = $derived(runOnly ? cases.filter((c) => runIds[c.key]) : cases);
	const shown = $derived(listed.filter((c) => !needle || Object.values(c).join(' ').toLowerCase().includes(needle)));
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

<section class="main">
	<div class="forms">
		<form class="card form scout" class:scanning={sweeping} onsubmit={sweep}>
			<select class="wide" bind:value={region} aria-label="Region">
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
			<select class="wider" bind:value={career} aria-label="Career">{#each careers as name (name)}<option>{name}</option>{/each}</select>
			<select bind:value={arrangement} aria-label="Arrangement">{#each arrangements as a (a)}<option value={a}>{label(a)}</option>{/each}</select>
			<button class="btn primary" disabled={sweeping}>
				<span class="radar" class:on={sweeping}>
					<Radar size={15} />
					{#if sweeping}<span class="ring"></span><span class="ring late"></span>{/if}
				</span>
				{sweeping ? 'Locked in…' : 'Sweep'}
			</button>
		</form>
		<form class="card form link" onsubmit={add}>
			<Link size={15} />
			<input type="url" bind:value={url} placeholder="Got a link? Paste it" aria-label="Job link" required />
			<button class="btn">Open it</button>
		</form>
	</div>
	{#if note || scout}
		<p class="small" class:error-text={!note && scout && !scout.ok} class:muted={note || scout?.ok}>
			{note || `last sweep ${ago(scout?.at)}: ${scout?.detail}`}
		</p>
	{/if}

	<ScoutTable
		rows={shown}
		{region}
		{career}
		bind:query
		bind:runOnly
		showRun={Boolean(scout?.run_id)}
		{sweeping}
		{fresh}
		{stagger}
		empty={runOnly ? 'this sweep came back dry.' : cases.length ? 'nothing in here matches.' : 'no cases yet. hit sweep and let scout cook.'}
	/>
</section>

<style>
	.main {
		height: 100%;
		padding: 0 32px 16px;
		display: flex;
		flex-direction: column;
		gap: 10px;
		overflow: auto;
	}
	.main > :global(*) {
		width: 100%;
		max-width: 980px;
		margin-inline: auto;
	}
	.forms {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
		margin-top: 16px;
	}
	.form {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 12px;
	}
	.scout {
		flex: 3 1 600px;
		flex-wrap: wrap;
	}
	.link {
		flex: 2 1 240px;
		color: var(--muted);
	}
	.link input {
		flex: 1;
		width: 0;
	}
	.scout select {
		flex: 1 1 100px;
		padding-right: 30px;
		background-position: right 10px center;
	}
	.scout select.wide {
		flex: 2 1 130px;
	}
	.scout select.wider {
		flex: 3 1 160px;
	}
	@media (max-width: 760px) {
		.main {
			padding-inline: 16px;
		}
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
		width: 18px;
		height: 18px;
	}
	.radar.on :global(svg) {
		animation: spin 2.8s linear infinite;
	}
	.ring {
		position: absolute;
		inset: 2px;
		border: 1.5px solid currentColor;
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
		.ring {
			animation: none;
		}
	}
</style>
