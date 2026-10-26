/**
 * FarmerLinkage — Utility Functions
 * Safe rendering, notifications, formatting, and validation helpers.
 */
const Utils = {
  /**
   * Escape untrusted text to prevent XSS injection
   */
  escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  },

  /**
   * Format numbers to Indian Rupee currency standard
   */
  formatCurrency(amount, unit) {
    if (amount === null || amount === undefined || isNaN(amount)) return '₹0.00';
    const num = Number(amount);
    const formatted = new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(num);

    return unit ? `${formatted} / ${unit}` : formatted;
  },

  /**
   * Format dates to readable Indian format
   */
  formatDate(dateInput) {
    if (!dateInput) return '—';
    try {
      const d = new Date(dateInput);
      if (isNaN(d.getTime())) return String(dateInput);
      return new Intl.DateTimeFormat('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      }).format(d);
    } catch {
      return String(dateInput);
    }
  },

  formatDateTime(dateInput) {
    if (!dateInput) return '—';
    try {
      const d = new Date(dateInput);
      if (isNaN(d.getTime())) return String(dateInput);
      return new Intl.DateTimeFormat('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(d);
    } catch {
      return String(dateInput);
    }
  },

  /**
   * Generate semantic status badges
   */
  getStatusBadge(status) {
    if (!status) return '<span class="badge badge-neutral">Unknown</span>';
    const st = String(status).toUpperCase();

    if (['AVAILABLE', 'ACCEPTED', 'CONFIRMED', 'VERIFIED', 'COMPLETED', 'PAID'].includes(st)) {
      return `<span class="badge badge-success">${Utils.escapeHTML(st.replace(/_/g, ' '))}</span>`;
    }
    if (['PENDING', 'IN_TRANSIT', 'COMMITTED', 'PAYMENT_INITIATED', 'ESCROW_HELD'].includes(st)) {
      return `<span class="badge badge-warning">${Utils.escapeHTML(st.replace(/_/g, ' '))}</span>`;
    }
    if (['REJECTED', 'CANCELLED', 'WITHDRAWN', 'SUSPENDED', 'FAILED'].includes(st)) {
      return `<span class="badge badge-danger">${Utils.escapeHTML(st.replace(/_/g, ' '))}</span>`;
    }
    return `<span class="badge badge-neutral">${Utils.escapeHTML(st.replace(/_/g, ' '))}</span>`;
  },

  /**
   * Toast notification system
   */
  showToast(message, type = 'info', duration = 4000) {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '⚠️';
    if (type === 'warning') icon = '🔔';

    toast.innerHTML = `
      <span style="font-size:1.1rem; line-height:1;">${icon}</span>
      <div style="flex:1;">${Utils.escapeHTML(message)}</div>
      <button class="toast-close" aria-label="Close">&times;</button>
    `;

    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => {
      toast.remove();
    });

    container.appendChild(toast);

    if (duration > 0) {
      setTimeout(() => {
        if (toast.parentElement) {
          toast.style.opacity = '0';
          toast.style.transform = 'translateX(100%)';
          setTimeout(() => toast.remove(), 250);
        }
      }, duration);
    }
  },

  /**
   * Form validation utilities
   */
  clearFormErrors(form) {
    if (!form) return;
    const errors = form.querySelectorAll('.form-error');
    errors.forEach(el => {
      el.textContent = '';
      el.classList.remove('visible');
    });
    const inputs = form.querySelectorAll('.form-control, .form-select');
    inputs.forEach(el => el.classList.remove('is-invalid'));
  },

  showFieldError(fieldElement, errorMessage) {
    if (!fieldElement) return;
    fieldElement.classList.add('is-invalid');
    const formGroup = fieldElement.closest('.form-group') || fieldElement.parentElement;
    let errorEl = formGroup ? formGroup.querySelector('.form-error') : null;
    if (errorEl) {
      errorEl.textContent = errorMessage;
      errorEl.classList.add('visible');
    }
  },

  validateEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email).trim());
  },

  validatePhone(phone) {
    // 10-digit Indian phone validation
    return /^[6-9]\d{9}$/.test(String(phone).trim());
  },

  /**
   * Modal management
   */
  openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
      document.body.style.overflow = 'hidden';
    }
  },

  closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
      document.body.style.overflow = '';
    }
  },

  /**
   * Empty state template
   */
  renderEmptyState(icon, title, desc, actionBtnHtml = '') {
    return `
      <div class="empty-state">
        <div class="empty-state-icon">${icon || '🌾'}</div>
        <h3 class="empty-state-title">${Utils.escapeHTML(title)}</h3>
        <p class="empty-state-desc">${Utils.escapeHTML(desc)}</p>
        ${actionBtnHtml}
      </div>
    `;
  },
};
