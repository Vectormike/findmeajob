<script lang="ts">
	import { Building2, Calendar, ChevronRight, CircleCheck, House, Plane, Radar, Send, Shuffle, Sparkles, TriangleAlert } from '@lucide/svelte';
	import { agent } from '#lib/agents.ts';
	import type { CaseRow } from '#lib/api.ts';
	import Badge from '#lib/components/Badge.svelte';
	import { ago, label } from '#lib/format.ts';
	import { live } from '#lib/live.svelte.ts';

	const OPEN = ['applied', 'acknowledged', 'in_conversation', 'interview', 'debriefed', 'offer'];
	const QUIET = ['opening', 'new', 'judged', 'tailored', 'skipped'];
	const TILES = [
		['#e8f0ff', '#2f5bd3'], ['#fde8f1', '#be185d'], ['#e3f6ec', '#047857'],
		['#fff1dc', '#b45309'], ['#efe9fe', '#6d28d9'], ['#e2f4f8', '#0e7490']
	];
	const CHIPS = [
		{ key: 'worth', label: 'Worth applying', icon: Sparkles, test: (r: CaseRow) => r.fit === 'apply' || r.fit === 'stretch' },
		{ key: 'remote', label: 'Remote', icon: House, test: (r: CaseRow) => r.remote || r.arrangement === 'remote' },
		{ key: 'hybrid', label: 'Hybrid', icon: Shuffle, test: (r: CaseRow) => r.arrangement === 'hybrid' },
		{ key: 'onsite', label: 'Onsite', icon: Building2, test: (r: CaseRow) => r.arrangement === 'onsite' },
		{ key: 'relocation', label: 'Relocation', icon: Plane, test: (r: CaseRow) => r.arrangement === 'relocation' },
		{ key: 'needs', label: 'Needs you', icon: TriangleAlert, test: (r: CaseRow) => r.stage === 'blocked' || Boolean(r.error) },
		{ key: 'moving', label: 'In progress', icon: Send, test: (r: CaseRow) => OPEN.includes(r.stage) }
	];

	let {
		rows,
		region,
		career,
		query = $bindable(''),
		runOnly = $bindable(false),
		showRun = false,
		sweeping = false,
		empty = '',
		fresh = {},
		stagger = {}
	}: {
		rows: CaseRow[];
		region: string;
		career: string;
		query?: string;
		runOnly?: boolean;
		showRun?: boolean;
		sweeping?: boolean;
		empty?: string;
		fresh?: Record<string, boolean>;
		stagger?: Record<string, number>;
	} = $props();

	let chip = $state('');
	let list = $state<HTMLElement>();
	let tools = $state<HTMLElement>();

	const active = $derived(CHIPS.find((c) => c.key === chip));
	const listed = $derived(active ? rows.filter(active.test) : rows);
	const companies = $derived(new Set(listed.map((r) => r.company).filter(Boolean)).size);
	const counts = $derived(Object.fromEntries(CHIPS.map((c) => [c.key, rows.filter(c.test).length])));
	const today = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
	const n = (value: number) => value.toLocaleString('en-GB');
	const some = (value: number, one: string, many = `${one}s`) => `${n(value)} ${value === 1 ? one : many}`;

	$effect(() => {
		void [chip, query, runOnly];
		if (!list || !tools) return;
		list.scrollTop = 0;
		if (list.getBoundingClientRect().top < tools.getBoundingClientRect().bottom - 1) {
			list.style.scrollMarginTop = `${tools.offsetHeight}px`;
			list.scrollIntoView();
		}
	});
	const place = $derived(active && ['remote', 'hybrid', 'onsite', 'relocation'].includes(active.key) ? active.label : '');
	const title = $derived(
		runOnly
			? `${place ? `${place} ` : ''}${career} jobs${region ? ` in ${region}` : ''}`
			: place ? `${place} jobs Scout found for you` : 'Jobs Scout found for you'
	);

	function tile(name: string): string[] {
		return TILES[[...name].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % TILES.length];
	}

	function initials(name: string): string {
		const words = name.replace(/[^\p{L}\p{N} ]/gu, ' ').split(/\s+/).filter(Boolean);
		return (words.length > 1 ? words[0][0] + words[1][0] : (words[0] ?? '?').slice(0, 2)).toUpperCase();
	}

	function when(r: CaseRow): string {
		return r.posted_at ? `Posted ${ago(r.posted_at)}` : `Found ${ago(r.updated_at)}`;
	}

	function toggle(key: string) {
		chip = chip === key ? '' : key;
	}
</script>

