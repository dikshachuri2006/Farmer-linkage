/**
 * FarmerLinkage — Buyer Module Logic
 * Manages buyer dashboard statistics, business profile & verification, and buyer offers.
 */
const Buyer = {
  /**
   * Load Buyer Dashboard Overview: buyer.html
   */
  async loadDashboard() {
    Navigation.renderDashboardShell('BUYER', 'dashboard', 'Buyer Dashboard');

    const statsGrid = document.getElementById('buyer-stats-grid');
    const recentOffersEl = document.getElementById('buyer-recent-offers');
    const recentTxnsEl = document.getElementById('buyer-recent-txns');

    try {
      // 1. Fetch buyer's submitted offers
      const offersData = await api.get('/buyer/offers', { limit: 50 });
      const offers = (offersData && offersData.items) ? offersData.items : [];
      const totalSubmitted = offersData ? offersData.total : offers.length;
      const pendingOffers = offers.filter(o => o.status === 'PENDING').length;
      const acceptedOffers = offers.filter(o => o.status === 'ACCEPTED').length;

      // 2. Fetch transactions for buyer
      let completedTxns = 0;
      let txns = [];
      try {
        const txnData = await api.get('/transactions', { limit: 50 });
        txns = (txnData && txnData.items) ? txnData.items : [];
        completedTxns = txns.filter(t => t.transaction_status === 'COMPLETED' || t.transaction_status === 'DELIVERED').length;
      } catch {
        // Transactions schema optional
      }

      // 3. Render stats
      if (statsGrid) {
        statsGrid.innerHTML = `
          <div class="stat-card">
            <div class="stat-icon green">🏷️</div>
            <div class="stat-info">
              <div class="stat-value">${totalSubmitted}</div>
              <div class="stat-label">Submitted Offers</div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon amber">⏳</div>
            <div class="stat-info">
              <div class="stat-value">${pendingOffers}</div>
              <div class="stat-label">Pending Acceptance</div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon blue">🤝</div>
            <div class="stat-info">
              <div class="stat-value">${acceptedOffers}</div>
              <div class="stat-label">Accepted Agreements</div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon purple">📑</div>
            <div class="stat-info">
              <div class="stat-value">${completedTxns}</div>
              <div class="stat-label">Completed Orders</div>
            </div>
          </div>
        `;
      }

      // 4. Render recent offers
      if (recentOffersEl) {
        if (offers.length === 0) {
          recentOffersEl.innerHTML = `
            <div class="empty-state" style="margin: var(--spacing-4) 0;">
              <div class="empty-state-icon">🛒</div>
              <h4 class="empty-state-title">No Purchase Offers Yet</h4>
              <p class="empty-state-desc">Explore available produce lots in the marketplace and submit direct offers.</p>
              <a href="marketplace.html" class="btn btn-sm btn-primary">Browse Marketplace</a>
            </div>
          `;
        } else {
          recentOffersEl.innerHTML = `
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Offer ID</th>
                    <th>Lot ID</th>
                    <th>Offered Rate</th>
                    <th>Requested Qty</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${offers.slice(0, 5).map(o => `
                    <tr>
                      <td>#${o.id}</td>
                      <td>Lot #${o.lot_id}</td>
                      <td style="font-weight:700; color:var(--color-deep-green);">₹${Number(o.offered_price_per_unit).toFixed(2)}</td>
                      <td>${o.quantity_requested} ${Utils.escapeHTML(o.quantity_unit || '')}</td>
                      <td>${Utils.getStatusBadge(o.status)}</td>
                      <td>
                        <a href="buyer-offers.html" class="btn btn-sm btn-outline">Details</a>
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          `;
        }
      }

      // 5. Render recent transactions
      if (recentTxnsEl) {
        if (txns.length === 0) {
          recentTxnsEl.innerHTML = `
            <div class="empty-state" style="margin: var(--spacing-4) 0;">
              <div class="empty-state-icon">📑</div>
              <h4 class="empty-state-title">No Trade Transactions</h4>
              <p class="empty-state-desc">Digital transactions appear here once a farmer accepts your offer.</p>
            </div>
          `;
        } else {
          recentTxnsEl.innerHTML = `
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Txn ID</th>
                    <th>Crop</th>
                    <th>Agreed Value</th>
                    <th>Fulfillment</th>
                    <th>Payment</th>
                  </tr>
                </thead>
                <tbody>
                  ${txns.slice(0, 5).map(t => `
                    <tr>
                      <td><strong>${Utils.escapeHTML(t.transaction_id || '#' + t.id)}</strong></td>
                      <td>${Utils.escapeHTML(t.crop_name || 'Produce')}</td>
                      <td>₹${Number(t.net_amount || t.gross_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                      <td>${Utils.getStatusBadge(t.transaction_status)}</td>
                      <td>${Utils.getStatusBadge(t.payment_status)}</td>
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
            <div><strong>Unable to load buyer overview:</strong> ${Utils.escapeHTML(err.message)}</div>
          </div>
        `;
      }
    }
  },

  /**
   * Load Buyer Profile & Verification Status: buyer-profile.html
   */
  async loadProfile() {
    Navigation.renderDashboardShell('BUYER', 'profile', 'Buyer Profile');

    const form = document.getElementById('buyer-profile-form');
    const verifForm = document.getElementById('buyer-verif-form');
    const statusChip = document.getElementById('buyer-verification-chip');
    const alertBox = document.getElementById('buyer-profile-alert');
    const successBox = document.getElementById('buyer-profile-success');

    try {
      const profile = await api.get('/buyer/profile');
      if (profile) {
        if (statusChip) {
          statusChip.innerHTML = Utils.getStatusBadge(profile.verification_status || 'PENDING');
        }
        document.getElementById('buyer-bus-name').value = profile.business_name || '';
        document.getElementById('buyer-bus-type').value = profile.business_type || 'WHOLESALER';
        document.getElementById('buyer-license').value = profile.license_number || '';
        document.getElementById('buyer-address').value = profile.market_address || '';
      }
    } catch (err) {
      if (err.status !== 404) {
        alertBox.style.display = 'flex';
        alertBox.innerHTML = `<span>⚠️</span><div>${Utils.escapeHTML(err.message)}</div>`;
      }
    }

    // Profile update submission
    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        Utils.clearFormErrors(form);
        alertBox.style.display = 'none';
        successBox.style.display = 'none';

        const nameInput = document.getElementById('buyer-bus-name');
        const typeInput = document.getElementById('buyer-bus-type');
        const licInput = document.getElementById('buyer-license');
        const addrInput = document.getElementById('buyer-address');
        const submitBtn = document.getElementById('btn-save-buyer-profile');

        let isValid = true;
        if (!nameInput.value.trim()) {
          Utils.showFieldError(nameInput, 'Business name is required.');
          isValid = false;
        }
        if (!licInput.value.trim()) {
          Utils.showFieldError(licInput, 'Mandatory Trade/APMC License or GSTIN is required.');
          isValid = false;
        }
        if (!addrInput.value.trim()) {
          Utils.showFieldError(addrInput, 'Market / Commercial address is required.');
          isValid = false;
        }

        if (!isValid) return;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Saving profile...';

        const payload = {
          business_name: nameInput.value.trim(),
          business_type: typeInput.value,
          license_number: licInput.value.trim(),
          market_address: addrInput.value.trim(),
        };

        try {
          const updated = await api.put('/buyer/profile', payload);
          submitBtn.disabled = false;
          submitBtn.textContent = 'Save Profile Details';
          successBox.style.display = 'flex';
          successBox.innerHTML = '<span>✅</span><div>Buyer profile details updated successfully.</div>';
          Utils.showToast('Profile updated!', 'success');
        } catch (err) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Save Profile Details';
          alertBox.style.display = 'flex';
          alertBox.innerHTML = `<span>⚠️</span><div>${Utils.escapeHTML(err.message || 'Unable to update buyer profile.')}</div>`;
        }
      });
    }

    // Official Verification Request submission
    if (verifForm) {
      verifForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        Utils.clearFormErrors(verifForm);

        const licInput = document.getElementById('verif-license');
        const nameInput = document.getElementById('verif-name');
        const typeInput = document.getElementById('verif-type');
        const addrInput = document.getElementById('verif-address');
        const notesInput = document.getElementById('verif-notes');
        const submitBtn = document.getElementById('btn-submit-verification');

        let isValid = true;
        if (!licInput.value.trim()) {
          Utils.showFieldError(licInput, 'Trade License is required for verification.');
          isValid = false;
        }
        if (!nameInput.value.trim()) {
          Utils.showFieldError(nameInput, 'Business name is required.');
          isValid = false;
        }
        if (!addrInput.value.trim()) {
          Utils.showFieldError(addrInput, 'Address is required.');
          isValid = false;
        }

        if (!isValid) return;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Submitting verification request...';

        const payload = {
          license_number: licInput.value.trim(),
          business_name: nameInput.value.trim(),
          business_type: typeInput.value,
          market_address: addrInput.value.trim(),
          verification_notes: notesInput.value.trim() || undefined,
        };

        try {
          const res = await api.post('/buyer/verification', payload);
          submitBtn.disabled = false;
          submitBtn.textContent = 'Submit Verification Request';
          Utils.closeModal('verification-modal');
          Utils.showToast('Verification request submitted for Administrator review!', 'success');
          setTimeout(() => location.reload(), 1200);
        } catch (err) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Submit Verification Request';
          Utils.showToast(err.message || 'Verification submission failed.', 'error');
        }
      });
    }
  },

  /**
   * Load Buyer Offers: buyer-offers.html
   */
  async loadBuyerOffers() {
    Navigation.renderDashboardShell('BUYER', 'offers', 'My Submitted Offers');

    const container = document.getElementById('buyer-offers-container');
    if (!container) return;

    container.innerHTML = `
      <div class="loading-container">
        <div class="spinner spinner-lg"></div>
        <span>Retrieving your purchase offers...</span>
      </div>
    `;

    try {
      const data = await api.get('/buyer/offers', { limit: 100 });
      const offers = (data && data.items) ? data.items : [];

      if (offers.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">🛒</div>
            <h3 class="empty-state-title">No Submitted Offers</h3>
            <p class="empty-state-desc">You have not submitted any purchase offers on marketplace produce lots yet.</p>
            <a href="marketplace.html" class="btn btn-primary">Browse Marketplace Lots</a>
          </div>
        `;
        return;
      }

      container.innerHTML = `
        <div class="card">
          <div class="card-header">
            <h3 style="font-size:var(--font-size-base);">Your Submitted Offers (${offers.length})</h3>
            <a href="marketplace.html" class="btn btn-sm btn-primary">Browse More Produce</a>
          </div>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Offer ID</th>
                  <th>Lot ID</th>
                  <th>Offered Rate</th>
                  <th>Requested Quantity</th>
                  <th>Pickup / Delivery</th>
                  <th>Submitted Date</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                ${offers.map(o => `
                  <tr>
                    <td>#${o.id}</td>
                    <td>
                      <a href="listing-details.html?id=${o.lot_id}" style="font-weight:600;">Lot #${o.lot_id}</a>
                    </td>
                    <td>
                      <span style="font-weight:700; color:var(--color-deep-green);">₹${Number(o.offered_price_per_unit).toFixed(2)}</span>
                      <span style="font-size:0.75rem; color:var(--color-secondary-text);">${Utils.escapeHTML(o.price_unit || '')}</span>
                    </td>
                    <td>${o.quantity_requested} ${Utils.escapeHTML(o.quantity_unit || '')}</td>
                    <td>${o.pickup_from_farm ? '🚜 Farmgate Pickup' : Utils.escapeHTML(o.delivery_location || 'Delivery')}</td>
                    <td>${Utils.formatDate(o.created_at)}</td>
                    <td>${Utils.getStatusBadge(o.status)}</td>
                    <td>
                      ${o.status === 'PENDING' ? `
                        <button class="btn btn-sm btn-danger" onclick="Buyer.withdrawOffer(${o.id})">
                          Withdraw
                        </button>
                      ` : o.status === 'ACCEPTED' ? `
                        <a href="transactions.html" class="btn btn-sm btn-primary">View Trade</a>
                      ` : `
                        <span style="font-size:var(--font-size-xs); color:var(--color-secondary-text);">Closed</span>
                      `}
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
   * Withdraw submitted offer: DELETE /api/buyer/offers/{offer_id}
   */
  async withdrawOffer(offerId) {
    if (!confirm('Are you sure you want to withdraw this purchase offer?')) {
      return;
    }

    try {
      await api.delete(`/buyer/offers/${offerId}`);
      Utils.showToast('Purchase offer withdrawn successfully.', 'success');
      this.loadBuyerOffers();
    } catch (err) {
      Utils.showToast(err.message || 'Unable to withdraw offer.', 'error');
    }
  }
};
