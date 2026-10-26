/**
 * FarmerLinkage — Market Prices Module
 * Fetches and displays official APMC mandi arrival prices from the backend.
 * Provides multi-criteria filtering, full pagination across all records, and provenance details.
 */
const MarketPrices = {
  crops: [],
  markets: [],
  states: [],
  currentPage: 1,
  limit: 50,
  totalCount: 0,

  async loadCatalogs() {
    try {
      const [cropsData, marketsData] = await Promise.allSettled([
        api.get('/crops', { limit: 300 }),
        api.get('/markets', { limit: 100 }),
      ]);

      if (cropsData.status === 'fulfilled' && cropsData.value && cropsData.value.items) {
        this.crops = cropsData.value.items;
        const cropSelect = document.getElementById('price-filter-crop');
        if (cropSelect) {
          cropSelect.innerHTML = '<option value="">All Commodities (238 Crops)</option>' +
            this.crops.map(c => `<option value="${c.id}">${Utils.escapeHTML(c.name)}</option>`).join('');
        }
      }

      // Populate distinct agricultural states
      const stateSelect = document.getElementById('price-filter-state');
      if (stateSelect) {
        const defaultStates = [
          'Maharashtra', 'Tamil Nadu', 'Gujarat', 'Madhya Pradesh',
          'Uttar Pradesh', 'Punjab', 'Rajasthan', 'Karnataka',
          'Andhra Pradesh', 'Haryana', 'Keralam', 'Odisha', 'Telangana'
        ];
        stateSelect.innerHTML = '<option value="">All States</option>' +
          defaultStates.map(s => `<option value="${s}">${s}</option>`).join('');

        stateSelect.addEventListener('change', async () => {
          await this.loadMarketsForState(stateSelect.value);
        });
      }

      if (marketsData.status === 'fulfilled' && marketsData.value && marketsData.value.items) {
        this.markets = marketsData.value.items;
        this.populateMarketsDropdown(this.markets);
      }
    } catch (err) {
      console.warn('Market catalogs could not be loaded:', err);
    }
  },

  async loadMarketsForState(state) {
    const marketSelect = document.getElementById('price-filter-market');
    if (!marketSelect) return;

    try {
      const params = { limit: 100 };
      if (state) params.state = state;
      const data = await api.get('/markets', params);
      const items = (data && data.items) ? data.items : [];
      this.populateMarketsDropdown(items);
    } catch (err) {
      console.warn('Failed loading markets for state:', err);
    }
  },

  populateMarketsDropdown(items) {
    const marketSelect = document.getElementById('price-filter-market');
    if (!marketSelect) return;

    marketSelect.innerHTML = '<option value="">All Mandis / APMCs</option>' +
      items.map(m => `<option value="${m.id}">${Utils.escapeHTML(m.name)} (${Utils.escapeHTML(m.state)})</option>`).join('');
  },

  async fetchPrices(page = 1) {
    const container = document.getElementById('market-prices-table-container');
    if (!container) return;

    this.currentPage = page;
    const skip = (this.currentPage - 1) * this.limit;

    container.innerHTML = `
      <div class="loading-container">
        <div class="spinner spinner-lg"></div>
        <span>Retrieving official mandi price records...</span>
      </div>
    `;

    const cropId = document.getElementById('price-filter-crop')?.value;
    const marketId = document.getElementById('price-filter-market')?.value;
    const startDate = document.getElementById('price-filter-start-date')?.value;
    const endDate = document.getElementById('price-filter-end-date')?.value;
    const sortBy = document.getElementById('price-sort-by')?.value || 'price_date';
    const sortOrder = document.getElementById('price-sort-order')?.value || 'desc';

    const params = {
      sort_by: sortBy,
      sort_order: sortOrder,
      skip: skip,
      limit: this.limit,
    };

    if (cropId) params.crop_id = cropId;
    if (marketId) params.market_id = marketId;
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;

    try {
      const data = await api.get('/market-prices', params);
      const items = (data && data.items) ? data.items : [];
      this.totalCount = data ? (data.total || 0) : items.length;
      this.renderTable(items, this.totalCount);
    } catch (err) {
      container.innerHTML = `
        <div class="alert alert-error">
          <span>⚠️</span>
          <div>
            <strong>Unable to retrieve market prices:</strong> ${Utils.escapeHTML(err.message)}
          </div>
        </div>
      `;
    }
  },

  renderTable(items, totalCount) {
    const container = document.getElementById('market-prices-table-container');
    if (!container) return;

    if (!items || items.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📊</div>
          <h3 class="empty-state-title">No Official Mandi Price Records Found</h3>
          <p class="empty-state-desc">
            No historical or daily mandi price records match the selected parameters. Try widening your filters.
          </p>
          <button class="btn btn-sm btn-outline" onclick="MarketPrices.clearFilters()">Clear Filters</button>
        </div>
      `;
      return;
    }

    const totalPages = Math.ceil(totalCount / this.limit) || 1;
    const startRecord = (this.currentPage - 1) * this.limit + 1;
    const endRecord = Math.min(startRecord + items.length - 1, totalCount);

    container.innerHTML = `
      <!-- AGMARKNET BULLETIN BANNER -->
      <div class="alert alert-info" style="margin-bottom:var(--spacing-4); display:flex; align-items:center; gap:var(--spacing-3);">
        <span style="font-size:1.5rem;">🌾</span>
        <div>
          <strong>Official AGMARKNET Mandi Bulletin (Reported: 24 Oct 2026):</strong>
          Prevailing daily wholesale prices compiled by the Directorate of Marketing & Inspection, Ministry of Agriculture & Farmers Welfare. Rates reflect spot clearing quotes per quintal.
        </div>
      </div>

      <!-- METRICS HEADER -->
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:var(--spacing-2); flex-wrap:wrap; gap:var(--spacing-2);">
        <div style="font-size:var(--font-size-xs); color:var(--color-secondary-text);">
          Showing <strong>${startRecord.toLocaleString()}–${endRecord.toLocaleString()}</strong> of <strong>${totalCount.toLocaleString()}</strong> published price records
        </div>
        <div style="font-size:var(--font-size-xs); color:var(--color-secondary-text);">
          Page <strong>${this.currentPage}</strong> of <strong>${totalPages}</strong>
        </div>
      </div>

      <!-- DATA TABLE -->
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Commodity</th>
              <th>Market (Mandi)</th>
              <th>State & District</th>
              <th>Price Date</th>
              <th>Modal Rate</th>
              <th>Min Price</th>
              <th>Max Price</th>
              <th>Variety / Grade</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            ${items.map(p => `
              <tr>
                <td><strong>${Utils.escapeHTML(p.crop_name || `Crop #${p.crop_id}`)}</strong></td>
                <td>${Utils.escapeHTML(p.market_name || `Market #${p.market_id}`)}</td>
                <td>${Utils.escapeHTML([p.district, p.state].filter(Boolean).join(', ') || '—')}</td>
                <td>
                  <span class="badge badge-info" style="font-size:0.75rem;">${Utils.formatDate(p.price_date)}</span>
                </td>
                <td>
                  <span style="font-weight:700; color:var(--color-deep-green);">₹${Number(p.modal_price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  <span style="font-size:0.75rem; color:var(--color-secondary-text);">${Utils.escapeHTML(p.price_unit || '')}</span>
                </td>
                <td>₹${Number(p.min_price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                <td>₹${Number(p.max_price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                <td>${Utils.escapeHTML([p.variety, p.grade].filter(Boolean).join(' / ') || 'General')}</td>
                <td>
                  <span class="badge badge-neutral" style="font-size:0.75rem;" title="${Utils.escapeHTML(p.source || '')}">
                    ${Utils.escapeHTML(p.source || 'Agmarknet')}
                  </span>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>

      <!-- PAGINATION BAR -->
      ${totalPages > 1 ? `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:var(--spacing-4); padding-top:var(--spacing-3); border-top:1px solid var(--color-border); flex-wrap:wrap; gap:var(--spacing-2);">
          <button 
            type="button" 
            class="btn btn-sm btn-outline" 
            id="btn-prev-page" 
            ${this.currentPage <= 1 ? 'disabled style="opacity:0.5; cursor:not-allowed;"' : ''}
            onclick="MarketPrices.fetchPrices(${this.currentPage - 1})"
          >
            &larr; Previous 50
          </button>

          <span style="font-size:var(--font-size-sm); color:var(--color-secondary-text);">
            Page <strong>${this.currentPage}</strong> of <strong>${totalPages}</strong>
          </span>

          <button 
            type="button" 
            class="btn btn-sm btn-outline" 
            id="btn-next-page" 
            ${this.currentPage >= totalPages ? 'disabled style="opacity:0.5; cursor:not-allowed;"' : ''}
            onclick="MarketPrices.fetchPrices(${this.currentPage + 1})"
          >
            Next 50 &rarr;
          </button>
        </div>
      ` : ''}
    `;
  },

  clearFilters() {
    const cropSelect = document.getElementById('price-filter-crop');
    const stateSelect = document.getElementById('price-filter-state');
    const marketSelect = document.getElementById('price-filter-market');
    const startDate = document.getElementById('price-filter-start-date');
    const endDate = document.getElementById('price-filter-end-date');
    const sortBy = document.getElementById('price-sort-by');
    const sortOrder = document.getElementById('price-sort-order');

    if (cropSelect) cropSelect.value = '';
    if (stateSelect) stateSelect.value = '';
    if (marketSelect) marketSelect.value = '';
    if (startDate) startDate.value = '';
    if (endDate) endDate.value = '';
    if (sortBy) sortBy.value = 'price_date';
    if (sortOrder) sortOrder.value = 'desc';

    this.loadMarketsForState('');
    this.fetchPrices(1);
  },

  init() {
    this.loadCatalogs();
    this.fetchPrices(1);

    const form = document.getElementById('market-prices-filter-form');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        this.fetchPrices(1);
      });
    }

    const clearBtn = document.getElementById('btn-clear-price-filters');
    if (clearBtn) {
      clearBtn.addEventListener('click', (e) => {
        e.preventDefault();
        this.clearFilters();
      });
    }
  }
};
