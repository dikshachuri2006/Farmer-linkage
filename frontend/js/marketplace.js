/**
 * FarmerLinkage — Marketplace Logic
 * Produce discovery, filtering, listing details view, and buyer offer submission.
 */
const Marketplace = {
  crops: [],
  currentListings: [],

  /**
   * Load crops catalog for filter dropdown: GET /api/crops
   */
  async loadCrops() {
    const cropSelect = document.getElementById('filter-crop');
    if (!cropSelect) return;

    try {
      const data = await api.get('/crops', { limit: 100 });
      if (data && data.items) {
        this.crops = data.items;
        cropSelect.innerHTML = '<option value="">All Crops</option>' +
          data.items.map(c => `<option value="${c.id}">${Utils.escapeHTML(c.name)} (${Utils.escapeHTML(c.category)})</option>`).join('');
      }
    } catch (err) {
      // Catalog load failure is non-fatal
      console.warn('Crops catalog unavailable:', err);
    }
  },

  /**
   * Fetch produce listings: GET /api/marketplace/lots
   */
  async loadListings() {
    const grid = document.getElementById('produce-grid');
    if (!grid) return;

    const isAuth = Auth.isAuthenticated();
    if (!isAuth) {
      grid.innerHTML = `
        <div class="card" style="grid-column: 1 / -1; padding: var(--spacing-8); text-align: center; max-width: 600px; margin: 0 auto;">
          <div style="font-size: 3rem; margin-bottom: var(--spacing-2);">🔒</div>
          <h3 style="font-size: var(--font-size-xl); margin-bottom: var(--spacing-2);">Sign In to Discover Produce Listings</h3>
          <p style="color: var(--color-secondary-text); margin-bottom: var(--spacing-6);">
            To protect farmer farmgate locations and facilitate secure direct trade, available lots and counterparty discovery require an active account.
          </p>
          <div style="display: flex; justify-content: center; gap: var(--spacing-4);">
            <a href="login.html?redirect=marketplace.html" class="btn btn-primary">Sign In</a>
            <a href="register.html?role=BUYER" class="btn btn-outline">Register as Buyer</a>
          </div>
        </div>
      `;
      return;
    }

    grid.innerHTML = `
      <div class="loading-container" style="grid-column: 1 / -1;">
        <div class="spinner spinner-lg"></div>
        <span>Discovering available farmgate produce lots...</span>
      </div>
    `;

    // Extract active filters
    const cropId = document.getElementById('filter-crop')?.value;
    const state = document.getElementById('filter-state')?.value;
    const minPrice = document.getElementById('filter-min-price')?.value;
    const maxPrice = document.getElementById('filter-max-price')?.value;
    const grade = document.getElementById('filter-grade')?.value;

    const params = { limit: 50 };
    if (cropId) params.crop_id = cropId;
    if (state && state.trim()) params.state = state.trim();
    if (minPrice && Number(minPrice) >= 0) params.min_price = Number(minPrice);
    if (maxPrice && Number(maxPrice) >= 0) params.max_price = Number(maxPrice);
    if (grade) params.grade = grade;

    try {
      const data = await api.get('/marketplace/lots', params);
      this.currentListings = (data && data.items) ? data.items : [];
      this.renderListings(this.currentListings);
    } catch (err) {
      grid.innerHTML = `
        <div class="alert alert-error" style="grid-column: 1 / -1; max-width: 640px; margin: 0 auto;">
          <span>⚠️</span>
          <div>
            <strong>Unable to load marketplace listings:</strong> ${Utils.escapeHTML(err.message)}
          </div>
        </div>
      `;
    }
  },

  /**
   * Render listing cards
   */
  renderListings(items) {
    const grid = document.getElementById('produce-grid');
    if (!grid) return;

    if (!items || items.length === 0) {
      grid.innerHTML = `
        <div style="grid-column: 1 / -1;">
          ${Utils.renderEmptyState(
            '🌾',
            'No Available Produce Lots Found',
            'There are currently no active listings matching your filter criteria. Try clearing or expanding your filters.',
            '<button class="btn btn-sm btn-outline" onclick="Marketplace.clearFilters()">Clear Filters</button>'
          )}
        </div>
      `;
      return;
    }

    grid.innerHTML = items.map(lot => {
      const cropName = lot.crop_name || `Crop #${lot.crop_id}`;
      const qty = lot.quantity || 0;
      const unit = lot.quantity_unit || 'quintal';
      const price = lot.expected_price_per_unit || lot.price_per_unit || 0;
      const priceUnit = lot.price_unit || `INR/${unit}`;
      const location = [lot.district, lot.state].filter(Boolean).join(', ') || 'Farmgate';
      const grade = lot.quality_grade || 'Standard';

      return `
        <article class="produce-card">
          <div class="produce-card-top">
            <span class="produce-crop-icon">🌱</span>
            <div class="produce-card-status">
              ${Utils.getStatusBadge(lot.status || 'AVAILABLE')}
            </div>
          </div>
          <div class="produce-card-body">
            <h3 class="produce-card-title">${Utils.escapeHTML(cropName)}</h3>
            <div class="produce-card-subtitle">${Utils.escapeHTML(location)} • Grade: ${Utils.escapeHTML(grade)}</div>

            <div class="produce-meta-row">
              <span class="produce-meta-label">Quantity:</span>
              <span class="produce-meta-val">${qty} ${Utils.escapeHTML(unit)}</span>
            </div>
            <div class="produce-meta-row">
              <span class="produce-meta-label">Asking Rate:</span>
              <span class="produce-price-highlight">₹${Number(price).toFixed(2)}</span>
            </div>

            <div class="produce-card-footer">
              <a href="listing-details.html?id=${lot.id}" class="btn btn-primary btn-block">
                View Details
              </a>
            </div>
          </div>
        </article>
      `;
    }).join('');
  },

  /**
   * Clear all filters
   */
  clearFilters() {
    const cropSel = document.getElementById('filter-crop');
    const stateInput = document.getElementById('filter-state');
    const minP = document.getElementById('filter-min-price');
    const maxP = document.getElementById('filter-max-price');
    const gradeSel = document.getElementById('filter-grade');
    const searchInput = document.getElementById('marketplace-search');

    if (cropSel) cropSel.value = '';
    if (stateInput) stateInput.value = '';
    if (minP) minP.value = '';
    if (maxP) maxP.value = '';
    if (gradeSel) gradeSel.value = '';
    if (searchInput) searchInput.value = '';

    this.loadListings();
  },

  /**
   * Initialize marketplace page
   */
  initMarketplace() {
    this.loadCrops();
    this.loadListings();

    const filterForm = document.getElementById('marketplace-filter-form');
    if (filterForm) {
      filterForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.loadListings();
      });
    }

    const clearBtn = document.getElementById('btn-clear-filters');
    if (clearBtn) {
      clearBtn.addEventListener('click', (e) => {
        e.preventDefault();
        this.clearFilters();
      });
    }

    // Client-side quick search filter
    const searchInput = document.getElementById('marketplace-search');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        if (!query) {
          this.renderListings(this.currentListings);
          return;
        }
        const filtered = this.currentListings.filter(lot => {
          const name = (lot.crop_name || '').toLowerCase();
          const state = (lot.state || '').toLowerCase();
          const dist = (lot.district || '').toLowerCase();
          return name.includes(query) || state.includes(query) || dist.includes(query);
        });
        this.renderListings(filtered);
      });
    }
  },

  /**
   * Initialize single listing details page: listing-details.html?id=123
   */
  async initListingDetails() {
    const params = new URLSearchParams(window.location.search);
    const lotId = params.get('id');
    const container = document.getElementById('listing-details-container');
    if (!container) return;

    if (!lotId || isNaN(lotId)) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">⚠️</div>
          <h3 class="empty-state-title">Invalid Listing ID</h3>
          <p class="empty-state-desc">The requested produce lot identifier is invalid or missing.</p>
          <a href="marketplace.html" class="btn btn-outline">Back to Marketplace</a>
        </div>
      `;
      return;
    }

    const user = Auth.getUser();
    const isBuyer = user && user.role === 'BUYER';

    try {
      // Find lot details: query lots
      const data = await api.get('/marketplace/lots', { limit: 100 });
      const lot = (data && data.items) ? data.items.find(l => String(l.id) === String(lotId)) : null;

      if (!lot) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">🌾</div>
            <h3 class="empty-state-title">Listing Unavailable</h3>
            <p class="empty-state-desc">This produce lot is no longer available or has been fulfilled/withdrawn.</p>
            <a href="marketplace.html" class="btn btn-primary">Return to Marketplace</a>
          </div>
        `;
        return;
      }

      const cropName = lot.crop_name || `Crop #${lot.crop_id}`;
      const qty = lot.quantity || 0;
      const unit = lot.quantity_unit || 'quintal';
      const price = lot.expected_price_per_unit || lot.price_per_unit || 0;
      const priceUnit = lot.price_unit || `INR/${unit}`;
      const location = [lot.district, lot.state].filter(Boolean).join(', ') || 'Farmgate';
      const harvestDate = lot.harvest_date ? Utils.formatDate(lot.harvest_date) : 'Recent Harvest';
      const grade = lot.quality_grade || 'Standard Quality';

      container.innerHTML = `
        <div class="listing-details-grid">
          <!-- MAIN LOT DETAILS -->
          <div class="listing-main-card">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:var(--spacing-4);">
              <div>
                <span class="section-tag">${Utils.escapeHTML(grade)}</span>
                <h1 style="font-size:var(--font-size-3xl); margin-top:var(--spacing-1);">${Utils.escapeHTML(cropName)}</h1>
                <p style="color:var(--color-secondary-text);">Farmgate Location: ${Utils.escapeHTML(location)}</p>
              </div>
              <div>${Utils.getStatusBadge(lot.status)}</div>
            </div>

            <div class="detail-specs-grid">
              <div class="detail-spec-box">
                <div class="detail-spec-label">Available Quantity</div>
                <div class="detail-spec-value">${qty} ${Utils.escapeHTML(unit)}</div>
              </div>
              <div class="detail-spec-box">
                <div class="detail-spec-label">Farmer Expected Rate</div>
                <div class="detail-spec-value" style="color:var(--color-deep-green);">₹${Number(price).toFixed(2)} (${Utils.escapeHTML(priceUnit)})</div>
              </div>
              <div class="detail-spec-box">
                <div class="detail-spec-label">Harvest Date</div>
                <div class="detail-spec-value">${Utils.escapeHTML(harvestDate)}</div>
              </div>
              <div class="detail-spec-box">
                <div class="detail-spec-label">Estimated Gross Lot Value</div>
                <div class="detail-spec-value">₹${(Number(qty) * Number(price)).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
              </div>
            </div>

            <div style="margin-top:var(--spacing-6);">
              <h3 style="font-size:var(--font-size-lg); margin-bottom:var(--spacing-2);">Produce Specifications</h3>
              <p style="color:var(--color-secondary-text); font-size:var(--font-size-sm); line-height:1.6;">
                ${Utils.escapeHTML(lot.description || 'Verified agricultural lot listing posted directly by the producer. Quality meets commercial standards.')}
              </p>
            </div>

            <div class="alert alert-info" style="margin-top:var(--spacing-6);">
              <span>🛡️</span>
              <div>
                <strong>Farmer Privacy Protected:</strong> Exact coordinates and contact numbers remain confidential until an offer is formally accepted by the farmer.
              </div>
            </div>
          </div>

          <!-- OFFER ACTION CARD -->
          <aside class="listing-offer-card">
            <h3 style="font-size:var(--font-size-lg); margin-bottom:var(--spacing-2);">Commercial Procurement</h3>
            <p style="font-size:var(--font-size-sm); color:var(--color-secondary-text); margin-bottom:var(--spacing-4);">
              Submit a binding purchase offer to the farmer with your proposed rate and delivery terms.
            </p>

            ${!Auth.isAuthenticated() ? `
              <div class="alert alert-warning">
                Sign in with an active buyer account to make an offer.
              </div>
              <a href="login.html?redirect=${encodeURIComponent(window.location.href)}" class="btn btn-primary btn-block">
                Sign In to Make Offer
              </a>
            ` : !isBuyer ? `
              <div class="alert alert-info">
                You are currently signed in as a ${user.role}. Only verified commercial buyers can submit offers on marketplace produce lots.
              </div>
            ` : `
              <button id="open-offer-modal-btn" class="btn btn-primary btn-block">
                Make Purchase Offer
              </button>
            `}
          </aside>
        </div>
      `;

      // Wire modal if buyer
      if (isBuyer) {
        const offerBtn = document.getElementById('open-offer-modal-btn');
        if (offerBtn) {
          offerBtn.addEventListener('click', () => {
            Utils.openModal('offer-modal');
            document.getElementById('offer-lot-id').value = lot.id;
            document.getElementById('offer-qty').value = lot.quantity;
            document.getElementById('offer-rate').value = lot.expected_price_per_unit || lot.price_per_unit;
          });
        }

        const offerForm = document.getElementById('buyer-offer-form');
        if (offerForm) {
          offerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            Utils.clearFormErrors(offerForm);

            const qtyVal = Number(document.getElementById('offer-qty').value);
            const rateVal = Number(document.getElementById('offer-rate').value);
            const pickupVal = document.getElementById('offer-pickup').checked;
            const deliveryLocation = document.getElementById('offer-delivery-loc').value;
            const notes = document.getElementById('offer-notes').value;
            const submitBtn = document.getElementById('submit-offer-btn');

            let isValid = true;
            if (!qtyVal || qtyVal <= 0 || qtyVal > lot.quantity) {
              Utils.showFieldError(document.getElementById('offer-qty'), `Quantity must be between 1 and ${lot.quantity}`);
              isValid = false;
            }
            if (!rateVal || rateVal <= 0) {
              Utils.showFieldError(document.getElementById('offer-rate'), 'Please enter a valid offered rate');
              isValid = false;
            }
            if (!pickupVal && !deliveryLocation.trim()) {
              Utils.showFieldError(document.getElementById('offer-delivery-loc'), 'Delivery location is required unless farmgate pickup is checked');
              isValid = false;
            }

            if (!isValid) return;

            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner"></span> Submitting offer...';

            try {
              const offerPayload = {
                lot_id: lot.id,
                offered_price_per_unit: rateVal,
                price_unit: priceUnit,
                quantity_requested: qtyVal,
                quantity_unit: unit,
                pickup_from_farm: pickupVal,
                delivery_location: deliveryLocation.trim() || 'Farmgate Pickup',
                terms_and_conditions: notes.trim() || undefined,
              };

              const response = await api.post('/buyer/offers', offerPayload);
              Utils.closeModal('offer-modal');
              Utils.showToast('Your purchase offer has been successfully transmitted to the farmer!', 'success');
              
              setTimeout(() => {
                window.location.href = 'buyer-offers.html';
              }, 1500);
            } catch (err) {
              submitBtn.disabled = false;
              submitBtn.textContent = 'Submit Binding Offer';
              Utils.showToast(err.message || 'Unable to submit offer.', 'error');
            }
          });
        }
      }
    } catch (err) {
      container.innerHTML = `
        <div class="alert alert-error">
          <span>⚠️</span>
          <div>${Utils.escapeHTML(err.message)}</div>
        </div>
      `;
    }
  }
};