<section class="board">
	<div class="top">
		<header>
			<h1>{title}</h1>
			<p class="date">
				<Calendar size={14} />
				<span>
					On {today}: {some(listed.length, 'job')} from {some(companies, 'company', 'companies')}{active ? '' : `, ${n(counts.worth)} worth applying`}.
				</span>
			</p>
			<p class="lede">
				Every vacancy Scout has picked up, with Judge's verdict on each.
				{counts.moving ? `${n(counts.moving)} ${counts.moving === 1 ? 'is' : 'are'} already moving.` : 'Nothing has moved past applying yet.'}
				{counts.needs ? `${n(counts.needs)} ${counts.needs === 1 ? 'needs' : 'need'} a hand from you.` : ''}
			</p>
		</header>

		<div class="stats">
			<div class="stat"><span>Jobs found</span><b>{n(rows.length)}</b></div>
			{#each [{ key: 'worth', label: 'Worth applying' }, { key: 'needs', label: 'Needs you' }] as stat (stat.key)}
				<button type="button" class="stat link" class:on={chip === stat.key} aria-pressed={chip === stat.key} onclick={() => toggle(stat.key)}>
					<span>{stat.label}</span><b>{some(counts[stat.key], 'job')}</b>
				</button>
			{/each}
		</div>
	</div>

	<div class="tools" bind:this={tools}>
		<div class="chips">
			{#if showRun}
				<button type="button" class:on={runOnly} aria-pressed={runOnly} onclick={() => (runOnly = !runOnly)}>
					<Radar size={14} /> Latest sweep
				</button>
			{/if}
			{#each CHIPS as c (c.key)}
				{#if counts[c.key] || chip === c.key}
					<button type="button" class:on={chip === c.key} aria-pressed={chip === c.key} onclick={() => toggle(c.key)}>
						<c.icon size={14} /> {c.label} <small>{n(counts[c.key])}</small>
					</button>
				{/if}
			{/each}
		</div>
		<input class="filter" type="search" bind:value={query} placeholder="Filter by company, role, place…" aria-label="Filter jobs" />
	</div>

	<div class="list" bind:this={list}>
		{#each listed as r (r.key)}
			{@const [bg, fg] = tile(r.company || '?')}
			<div class="slot" class:arrive={fresh[r.key]} style:--d={`${(stagger[r.key] ?? 0) * 420}ms`}>
				<div class="clip">
					<a class="job" href={`/inbox?case=${r.key}`}>
						<span class="logo" style:background={bg} style:color={fg}>{initials(r.company || '?')}</span>
						<span class="body">
							<span class="name">{r.title}</span>
							<span class="meta">
								<b>{r.company}</b>{#if r.location || r.region}<span>{r.location || r.region}</span>{/if}<span>{when(r)}</span>
							</span>
							<span class="tags">
								{#if r.fit === 'apply'}<span class="tag green"><CircleCheck size={12} /> Strong fit</span>
								{:else if r.fit === 'stretch'}<span class="tag amber">Stretch fit</span>
								{:else if r.fit === 'skip'}<span class="tag">Judge passed</span>{/if}
								{#if r.remote || r.arrangement === 'remote'}<span class="tag violet"><House size={12} /> Remote</span>
								{:else if r.arrangement && r.arrangement !== 'any'}<span class="tag violet">{label(r.arrangement)}</span>{/if}
								{#if r.salary}<span class="tag">{r.salary}</span>{/if}
								{#if r.source}<span class="tag ghost">via {r.source}</span>{/if}
							</span>
						</span>
						<span class="end">
							{#if live.working[r.key]}<span class="pulse small working">{agent(live.working[r.key]).title}'s on it</span>
							{:else if r.error}<Badge value="error" />
							{:else if !QUIET.includes(r.stage)}<Badge value={r.stage} />{/if}
							<ChevronRight size={18} />
						</span>
					</a>
				</div>
			</div>
		{:else}
			<p class="empty">{sweeping ? "any second now. they'll slide in." : empty}</p>
		{/each}
	</div>
</section>

<style>
	.board { display: flex; flex-direction: column; gap: 12px; flex: none; }
	.top { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px 24px; }
	header { display: flex; flex-direction: column; gap: 6px; flex: 1 1 380px; }
	h1 { font-size: 26px; line-height: 1.2; letter-spacing: -0.035em; }
	.date { display: flex; align-items: flex-start; gap: 8px; color: var(--muted); font-size: 13px; }
	.date :global(svg) { flex: none; margin-top: 2px; }
	.meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; color: var(--muted); font-size: 13px; }
	.lede { color: var(--muted); font-size: 14.5px; line-height: 1.55; }
	.stats { display: grid; grid-template-columns: repeat(3, minmax(132px, 1fr)); gap: 10px; }
	.stat {
		display: flex; flex-direction: column; align-items: flex-start; gap: 2px;
		padding: 9px 16px; border: 1px solid var(--line); border-radius: 12px;
		background: var(--panel); text-align: left;
	}
	.stat span { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; }
	.stat b { font-size: 19px; letter-spacing: -0.02em; }
	.stat.link { cursor: pointer; }
	.stat.link b { color: #d9541e; text-decoration: underline; text-underline-offset: 4px; text-decoration-thickness: 1.5px; }
	.stat.link:hover { border-color: #f1c3ad; }
	/* When the page scrolls, the filters stay pinned and rows fade out beneath them. */
	.tools {
		display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px;
		position: sticky; top: 0; z-index: 1; margin-block: -10px -12px; padding-block: 10px 12px;
		background: linear-gradient(var(--panel) calc(100% - 12px), transparent);
	}
	.chips { display: flex; flex-wrap: wrap; gap: 6px; }
	.chips button {
		display: inline-flex; align-items: center; gap: 6px; padding: 6px 11px;
		border: 1px solid #d9dce2; border-radius: 999px; background: var(--panel);
		font-size: 13px; cursor: pointer;
	}
	.chips small { color: var(--faint); font-size: 12px; font-variant-numeric: tabular-nums; }
	.chips button:hover { background: var(--soft); }
	.chips button.on, .stat.link.on { color: #d9541e; background: #fff3ec; border-color: #f1b99c; }
	.chips button.on small { color: inherit; }
	.chips button:focus-visible, .stat.link:focus-visible, .job:focus-visible { outline: 2px solid var(--blue); outline-offset: -2px; }
	.filter { flex: 1 1 180px; max-width: 260px; margin-left: auto; }
	.list {
		overflow: hidden;
		border: 1px solid var(--line); border-radius: 14px;
		/* Shadows at the top and bottom edge show there is more to scroll. */
		background:
			linear-gradient(var(--panel) 40%, transparent) top / 100% 36px no-repeat local,
			linear-gradient(transparent, var(--panel) 60%) bottom / 100% 36px no-repeat local,
			linear-gradient(rgb(16 24 40 / 9%), transparent) top / 100% 12px no-repeat scroll,
			linear-gradient(transparent, rgb(16 24 40 / 9%)) bottom / 100% 12px no-repeat scroll,
			var(--panel);
	}
	.list::-webkit-scrollbar { width: 12px; }
	.list::-webkit-scrollbar-thumb { border: 4px solid transparent; border-radius: 999px; background: #cdd2da content-box; }
	.slot { display: grid; grid-template-rows: 1fr; }
	.slot + .slot { border-top: 1px solid var(--line); }
	.slot.arrive { animation: unfold 1.35s cubic-bezier(0.22, 1, 0.36, 1) both; animation-delay: var(--d, 0ms); }
	.clip { overflow: hidden; min-height: 0; }
	.job {
		display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 16px;
		padding: 12px 18px;
	}
	.job:hover { background: #fafbfc; }
	.job:hover .end :global(svg) { transform: translateX(2px); color: var(--text); }
	.logo {
		display: grid; place-items: center; width: 42px; height: 42px; border-radius: 12px;
		font-size: 14px; font-weight: 700; letter-spacing: -0.02em; box-shadow: inset 0 0 0 1px rgb(0 0 0 / 5%);
	}
	.body { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
	.name { font-size: 15.5px; font-weight: 650; letter-spacing: -0.01em; line-height: 1.35; }
	.body .meta b { color: var(--text); font-weight: 600; }
	.body .meta span::before { content: '·'; margin-right: 6px; color: var(--faint); }
	.tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 3px; }
	.tag {
		display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 6px;
		background: var(--gray-bg); color: var(--gray); font-size: 11.5px; font-weight: 500;
	}
	.tag.green { color: #047857; background: #e6f6ee; }
	.tag.amber { color: #b45309; background: #fdf1e1; }
	.tag.violet { color: #6d28d9; background: #f1ebfd; }
	.tag.ghost { background: transparent; box-shadow: inset 0 0 0 1px var(--line); color: var(--faint); }
	.end { display: flex; align-items: center; gap: 12px; color: var(--faint); }
	.end :global(svg) { transition: transform 0.15s ease; }
	.working { color: var(--blue); }
	.empty { padding: 36px 16px; text-align: center; color: var(--muted); }
	/* With enough room, the header stays put and the list scrolls on its own. */
	@media (min-height: 680px) and (min-width: 1200px), (min-height: 880px) and (min-width: 761px) {
		.board { flex: 1 1 0; min-height: 0; }
		.list { flex: 0 1 auto; min-height: 0; overflow-y: auto; overscroll-behavior: contain; }
	}
	@media (min-height: 680px) and (max-height: 899px) and (min-width: 1200px) {
		.lede { display: none; }
	}
	@media (max-width: 760px) {
		.stats { flex: 1 1 100%; grid-template-columns: repeat(3, minmax(0, 1fr)); }
		.stat { padding-inline: 12px; }
		h1 { font-size: 22px; }
		.filter { flex-basis: 100%; max-width: none; }
	}
	@media (prefers-reduced-motion: reduce) {
		.slot.arrive { animation: none; }
		.end :global(svg) { transition: none; }
	}
	@keyframes unfold {
		from { grid-template-rows: 0fr; }
		to { grid-template-rows: 1fr; }
	}
</style>
