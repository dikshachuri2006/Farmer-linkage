/**
 * FarmerLinkage — Transactions & Settlement Module
 * Manages digital trade records, fulfillment status transitions, and PDF receipt downloads.
 */
const Transactions = {
  transactions: [],

  async loadTransactions() {
    const user = Auth.getUser();
    if (!user) return;

    // Render dashboard shell according to role
    Navigation.renderDashboardShell(user.role, 'transactions', 'Digital Trade Transactions');

    const container = document.getElementById('transactions-container');
    if (!container) return;

    container.innerHTML = `
      <div class="loading-container">
        <div class="spinner spinner-lg"></div>
        <span>Retrieving digital trade records...</span>
      </div>
    `;

    try {
      const endpoint = user.role === 'ADMIN' ? '/admin/transactions' : '/transactions';
      const data = await api.get(endpoint, { limit: 100 });
      this.transactions = (data && data.items) ? data.items : [];
      this.renderTable(this.transactions);
    } catch (err) {
      container.innerHTML = `
        <div class="alert alert-error">
          <span>⚠️</span>
          <div>${Utils.escapeHTML(err.message)}</div>
        </div>
      `;
    }
  },

  renderTable(items) {
    const container = document.getElementById('transactions-container');
    if (!container) return;

    if (!items || items.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📑</div>
          <h3 class="empty-state-title">No Digital Transactions Recorded</h3>
          <p class="empty-state-desc">Transactions are generated once a farmer accepts a purchase offer or an agreement is formalized.</p>
        </div>
      `;
      return;
    }

    const user = Auth.getUser();
    const isFarmer = user && user.role === 'FARMER';
    const isBuyer = user && user.role === 'BUYER';
    const isAdmin = user && user.role === 'ADMIN';

    container.innerHTML = `
      <div class="card">
        <div class="card-header">
          <h3 style="font-size:var(--font-size-base);">Electronic Settlement Records (${items.length})</h3>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Receipt Reference</th>
                <th>Produce Commodity</th>
                <th>Quantity</th>
                <th>Net Payable Value</th>
                <th>Trade Status</th>
                <th>Payment</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${items.map(t => {
                const code = t.transaction_id || `TXN-${t.id}`;
                const crop = t.crop_name || 'Produce';
                const qty = `${t.quantity} ${Utils.escapeHTML(t.quantity_unit || '')}`;
                const net = Number(t.net_amount || t.gross_amount || 0);
                const canDownloadReceipt = true;

                return `
                  <tr>
                    <td><strong>${Utils.escapeHTML(code)}</strong></td>
                    <td>${Utils.escapeHTML(crop)}</td>
                    <td>${qty}</td>
                    <td style="font-weight:700; color:var(--color-deep-green);">
                      ₹${net.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td>${Utils.getStatusBadge(t.transaction_status)}</td>
                    <td>${Utils.getStatusBadge(t.payment_status)}</td>
                    <td>${Utils.formatDate(t.created_at)}</td>
                    <td>
                      <div style="display:flex; gap:var(--spacing-2); flex-wrap:wrap;">
                        <button class="btn btn-sm btn-outline" onclick="Transactions.downloadReceipt(${t.id}, '${code}')">
                          📥 Receipt PDF
                        </button>
                        ${isFarmer && t.transaction_status === 'CONFIRMED' ? `
                          <button class="btn btn-sm btn-primary" onclick="Transactions.updateStatus(${t.id}, 'IN_TRANSIT', null)">
                            Mark In-Transit
                          </button>
                        ` : ''}
                        ${isBuyer && t.transaction_status === 'IN_TRANSIT' ? `
                          <button class="btn btn-sm btn-primary" onclick="Transactions.updateStatus(${t.id}, 'DELIVERED', null)">
                            Confirm Delivery
                          </button>
                        ` : ''}
                        ${isBuyer && t.payment_status === 'PENDING' ? `
                          <button class="btn btn-sm btn-secondary" onclick="Transactions.updateStatus(${t.id}, null, 'PAYMENT_INITIATED')">
                            Initiate Payment
                          </button>
                        ` : ''}
                      </div>
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  },

  /**
   * Download formal trade settlement PDF receipt: GET /api/transactions/{transaction_id}/receipt
   */
  async downloadReceipt(transactionId, code) {
    try {
      Utils.showToast(`Generating certified PDF receipt for ${code}...`, 'info');
      await api.downloadFile(`/transactions/${transactionId}/receipt`, `FarmerLinkage_Receipt_${code}.pdf`);
      Utils.showToast(`Receipt downloaded successfully!`, 'success');
    } catch (err) {
      Utils.showToast(err.message || 'Unable to download receipt.', 'error');
    }
  },

  /**
   * Update transaction fulfillment or payment status: PUT /api/transactions/{transaction_id}/status
   */
  async updateStatus(transactionId, newTransStatus, newPayStatus) {
    const payload = {};
    if (newTransStatus) payload.transaction_status = newTransStatus;
    if (newPayStatus) payload.payment_status = newPayStatus;

    try {
      await api.put(`/transactions/${transactionId}/status`, payload);
      Utils.showToast('Transaction status updated successfully!', 'success');
      this.loadTransactions();
    } catch (err) {
      Utils.showToast(err.message || 'Failed to update transaction status.', 'error');
    }
  }
};
