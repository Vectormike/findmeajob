<script lang="ts">
	import '../app.css';
	import favicon from '#lib/assets/favicon.svg';
	import { api } from '#lib/api.ts';
	import Sidebar from '#lib/components/Sidebar.svelte';
	import Topbar from '#lib/components/Topbar.svelte';
	import { live } from '#lib/live.svelte.ts';

	let { children } = $props();
	let name = $state('');
	let waiting = $state(0);

	$effect(() => live.start());

	$effect(() => {
		void live.tick;
		api.profile().then((data) => (name = data.profile.name));
		api.inbox().then((data) => (waiting = data.unmatched.length));
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>findmeajob</title>
</svelte:head>

<div class="frame">
	<Sidebar />
	<div class="main">
		<Topbar {name} {waiting} />
		<div class="content">{@render children()}</div>
	</div>
</div>

<style>
	.frame {
		display: flex;
		height: 100vh;
		background: var(--panel);
		overflow: hidden;
	}
	.main {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.content {
		flex: 1;
		min-height: 0;
		overflow: auto;
	}
</style>
