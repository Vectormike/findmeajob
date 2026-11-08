<script lang="ts">
	import { goto } from '$app/navigation';
	import { Bell, Search } from '@lucide/svelte';
	import { initials } from '#lib/format.ts';

	let { name, waiting }: { name: string; waiting: number } = $props();
	let query = $state('');

	function search(event: SubmitEvent) {
		event.preventDefault();
		goto(`/cases?q=${encodeURIComponent(query.trim())}`);
	}
</script>

<header>
	<form class="search" onsubmit={search}>
		<Search size={14} class="faint" />
		<input bind:value={query} placeholder="Search cases" aria-label="Search cases" />
	</form>
	<div class="row">
		<a class="icon-btn bell" href="/inbox" title="Mail that needs you">
			<Bell size={15} />
			{#if waiting}<span class="count">{waiting}</span>{/if}
		</a>
		<a class="user" href="/profile">
			<span class="initials">{initials(name || 'You')}</span>
			{name || 'Set up profile'}
		</a>
	</div>
</header>

<style>
	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 52px;
		padding: 0 16px;
		border-bottom: 1px solid var(--line);
		background: var(--panel);
	}
	.search {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 280px;
		padding: 0 10px;
		background: var(--soft);
		border: 1px solid var(--line);
		border-radius: 9px;
	}
	.search input {
		border: none;
		background: transparent;
		box-shadow: none;
		padding: 6px 0;
		flex: 1;
	}
	.bell {
		position: relative;
	}
	.count {
		position: absolute;
		top: -5px;
		right: -5px;
		min-width: 16px;
		height: 16px;
		padding: 0 4px;
		border-radius: 8px;
		background: var(--red);
		color: #fff;
		font-size: 10px;
		display: grid;
		place-items: center;
	}
	.user {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 3px 10px 3px 3px;
		border: 1px solid var(--line);
		border-radius: 9px;
		font-weight: 500;
	}
	.initials {
		display: grid;
		place-items: center;
		width: 24px;
		height: 24px;
		border-radius: 6px;
		background: #e2552c;
		color: #fff;
		font-size: 11px;
	}
</style>
