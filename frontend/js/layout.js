/**
 * STUDIORA — Shared Layout Manager
 * Injects dark-teal sidebar and top cream header into pages.
 */

const Layout = {
  init(activePage) {
    // Check authentication for protected pages
    const token = api.getToken();
    if (!token && !window.location.pathname.includes('login.html') && !window.location.pathname.includes('register.html') && !window.location.pathname.includes('forgot-password.html') && !window.location.pathname.includes('index.html')) {
      window.location.href = '/login.html';
      return;
    }

    this.renderSidebar(activePage);
    this.renderHeader();
    this.bindEvents();
    this.loadUserData();
  },

  renderSidebar(activePage) {
    const sidebarEl = document.getElementById('sidebar-container');
    if (!sidebarEl) return;

    const isCollapsed = localStorage.getItem('studiora_sidebar_collapsed') === 'true';

    sidebarEl.innerHTML = `
      <aside class="app-sidebar ${isCollapsed ? 'collapsed' : ''}" id="main-sidebar">
        <!-- Sidebar Brand Header -->
        <div class="sidebar-header">
          <a href="/dashboard.html" class="brand-logo-wrap">
            <img src="/assets/studiora-logo.png" alt="Studiora Logo" class="brand-logo-img" />
            <div class="brand-text">
              <span class="brand-title">Studiora</span>
              <span class="brand-subtitle">Learn. Practice. Improve.</span>
            </div>
          </a>
          <button class="sidebar-toggle-btn" id="sidebar-collapse-btn" title="Toggle Sidebar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="15 18 9 12 15 6"></polyline>
            </svg>
          </button>
        </div>

        <!-- Sidebar Navigation -->
        <nav class="sidebar-nav">
          <a href="/dashboard.html" class="nav-item ${activePage === 'dashboard' ? 'active' : ''}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9"></rect><rect x="14" y="3" width="7" height="5"></rect><rect x="14" y="12" width="7" height="9"></rect><rect x="3" y="16" width="7" height="5"></rect></svg>
            <span>Dashboard</span>
          </a>
          <a href="/study-material.html" class="nav-item ${activePage === 'materials' ? 'active' : ''}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            <span>Study Material</span>
          </a>
          <a href="/notes.html" class="nav-item ${activePage === 'notes' ? 'active' : ''}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
            <span>Notes</span>
          </a>
          <a href="/quizzes.html" class="nav-item ${activePage === 'quizzes' ? 'active' : ''}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
            <span>Quizzes</span>
          </a>
          <a href="/test-papers.html" class="nav-item ${activePage === 'test-papers' ? 'active' : ''}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            <span>Test Paper</span>
          </a>
          <a href="/reports.html" class="nav-item ${activePage === 'reports' ? 'active' : ''}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>
            <span>Reports</span>
          </a>
        </nav>

        <!-- Sidebar Footer -->
        <div class="sidebar-footer">
          <button class="nav-item logout-btn" id="logout-btn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
            <span>Logout</span>
          </button>
        </div>
      </aside>
    `;

    const mainWrap = document.querySelector('.app-main');
    if (mainWrap && isCollapsed) {
      mainWrap.classList.add('sidebar-collapsed');
    }
  },

  renderHeader() {
    const headerEl = document.getElementById('header-container');
    if (!headerEl) return;

    headerEl.innerHTML = `
      <header class="app-header">
        <div class="header-left">
          <button class="mobile-menu-trigger" id="mobile-menu-btn" title="Open Navigation Menu">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
          </button>
          <div class="header-search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            <input type="text" placeholder="Search anything..." id="global-search-input" />
          </div>
        </div>
        <div class="header-right">
          <!-- Notification Bell -->
          <button class="header-icon-btn" title="Notifications">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
          </button>

          <!-- User Badge / Profile -->
          <div class="user-badge" id="header-user-badge">
            <div class="user-avatar" id="header-user-avatar">S</div>
            <div class="user-info-text">
              <span class="user-name" id="header-user-name">Student</span>
            </div>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </div>
        </div>
      </header>
    `;
  },

  bindEvents() {
    // Sidebar Collapse
    const collapseBtn = document.getElementById('sidebar-collapse-btn');
    if (collapseBtn) {
      collapseBtn.addEventListener('click', () => {
        const sidebar = document.getElementById('main-sidebar');
        const main = document.querySelector('.app-main');
        const isCollapsed = sidebar.classList.toggle('collapsed');
        if (main) main.classList.toggle('sidebar-collapsed', isCollapsed);
        localStorage.setItem('studiora_sidebar_collapsed', isCollapsed);
      });
    }

    // Mobile Menu Trigger
    const mobileBtn = document.getElementById('mobile-menu-btn');
    if (mobileBtn) {
      mobileBtn.addEventListener('click', () => {
        const sidebar = document.getElementById('main-sidebar');
        sidebar.classList.toggle('mobile-open');
      });
    }

    // Logout Button
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', async () => {
        try {
          await api.post('/auth/logout');
        } catch (e) {
          // ignore error on logout
        }
        api.clearAuth();
        window.location.href = '/login.html';
      });
    }
  },

  async loadUserData() {
    let user = api.getUser();
    if (!user) {
      try {
        user = await api.get('/auth/me');
        if (user) api.setUser(user);
      } catch (e) {
        return;
      }
    }

    if (user) {
      const nameEl = document.getElementById('header-user-name');
      const avatarEl = document.getElementById('header-user-avatar');
      if (nameEl) nameEl.textContent = user.full_name || 'Student';
      if (avatarEl) {
        const initial = (user.full_name || 'S').charAt(0).toUpperCase();
        avatarEl.textContent = initial;
      }
    }
  },

  showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${message}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
};
