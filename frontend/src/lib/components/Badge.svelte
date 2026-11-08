<script lang="ts">
	import { label, tone } from '#lib/format.ts';

	let { value, text }: { value: string | undefined; text?: string } = $props();
</script>

<span class="badge {tone(value)}">{text ?? label(value)}</span>

<style>
	.badge {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 1px 8px;
		border-radius: 99px;
		font-size: 11px;
		font-weight: 500;
		white-space: nowrap;
		border: 1px solid transparent;
	}
	.green { color: var(--green); background: var(--green-bg); }
	.blue { color: var(--blue); background: var(--blue-bg); }
	.amber { color: var(--amber); background: var(--amber-bg); }
	.red { color: var(--red); background: var(--red-bg); }
	.violet { color: var(--violet); background: var(--violet-bg); }
	.gray { color: var(--gray); background: var(--gray-bg); }
</style>
