<script lang="ts">
	import { ArrowUp, Trash2 } from '@lucide/svelte';
	import { api, type CaseDetail } from '#lib/api.ts';
	import AgentAvatar from '../AgentAvatar.svelte';

	let { detail, onchange }: { detail: CaseDetail; onchange: (next: CaseDetail) => void } = $props();
	const draft = $derived(detail.case.draft);
	const drafted = $derived(draft?.body ?? '');
	let body = $state('');
	let busy = $state(false);
	let error = $state('');

	$effect(() => {
		body = drafted;
	});

	async function run(action: () => Promise<CaseDetail>) {
		busy = true;
		error = '';
		try {
			onchange(await action());
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}
</script>

<div class="composer">
	{#if draft}
		<div class="row between small">
			<span class="row"><AgentAvatar name="chaser" size={20} /> Chaser drafted a {draft.kind.replace('_', '-')} to <b>{draft.to}</b></span>
			<span class="muted">Re: {draft.subject}</span>
		</div>
		{#if draft.error}<p class="small error-text">{draft.error}</p>{/if}
		{#if error}<p class="small error-text">{error}</p>{/if}
		<div class="box">
			<textarea bind:value={body} rows="5" disabled={busy}></textarea>
			<div class="row actions">
				<button class="btn" disabled={busy || !detail.waiting} onclick={() => run(() => api.discard(detail.case.case_id))}>
					<Trash2 size={14} /> Discard
				</button>
				<button
					class="btn primary"
					disabled={busy || !detail.waiting || !body.trim()}
					onclick={() => run(() => api.approve(detail.case.case_id, body))}
				>
					Approve and send <ArrowUp size={14} />
				</button>
			</div>
		</div>
	{:else}
		<div class="box idle">
			<span class="faint">Chaser drafts replies here when a recruiter needs an answer. Nothing goes out until you approve.</span>
		</div>
	{/if}
</div>

<style>
	.composer {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 12px 20px 16px;
		border-top: 1px solid var(--line);
	}
	.box {
		border: 1px solid var(--line);
		border-radius: 12px;
		background: var(--soft);
		padding: 8px;
	}
	.box textarea {
		border: none;
		background: transparent;
		box-shadow: none;
	}
	.box.idle {
		padding: 12px 14px;
	}
	.actions {
		justify-content: flex-end;
	}
</style>
