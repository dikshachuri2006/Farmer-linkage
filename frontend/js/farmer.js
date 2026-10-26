/**
 * FarmerLinkage — Farmer Module Logic
 * Manages dashboard metrics, profile, lots/produce creation & management, and received offer actions.
 */
const Farmer = {
  /**
   * Load Farmer Dashboard Overview metrics and recent activity: farmer.html
   */
  async loadDashboard() {
    Navigation.renderDashboardShell('FARMER', 'dashboard', 'Farmer Dashboard');

    const statsGrid = document.getElementById('farmer-stats-grid');
    const recentLotsEl = document.getElementById('farmer-recent-lots');
    const recentOffersEl = document.getElementById('farmer-recent-offers');

    try {
      // 1. Fetch lots
      const lotsData = await api.get('/farmer/lots', { limit: 50 });
      const lots = (lotsData && lotsData.items) ? lotsData.items : [];
      const totalListings = lotsData ? lotsData.total : lots.length;
      const activeListings = lots.filter(l => l.status === 'AVAILABLE').length;

      // 2. Fetch transactions for farmer
      let completedTxns = 0;
      try {
        const txnData = await api.get('/transactions', { limit: 50 });
        const txns = (txnData && txnData.items) ? txnData.items : [];
        completedTxns = txns.filter(t => t.transaction_status === 'COMPLETED' || t.transaction_status === 'DELIVERED').length;
      } catch {
        // Transactions schema may be pending or empty
      }

      // 3. Collect pending offers count across available lots
      let pendingOffersCount = 0;
      const recentOffersList = [];
      for (const lot of lots.slice(0, 5)) {
        try {
          const offers = await api.get(`/farmer/lots/${lot.id}/offers`);
          if (Array.isArray(offers)) {
            pendingOffersCount += offers.filter(o => o.status === 'PENDING').length;
            offers.forEach(o => recentOffersList.push({ ...o, lotCrop: lot.crop_name, lotUnit: lot.quantity_unit }));
          }
        } catch {
          // ignore individual lot offer lookup failures
        }
      }

      if (statsGrid) {
        statsGrid.innerHTML = `
          <div class="stat-card">
            <div class="stat-icon green">🌾</div>
            <div class="stat-info">
              <div class="stat-value">${totalListings}</div>
              <div class="stat-label">Total Produce Lots</div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon blue">✨</div>
            <div class="stat-info">
              <div class="stat-value">${activeListings}</div>
              <div class="stat-label">Active Listings</div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon amber">📩</div>
            <div class="stat-info">
              <div class="stat-value">${pendingOffersCount}</div>
              <div class="stat-label">Pending Buyer Offers</div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon purple">📑</div>
            <div class="stat-info">
              <div class="stat-value">${completedTxns}</div>
              <div class="stat-label">Completed Trades</div>
            </div>
          </div>
        `;
      }

      if (recentLotsEl) {
        if (lots.length === 0) {
          recentLotsEl.innerHTML = `
            <div class="empty-state" style="margin: var(--spacing-4) 0;">
              <div class="empty-state-icon">🌱</div>
              <h4 class="empty-state-title">No Produce Listed Yet</h4>
              <p class="empty-state-desc">Post your harvest to start receiving verified buyer purchase bids.</p>
              <a href="add-produce.html" class="btn btn-sm btn-primary">Add Your First Lot</a>
            </div>
          `;
        } else {
          recentLotsEl.innerHTML = `
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Crop</th>
                    <th>Quantity</th>
                    <th>Asking Rate</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${lots.slice(0, 5).map(lot => `
                    <tr>
                      <td><strong>${Utils.escapeHTML(lot.crop_name)}</strong></td>
                      <td>${lot.quantity} ${Utils.escapeHTML(lot.quantity_unit)}</td>
                      <td>₹${Number(lot.expected_price_per_unit).toFixed(2)}</td>
                      <td>${Utils.getStatusBadge(lot.status)}</td>
                      <td>
                        <a href="listing-details.html?id=${lot.id}" class="btn btn-sm btn-outline">View</a>
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          `;
        }
      }

      if (recentOffersEl) {
        if (recentOffersList.length === 0) {
          recentOffersEl.innerHTML = `
            <div class="empty-state" style="margin: var(--spacing-4) 0;">
              <div class="empty-state-icon">📩</div>
              <h4 class="empty-state-title">No Received Offers</h4>
              <p class="empty-state-desc">Buyer offers submitted on your active lots will appear here for review.</p>
            </div>
          `;
        } else {
          recentOffersEl.innerHTML = `
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Produce Lot</th>
                    <th>Offered Rate</th>
                    <th>Requested Qty</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${recentOffersList.slice(0, 5).map(o => `
                    <tr>
                      <td><strong>${Utils.escapeHTML(o.lotCrop || 'Produce')}</strong></td>
                      <td style="font-weight:700; color:var(--color-deep-green);">₹${Number(o.offered_price_per_unit).toFixed(2)}</td>
                      <td>${o.quantity_requested} ${Utils.escapeHTML(o.lotUnit || '')}</td>
                      <td>${Utils.getStatusBadge(o.status)}</td>
                      <td>
                        <a href="farmer-offers.html" class="btn btn-sm btn-primary">Review</a>
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
            <div><strong>Unable to load dashboard metrics:</strong> ${Utils.escapeHTML(err.message)}</div>
          </div>
        `;
      }
    }
  },

  /**
   * Load and save farmer profile: farmer-profile.html
   */
  async loadProfile() {
    Navigation.renderDashboardShell('FARMER', 'profile', 'Farmer Profile');

    const form = document.getElementById('farmer-profile-form');
    const alertBox = document.getElementById('profile-alert');
    const successBox = document.getElementById('profile-success');

    try {
      const profile = await api.get('/farmer/profile');
      if (profile) {
        document.getElementById('profile-state').value = profile.state || '';
        document.getElementById('profile-district').value = profile.district || '';
        document.getElementById('profile-taluka').value = profile.taluka || '';
        document.getElementById('profile-village').value = profile.village || '';
        document.getElementById('profile-pincode').value = profile.pincode || '';
        document.getElementById('profile-land-area').value = profile.land_area_acres || '';
      }
    } catch (err) {
      // 404 indicates profile not yet initialized; user can fill in creation form
      if (err.status !== 404) {
        alertBox.style.display = 'flex';
        alertBox.innerHTML = `<span>⚠️</span><div>${Utils.escapeHTML(err.message)}</div>`;
      }
    }

    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        Utils.clearFormErrors(form);
        alertBox.style.display = 'none';
        successBox.style.display = 'none';

        const stateInput = document.getElementById('profile-state');
        const distInput = document.getElementById('profile-district');
        const pinInput = document.getElementById('profile-pincode');
        const talukaInput = document.getElementById('profile-taluka');
        const villageInput = document.getElementById('profile-village');
        const landInput = document.getElementById('profile-land-area');
        const submitBtn = document.getElementById('save-profile-btn');

        let isValid = true;
        if (!stateInput.value.trim()) {
          Utils.showFieldError(stateInput, 'State is required.');
          isValid = false;
        }
        if (!distInput.value.trim()) {
          Utils.showFieldError(distInput, 'District is required.');
          isValid = false;
        }
        if (!pinInput.value.trim() || !/^\d{6}$/.test(pinInput.value.trim())) {
          Utils.showFieldError(pinInput, 'A valid 6-digit postal pincode is required.');
          isValid = false;
        }

        if (!isValid) return;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Saving profile...';

        const payload = {
          state: stateInput.value.trim(),
          district: distInput.value.trim(),
          pincode: pinInput.value.trim(),
          taluka: talukaInput.value.trim() || undefined,
          village: villageInput.value.trim() || undefined,
          land_area_acres: landInput.value ? Number(landInput.value) : undefined,
        };

        try {
          const updated = await api.put('/farmer/profile', payload);
          submitBtn.disabled = false;
          submitBtn.textContent = 'Save Profile Changes';
          successBox.style.display = 'flex';
          successBox.innerHTML = '<span>✅</span><div>Your farmer profile details have been saved successfully.</div>';
          Utils.showToast('Profile updated successfully!', 'success');
        } catch (err) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Save Profile Changes';
          alertBox.style.display = 'flex';
          alertBox.innerHTML = `<span>⚠️</span><div>${Utils.escapeHTML(err.message || 'Failed to update profile.')}</div>`;
        }
      });
    }
  },

  /**
   * Load farmer produce listings: farmer-produce.html
   */
  async loadProduceList() {
    Navigation.renderDashboardShell('FARMER', 'produce', 'My Produce Lots');

    const container = document.getElementById('farmer-produce-container');
    if (!container) return;

    container.innerHTML = `
      <div class="loading-container">
        <div class="spinner spinner-lg"></div>
        <span>Loading your produce lots...</span>
      </div>
    `;

    try {
      const data = await api.get('/farmer/lots', { limit: 100 });
      const lots = (data && data.items) ? data.items : [];

      if (lots.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">🌾</div>
            <h3 class="empty-state-title">No Produce Lots Listed</h3>
            <p class="empty-state-desc">You have not created any produce lots yet. Post your harvest to receive buyer bids.</p>
            <a href="add-produce.html" class="btn btn-primary">➕ Add Produce Lot</a>
          </div>
        `;
        return;
      }

      container.innerHTML = `
        <div class="card">
          <div class="card-header">
            <h3 style="font-size:var(--font-size-base);">Your Active & Past Produce Lots (${lots.length})</h3>
            <a href="add-produce.html" class="btn btn-sm btn-primary">➕ Add New Lot</a>
          </div>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Lot ID</th>
                  <th>Crop</th>
                  <th>Quantity</th>
                  <th>Asking Rate</th>
                  <th>Quality Grade</th>
                  <th>Location</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                ${lots.map(lot => `
                  <tr>
                    <td>#${lot.id}</td>
                    <td><strong>${Utils.escapeHTML(lot.crop_name)}</strong></td>
                    <td>${lot.quantity} ${Utils.escapeHTML(lot.quantity_unit)}</td>
                    <td>₹${Number(lot.expected_price_per_unit).toFixed(2)}</td>
                    <td><span class="badge badge-neutral">${Utils.escapeHTML(lot.quality_grade || 'Standard')}</span></td>
                    <td>${Utils.escapeHTML([lot.district, lot.state].filter(Boolean).join(', ') || 'Farmgate')}</td>
                    <td>${Utils.getStatusBadge(lot.status)}</td>
                    <td>
                      <div style="display:flex; gap:var(--spacing-2);">
                        <a href="listing-details.html?id=${lot.id}" class="btn btn-sm btn-outline">View</a>
                        ${lot.status === 'AVAILABLE' ? `
                          <button class="btn btn-sm btn-danger" onclick="Farmer.withdrawLot(${lot.id})">Withdraw</button>
                        ` : ''}
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
   * Withdraw own lot: DELETE /api/farmer/lots/{lot_id}
   */
  async withdrawLot(lotId) {
    if (!confirm('Are you sure you want to withdraw this produce listing? This will deactivate the lot from the marketplace.')) {
      return;
    }

    try {
      await api.delete(`/farmer/lots/${lotId}`);
      Utils.showToast('Produce lot withdrawn successfully.', 'success');
      this.loadProduceList();
    } catch (err) {
      Utils.showToast(err.message || 'Unable to withdraw lot.', 'error');
    }
  },

  /**
   * Add Produce page logic: add-produce.html
   */
  async initAddProduce() {
    Navigation.renderDashboardShell('FARMER', 'add-produce', 'Add Produce Lot');

    const form = document.getElementById('add-produce-form');
    const cropSelect = document.getElementById('lot-crop-id');
    const alertBox = document.getElementById('add-produce-alert');

    // 1. Load crops catalog
    try {
      const cropsData = await api.get('/crops', { limit: 100 });
      if (cropsData && cropsData.items) {
        cropSelect.innerHTML = '<option value="">Select Crop / Commodity *</option>' +
          cropsData.items.map(c => `<option value="${c.id}" data-name="${Utils.escapeHTML(c.name)}">${Utils.escapeHTML(c.name)} (${Utils.escapeHTML(c.category)})</option>`).join('');
      }
    } catch (err) {
      console.warn('Unable to populate crops catalog:', err);
    }

    // 2. Pre-fill farmer location from profile if available
    try {
      const profile = await api.get('/farmer/profile');
      if (profile) {
        if (profile.state) document.getElementById('lot-state').value = profile.state;
        if (profile.district) document.getElementById('lot-district').value = profile.district;
        if (profile.taluka) document.getElementById('lot-taluka').value = profile.taluka;
        if (profile.village) document.getElementById('lot-village').value = profile.village;
      }
    } catch {
      // Profile pre-fill optional
    }

    // 3. Handle submission
    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        Utils.clearFormErrors(form);
        alertBox.style.display = 'none';

        const cropOpt = cropSelect.options[cropSelect.selectedIndex];
        const cropId = cropSelect.value;
        const cropName = cropOpt ? cropOpt.getAttribute('data-name') : '';
        const qtyVal = Number(document.getElementById('lot-quantity').value);
        const qtyUnit = document.getElementById('lot-quantity-unit').value;
        const gradeVal = document.getElementById('lot-grade').value;
        const priceVal = Number(document.getElementById('lot-price').value);
        const priceUnit = document.getElementById('lot-price-unit').value;
        const harvestDate = document.getElementById('lot-harvest-date').value;
        const stateVal = document.getElementById('lot-state').value.trim();
        const distVal = document.getElementById('lot-district').value.trim();
        const talukaVal = document.getElementById('lot-taluka').value.trim();
        const villageVal = document.getElementById('lot-village').value.trim();
        const descVal = document.getElementById('lot-description').value.trim();
        const submitBtn = document.getElementById('btn-submit-lot');

        let isValid = true;
        if (!cropId) {
          Utils.showFieldError(cropSelect, 'Please select a crop.');
          isValid = false;
        }
        if (!qtyVal || qtyVal <= 0) {
          Utils.showFieldError(document.getElementById('lot-quantity'), 'Quantity must be greater than zero.');
          isValid = false;
        }
        if (!priceVal || priceVal <= 0) {
          Utils.showFieldError(document.getElementById('lot-price'), 'Expected price must be greater than zero.');
          isValid = false;
        }
        if (!stateVal) {
          Utils.showFieldError(document.getElementById('lot-state'), 'State is required.');
          isValid = false;
        }
        if (!distVal) {
          Utils.showFieldError(document.getElementById('lot-district'), 'District is required.');
          isValid = false;
        }

        if (!isValid) return;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Publishing produce lot...';

        const payload = {
          crop_id: Number(cropId),
          crop_name: cropName,
          quantity: qtyVal,
          quantity_unit: qtyUnit,
          quality_grade: gradeVal,
          expected_price_per_unit: priceVal,
          price_unit: priceUnit,
          harvest_date: harvestDate || new Date().toISOString().split('T')[0],
          state: stateVal,
          district: distVal,
          taluka: talukaVal || undefined,
          village: villageVal || undefined,
          description: descVal || undefined,
        };

        try {
          const created = await api.post('/farmer/lots', payload);
          Utils.showToast('Produce lot published to marketplace successfully!', 'success');
          setTimeout(() => {
            window.location.href = 'farmer-produce.html';
          }, 1000);
        } catch (err) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Publish Produce Lot';
          alertBox.style.display = 'flex';
          alertBox.innerHTML = `<span>⚠️</span><div>${Utils.escapeHTML(err.message || 'Unable to publish lot.')}</div>`;
        }
      });
    }
  },

  /**
   * Load Received Offers on farmer's produce: farmer-offers.html
   */
  async loadReceivedOffers() {
    Navigation.renderDashboardShell('FARMER', 'offers', 'Received Offers');

    const container = document.getElementById('farmer-offers-container');
    if (!container) return;

    container.innerHTML = `
      <div class="loading-container">
        <div class="spinner spinner-lg"></div>
        <span>Scanning offers across your produce lots...</span>
      </div>
    `;

    try {
      const lotsData = await api.get('/farmer/lots', { limit: 100 });
      const lots = (lotsData && lotsData.items) ? lotsData.items : [];

      if (lots.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">🌾</div>
            <h3 class="empty-state-title">No Produce Lots Available</h3>
            <p class="empty-state-desc">You need to create produce lots before commercial buyers can submit offers.</p>
            <a href="add-produce.html" class="btn btn-primary">➕ Add Produce Lot</a>
          </div>
        `;
        return;
      }

      // Collect offers for all farmer lots
      const allOffers = [];
      for (const lot of lots) {
        try {
          const offers = await api.get(`/farmer/lots/${lot.id}/offers`);
          if (Array.isArray(offers)) {
            offers.forEach(o => {
              allOffers.push({ ...o, lot: lot });
            });
          }
        } catch {
          // ignore individual lookup
        }
      }

      if (allOffers.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">📩</div>
            <h3 class="empty-state-title">No Received Offers Yet</h3>
            <p class="empty-state-desc">When verified buyers browse your produce and make purchase bids, they will appear here.</p>
            <a href="farmer-produce.html" class="btn btn-outline">View My Produce Lots</a>
          </div>
        `;
        return;
      }

      container.innerHTML = `
        <div class="card">
          <div class="card-header">
            <h3 style="font-size:var(--font-size-base);">Offers on Your Produce Lots (${allOffers.length})</h3>
          </div>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Offer ID</th>
                  <th>Produce Lot</th>
                  <th>Buyer ID</th>
                  <th>Offered Price</th>
                  <th>Quantity</th>
                  <th>Pickup / Delivery</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                ${allOffers.map(o => `
                  <tr>
                    <td>#${o.id}</td>
                    <td><strong>${Utils.escapeHTML(o.lot.crop_name)}</strong> (Lot #${o.lot.id})</td>
                    <td>Buyer #${o.buyer_id}</td>
                    <td>
                      <span style="font-weight:700; color:var(--color-deep-green);">₹${Number(o.offered_price_per_unit).toFixed(2)}</span>
                      <span style="font-size:0.75rem; color:var(--color-secondary-text);">${Utils.escapeHTML(o.price_unit)}</span>
                    </td>
                    <td>${o.quantity_requested} ${Utils.escapeHTML(o.quantity_unit)}</td>
                    <td>${o.pickup_from_farm ? '🚜 Farmgate Pickup' : Utils.escapeHTML(o.delivery_location || 'Delivery')}</td>
                    <td>${Utils.getStatusBadge(o.status)}</td>
                    <td>
                      ${o.status === 'PENDING' ? `
                        <button class="btn btn-sm btn-primary" onclick="Farmer.acceptOffer(${o.id})">
                          Accept Offer
                        </button>
                      ` : `
                        <span style="font-size:var(--font-size-xs); color:var(--color-secondary-text);">Processed</span>
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
   * Accept an offer: POST /api/farmer/offers/{offer_id}/accept
   */
  async acceptOffer(offerId) {
    if (!confirm('Are you sure you want to accept this buyer offer? Accepting will commit your produce lot and generate an official trade agreement.')) {
      return;
    }

    try {
      const response = await api.post(`/farmer/offers/${offerId}/accept`);
      Utils.showToast('Offer accepted! Trade agreement and selling request generated.', 'success');
      setTimeout(() => {
        window.location.href = 'transactions.html';
      }, 1200);
    } catch (err) {
      Utils.showToast(err.message || 'Failed to accept offer.', 'error');
    }
  }
};
