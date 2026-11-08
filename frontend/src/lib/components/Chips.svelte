<script lang="ts">
	import { X } from '@lucide/svelte';

	let { values = $bindable([]), placeholder }: { values: string[]; placeholder: string } = $props();
	let draft = $state('');

	function add(event: KeyboardEvent) {
		if (event.key !== 'Enter' && event.key !== ',') return;
		event.preventDefault();
		const next = draft.trim();
		if (next && !values.includes(next)) values = [...values, next];
		draft = '';
	}
</script>

<div class="chips">
	{#each values as value (value)}
		<span class="chip">{value}<button type="button" aria-label="Remove {value}" onclick={() => (values = values.filter((v) => v !== value))}><X size={12} /></button></span>
	{/each}
	<input bind:value={draft} onkeydown={add} {placeholder} />
</div>

<style>
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		padding: 6px;
		border: 1px solid var(--line);
		border-radius: 9px;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 2px 4px 2px 9px;
		border-radius: 99px;
		background: var(--soft);
		border: 1px solid var(--line);
	}
	.chip button {
		display: grid;
		place-items: center;
		border: none;
		background: none;
		padding: 2px;
		cursor: pointer;
		color: var(--muted);
	}
	input {
		flex: 1;
		min-width: 140px;
		border: none;
		box-shadow: none;
		padding: 3px 4px;
	}
	input:focus {
		box-shadow: none;
	}
</style>
