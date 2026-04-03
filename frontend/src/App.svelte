<script>
  import { onMount, onDestroy } from 'svelte';

  const apiBase = import.meta.env.VITE_API_BASE ?? '';

  const defaults = {
    ssh_port: 22,
    remote_host: '127.0.0.1',
    compression: false,
    expose_to_lan: false,
    enabled: true
  };

  let tunnels = [];
  let selectedId = null;
  let mode = 'create';
  let loading = false;
  let saving = false;
  let error = '';
  let notice = '';
  let statuses = {};
  let statusTimer = null;

  const blankForm = () => ({
    name: '',
    mode: 'local',
    ssh_host: '',
    ssh_host_alias: '',
    ssh_user: '',
    ssh_port: defaults.ssh_port,
    local_port: '',
    remote_host: defaults.remote_host,
    remote_port: '',
    identity_file: '',
    keepalive_interval: '',
    compression: defaults.compression,
    expose_to_lan: defaults.expose_to_lan,
    enabled: defaults.enabled
  });

  let form = blankForm();
  $: aliasActive = form.ssh_host_alias.trim().length > 0;

  const toInt = (value) => {
    if (value === '' || value === null || value === undefined) return null;
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? null : parsed;
  };

  const normalizeForm = () => {
    const alias = form.ssh_host_alias.trim() || null;
    const omit = alias ? undefined : null;
    return {
      name: form.name.trim(),
      mode: form.mode,
      ssh_host: alias ? omit : form.ssh_host.trim() || null,
      ssh_host_alias: alias,
      ssh_user: alias ? omit : form.ssh_user.trim() || null,
      ssh_port: alias ? omit : toInt(form.ssh_port) ?? defaults.ssh_port,
      local_port: toInt(form.local_port),
      remote_host: form.remote_host.trim() || defaults.remote_host,
      remote_port: toInt(form.remote_port),
      identity_file: alias ? omit : form.identity_file.trim() || null,
      keepalive_interval: toInt(form.keepalive_interval),
      compression: Boolean(form.compression),
      expose_to_lan: Boolean(form.expose_to_lan),
      enabled: Boolean(form.enabled)
    };
  };

  const validate = () => {
    if (!form.name.trim()) return 'Name is required.';
    if (!form.local_port) return 'Local port is required.';
    if (!form.remote_port) return 'Remote port is required.';
    if (!form.ssh_host.trim() && !form.ssh_host_alias.trim()) {
      return 'Provide SSH host or SSH host alias.';
    }
    if (!form.ssh_host_alias.trim()) {
      if (!form.ssh_host.trim()) return 'SSH host is required when no alias is provided.';
      if (!form.ssh_user.trim()) return 'SSH user is required when no alias is provided.';
    }
    return '';
  };

  const resetForm = () => {
    mode = 'create';
    selectedId = null;
    form = blankForm();
  };

  const loadTunnels = async () => {
    loading = true;
    error = '';
    try {
      const res = await fetch(`${apiBase}/api/tunnels`);
      if (!res.ok) throw new Error(`Failed to load tunnels (${res.status})`);
      tunnels = await res.json();
      await loadStatus();
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  };

  const loadStatus = async () => {
    try {
      const res = await fetch(`${apiBase}/api/tunnel-status`);
      if (!res.ok) throw new Error(`Failed to load status (${res.status})`);
      statuses = await res.json();
    } catch (err) {
      error = err.message;
    }
  };

  const isRunning = (id) => statuses[id]?.running ?? false;
  const isReachable = (id) => statuses[id]?.reachable ?? false;
  const tunnelError = (id) => statuses[id]?.error ?? '';
  const tunnelProbeError = (id) => statuses[id]?.probe_error ?? '';
  const tunnelRetries = (id) => statuses[id]?.retries ?? 0;
  const tunnelProbeFailures = (id) => statuses[id]?.probe_failures ?? 0;

  const startStatusPolling = () => {
    stopStatusPolling();
    statusTimer = setInterval(loadStatus, 10000);
  };

  const stopStatusPolling = () => {
    if (statusTimer) {
      clearInterval(statusTimer);
      statusTimer = null;
    }
  };

  const selectTunnel = (tunnel) => {
    mode = 'edit';
    selectedId = tunnel.id;
    form = {
      name: tunnel.name ?? '',
      mode: tunnel.mode ?? 'local',
      ssh_host: tunnel.ssh_host ?? '',
      ssh_host_alias: tunnel.ssh_host_alias ?? '',
      ssh_user: tunnel.ssh_user ?? '',
      ssh_port: tunnel.ssh_port ?? defaults.ssh_port,
      local_port: tunnel.local_port ?? '',
      remote_host: tunnel.remote_host ?? defaults.remote_host,
      remote_port: tunnel.remote_port ?? '',
      identity_file: tunnel.identity_file ?? '',
      keepalive_interval: tunnel.keepalive_interval ?? '',
      compression: tunnel.compression ?? defaults.compression,
      expose_to_lan: tunnel.expose_to_lan ?? defaults.expose_to_lan,
      enabled: tunnel.enabled ?? defaults.enabled
    };
  };

  const saveTunnel = async () => {
    error = '';
    notice = '';
    const validationError = validate();
    if (validationError) {
      error = validationError;
      return;
    }

    const payload = normalizeForm();
    const url =
      mode === 'edit'
        ? `${apiBase}/api/tunnels/${selectedId}`
        : `${apiBase}/api/tunnels`;
    const method = mode === 'edit' ? 'PUT' : 'POST';

    saving = true;
    try {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error(`Save failed (${res.status})`);
      const saved = await res.json();
      await loadTunnels();
      await loadStatus();
      if (mode === 'edit') {
        selectTunnel(saved);
        notice = 'Tunnel updated.';
      } else {
        resetForm();
        notice = 'Tunnel created.';
      }
    } catch (err) {
      error = err.message;
    } finally {
      saving = false;
    }
  };

  const deleteTunnel = async () => {
    if (!selectedId) return;
    const ok = confirm('Delete this tunnel?');
    if (!ok) return;
    saving = true;
    error = '';
    notice = '';
    try {
      const res = await fetch(`${apiBase}/api/tunnels/${selectedId}`, { method: 'DELETE' });
      if (!res.ok && res.status !== 204) throw new Error(`Delete failed (${res.status})`);
      await loadTunnels();
      await loadStatus();
      resetForm();
      notice = 'Tunnel deleted.';
    } catch (err) {
      error = err.message;
    } finally {
      saving = false;
    }
  };

  const startTunnel = async () => {
    if (!selectedId) return;
    saving = true;
    error = '';
    notice = '';
    try {
      const res = await fetch(`${apiBase}/api/tunnels/${selectedId}/start`, { method: 'POST' });
      if (!res.ok) throw new Error(`Start failed (${res.status})`);
      await loadStatus();
      notice = 'Tunnel started.';
    } catch (err) {
      error = err.message;
    } finally {
      saving = false;
    }
  };

  const startAllTunnels = async () => {
    if (tunnels.length === 0) return;
    saving = true;
    error = '';
    notice = '';
    try {
      const results = await Promise.all(
        tunnels.map(async (tunnel) => {
          const res = await fetch(`${apiBase}/api/tunnels/${tunnel.id}/start`, { method: 'POST' });
          return { id: tunnel.id, ok: res.ok, status: res.status };
        })
      );
      const failed = results.filter((result) => !result.ok);
      await loadStatus();
      if (failed.length === 0) {
        notice = `Started ${results.length} tunnel${results.length === 1 ? '' : 's'}.`;
      } else {
        error = `Started ${results.length - failed.length}/${results.length} tunnels. ${failed.length} failed.`;
      }
    } catch (err) {
      error = err.message;
    } finally {
      saving = false;
    }
  };

  const stopTunnel = async () => {
    if (!selectedId) return;
    saving = true;
    error = '';
    notice = '';
    try {
      const res = await fetch(`${apiBase}/api/tunnels/${selectedId}/stop`, { method: 'POST' });
      if (!res.ok) throw new Error(`Stop failed (${res.status})`);
      await loadStatus();
      notice = 'Tunnel stopped.';
    } catch (err) {
      error = err.message;
    } finally {
      saving = false;
    }
  };

  onMount(() => {
    loadTunnels().then(startStatusPolling);
  });

  onDestroy(stopStatusPolling);
</script>

<div class="app">
  <header class="topbar">
    <div>
      <h1>SSH Tunnel Manager</h1>
      <p class="subtitle">Create, update, and manage SSH port forwarding.</p>
    </div>
    <div class="actions">
      <button class="outline" on:click={loadTunnels} disabled={loading || saving}>
        {loading ? 'Refreshing…' : 'Refresh'}
      </button>
      <button class="primary" on:click={resetForm} disabled={saving}>
        New Tunnel
      </button>
    </div>
  </header>

  <section class="grid">
    <aside class="list-panel">
      <div class="list-header">
        <div>
          <p class="eyebrow">Tunnels</p>
          <p class="muted">{tunnels.length} configured</p>
        </div>
        <button
          class="outline list-action"
          type="button"
          on:click={startAllTunnels}
          disabled={saving || loading || tunnels.length === 0}
        >
          Start All
        </button>
      </div>
      {#if loading}
        <p class="muted">Loading tunnels…</p>
      {:else if tunnels.length === 0}
        <p class="muted">No tunnels yet. Create your first one.</p>
      {:else}
        <ul class="tunnel-list">
          {#each tunnels as tunnel}
            <li>
              <button
                class:selected={tunnel.id === selectedId}
                on:click={() => selectTunnel(tunnel)}
              >
                <span
                  class="status-dot"
                  class:running={isRunning(tunnel.id) && isReachable(tunnel.id)}
                  class:degraded={isRunning(tunnel.id) && !isReachable(tunnel.id)}
                  class:stopped={!isRunning(tunnel.id) && !tunnelError(tunnel.id)}
                  class:errored={!isRunning(tunnel.id) && !!tunnelError(tunnel.id)}
                ></span>
                <div class="tunnel-main">
                  <div class="name-row">
                    <p class="name">{tunnel.name}</p>
                    <span class="port">:{tunnel.local_port}</span>
                    {#if tunnel.mode === 'reverse'}
                      <span class="mode-badge reverse">R</span>
                    {:else}
                      <span class="mode-badge local">L</span>
                    {/if}
                  </div>
                  <p class="alias">{tunnel.ssh_host_alias ?? tunnel.ssh_host}</p>
                  {#if isRunning(tunnel.id) && !isReachable(tunnel.id) && tunnelProbeError(tunnel.id)}
                    <p class="tunnel-warning">{tunnelProbeError(tunnel.id)}</p>
                  {/if}
                  {#if !isRunning(tunnel.id) && tunnelError(tunnel.id)}
                    <p class="tunnel-error">{tunnelError(tunnel.id)}</p>
                  {/if}
                </div>
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </aside>

    <main>
      <div class="panel form-panel">
        <div class="panel-header">
          <div>
            <h2>{mode === 'edit' ? 'Edit Tunnel' : 'Create Tunnel'}</h2>
            <p class="muted">Keep settings precise and consistent.</p>
          </div>
        </div>

        <div class="status">
          {#if error}
            <p class="error">{error}</p>
          {/if}
          {#if notice}
            <p class="notice">{notice}</p>
          {/if}
          {#if mode === 'edit' && selectedId && isRunning(selectedId) && !isReachable(selectedId) && tunnelProbeError(selectedId)}
            <div class="tunnel-warning-detail">
              <p class="warning">
                Reachability probe failing ({tunnelProbeFailures(selectedId)}): {tunnelProbeError(selectedId)}
              </p>
            </div>
          {/if}
          {#if mode === 'edit' && selectedId && tunnelError(selectedId)}
            <div class="tunnel-error-detail">
              <p class="error">Tunnel error (retry {tunnelRetries(selectedId)}/{5}): {tunnelError(selectedId)}</p>
            </div>
          {/if}
        </div>

        <form on:submit|preventDefault={saveTunnel}>
          <section class="form-section">
            <div class="section-title">
              <h3>Basic</h3>
              <p class="muted">Identify the tunnel and its SSH entry point.</p>
            </div>
            <div class="form-grid two-col">
              <label>
                <span>Name</span>
                <input type="text" bind:value={form.name} placeholder="Prod DB" />
              </label>
              <label>
                <span>Mode</span>
                <select bind:value={form.mode}>
                  <option value="local">Local (-L)</option>
                  <option value="reverse">Reverse (-R)</option>
                </select>
              </label>
              <label>
                <span>SSH Host</span>
                <input
                  type="text"
                  bind:value={form.ssh_host}
                  placeholder="ssh.example.com"
                />
                {#if aliasActive}
                  <span class="field-helper">Ignored when Host Alias is provided.</span>
                {/if}
              </label>
              <label>
                <span>SSH User</span>
                <input
                  type="text"
                  bind:value={form.ssh_user}
                  placeholder="deploy"
                  disabled={aliasActive}
                />
              </label>
              <label>
                <span>SSH Port</span>
                <input type="number" min="1" bind:value={form.ssh_port} disabled={aliasActive} />
              </label>
              <label>
                <span>SSH Host Alias</span>
                <input type="text" bind:value={form.ssh_host_alias} placeholder="company" />
              </label>
              <div class="field-note muted">
                Use your `~/.ssh/config` Host entry. When alias is set, direct host settings are ignored.
              </div>
            </div>
          </section>

          <section class="form-section">
            <div class="section-title">
              <h3>Port Forwarding</h3>
              <p class="muted">
                {form.mode === 'reverse'
                  ? 'Remote listens, traffic forwarded to local destination.'
                  : 'Define the local and remote endpoints.'}
              </p>
            </div>
            <div class="form-grid two-col">
              <label>
                <span>Local Port</span>
                <input type="number" min="1" bind:value={form.local_port} placeholder="9092" />
              </label>
              <label>
                <span>Remote Host</span>
                <input type="text" bind:value={form.remote_host} placeholder="127.0.0.1" />
              </label>
              <label>
                <span>Remote Port</span>
                <input type="number" min="1" bind:value={form.remote_port} placeholder="8081" />
              </label>
            </div>
            <div class="mapping-preview">
              {#if form.mode === 'reverse'}
                <div>{`${form.remote_host || '127.0.0.1'}:${form.remote_port || '____'}`} <span class="muted">(remote listens)</span></div>
                <span class="arrow">↓</span>
                <div>{form.ssh_host_alias || form.ssh_host || 'SSH host'}</div>
                <span class="arrow">↓</span>
                <div>{`localhost:${form.local_port || '____'}`} <span class="muted">(local destination)</span></div>
              {:else}
                <div>{`localhost:${form.local_port || '____'}`}</div>
                <span class="arrow">↓</span>
                <div>{form.ssh_host_alias || form.ssh_host || 'SSH host'}</div>
                <span class="arrow">↓</span>
                <div>{`${form.remote_host || '127.0.0.1'}:${form.remote_port || '____'}`}</div>
              {/if}
            </div>
          </section>

          <section class="form-section">
            <div class="section-title">
              <h3>Security</h3>
              <p class="muted">Credentials and connection hardening.</p>
            </div>
            <div class="form-grid two-col">
              <label>
                <span>Identity File</span>
                <input
                  type="text"
                  bind:value={form.identity_file}
                  placeholder="~/.ssh/id_ed25519"
                  disabled={aliasActive}
                />
              </label>
              <div class="toggle-field">
                <span>Enable Compression</span>
                <label class="toggle">
                  <input type="checkbox" bind:checked={form.compression} />
                  <span class="track"></span>
                </label>
              </div>
            </div>
          </section>

          <section class="form-section">
            <div class="section-title">
              <h3>Runtime</h3>
              <p class="muted">Keep the tunnel healthy and persistent.</p>
            </div>
            <div class="form-grid two-col">
              <label>
                <span>Keepalive Interval</span>
                <input type="number" min="0" bind:value={form.keepalive_interval} placeholder="30" />
              </label>
              <div class="toggle-field">
                <span>Auto-start on service startup</span>
                <label class="toggle">
                  <input type="checkbox" bind:checked={form.enabled} />
                  <span class="track"></span>
                </label>
              </div>
              <div class="toggle-field">
                <span>{form.mode === 'reverse' ? 'Expose remote port to LAN' : 'Expose local port to LAN'}</span>
                <label class="toggle">
                  <input type="checkbox" bind:checked={form.expose_to_lan} />
                  <span class="track"></span>
                </label>
              </div>
            </div>
          </section>

          <div class="form-footer">
            <div>
              <button
                class="danger subtle"
                type="button"
                on:click={deleteTunnel}
                disabled={saving || mode !== 'edit'}
              >
                Delete
              </button>
            </div>
            <div class="footer-actions">
              <button
                class="outline"
                type="button"
                on:click={stopTunnel}
                disabled={saving || mode !== 'edit'}
              >
                Stop
              </button>
              <button
                class="outline"
                type="button"
                on:click={startTunnel}
                disabled={saving || mode !== 'edit'}
              >
                Start
              </button>
              <button class="primary" type="submit" disabled={saving}>
                {saving ? 'Saving…' : 'Save Changes'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </main>
  </section>
</div>
