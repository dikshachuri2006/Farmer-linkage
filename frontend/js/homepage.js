/**
 * FarmerLinkage — Homepage Dynamic Logic
 * Fetches real market prices preview from backend if available, or renders graceful status.
 */
document.addEventListener('DOMContentLoaded', async () => {
  Navigation.renderPublicNavbar();
  Navigation.renderPublicFooter();

  // Try fetching actual market price preview from GET /api/market-prices?limit=3
  const previewContainer = document.getElementById('market-price-preview-container');
  if (!previewContainer) return;

  try {
    const data = await api.get('/market-prices', { limit: 3, sort_by: 'price_date', sort_order: 'desc' });
    if (data && data.items && data.items.length > 0) {
      previewContainer.innerHTML = `
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Commodity</th>
                <th>Market (Mandi)</th>
                <th>Date</th>
                <th>Modal Price</th>
                <th>Min / Max</th>
              </tr>
            </thead>
            <tbody>
              ${data.items.map(item => `
                <tr>
                  <td><strong>${Utils.escapeHTML(item.crop_name || 'Crop #' + item.crop_id)}</strong></td>
                  <td>${Utils.escapeHTML(item.market_name || 'Market #' + item.market_id)}</td>
                  <td>${Utils.formatDate(item.price_date)}</td>
                  <td><span class="produce-price-highlight">₹${Number(item.modal_price).toFixed(2)}</span> <span style="font-size:0.75rem; color:var(--color-secondary-text);">${Utils.escapeHTML(item.price_unit || '')}</span></td>
                  <td>₹${Number(item.min_price).toFixed(2)} – ₹${Number(item.max_price).toFixed(2)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } else {
      // Empty state (no records in DB yet)
      previewContainer.innerHTML = `
        <div class="empty-state" style="margin:0 auto; max-width:540px;">
          <div class="empty-state-icon">📊</div>
          <h4 class="empty-state-title">No Official Mandi Prices Published Yet</h4>
          <p class="empty-state-desc">Daily mandi arrival price datasets can be explored directly on the dedicated market prices page.</p>
          <a href="market-prices.html" class="btn btn-sm btn-outline">Go to Market Prices</a>
        </div>
      `;
    }
  } catch (err) {
    // If backend or DB is not reachable, display an informative note without breaking the page
    previewContainer.innerHTML = `
      <div class="alert alert-info" style="max-width:600px; margin:0 auto;">
        <span>ℹ️</span>
        <div>Live market prices will stream here once the daily Agmarknet records are imported into the backend. Explore price discovery calculations directly.</div>
      </div>
    `;
  }
});
