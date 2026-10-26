/**
 * FarmerLinkage — Price Discovery Engine Client
 * Interactive net-realization calculator comparing market options and buyer offers.
 */
const PriceDiscovery = {
  candidateCount: 0,

  init() {
    this.candidateCount = 0;
    const candidatesContainer = document.getElementById('candidate-options-container');
    if (!candidatesContainer) return;

    candidatesContainer.innerHTML = '';
    // Pre-populate with 2 default candidate options
    this.addCandidateOption('Lasalgaon APMC (Nashik)', 1450, 'INR/quintal', 45, 12, 1.05);
    this.addCandidateOption('Vashi APMC (Navi Mumbai)', 1680, 'INR/quintal', 180, 14, 1.20);

    const addBtn = document.getElementById('btn-add-candidate');
    if (addBtn) {
      addBtn.addEventListener('click', () => {
        this.addCandidateOption();
      });
    }

    const form = document.getElementById('price-discovery-form');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        this.calculateRealization();
      });
    }
  },

  addCandidateOption(defaultName = '', defaultRate = '', defaultUnit = 'INR/quintal', defaultDist = '', defaultRateKm = '', defaultCess = '1.05') {
    this.candidateCount++;
    const id = this.candidateCount;
    const container = document.getElementById('candidate-options-container');
    if (!container) return;

    const row = document.createElement('div');
    row.className = 'candidate-market-row';
    row.id = `candidate-row-${id}`;
    row.innerHTML = `
      <div>
        <label class="form-label" style="font-size:var(--font-size-xs);">Destination Market / Mandi Name</label>
        <input type="text" class="form-control candidate-name" placeholder="e.g. Pune APMC or Direct Buyer" value="${Utils.escapeHTML(defaultName)}" required>
      </div>

      <div>
        <label class="form-label" style="font-size:var(--font-size-xs);">Offered Rate & Unit</label>
        <div style="display:flex; gap:var(--spacing-1);">
          <input type="number" class="form-control candidate-rate" placeholder="Rate" value="${defaultRate}" min="1" step="any" required>
          <select class="form-select candidate-unit" style="width:120px;">
            <option value="INR/quintal" ${defaultUnit === 'INR/quintal' ? 'selected' : ''}>₹/Quintal</option>
            <option value="INR/kg" ${defaultUnit === 'INR/kg' ? 'selected' : ''}>₹/kg</option>
            <option value="INR/tonne" ${defaultUnit === 'INR/tonne' ? 'selected' : ''}>₹/Tonne</option>
          </select>
        </div>
      </div>

      <div>
        <label class="form-label" style="font-size:var(--font-size-xs);">Distance (km) & Transport (₹/km)</label>
        <div style="display:flex; gap:var(--spacing-1);">
          <input type="number" class="form-control candidate-dist" placeholder="Distance (km)" value="${defaultDist}" min="0">
          <input type="number" class="form-control candidate-transport" placeholder="₹/km" value="${defaultRateKm}" min="0">
        </div>
      </div>

      <div>
        <label class="form-label" style="font-size:var(--font-size-xs);">Mandi Cess %</label>
        <input type="number" class="form-control candidate-cess" placeholder="1.05" value="${defaultCess}" min="0" step="0.01">
      </div>

      <div style="text-align:right;">
        <button type="button" class="btn btn-sm btn-outline" style="color:var(--color-error); border-color:var(--color-error); margin-top:20px;" onclick="PriceDiscovery.removeCandidateOption(${id})">
          ✕
        </button>
      </div>
    `;

    container.appendChild(row);
  },

  removeCandidateOption(id) {
    const row = document.getElementById(`candidate-row-${id}`);
    if (row) {
      row.remove();
    }
  },

  async calculateRealization() {
    const resultsContainer = document.getElementById('discovery-results-container');
    if (!resultsContainer) return;

    const cropName = document.getElementById('disc-crop-name')?.value.trim();
    const qtyVal = Number(document.getElementById('disc-sale-qty')?.value);
    const unitVal = document.getElementById('disc-qty-unit')?.value || 'quintal';
    const farmerLoc = document.getElementById('disc-farmer-loc')?.value.trim() || 'Farmgate';

    if (!cropName) {
      Utils.showToast('Please provide the crop or commodity name.', 'error');
      return;
    }
    if (!qtyVal || qtyVal <= 0) {
      Utils.showToast('Sale quantity must be greater than zero.', 'error');
      return;
    }

    const candidateRows = document.querySelectorAll('.candidate-market-row');
    if (candidateRows.length === 0) {
      Utils.showToast('Please add at least one candidate market or buyer offer.', 'error');
      return;
    }

    const candidateOptions = [];
    let hasError = false;

    candidateRows.forEach(row => {
      const name = row.querySelector('.candidate-name')?.value.trim();
      const rate = Number(row.querySelector('.candidate-rate')?.value);
      const pUnit = row.querySelector('.candidate-unit')?.value || 'INR/quintal';
      const dist = Number(row.querySelector('.candidate-dist')?.value) || 0;
      const transRate = Number(row.querySelector('.candidate-transport')?.value) || 0;
      const cess = Number(row.querySelector('.candidate-cess')?.value) || 1.05;

      if (!name || !rate || rate <= 0) {
        hasError = true;
      }

      candidateOptions.push({
        market_name: name,
        offered_price: rate,
        price_unit: pUnit,
        distance_km: dist > 0 ? dist : undefined,
        transport_cost_per_km: transRate > 0 ? transRate : undefined,
        market_cess_rate_percent: cess,
        fixed_market_charges: 50.0,
      });
    });

    if (hasError) {
      Utils.showToast('Please provide valid market names and offered prices for all rows.', 'error');
      return;
    }

    resultsContainer.innerHTML = `
      <div class="loading-container">
        <div class="spinner spinner-lg"></div>
        <span>Running Net-Realization Discovery Algorithm...</span>
      </div>
    `;

    const requestPayload = {
      crop_name: cropName,
      sale_quantity: qtyVal,
      quantity_unit: unitVal,
      farmer_location: farmerLoc,
      candidate_options: candidateOptions,
    };

    try {
      const response = await api.post('/price-discovery/compare', requestPayload);
      this.renderResults(response);
    } catch (err) {
      resultsContainer.innerHTML = `
        <div class="alert alert-error">
          <span>⚠️</span>
          <div><strong>Calculation Error:</strong> ${Utils.escapeHTML(err.message)}</div>
        </div>
      `;
    }
  },

  renderResults(res) {
    const container = document.getElementById('discovery-results-container');
    if (!container) return;

    if (!res || !res.ranked_options || res.ranked_options.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">⚠️</div>
          <h3 class="empty-state-title">No Comparison Computed</h3>
          <p class="empty-state-desc">The comparison engine was unable to compute net realizations for the supplied values.</p>
        </div>
      `;
      return;
    }

    const best = res.best_net_realization_option;

    container.innerHTML = `
      <div style="margin-top:var(--spacing-8);">
        <div style="text-align:center; margin-bottom:var(--spacing-6);">
          <span class="section-tag">Comparison Engine Output</span>
          <h2 style="font-size:var(--font-size-2xl);">Net Realization Analysis for ${Utils.escapeHTML(res.crop_name)}</h2>
          <p style="color:var(--color-secondary-text);">
            Total Sale Quantity: <strong>${res.sale_quantity} ${Utils.escapeHTML(res.quantity_unit)}</strong> (${res.normalized_quantity_kg.toFixed(0)} kg)
          </p>
        </div>

        ${best ? `
          <div class="card" style="border: 2px solid var(--color-fresh-green); background-color: var(--color-light-green); padding:var(--spacing-6); margin-bottom:var(--spacing-8);">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:var(--spacing-4);">
              <div>
                <span class="badge badge-success" style="font-size:0.8rem; margin-bottom:var(--spacing-2);">🏆 Optimal Selling Destination</span>
                <h3 style="font-size:var(--font-size-2xl); color:var(--color-deep-green); margin-top:var(--spacing-1);">
                  ${Utils.escapeHTML(best.market_name)}
                </h3>
                <p style="color:var(--color-secondary-text); margin-bottom:0;">
                  Yields the highest net earnings after all transport, statutory cess, and market handling costs.
                </p>
              </div>
              <div style="text-align:right;">
                <div style="font-size:var(--font-size-xs); color:var(--color-secondary-text);">Estimated Net Realization</div>
                <div style="font-size:2.25rem; font-weight:800; color:var(--color-deep-green);">
                  ₹${Number(best.estimated_net_realization ?? best.net_realization_value ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </div>
                <div style="font-size:var(--font-size-sm); font-weight:600; color:var(--color-primary-green);">
                  (₹${Number(best.estimated_net_per_kg ?? best.net_realization_per_kg ?? 0).toFixed(2)} / kg net)
                </div>
              </div>
            </div>
          </div>
        ` : ''}

        <h3 style="font-size:var(--font-size-lg); margin-bottom:var(--spacing-4);">Comparative Net Breakdown</h3>

        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Destination Market</th>
                <th>Gross Value</th>
                <th>Transport Cost</th>
                <th>Mandi Cess & Charges</th>
                <th>Total Deductions</th>
                <th>Estimated Net Realization</th>
                <th>Net Rate / kg</th>
              </tr>
            </thead>
            <tbody>
              ${res.ranked_options.map(opt => {
                const netVal = Number(opt.estimated_net_realization ?? opt.net_realization_value ?? 0);
                const netKg = Number(opt.estimated_net_per_kg ?? opt.net_realization_per_kg ?? 0);
                const trans = Number(opt.transport_cost ?? opt.breakdown?.transport_cost ?? 0);
                const cessAndCharges = Number(opt.market_cess_charges ?? opt.breakdown?.market_cess_amount ?? 0) + Number(opt.fixed_market_charges ?? opt.breakdown?.fixed_charges ?? 0);
                const deductions = Number(opt.total_deductions ?? 0);
                const isBest = opt.rank === 1 || opt.is_best_recommendation;

                return `
                  <tr style="${isBest ? 'background-color:#F0FDF4; font-weight:600;' : ''}">
                    <td>
                      ${isBest ? '<span class="badge badge-success">#1 Best</span>' : `#${opt.rank}`}
                    </td>
                    <td><strong>${Utils.escapeHTML(opt.market_name)}</strong></td>
                    <td>₹${Number(opt.gross_sale_value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                    <td style="color:var(--color-error);">- ₹${trans.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                    <td style="color:var(--color-error);">- ₹${cessAndCharges.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                    <td style="color:var(--color-error); font-weight:700;">- ₹${deductions.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                    <td>
                      <span style="font-size:1.1rem; font-weight:800; color:var(--color-deep-green);">
                        ₹${netVal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </td>
                    <td>₹${netKg.toFixed(2)}</td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>

        <div style="margin-top:var(--spacing-6); font-size:var(--font-size-xs); color:var(--color-secondary-text);">
          ${(res.general_disclaimers || []).map(d => `<p style="margin-bottom:4px;">* ${Utils.escapeHTML(d)}</p>`).join('')}
        </div>
      </div>
    `;
  }
};
