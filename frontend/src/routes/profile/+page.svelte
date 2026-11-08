<script lang="ts">
	import { Plus, Trash2 } from '@lucide/svelte';
	import { untrack } from 'svelte';
	import { api, type MemoryEntry, type Profile } from '#lib/api.ts';
	import AgentAvatar from '#lib/components/AgentAvatar.svelte';
	import Chips from '#lib/components/Chips.svelte';
	import CvUpload from '#lib/components/CvUpload.svelte';
	import { live } from '#lib/live.svelte.ts';

	const FIELDS: [keyof Profile, string, string][] = [
		['name', 'Name', 'As it should appear on applications'],
		['email', 'Email', 'you@email.com'],
		['phone', 'Phone', ''],
		['location', 'Location', 'City, country'],
		['links', 'Links', 'LinkedIn, GitHub, portfolio'],
		['titles', 'Titles', 'Roles you have held'],
		['work_authorization', 'Work authorization', 'For example, EU citizen or needs a visa']
	];

	let profile = $state<Profile | null>(null);
	let memory = $state<MemoryEntry[]>([]);
	let saving = $state(false);
	let note = $state('');
	let details = $state<HTMLElement | undefined>(undefined);
	const proposed = $derived(memory.filter((m) => m.status === 'proposed'));
	const kept = $derived(memory.filter((m) => m.status === 'accepted' && m.kind === 'lesson'));

	$effect(() => {
		void live.tick;
		untrack(async () => {
			const data = await api.profile();
			memory = data.memory;
			profile ??= data.profile;
		});
	});

	async function save(event: SubmitEvent) {
		event.preventDefault();
		if (!profile) return;
		saving = true;
		const data = await api.saveProfile(profile).finally(() => (saving = false));
		profile = data.profile;
		note = 'Saved. Agents use this from their next turn.';
	}

	async function decide(key: string, decision: 'accepted' | 'dismissed') {
		const data = await api.decide(key, decision);
		memory = data.memory;
		if (profile) profile.stories = data.profile.stories;
	}
</script>

<div class="page">
	<div class="row between">
		<h1>Profile</h1>
		<span class="small muted">Start with your CV. The form fills in from it.</span>
	</div>

	{#if proposed.length}
		<section class="card panel">
			<p class="row"><AgentAvatar name="archivist" size={22} /> <b>Archivist proposes</b></p>
			{#each proposed as entry (entry.key)}
				<div class="row between proposal">
					<p><span class="kind">{entry.kind}</span> {entry.text}</p>
					<span class="row">
						<button class="btn small primary" onclick={() => decide(entry.key, 'accepted')}>Keep</button>
						<button class="btn small" onclick={() => decide(entry.key, 'dismissed')}>Dismiss</button>
					</span>
				</div>
			{/each}
		</section>
	{/if}

	{#if profile}
		<form class="card panel" onsubmit={save}>
			<CvUpload bind:profile onfilled={() => details?.scrollIntoView({ behavior: 'smooth', block: 'start' })} />

			<div class="block" bind:this={details}>
				<b>Your details</b>
				<div class="fields">
					{#each FIELDS as [key, title, hint] (key)}
						<label>{title}<input bind:value={profile[key]} placeholder={hint} /></label>
					{/each}
				</div>
			</div>
			<label>Skills
				<Chips bind:values={profile.skills} placeholder="Type a skill and press Enter" />
				<span class="faint">Taken from your CV. Add any that were missed.</span>
			</label>
			<label>Don't apply at
				<Chips bind:values={profile.skip_companies} placeholder="Company name, then Enter" />
				<span class="faint">Your current company is added from the CV. Jobs there are skipped.</span>
			</label>

			<div class="row between"><b>Roles</b>
				<button type="button" class="btn small" onclick={() => profile?.stories.push({ title: '', text: '' })}><Plus size={13} /> Add story</button>
			</div>
			{#if profile.stories.length}<p class="small faint">These are the examples used on forms and in interview prep.</p>{/if}
			{#each profile.stories as story, i (i)}
				<div class="story">
					<div class="row">
						<input bind:value={story.title} placeholder="Title, e.g. Moved billing to Kafka" />
						<button type="button" class="icon-btn" aria-label="Remove story" onclick={() => profile?.stories.splice(i, 1)}><Trash2 size={14} /></button>
					</div>
					<textarea bind:value={story.text} rows="3" placeholder="What happened, what you did, the result"></textarea>
				</div>
			{:else}
				<p class="small faint">No roles yet. Upload a CV and they show up here.</p>
			{/each}

			<div class="row save">
				{#if note}<span class="small muted">{note}</span>{/if}
				<button class="btn primary" disabled={saving}>{saving ? 'Saving…' : 'Save profile'}</button>
			</div>
		</form>
	{/if}

	{#if kept.length}
		<section class="card panel">
			<b>Lessons kept</b>
			<ul>{#each kept as entry (entry.key)}<li>{entry.text}</li>{/each}</ul>
		</section>
	{/if}
</div>

<style>
	.page {
		max-width: 920px;
		padding: 16px 20px 40px;
		display: flex;
		flex-direction: column;
		gap: 14px;
	}
	.panel {
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.block {
		display: flex;
		flex-direction: column;
		gap: 12px;
		scroll-margin-top: 12px;
	}
	.fields {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 12px;
	}
	label {
		display: flex;
		flex-direction: column;
		gap: 4px;
		font-size: 12px;
		color: var(--muted);
	}
	label :global(input) {
		color: var(--text);
		font-size: 13px;
	}
	.story {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 10px;
		border: 1px solid var(--line);
		border-radius: 10px;
		background: var(--soft);
	}
	.story input {
		flex: 1;
	}
	.proposal {
		padding: 8px 0;
		border-top: 1px solid var(--line);
		gap: 12px;
	}
	.kind {
		font-size: 11px;
		padding: 1px 7px;
		border-radius: 99px;
		background: var(--gray-bg);
		color: var(--muted);
		text-transform: capitalize;
	}
	.save {
		justify-content: flex-end;
	}
	ul {
		margin: 0;
		padding-left: 18px;
	}
</style>
