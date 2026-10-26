/**
 * FarmerLinkage — Shared Navigation Component
 * Implements strict public navbar (Section 6), footer (Section 37), and role-based dashboard navigation.
 */
const Navigation = {
  /**
   * Render strict public navbar
   */
  renderPublicNavbar(containerId = 'public-navbar') {
    const container = document.getElementById(containerId);
    if (!container) return;

    const user = Auth.getUser();
    const isAuth = Auth.isAuthenticated();

    let authActionsHtml = '';
    if (isAuth && user) {
      const dashboardUrl = CONFIG.ROLE_REDIRECTS[user.role] || 'farmer.html';
      authActionsHtml = `
        <div class="auth-user-dropdown" id="user-nav-dropdown">
          <button class="user-badge-btn" id="user-menu-btn" aria-expanded="false">
            <span>👤</span>
            <span style="max-width:130px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${Utils.escapeHTML(user.full_name || 'User')}</span>
            <span style="font-size:0.65rem;">▼</span>
          </button>
          <div class="user-dropdown-menu" id="user-menu-items">
            <a href="${dashboardUrl}" class="user-dropdown-item" data-i18n="nav.dashboard">My Dashboard</a>
            <div class="user-dropdown-divider"></div>
            <a href="#" class="user-dropdown-item" id="nav-logout-btn" style="color:var(--color-error);" data-i18n="nav.logout">Sign Out</a>
          </div>
        </div>
      `;
    } else {
      authActionsHtml = `
        <a href="login.html" class="btn btn-sm btn-outline" data-i18n="nav.signin">Sign In</a>
        <a href="register.html" class="btn btn-sm btn-primary" data-i18n="nav.register">Create Account</a>
      `;
    }

    const currentLang = I18N.currentLang || 'en';

    container.innerHTML = `
      <header class="public-navbar">
        <div class="container public-navbar-container">
          <!-- LEFT SIDE: Logo & Name -->
          <a href="index.html" class="navbar-brand" aria-label="FarmerLinkage Home">
            <span class="navbar-brand-icon">🌱</span>
            <span data-i18n="app.name">FarmerLinkage</span>
          </a>

          <!-- RIGHT SIDE: Language Selector, Sign In, Create Account (Strict Section 6) -->
          <div class="navbar-actions">
            <div class="lang-selector-wrap">
              <label for="public-lang-select" class="sr-only">Preferred Language</label>
              <select id="public-lang-select" class="lang-select" aria-label="Select preferred language">
                <option value="en" ${currentLang === 'en' ? 'selected' : ''}>🌐 English</option>
                <option value="mr" ${currentLang === 'mr' ? 'selected' : ''}>🌐 मराठी</option>
                <option value="hi" ${currentLang === 'hi' ? 'selected' : ''}>🌐 हिन्दी</option>
              </select>
            </div>
            ${authActionsHtml}
          </div>
        </div>
      </header>
    `;

    // Bind language selector change
    const langSelect = container.querySelector('#public-lang-select');
    if (langSelect) {
      langSelect.addEventListener('change', (e) => {
        I18N.setLanguage(e.target.value);
      });
    }

    // Bind dropdown menu toggle if authenticated
    const userMenuBtn = container.querySelector('#user-menu-btn');
    const userMenuItems = container.querySelector('#user-menu-items');
    if (userMenuBtn && userMenuItems) {
      userMenuBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        userMenuItems.classList.toggle('show');
      });
      document.addEventListener('click', () => {
        userMenuItems.classList.remove('show');
      });
    }

    // Bind logout action
    const logoutBtn = container.querySelector('#nav-logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', (e) => {
        e.preventDefault();
        Auth.logout();
      });
    }

    // Apply translations
    I18N.applyTranslations();
  },

  /**
   * Render compact public footer (Section 37)
   */
  renderPublicFooter(containerId = 'public-footer') {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
      <footer class="public-footer">
        <div class="container footer-content">
          <ul class="footer-links">
            <li><a href="about.html" data-i18n="footer.about">About Us</a></li>
            <li><a href="index.html#how-it-works" data-i18n="footer.how">How It Works</a></li>
            <li><a href="marketplace.html" data-i18n="footer.marketplace">Marketplace</a></li>
            <li><a href="market-prices.html" data-i18n="footer.prices">Market Prices</a></li>
            <li><a href="price-discovery.html" data-i18n="dash.pricedisc">Price Discovery</a></li>
            <li><a href="contact.html" data-i18n="footer.contact">Contact Us</a></li>
            <li><a href="login.html" data-i18n="footer.signin">Sign In</a></li>
          </ul>
          <div class="footer-copyright" data-i18n="footer.rights">
            © 2026 FarmerLinkage. All rights reserved.
          </div>
        </div>
      </footer>
    `;
    I18N.applyTranslations();
  },

  /**
   * Render Role-Based Dashboard Shell (Sidebar + Top Header)
   */
  renderDashboardShell(role, activePageId, pageTitle) {
    const user = Auth.getUser() || { full_name: 'User', role: role, email: '' };
    const currentLang = I18N.currentLang || 'en';

    // Farmer sidebar links
    const farmerLinks = [
      { id: 'dashboard', href: 'farmer.html', icon: '📊', textKey: 'dash.title' },
      { id: 'profile', href: 'farmer-profile.html', icon: '👤', textKey: 'dash.profile' },
      { id: 'produce', href: 'farmer-produce.html', icon: '🌾', textKey: 'dash.produce' },
      { id: 'add-produce', href: 'add-produce.html', icon: '➕', textKey: 'dash.addproduce' },
      { id: 'offers', href: 'farmer-offers.html', icon: '📩', textKey: 'dash.offers' },
      { id: 'transactions', href: 'transactions.html', icon: '📑', textKey: 'dash.txns' },
      { id: 'market-prices', href: 'market-prices.html', icon: '📈', textKey: 'dash.marketprices' },
      { id: 'price-discovery', href: 'price-discovery.html', icon: '⚖️', textKey: 'dash.pricedisc' },
    ];

    // Buyer sidebar links
    const buyerLinks = [
      { id: 'dashboard', href: 'buyer.html', icon: '📊', textKey: 'dash.title' },
      { id: 'profile', href: 'buyer-profile.html', icon: '🏢', textKey: 'dash.profile' },
      { id: 'marketplace', href: 'marketplace.html', icon: '🛒', textKey: 'footer.marketplace' },
      { id: 'offers', href: 'buyer-offers.html', icon: '🏷️', textKey: 'dash.myoffers' },
      { id: 'transactions', href: 'transactions.html', icon: '📑', textKey: 'dash.txns' },
      { id: 'market-prices', href: 'market-prices.html', icon: '📈', textKey: 'dash.marketprices' },
      { id: 'price-discovery', href: 'price-discovery.html', icon: '⚖️', textKey: 'dash.pricedisc' },
    ];

    // Admin sidebar links
    const adminLinks = [
      { id: 'dashboard', href: 'admin.html', icon: '📊', textKey: 'dash.title' },
      { id: 'users', href: 'admin-users.html', icon: '👥', textKey: 'dash.admin.users' },
      { id: 'verification', href: 'admin-verification.html', icon: '🛡️', textKey: 'dash.admin.verify' },
      { id: 'markets', href: 'admin-markets.html', icon: '🏛️', textKey: 'dash.admin.markets' },
      { id: 'transactions', href: 'transactions.html', icon: '📑', textKey: 'dash.txns' },
      { id: 'reports', href: 'admin-reports.html', icon: '📈', textKey: 'dash.admin.reports' },
    ];

    let links = farmerLinks;
    if (role === 'BUYER') links = buyerLinks;
    if (role === 'ADMIN') links = adminLinks;

    const navLinksHtml = links.map(link => {
      const isActive = link.id === activePageId;
      return `
        <a href="${link.href}" class="sidebar-nav-item ${isActive ? 'active' : ''}">
          <span class="sidebar-nav-icon">${link.icon}</span>
          <span data-i18n="${link.textKey}">${I18N.t(link.textKey)}</span>
        </a>
      `;
    }).join('');

    const sidebarContainer = document.getElementById('dashboard-sidebar-container');
    if (sidebarContainer) {
      sidebarContainer.innerHTML = `
        <div class="sidebar-overlay" id="sidebar-overlay"></div>
        <aside class="dashboard-sidebar" id="dashboard-sidebar">
          <div class="sidebar-header">
            <a href="index.html" class="sidebar-brand">
              <span>🌱</span>
              <span data-i18n="app.name">FarmerLinkage</span>
            </a>
            <span class="sidebar-badge">${Utils.escapeHTML(role)}</span>
          </div>

          <div class="sidebar-content">
            <div class="sidebar-nav-title">Navigation</div>
            ${navLinksHtml}
          </div>

          <div class="sidebar-footer">
            <button class="sidebar-logout-btn" id="sidebar-logout-btn">
              <span>🚪</span>
              <span data-i18n="nav.logout">Sign Out</span>
            </button>
          </div>
        </aside>
      `;

      // Wire logout
      const logoutBtn = document.getElementById('sidebar-logout-btn');
      if (logoutBtn) {
        logoutBtn.addEventListener('click', () => Auth.logout());
      }

      // Wire mobile sidebar toggle
      const overlay = document.getElementById('sidebar-overlay');
      const sidebar = document.getElementById('dashboard-sidebar');
      if (overlay && sidebar) {
        overlay.addEventListener('click', () => {
          sidebar.classList.remove('open');
          overlay.classList.remove('active');
        });
      }
    }

    const headerContainer = document.getElementById('dashboard-header-container');
    if (headerContainer) {
      headerContainer.innerHTML = `
        <header class="dashboard-header">
          <div class="header-left">
            <button class="sidebar-toggle-btn" id="sidebar-toggle-btn" aria-label="Toggle Navigation">
              ☰
            </button>
            <h1 class="page-title">${Utils.escapeHTML(pageTitle)}</h1>
          </div>
          <div class="header-right">
            <div class="lang-selector-wrap">
              <select id="dash-lang-select" class="lang-select" aria-label="Change Language">
                <option value="en" ${currentLang === 'en' ? 'selected' : ''}>🌐 English</option>
                <option value="mr" ${currentLang === 'mr' ? 'selected' : ''}>🌐 मराठी</option>
                <option value="hi" ${currentLang === 'hi' ? 'selected' : ''}>🌐 हिन्दी</option>
              </select>
            </div>
            <div class="user-profile-badge">
              <div class="user-avatar-circle">${(user.full_name || 'U').charAt(0).toUpperCase()}</div>
              <div>
                <div class="user-profile-name">${Utils.escapeHTML(user.full_name || 'User')}</div>
                <div class="user-profile-role">${Utils.escapeHTML(user.role || role)}</div>
              </div>
            </div>
          </div>
        </header>
      `;

      // Wire sidebar toggle
      const toggleBtn = document.getElementById('sidebar-toggle-btn');
      const sidebar = document.getElementById('dashboard-sidebar');
      const overlay = document.getElementById('sidebar-overlay');
      if (toggleBtn && sidebar && overlay) {
        toggleBtn.addEventListener('click', () => {
          sidebar.classList.toggle('open');
          overlay.classList.toggle('active');
        });
      }

      // Wire dashboard language selector
      const dashLangSelect = document.getElementById('dash-lang-select');
      if (dashLangSelect) {
        dashLangSelect.addEventListener('change', (e) => {
          I18N.setLanguage(e.target.value);
        });
      }
    }

    I18N.applyTranslations();
  }
};
