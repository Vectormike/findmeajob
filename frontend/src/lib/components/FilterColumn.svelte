<script lang="ts">
	type Item = { key: string; label: string; count: number; tone?: 'red' };

	let { title, items, active = $bindable() }: { title: string; items: Item[]; active?: string } = $props();
</script>

<aside>
	<p class="section-label">{title}</p>
	<ul>
		{#each items as item (item.key)}
			<li>
				<button class:on={active === item.key} onclick={() => (active = item.key)}>
					<span>{item.label}</span>
					<span class="num" class:red={item.tone === 'red' && item.count}>{item.count}</span>
				</button>
			</li>
		{/each}
	</ul>
</aside>

<style>
	aside {
		padding: 0 14px;
		border-right: 1px solid var(--line);
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	button {
		display: flex;
		justify-content: space-between;
		align-items: center;
		width: 100%;
		padding: 7px 8px;
		border: none;
		border-radius: 8px;
		background: none;
		cursor: pointer;
		color: #374151;
	}
	button:hover,
	button.on {
		background: var(--soft);
	}
	.num {
		min-width: 22px;
		padding: 0 6px;
		border: 1px solid var(--line);
		border-radius: 6px;
		font-size: 11px;
		text-align: center;
		color: var(--muted);
	}
	.num.red {
		color: var(--red);
		border-color: #f7caca;
		background: var(--red-bg);
	}
</style>
