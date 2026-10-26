/**
 * FarmerLinkage — Administrator Module Logic
 * Admin dashboard metrics, user directory, buyer verification actions, market registry, and data exports.
 */
const Admin = {
  /**
   * Load Admin Dashboard Overview: admin.html
   */
  async loadDashboard() {
    Navigation.renderDashboardShell('ADMIN', 'dashboard', 'System Administration');

    const statsGrid = document.getElementById('admin-stats-grid');
    const pendingListEl = document.getElementById('admin-pending-verifications');

    try {
      const [farmersRes, buyersRes, pendingRes, txnRes] = await Promise.allSettled([
        api.get('/admin/farmers', { limit: 100 }),
        api.get('/admin/buyers', { limit: 100 }),
        api.get('/admin/buyers/pending', { limit: 100 }),
        api.get('/admin/transactions', { limit: 100 }),
      ]);

      const farmers = (farmersRes.status === 'fulfilled' && Array.isArray(farmersRes.value)) ? farmersRes.value : [];
      const buyers = (buyersRes.status === 'fulfilled' && Array.isArray(buyersRes.value)) ? buyersRes.value : [];
      const pendingBuyers = (pendingRes.status === 'fulfilled' && Array.isArray(pendingRes.value)) ? pendingRes.value : [];
      const txns = (txnRes.status === 'fulfilled' && txnRes.value && txnRes.value.items) ? txnRes.value.items : [];

      if (statsGrid) {
        statsGrid.innerHTML = `
          <div class="stat-card">
            <div class="stat-icon green">👨‍🌾</div>
            <div class="stat-info">
              <div class="stat-value">${farmers.length}</div>
              <div class="stat-label">Registered Farmers</div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon blue">🏪</div>
            <div class="stat-info">
              <div class="stat-value">${buyers.length}</div>
              <div class="stat-label">Commercial Buyers</div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon amber">🛡️</div>
            <div class="stat-info">
              <div class="stat-value">${pendingBuyers.length}</div>
              <div class="stat-label">Pending Verifications</div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon purple">📑</div>
            <div class="stat-info">
              <div class="stat-value">${txns.length}</div>
              <div class="stat-label">System Transactions</div>
            </div>
          </div>
        `;
      }

      if (pendingListEl) {
        if (pendingBuyers.length === 0) {
          pendingListEl.innerHTML = `
            <div class="empty-state" style="margin: var(--spacing-4) 0;">
              <div class="empty-state-icon">✅</div>
              <h4 class="empty-state-title">No Pending Verifications</h4>
              <p class="empty-state-desc">All commercial buyer profiles have been reviewed.</p>
            </div>
          `;
        } else {
          pendingListEl.innerHTML = `
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Buyer ID</th>
                    <th>Business Name</th>
                    <th>Type</th>
                    <th>License / GSTIN</th>
                    <th>Market Address</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${pendingBuyers.slice(0, 5).map(b => `
                    <tr>
                      <td>#${b.id}</td>
                      <td><strong>${Utils.escapeHTML(b.business_name)}</strong></td>
                      <td><span class="badge badge-neutral">${Utils.escapeHTML(b.business_type)}</span></td>
                      <td><code>${Utils.escapeHTML(b.license_number)}</code></td>
                      <td>${Utils.escapeHTML(b.market_address)}</td>
                      <td>
                        <a href="admin-verification.html" class="btn btn-sm btn-primary">Review</a>
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          `;
        }
      }
    } catch (err) {
      if (statsGrid) {
        statsGrid.innerHTML = `
          <div class="alert alert-error" style="grid-column: 1 / -1;">
            <span>⚠️</span>
            <div>${Utils.escapeHTML(err.message)}</div>
          </div>
        `;
      }
    }
  },

  /**
   * Load user management directory: admin-users.html
   */
  async loadUsers() {
    Navigation.renderDashboardShell('ADMIN', 'users', 'User Directory');

    const container = document.getElementById('admin-users-container');
    if (!container) return;

    container.innerHTML = `
      <div class="loading-container">
        <div class="spinner spinner-lg"></div>
        <span>Loading registered participants...</span>
      </div>
    `;

    try {
      const [farmersRes, buyersRes] = await Promise.all([
        api.get('/admin/farmers', { limit: 100 }),
        api.get('/admin/buyers', { limit: 100 }),
      ]);

      const farmers = Array.isArray(farmersRes) ? farmersRes : [];
      const buyers = Array.isArray(buyersRes) ? buyersRes : [];

      container.innerHTML = `
        <div class="card" style="margin-bottom:var(--spacing-8);">
          <div class="card-header">
            <h3 style="font-size:var(--font-size-base);">Farmers / Producers (${farmers.length})</h3>
          </div>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Profile ID</th>
                  <th>User ID</th>
                  <th>State</th>
                  <th>District</th>
                  <th>Taluka</th>
                  <th>Land Area</th>
                  <th>Pincode</th>
                </tr>
              </thead>
              <tbody>
                ${farmers.map(f => `
                  <tr>
                    <td>#${f.id}</td>
                    <td>User #${f.user_id}</td>
                    <td>${Utils.escapeHTML(f.state)}</td>
                    <td>${Utils.escapeHTML(f.district)}</td>
                    <td>${Utils.escapeHTML(f.taluka || '—')}</td>
                    <td>${f.land_area_acres ? `${f.land_area_acres} Acres` : '—'}</td>
                    <td>${Utils.escapeHTML(f.pincode)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3 style="font-size:var(--font-size-base);">Commercial Buyers (${buyers.length})</h3>
          </div>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Buyer ID</th>
                  <th>User ID</th>
                  <th>Business Name</th>
                  <th>Type</th>
                  <th>License / GSTIN</th>
                  <th>Address</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                ${buyers.map(b => `
                  <tr>
                    <td>#${b.id}</td>
                    <td>User #${b.user_id}</td>
                    <td><strong>${Utils.escapeHTML(b.business_name)}</strong></td>
                    <td>${Utils.escapeHTML(b.business_type)}</td>
                    <td><code>${Utils.escapeHTML(b.license_number)}</code></td>
                    <td>${Utils.escapeHTML(b.market_address)}</td>
                    <td>${Utils.getStatusBadge(b.verification_status)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `;
    } catch (err) {
      container.innerHTML = `
        <div class="alert alert-error">
          <span>⚠️</span>
          <div>${Utils.escapeHTML(err.message)}</div>
        </div>
      `;
    }
  },

  /**
   * Load buyer verification decisions: admin-verification.html
   */
  async loadVerification() {
    Navigation.renderDashboardShell('ADMIN', 'verification', 'Buyer Verification Management');

    const container = document.getElementById('admin-verification-container');
    if (!container) return;

    container.innerHTML = `
      <div class="loading-container">
        <div class="spinner spinner-lg"></div>
        <span>Loading pending buyer verification records...</span>
      </div>
    `;

    try {
      const pending = await api.get('/admin/buyers/pending', { limit: 100 });
      const items = Array.isArray(pending) ? pending : [];

      if (items.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">✅</div>
            <h3 class="empty-state-title">No Pending Verification Applications</h3>
            <p class="empty-state-desc">All commercial buyer profiles have been verified or resolved.</p>
          </div>
        `;
        return;
      }

      container.innerHTML = `
        <div class="card">
          <div class="card-header">
            <h3 style="font-size:var(--font-size-base);">Pending Commercial Applications (${items.length})</h3>
          </div>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Buyer ID</th>
                  <th>Business Name</th>
                  <th>Type</th>
                  <th>Trade License</th>
                  <th>Market Address</th>
                  <th>Verification Notes</th>
                  <th>Decisions</th>
                </tr>
              </thead>
              <tbody>
                ${items.map(b => `
                  <tr>
                    <td>#${b.id}</td>
                    <td><strong>${Utils.escapeHTML(b.business_name)}</strong></td>
                    <td><span class="badge badge-neutral">${Utils.escapeHTML(b.business_type)}</span></td>
                    <td><code>${Utils.escapeHTML(b.license_number)}</code></td>
                    <td>${Utils.escapeHTML(b.market_address)}</td>
                    <td style="font-size:var(--font-size-xs); color:var(--color-secondary-text);">
                      ${Utils.escapeHTML(b.verification_notes || 'Standard verification requested')}
                    </td>
                    <td>
                      <div style="display:flex; gap:var(--spacing-2);">
                        <button class="btn btn-sm btn-primary" onclick="Admin.decideBuyer(${b.id}, 'approve')">
                          Approve
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="Admin.decideBuyer(${b.id}, 'reject')">
                          Reject
                        </button>
                      </div>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `;
    } catch (err) {
      container.innerHTML = `
        <div class="alert alert-error">
          <span>⚠️</span>
          <div>${Utils.escapeHTML(err.message)}</div>
        </div>
      `;
    }
  },

  /**
   * Decide buyer verification: PUT /api/admin/buyers/{buyer_id}/approve or reject
   */
  async decideBuyer(buyerId, action) {
    const notes = prompt(`Enter optional administrator note for ${action.toUpperCase()}:`, `Reviewed by Platform Admin`);
    if (notes === null) return;

    try {
      const endpoint = `/admin/buyers/${buyerId}/${action}`;
      await api.put(endpoint, { notes: notes.trim() || undefined });
      Utils.showToast(`Buyer application #${buyerId} marked as ${action.toUpperCase()}!`, 'success');
      this.loadVerification();
    } catch (err) {
      Utils.showToast(err.message || 'Action failed.', 'error');
    }
  },

  /**
   * Load markets registry: admin-markets.html
   */
  async loadMarkets() {
    Navigation.renderDashboardShell('ADMIN', 'markets', 'APMC Market Registry');

    const container = document.getElementById('admin-markets-container');
    if (!container) return;

    container.innerHTML = `
      <div class="loading-container">
        <div class="spinner spinner-lg"></div>
        <span>Retrieving market catalog records...</span>
      </div>
    `;

    try {
      const data = await api.get('/markets', { limit: 100 });
      const markets = (data && data.items) ? data.items : [];

      if (markets.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">🏛️</div>
            <h3 class="empty-state-title">No Mandis Registered</h3>
            <p class="empty-state-desc">APMC market catalog records will appear here once seeded or configured.</p>
          </div>
        `;
        return;
      }

      container.innerHTML = `
        <div class="card">
          <div class="card-header">
            <h3 style="font-size:var(--font-size-base);">Configured APMC Mandis (${markets.length})</h3>
          </div>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Market ID</th>
                  <th>Market Name</th>
                  <th>State</th>
                  <th>District</th>
                  <th>Code</th>
                  <th>Coordinates</th>
                </tr>
              </thead>
              <tbody>
                ${markets.map(m => `
                  <tr>
                    <td>#${m.id}</td>
                    <td><strong>${Utils.escapeHTML(m.name)}</strong></td>
                    <td>${Utils.escapeHTML(m.state)}</td>
                    <td>${Utils.escapeHTML(m.district)}</td>
                    <td><code>${Utils.escapeHTML(m.code || '—')}</code></td>
                    <td>${m.latitude && m.longitude ? `${m.latitude}, ${m.longitude}` : '—'}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `;
    } catch (err) {
      container.innerHTML = `
        <div class="alert alert-error">
          <span>⚠️</span>
          <div>${Utils.escapeHTML(err.message)}</div>
        </div>
      `;
    }
  },

  /**
   * Load system reports & export tools: admin-reports.html
   */
  async loadReports() {
    Navigation.renderDashboardShell('ADMIN', 'reports', 'System Reports & Data Export');

    const container = document.getElementById('admin-reports-container');
    if (!container) return;

    container.innerHTML = `
      <div class="grid grid-cols-2 gap-6">
        <div class="card">
          <div class="card-header">
            <h3 style="font-size:var(--font-size-base);">Export Transactions Dataset</h3>
          </div>
          <div class="card-body">
            <p style="font-size:var(--font-size-sm); color:var(--color-secondary-text); margin-bottom:var(--spacing-4);">
              Download a complete JSON export of all trade records and net realization breakdowns for audit and analytical reporting.
            </p>
            <button class="btn btn-outline" onclick="Admin.exportData('transactions')">
              📥 Export Transactions JSON
            </button>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3 style="font-size:var(--font-size-base);">Export User Directory</h3>
          </div>
          <div class="card-body">
            <p style="font-size:var(--font-size-sm); color:var(--color-secondary-text); margin-bottom:var(--spacing-4);">
              Export current farmer profiles and registered buyer entities to a structured JSON file.
            </p>
            <button class="btn btn-outline" onclick="Admin.exportData('users')">
              📥 Export Users JSON
            </button>
          </div>
        </div>
      </div>
    `;
  },

  async exportData(type) {
    try {
      Utils.showToast(`Preparing ${type} export...`, 'info');
      let data;
      if (type === 'transactions') {
        data = await api.get('/admin/transactions', { limit: 100 });
      } else {
        const [farmers, buyers] = await Promise.all([
          api.get('/admin/farmers', { limit: 100 }),
          api.get('/admin/buyers', { limit: 100 }),
        ]);
        data = { farmers, buyers };
      }

      const jsonStr = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `FarmerLinkage_${type}_export_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      URL.revokeObjectURL(url);
      a.remove();
      Utils.showToast('Export file downloaded successfully!', 'success');
    } catch (err) {
      Utils.showToast(err.message || 'Export failed.', 'error');
    }
  }
};
