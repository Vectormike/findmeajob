<script lang="ts">
	import { ShieldCheck } from '@lucide/svelte';
	import { api } from '#lib/api.ts';

	let { caseId }: { caseId: string } = $props();
	const KEYS = ['Enter', 'Tab', 'Backspace', 'Escape', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'];
	const FRAME_MS = 600;
	let frame = $state(0);
	let ended = $state(false);
	let timer: ReturnType<typeof setTimeout> | undefined;

	$effect(() => () => clearTimeout(timer));

	function next() {
		clearTimeout(timer);
		timer = setTimeout(() => frame++, FRAME_MS);
	}

	function click(event: MouseEvent) {
		const box = (event.currentTarget as HTMLElement).getBoundingClientRect();
		api.liveAct(caseId, { kind: 'click', x: (event.clientX - box.left) / box.width, y: (event.clientY - box.top) / box.height });
	}

	function key(event: KeyboardEvent) {
		if (event.metaKey || event.ctrlKey) return;
		if (KEYS.includes(event.key)) api.liveAct(caseId, { kind: 'key', key: event.key });
		else if (event.key.length === 1) api.liveAct(caseId, { kind: 'type', text: event.key });
		else return;
		event.preventDefault();
	}

	function paste(event: ClipboardEvent) {
		const text = event.clipboardData?.getData('text').slice(0, 200);
		if (text) api.liveAct(caseId, { kind: 'type', text });
		event.preventDefault();
	}

	function scroll(event: WheelEvent) {
		event.preventDefault();
		api.liveAct(caseId, { kind: 'scroll', dy: Math.max(-2000, Math.min(2000, event.deltaY)) });
	}
</script>

<div class="handoff">
	{#if ended}
		<p class="row"><ShieldCheck size={16} /> <b>Done. Clerk is finishing the application.</b></p>
	{:else}
		<p class="row"><ShieldCheck size={16} /> <b>Clerk needs you on this page: tick the captcha, type the code the site emailed you, or sign in to Google.</b></p>
		<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
		<div class="screen" tabindex="0" role="application" aria-label="Application page" onclick={click} onkeydown={key} onpaste={paste} onwheel={scroll}>
			<img
				src="/api/cases/{caseId}/live.jpg?f={frame}"
				alt="Clerk's application page"
				onload={next}
				onerror={() => (ended = true)}
				draggable="false"
			/>
		</div>
		<p class="small muted">Click, type, or paste here like it's the real page. Clerk waits up to 5 minutes.</p>
	{/if}
</div>

<style>
	.handoff {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 12px;
		border-radius: var(--radius);
		background: var(--amber-bg);
		border: 1px solid #f3d9a8;
	}
	.handoff > p:first-child {
		gap: 8px;
		color: var(--amber);
	}
	.screen {
		border-radius: 8px;
		overflow: hidden;
		border: 1px solid var(--line);
		background: var(--page);
		cursor: pointer;
	}
	.screen:focus-visible {
		outline: 2px solid var(--blue);
	}
	.screen img {
		display: block;
		width: 100%;
		user-select: none;
	}
</style>
