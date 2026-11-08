<script lang="ts">
	import { FileText, Upload } from '@lucide/svelte';
	import { api, type Profile } from '#lib/api.ts';

	let { profile = $bindable(), onfilled }: { profile: Profile; onfilled?: () => void } = $props();
	let busy = $state(false);
	let over = $state(false);
	let error = $state('');
	let filled = $state(false);
	const words = $derived(profile.master_cv.split(/\s+/).filter(Boolean).length);

	async function upload(file?: File) {
		if (!file || busy) return;
		busy = true;
		error = '';
		filled = false;
		try {
			const { profile: saved } = await api.uploadCv(file);
			profile = saved;
			filled = true;
			onfilled?.();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	function picked(event: Event & { currentTarget: HTMLInputElement }) {
		upload(event.currentTarget.files?.[0]);
		event.currentTarget.value = '';
	}

	function dropped(event: DragEvent) {
		event.preventDefault();
		over = false;
		upload(event.dataTransfer?.files[0]);
	}
</script>

<div class="cv">
	<label
		class="drop"
		class:over
		ondragover={(e) => { e.preventDefault(); over = true; }}
		ondragleave={() => (over = false)}
		ondrop={dropped}
	>
		<input type="file" accept=".pdf,.docx,.txt,.md" hidden disabled={busy} onchange={picked} />
		<span class="tile">{#if profile.master_cv}<FileText size={18} />{:else}<Upload size={18} />{/if}</span>
		<span class="name">
			{#if busy}
				<b>Filling your profile…</b>
				<span class="small faint">Name, jobs, and skills come straight from the file.</span>
			{:else if profile.master_cv}
				<b>{profile.master_cv_file || 'Your CV'}</b>
				<span class="small faint">{words} words · this is what applications are written from</span>
			{:else}
				<b>Drop your CV here</b>
				<span class="small faint">PDF or Word. Your name, jobs, and skills fill in below.</span>
			{/if}
		</span>
		<span class="btn small">{profile.master_cv && !busy ? 'Replace' : 'Choose file'}</span>
	</label>
	{#if filled}<p class="small muted">Filled in and saved. Check it below, and save again if you change anything.</p>{/if}
	{#if error}<p class="error-text small">{error}</p>{/if}
	{#if profile.master_cv}
		<details>
			<summary class="small muted">Show the text from the file</summary>
			<pre>{profile.master_cv}</pre>
		</details>
	{/if}
</div>

<style>
	.cv {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.drop {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 14px;
		border: 1px dashed #cfd3da;
		border-radius: 12px;
		background: var(--soft);
		cursor: pointer;
	}
	.drop.over,
	.drop:hover {
		border-color: var(--accent);
	}
	.tile {
		display: grid;
		place-items: center;
		width: 36px;
		height: 36px;
		border-radius: 10px;
		background: var(--blue-bg);
		color: var(--blue);
	}
	.name {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 2px;
		font-size: 13px;
	}
	pre {
		max-height: 320px;
		overflow: auto;
		margin: 6px 0 0;
		padding: 12px;
		border: 1px solid var(--line);
		border-radius: 10px;
		font: 12px/1.5 inherit;
		white-space: pre-wrap;
	}
</style>
