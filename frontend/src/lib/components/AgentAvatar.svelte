<script lang="ts">
	import { agent } from '#lib/agents.ts';

	let { name, size = 28 }: { name: string | undefined; size?: number } = $props();
	const meta = $derived(agent(name));
</script>

<span
	class="avatar"
	style="--c: {meta.color}; width: {size}px; height: {size}px"
	title={meta.title}
>
	<meta.icon size={Math.round(size * 0.52)} strokeWidth={2} />
</span>

<style>
	.avatar {
		display: inline-grid;
		place-items: center;
		flex-shrink: 0;
		border-radius: 8px;
		color: var(--c);
		background: color-mix(in srgb, var(--c) 12%, white);
		border: 1px solid color-mix(in srgb, var(--c) 18%, white);
	}
</style>
