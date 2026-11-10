<script lang="ts">
	import { UserPen } from '@lucide/svelte';
	import { api, type MissingFact } from '#lib/api.ts';

	let { caseId, questions }: { caseId: string; questions: MissingFact[] } = $props();
	let answers = $state<Record<string, string>>({});
	let sending = $state(false);
	let error = $state('');
	const ready = $derived(questions.every((q) => answers[q.question]?.trim()));

	function plain(question: string) {
		return question.replace(/^[^\p{L}\p{N}]+|[\s*]+$/gu, '');
	}

	async function send(event: SubmitEvent) {
		event.preventDefault();
		if (sending || !ready) return;
		sending = true;
		error = '';
		const facts = questions.map(({ question }) => ({ question, answer: answers[question].trim() }));
		await api
			.addFacts(caseId, facts)
			.catch((e: Error) => (error = e.message))
			.finally(() => (sending = false));
	}
</script>

<form class="facts" onsubmit={send}>
	<p class="row"><UserPen size={16} /> <b>Clerk needs {questions.length === 1 ? 'this' : 'these'} from you</b></p>
	{#each questions as { question, options } (question)}
		<label>{plain(question)}
			{#if options.length}
				<select bind:value={answers[question]}>
					<option value={undefined} disabled selected>Pick one</option>
					{#each options as option (option)}<option value={option}>{option}</option>{/each}
				</select>
			{:else}
				<input bind:value={answers[question]} placeholder="Your answer" />
			{/if}
		</label>
	{/each}
	<div class="row between">
		<span class="small muted">{error || 'Saved to your profile for the next forms, then Clerk retries.'}</span>
		<button class="btn small primary" disabled={!ready || sending}>{sending ? 'Saving…' : 'Save and retry'}</button>
	</div>
</form>

<style>
	.facts {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 12px;
		border-radius: var(--radius);
		background: var(--amber-bg);
		border: 1px solid #f3d9a8;
	}
	.facts > p:first-child {
		gap: 8px;
		color: var(--amber);
	}
	label {
		display: flex;
		flex-direction: column;
		gap: 4px;
		font-size: 12px;
		color: var(--muted);
	}
	.between {
		gap: 12px;
	}
</style>
