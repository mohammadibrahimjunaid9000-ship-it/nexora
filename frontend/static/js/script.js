/**
 * Nexora Learning Platform — Production Frontend Logic
 * Unified Auth, Google OAuth, Role Selection, Supabase Data Integration
 */

const API = 'http://127.0.0.1:5000/api';
let currentUser = null;
let allCourses = [];
let activeCourse = null;
let activeLesson = null;
let progressSaveInterval = null;
let selectedUserRole = 'learner';

document.addEventListener('DOMContentLoaded', async () => {
  window.addEventListener('scroll', () => {
    document.getElementById('navbar').classList.toggle('scrolled', window.scrollY > 50);
  });

  const urlParams = new URLSearchParams(window.location.search);
  const resetToken = urlParams.get('reset_token');
  const email = urlParams.get('email');
  const googleAuth = urlParams.get('google_auth');
  const authError = urlParams.get('auth_error');

  await checkAuth();

  if (resetToken && email) {
    const hiddenEmail = document.getElementById('resetEmailHidden');
    const hiddenToken = document.getElementById('resetTokenHidden');
    if (hiddenEmail) hiddenEmail.value = email;
    if (hiddenToken) hiddenToken.value = resetToken;
    openModal('authResetPasswordModal');
  } else if (authError) {
    showToast(`Auth Error: ${authError}`);
  } else if (googleAuth === 'success') {
    showToast('Signed in with Google!');
  }

  // Handle initial page routing or role selection prompt
  if (currentUser) {
    if (!currentUser.role) {
      openModal('authRoleSelectionModal');
    } else if (currentUser.role === 'creator') {
      showPage('creator');
    } else if (currentUser.role === 'learner') {
      showPage('dashboard');
    }
  } else {
    showPage('home');
  }
});

async function checkAuth() {
  try {
    const res = await fetch(`${API}/auth/me`, { credentials: 'include' });
    const data = await res.json();
    if (data.user) {
      currentUser = data.user;
      updateNavForUser();
    } else {
      currentUser = null;
    }
  } catch (e) { console.warn('Auth check failed.'); }
}

function updateNavForUser() {
  const authBar        = document.getElementById('navAuth');
  const userBar        = document.getElementById('navUser');
  const greeting       = document.getElementById('userGreeting');
  const dashNavItem    = document.getElementById('dashNavItem');
  const creatorNavItem = document.getElementById('creatorNavItem');
  const homeNavItem    = document.getElementById('homeNavItem');
  const coursesNavItem = document.getElementById('coursesNavItem');
  const collabNavItem  = document.getElementById('collabNavItem');

  if (currentUser) {
    if (authBar) authBar.style.display = 'none';
    if (userBar) userBar.style.display = 'flex';
    
    const avatar = currentUser.avatar_url || currentUser.profile_picture || `https://ui-avatars.com/api/?name=${encodeURIComponent(currentUser.name || 'User')}&background=8b5cf6&color=fff`;
    
    if (greeting) {
      greeting.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
          <img src="${escHtml(avatar)}" alt="${escHtml(currentUser.name)}" style="width: 36px; height: 36px; border-radius: 50%; object-fit: cover; border: 2px solid var(--primary);">
          <div style="text-align: right;">
            <div style="font-size: 13px; font-weight: 700; color: white;">${escHtml(currentUser.name)}</div>
            <div style="font-size: 11px; color: var(--gold); font-weight: 800;">🪙 ${currentUser.points} PTS</div>
          </div>
        </div>
      `;
    }

    if (currentUser.role === 'creator') {
      if (dashNavItem) dashNavItem.style.display = 'none';
      if (creatorNavItem) creatorNavItem.style.display = 'inline-block';
      if (homeNavItem) homeNavItem.style.display = 'none';
      if (coursesNavItem) coursesNavItem.style.display = 'none';
      if (collabNavItem) collabNavItem.style.display = 'inline-block';
    } else {
      if (dashNavItem) dashNavItem.style.display = 'inline-block';
      if (creatorNavItem) creatorNavItem.style.display = 'none';
      if (homeNavItem) homeNavItem.style.display = 'inline-block';
      if (coursesNavItem) coursesNavItem.style.display = 'inline-block';
      if (collabNavItem) collabNavItem.style.display = 'inline-block';
    }
  } else {
    if (authBar) authBar.style.display = 'flex';
    if (userBar) userBar.style.display = 'none';
    if (dashNavItem) dashNavItem.style.display = 'none';
    if (creatorNavItem) creatorNavItem.style.display = 'none';
    if (homeNavItem) homeNavItem.style.display = 'inline-block';
    if (coursesNavItem) coursesNavItem.style.display = 'inline-block';
    if (collabNavItem) collabNavItem.style.display = 'inline-block';
  }
}

// ─── Unified Authentication Handlers ─────────────────────────────────────────

async function loginWithGoogle() {
  try {
    const res = await fetch(`${API}/auth/google/url`);
    const data = await res.json();
    if (data.url) {
      window.location.href = data.url;
    } else {
      showToast(data.error || 'Failed to initialize Google Login');
    }
  } catch (e) {
    showToast('Failed to connect to Google Auth');
  }
}

function openRoleSelectionModal() {
  openModal('authChooseRoleModal');
}

function selectRegistrationRole(role) {
  closeModal('authChooseRoleModal');
  const roleInput = document.getElementById('regRole');
  if (roleInput) roleInput.value = role;

  const roleBadge = document.getElementById('regRoleBadge');
  const titleEl = document.getElementById('regModalTitle');
  const subtitleEl = document.getElementById('regModalSubtitle');
  const submitBtn = document.getElementById('regSubmitBtn');

  if (role === 'creator') {
    if (roleBadge) {
      roleBadge.innerHTML = `<span>👨‍🏫 Creator Account</span><a href="#" onclick="switchModal('authRegisterModal', 'authChooseRoleModal')" style="color: var(--text-dim); text-decoration: underline; font-weight: 500; font-size: 11px; margin-left: 4px;">Change</a>`;
      roleBadge.style.background = 'rgba(139, 92, 246, 0.15)';
      roleBadge.style.borderColor = 'rgba(139, 92, 246, 0.3)';
      roleBadge.style.color = 'var(--primary)';
    }
    if (titleEl) titleEl.innerHTML = 'Join as a <span class="text-gradient">Creator</span>';
    if (subtitleEl) subtitleEl.textContent = 'Teach courses, host live sessions, and collaborate with learners';
    if (submitBtn) submitBtn.textContent = 'Create Creator Account';
  } else {
    if (roleBadge) {
      roleBadge.innerHTML = `<span>🎓 Learner Account</span><a href="#" onclick="switchModal('authRegisterModal', 'authChooseRoleModal')" style="color: var(--text-dim); text-decoration: underline; font-weight: 500; font-size: 11px; margin-left: 4px;">Change</a>`;
      roleBadge.style.background = 'rgba(6, 182, 212, 0.15)';
      roleBadge.style.borderColor = 'rgba(6, 182, 212, 0.3)';
      roleBadge.style.color = 'var(--secondary)';
    }
    if (titleEl) titleEl.innerHTML = 'Join as a <span class="text-gradient">Learner</span>';
    if (subtitleEl) subtitleEl.textContent = 'Learn courses, join live sessions, and collaborate with creators';
    if (submitBtn) submitBtn.textContent = 'Create Learner Account';
  }

  const errorEl = document.getElementById('authRegisterError');
  if (errorEl) errorEl.style.display = 'none';

  setTimeout(() => openModal('authRegisterModal'), 150);
}

async function submitEmailRegister() {
  const nameEl = document.getElementById('regFullName');
  const emailEl = document.getElementById('regEmail');
  const passEl = document.getElementById('regPassword');
  const confirmEl = document.getElementById('regConfirmPassword');
  const roleEl = document.getElementById('regRole');
  const errorEl = document.getElementById('authRegisterError');

  if (errorEl) errorEl.style.display = 'none';

  const full_name = nameEl ? nameEl.value.trim() : '';
  const email = emailEl ? emailEl.value.trim() : '';
  const password = passEl ? passEl.value : '';
  const confirm_password = confirmEl ? confirmEl.value : '';
  const role = (roleEl && roleEl.value) ? roleEl.value : 'learner';

  if (!full_name || !email || !password) {
    if (errorEl) {
      errorEl.textContent = 'Full Name, Email, and Password are required.';
      errorEl.style.display = 'block';
    }
    return;
  }

  if (password !== confirm_password) {
    if (errorEl) {
      errorEl.textContent = 'Passwords do not match.';
      errorEl.style.display = 'block';
    }
    return;
  }

  try {
    const res = await apiFetch('/auth/register', 'POST', { full_name, email, password, confirm_password, role });
    const data = await res.json();

    if (!res.ok) {
      if (errorEl) {
        errorEl.textContent = data.error || 'Registration failed.';
        errorEl.style.display = 'block';
      }
      return;
    }

    currentUser = data.user;
    updateNavForUser();
    closeModal('authRegisterModal');
    showToast(`Account created as ${capitalize(currentUser.role || 'user')}! Welcome, ${currentUser.name}.`);

    if (currentUser.role === 'creator') {
      showPage('creator');
    } else if (currentUser.role === 'learner') {
      showPage('dashboard');
    } else {
      openModal('authRoleSelectionModal');
    }
  } catch (e) {
    if (errorEl) {
      errorEl.textContent = 'Server connection error during registration.';
      errorEl.style.display = 'block';
    }
  }
}

async function submitEmailLogin() {
  const emailEl = document.getElementById('loginEmail');
  const passEl = document.getElementById('loginPassword');
  const errorEl = document.getElementById('authLoginError');

  if (errorEl) errorEl.style.display = 'none';

  const email = emailEl ? emailEl.value.trim() : '';
  const password = passEl ? passEl.value : '';

  if (!email || !password) {
    if (errorEl) {
      errorEl.textContent = 'Email address and password are required.';
      errorEl.style.display = 'block';
    }
    return;
  }

  try {
    const res = await apiFetch('/auth/login', 'POST', { email, password });
    const data = await res.json();

    if (!res.ok) {
      if (errorEl) {
        errorEl.textContent = data.error || 'Login failed.';
        errorEl.style.display = 'block';
      }
      return;
    }

    currentUser = data.user;
    updateNavForUser();
    closeModal('authLoginModal');
    showToast(`Welcome back, ${currentUser.name}!`);

    if (data.requires_role_selection || !currentUser.role) {
      openModal('authRoleSelectionModal');
    } else if (currentUser.role === 'creator') {
      showPage('creator');
    } else {
      showPage('dashboard');
    }
  } catch (e) {
    if (errorEl) {
      errorEl.textContent = 'Server connection error.';
      errorEl.style.display = 'block';
    }
  }
}

function selectRoleOption(role) {
  if (role === 'admin') return;
  selectedUserRole = role;

  const learnerCard = document.getElementById('card-role-learner');
  const creatorCard = document.getElementById('card-role-creator');

  if (learnerCard && creatorCard) {
    if (role === 'learner') {
      learnerCard.classList.add('active');
      creatorCard.classList.remove('active');
    } else {
      creatorCard.classList.add('active');
      learnerCard.classList.remove('active');
    }
  }

  const radio = document.querySelector(`input[name="selectedRole"][value="${role}"]`);
  if (radio) radio.checked = true;
}

async function submitRoleSelection() {
  const errorEl = document.getElementById('roleSelectionError');
  if (errorEl) errorEl.style.display = 'none';

  if (!selectedUserRole || (selectedUserRole !== 'learner' && selectedUserRole !== 'creator')) {
    if (errorEl) {
      errorEl.textContent = 'Please select a valid role (Learner or Creator).';
      errorEl.style.display = 'block';
    }
    return;
  }

  try {
    const res = await apiFetch('/auth/set-role', 'POST', { role: selectedUserRole });
    const data = await res.json();

    if (!res.ok) {
      if (errorEl) {
        errorEl.textContent = data.error || 'Failed to save role.';
        errorEl.style.display = 'block';
      }
      return;
    }

    currentUser = data.user;
    updateNavForUser();
    closeModal('authRoleSelectionModal');
    showToast(`Role assigned as ${capitalize(currentUser.role)} permanently!`);

    if (currentUser.role === 'creator') {
      showPage('creator');
    } else {
      showPage('dashboard');
    }
  } catch (e) {
    if (errorEl) {
      errorEl.textContent = 'Server error saving role selection.';
      errorEl.style.display = 'block';
    }
  }
}

async function submitForgotPassword() {
  const emailEl = document.getElementById('forgotEmail');
  const errorEl = document.getElementById('forgotPasswordError');
  const successEl = document.getElementById('forgotPasswordSuccess');

  if (errorEl) errorEl.style.display = 'none';
  if (successEl) successEl.style.display = 'none';

  const email = emailEl ? emailEl.value.trim() : '';
  if (!email) {
    if (errorEl) {
      errorEl.textContent = 'Please enter your email address.';
      errorEl.style.display = 'block';
    }
    return;
  }

  try {
    const res = await apiFetch('/auth/forgot-password', 'POST', { email });
    const data = await res.json();

    if (!res.ok) {
      if (errorEl) {
        errorEl.textContent = data.error || 'Failed to process password reset request.';
        errorEl.style.display = 'block';
      }
      return;
    }

    if (successEl) {
      successEl.textContent = data.message;
      successEl.style.display = 'block';
    }
  } catch (e) {
    if (errorEl) {
      errorEl.textContent = 'Server connection error.';
      errorEl.style.display = 'block';
    }
  }
}

async function submitResetPassword() {
  const email = document.getElementById('resetEmailHidden').value;
  const token = document.getElementById('resetTokenHidden').value;
  const new_password = document.getElementById('newPasswordInput').value;
  const errorEl = document.getElementById('resetPasswordError');

  if (errorEl) errorEl.style.display = 'none';

  if (!new_password || new_password.length < 6) {
    if (errorEl) {
      errorEl.textContent = 'Password must be at least 6 characters long.';
      errorEl.style.display = 'block';
    }
    return;
  }

  try {
    const res = await apiFetch('/auth/reset-password', 'POST', { email, token, new_password });
    const data = await res.json();

    if (!res.ok) {
      if (errorEl) {
        errorEl.textContent = data.error || 'Failed to reset password.';
        errorEl.style.display = 'block';
      }
      return;
    }

    closeModal('authResetPasswordModal');
    showToast('Password reset successfully! Please log in.');
    openModal('authLoginModal');
  } catch (e) {
    if (errorEl) {
      errorEl.textContent = 'Server connection error.';
      errorEl.style.display = 'block';
    }
  }
}

async function logout() {
  await apiFetch('/auth/logout', 'POST');
  currentUser = null;
  updateNavForUser();
  showPage('home');
  showToast('Logged out successfully.');
}

// Navigation & Page Switching
function showPage(page) {
  if (page === 'dashboard' && (!currentUser || currentUser.role !== 'learner')) return openModal('authLoginModal');
  if (page === 'creator' && (!currentUser || currentUser.role !== 'creator')) return openModal('authLoginModal');

  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(`page-${page}`).classList.add('active');

  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  const activeLink = document.querySelector(`.nav-link[data-page="${page}"]`);
  if (activeLink) activeLink.classList.add('active');

  window.scrollTo({ top: 0, behavior: 'smooth' });

  if (page === 'home') loadHomePage();
  if (page === 'courses') loadCourses();
  if (page === 'dashboard') loadDashboard();
  if (page === 'creator') {
    switchCreatorTab('dashboard');
    loadCreatorDashboard();
  }
  if (page === 'collaboration') loadCollaboration();
}

// Homepage Dynamic Data
let userBookedSessionIds = [];

async function fetchUserBookings() {
  if (currentUser?.role === 'learner') {
    try {
      const res = await apiFetch('/bookings/my', 'GET');
      const data = await res.json();
      userBookedSessionIds = (data.bookings || []).map(b => b.session.id);
    } catch (e) {
      userBookedSessionIds = [];
    }
  } else {
    userBookedSessionIds = [];
  }
}

async function loadHomePage() {
  const newestGrid = document.getElementById('homeNewestGrid');
  const liveGrid = document.getElementById('homeLiveGrid');
  try {
    await fetchUserBookings();
    const [cRes, lRes] = await Promise.all([
      apiFetch('/courses/featured', 'GET'),
      apiFetch('/live', 'GET')
    ]);
    const cData = await cRes.json();
    const lData = await lRes.json();

    renderCourses(cData.newest || [], newestGrid, true);
    renderLiveSessions(lData.sessions || [], liveGrid, true, false, userBookedSessionIds);
  } catch (e) { console.error(e); }
}

// Courses Page
async function loadCourses() {
  const courseGrid = document.getElementById('coursesGrid');
  const liveGrid = document.getElementById('availableLiveGrid');
  try {
    await fetchUserBookings();
    const [cRes, lRes] = await Promise.all([
      apiFetch('/courses', 'GET'),
      apiFetch('/live', 'GET')
    ]);
    const cData = await cRes.json();
    const lData = await lRes.json();

    allCourses = cData.courses || [];
    renderCourses(allCourses, courseGrid, true);
    renderLiveSessions(lData.sessions || [], liveGrid, true, false, userBookedSessionIds);
  } catch (e) { console.error(e); }
}

function renderCourses(courses, container, showActions = false, isDashboard = false) {
  if (!courses || courses.length === 0) {
    container.innerHTML = `
      <div class="stat-card" style="text-align: center; grid-column: 1 / -1; padding: 40px;">
        <p style="color: var(--text-muted); font-size: 15px;">No courses available at the moment.</p>
      </div>`;
    return;
  }

  container.innerHTML = courses.map(c => {
    const isPaid = c.price > 0;
    const levelClass = `badge-${(c.level || 'beginner').toLowerCase()}`;

    return `
      <div class="course-card">
        <img src="${c.thumbnail}" alt="${escHtml(c.title)}" class="course-banner">
        <span class="badge ${levelClass}">${escHtml(c.level)}</span>
        <div class="course-body">
          <div class="course-meta">
            <span class="course-category">${escHtml(c.category)}</span>
            <span class="course-rating">⭐ ${c.rating || 5.0}</span>
          </div>
          <h3 class="course-title">${escHtml(c.title)}</h3>
          
          ${isDashboard ? `
            <div class="progress-wrap" style="margin: 15px 0;">
              <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--text-muted); margin-bottom:5px;">
                <span>Progress</span><span>${c.progress_percentage || 0}%</span>
              </div>
              <div style="height:4px; background:var(--border-glass); border-radius:10px; overflow:hidden;">
                <div style="width:${c.progress_percentage || 0}%; height:100%; background:var(--primary);"></div>
              </div>
            </div>
          ` : `<p class="course-desc">${escHtml(c.description)}</p>`}

          <div class="course-footer">
            <div class="instructor-info">
              <span class="instructor-name">By ${escHtml(c.instructor)}</span>
            </div>
            <div class="course-price-wrap">
              ${isDashboard ? '' : (isPaid ? `<span class="price-main">₹${c.price}</span>` : '<span class="price-main" style="color: #10b981">FREE</span>')}
            </div>
          </div>

          ${isDashboard ? `
            <button class="btn btn-primary btn-sm btn-full" style="margin-top:15px;" onclick="openVideoPlayer(${c.id})">Continue Watching 🎬</button>
          ` : (showActions && currentUser?.role === 'learner' ? `
            <div style="margin-top: 20px; display: flex; gap: 10px;">
              ${!isPaid ? 
                `<button class="btn btn-primary btn-sm btn-full" onclick="enroll(${c.id})">Enroll Now</button>` : 
                `<button class="btn btn-primary btn-sm" onclick="enroll(${c.id})" style="flex:1">Buy ₹</button>
                 <button class="btn btn-outline btn-sm" onclick="buyWithPoints(${c.id})" style="flex:1">Buy 🪙</button>`
              }
              <button class="btn btn-outline btn-sm" onclick="openVideoPlayer(${c.id})">Preview</button>
            </div>
          ` : (showActions ? `<button class="btn btn-primary btn-sm btn-full" style="margin-top: 15px;" onclick="openVideoPlayer(${c.id})">View Course</button>` : ''))}
        </div>
      </div>
    `;
  }).join('');
}

function renderLiveSessions(sessions, container, showBooking = false, isDashboard = false, userBookedSessionIds = []) {
  if (!container) return;
  if (!sessions || sessions.length === 0) {
    container.innerHTML = `<p style="color: var(--text-muted); padding: 20px;">No live sessions scheduled.</p>`;
    return;
  }

  container.innerHTML = sessions.map(s => {
    const isOwner = currentUser?.role === 'creator' && currentUser?.id === s.created_by;
    const isBooked = isDashboard || userBookedSessionIds.includes(s.id);
    const status = (s.status || 'scheduled').toLowerCase();

    let statusBadgeHtml = '';
    if (status === 'live') {
      statusBadgeHtml = `<span class="badge" style="background:#ef4444; color:#fff;">🔴 LIVE NOW</span>`;
    } else if (status === 'ended') {
      statusBadgeHtml = `<span class="badge" style="background:#6b7280; color:#fff;">🏁 ENDED</span>`;
    } else if (status === 'cancelled') {
      statusBadgeHtml = `<span class="badge" style="background:#dc2626; color:#fff;">❌ CANCELLED</span>`;
    } else {
      statusBadgeHtml = `<span class="badge badge-beginner">⏳ SCHEDULED</span>`;
    }

    let actionsHtml = '';

    if (isOwner) {
      actionsHtml = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 14px;">
          ${status === 'live' ? 
            `<button class="btn btn-outline btn-sm" style="color: #f59e0b; border-color: #f59e0b;" onclick="updateSessionStatus(${s.id}, 'ended')">⏹️ End Session</button>` :
            `<button class="btn btn-primary btn-sm" style="background: linear-gradient(90deg, #10b981, #059669);" onclick="updateSessionStatus(${s.id}, 'live')">▶️ Start Session</button>`
          }
          <button class="btn btn-outline btn-sm" onclick="openEditLiveModal(${s.id})">✏️ Edit Session</button>
          <button class="btn btn-outline btn-sm" style="color: #ef4444; border-color: #ef4444;" onclick="updateSessionStatus(${s.id}, 'cancelled')">❌ Cancel Session</button>
          <button class="btn btn-outline btn-sm" onclick="openRegisteredStudentsModal(${s.id})">👥 Students (${s.booking_count || 0})</button>
        </div>
      `;
    } else {
      if (isBooked) {
        if (status === 'live') {
          actionsHtml = `<a href="${escHtml(s.meeting_link)}" target="_blank" class="btn btn-primary btn-sm btn-full" style="margin-top:14px; background: linear-gradient(90deg, #ef4444, #f59e0b);">Join Session 🔴 LIVE</a>`;
        } else if (status === 'scheduled') {
          actionsHtml = `<button class="btn btn-outline btn-sm btn-full" disabled style="margin-top:14px; opacity:0.7; cursor:not-allowed; font-size:12px; border-color:var(--border-glass);">Waiting for the instructor to start the session.</button>`;
        } else if (status === 'ended') {
          actionsHtml = `<button class="btn btn-ghost btn-sm btn-full" disabled style="margin-top:14px; color:var(--text-muted);">Session Has Ended</button>`;
        } else if (status === 'cancelled') {
          actionsHtml = `<button class="btn btn-ghost btn-sm btn-full" disabled style="margin-top:14px; color:#ef4444;">Session Cancelled</button>`;
        }
      } else {
        if (showBooking && currentUser?.role === 'learner') {
          actionsHtml = `<button class="btn btn-primary btn-sm btn-full" style="margin-top:14px;" onclick="bookSession(${s.id})">Book Session (Reserve Seat)</button>`;
        } else if (!currentUser) {
          actionsHtml = `<button class="btn btn-primary btn-sm btn-full" style="margin-top:14px;" onclick="openModal('learnerLoginModal')">Book Session</button>`;
        }
      }
    }

    return `
      <div class="live-card" style="margin-bottom: 16px;">
        <div class="live-creator">
          <div class="creator-pfp" style="background: var(--bg-deep); display: grid; place-items: center; font-size: 18px;">🎙️</div>
          <div>
            <div style="font-weight: 700; font-size: 16px;">${escHtml(s.creator_name)}</div>
            <div style="font-size: 12px; color: var(--secondary); font-weight: 600;">Verified Instructor</div>
          </div>
          <div style="margin-left: auto;">${statusBadgeHtml}</div>
        </div>
        <div class="live-info">
          ${isDashboard ? `<div style="font-size: 10px; font-weight: 800; color: #10b981; margin-bottom: 8px;">CONFIRMED BOOKING ✅</div>` : ''}
          <h4>${escHtml(s.title)}</h4>
          <p style="font-size: 13px; color: var(--text-dim); margin-bottom: 8px;">${escHtml(s.description || s.topic)}</p>
          <div class="live-time">
            <span>📅 ${new Date(s.scheduled_at).toLocaleDateString()}</span>
            <span>⏰ ${new Date(s.scheduled_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
          </div>
          ${actionsHtml}
        </div>
      </div>
    `;
  }).join('');
}

// Learner Dashboard
async function loadDashboard() {
  const statsEl = document.getElementById('dashStats');
  const myCoursesGrid = document.getElementById('myCoursesGrid');
  const continueWatchingGrid = document.getElementById('continueWatchingGrid');
  const upcomingGrid = document.getElementById('myUpcomingLiveGrid');

  try {
    const res = await apiFetch('/dashboard/learner', 'GET');
    const stats = await res.json();

    statsEl.innerHTML = `
      <div class="stat-card">
        <span class="stat-lbl">Learning Points</span>
        <div class="stat-val">🪙 ${stats.points}</div>
      </div>
      <div class="stat-card">
        <span class="stat-lbl">Enrolled Courses</span>
        <div class="stat-val">${stats.enrolled_count}</div>
      </div>
      <div class="stat-card">
        <span class="stat-lbl">Completed Courses</span>
        <div class="stat-val">${stats.completed_count}</div>
      </div>
      <div class="stat-card">
        <span class="stat-lbl">Live Bookings</span>
        <div class="stat-val">${(stats.upcoming_bookings || []).length}</div>
      </div>
    `;

    renderCourses((stats.enrolled_courses || []).map(e => ({ ...e.course, progress_percentage: e.progress_percentage })), myCoursesGrid, false, true);
    renderCourses((stats.continue_watching || []).map(e => ({ ...e.course, progress_percentage: e.progress_percentage })), continueWatchingGrid, false, true);
    renderLiveSessions((stats.upcoming_bookings || []).map(b => b.session), upcomingGrid, false, true);

  } catch (e) { console.error(e); }
}

function switchDashTab(tab) {
  document.querySelectorAll('.dash-section').forEach(s => s.classList.remove('active'));
  document.getElementById(`dash-section-${tab}`).classList.add('active');

  document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
  document.getElementById(`tab-link-${tab}`).classList.add('active');
}

// Creator Studio Logic (Separated Views)
function switchCreatorTab(tab) {
  document.querySelectorAll('.creator-view').forEach(v => v.classList.remove('active'));
  const targetView = document.getElementById(`creator-view-${tab}`);
  if (targetView) targetView.classList.add('active');

  const creatorSidebar = document.querySelector('#page-creator .sidebar');
  if (creatorSidebar) {
    creatorSidebar.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
  }
  const linkEl = document.getElementById(`cside-link-${tab}`);
  if (linkEl) linkEl.classList.add('active');

  if (tab === 'dashboard' || tab === 'my-courses' || tab === 'live') loadCreatorDashboard();
  if (tab === 'requests') loadCreatorRequests();
  if (tab === 'analytics') loadCreatorAnalytics();
  if (tab === 'profile') loadCreatorProfile();

  const contentArea = document.querySelector('#page-creator .dashboard-content');
  if (contentArea) contentArea.scrollTop = 0;
}

async function loadCreatorDashboard() {
  const statsEl = document.getElementById('creatorStats');
  const playlistsList = document.getElementById('myPlaylistsList');
  const singleVideosList = document.getElementById('mySingleVideosList');
  const fullCoursesList = document.getElementById('creatorCoursesFullList');
  const liveList = document.getElementById('liveSessionsList');

  try {
    const res = await apiFetch('/dashboard/creator', 'GET');
    const stats = await res.json();

    if (statsEl) {
      statsEl.innerHTML = `
        <div class="stat-card">
          <span class="stat-lbl">Published Content</span>
          <div class="stat-val">${stats.published_courses_count || 0}</div>
        </div>
        <div class="stat-card">
          <span class="stat-lbl">Total Students</span>
          <div class="stat-val">${stats.total_students || 0}</div>
        </div>
        <div class="stat-card">
          <span class="stat-lbl">Total Revenue</span>
          <div class="stat-val">₹${stats.revenue || 0}</div>
        </div>
        <div class="stat-card">
          <span class="stat-lbl">Points Earned</span>
          <div class="stat-val">🪙 ${stats.points_earned || 0}</div>
        </div>
      `;
    }

    // Render Playlists Cards
    const playlistsHtml = (stats.playlists || []).map(c => `
      <div class="collab-post" style="margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <div style="display: flex; gap: 16px; align-items: center;">
            <img src="${c.thumbnail}" alt="${escHtml(c.title)}" style="width: 70px; height: 70px; border-radius: 12px; object-fit: cover;">
            <div>
              <h4 style="margin:0; font-size: 18px;">📁 ${escHtml(c.title)}</h4>
              <p style="margin:4px 0 0; font-size: 13px; color: var(--text-dim);">
                🎥 ${c.lessons_count} Videos | 👥 ${c.enrolled_count} Students | ₹${c.price * c.enrolled_count} Revenue | ⭐ ${c.rating || '0.0'}
              </p>
            </div>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button class="btn btn-primary btn-sm" onclick="openAddVideoToPlaylistModal(${c.id})">+ Add Video</button>
            <button class="btn btn-outline btn-sm" onclick="openManagePlaylistModal(${c.id})">Reorder Videos</button>
            <button class="btn btn-outline btn-sm" onclick="togglePublishCourse(${c.id})">${c.is_published ? 'Unpublish' : 'Publish'}</button>
            <button class="btn btn-outline btn-sm" style="color: #ef4444; border-color: #ef4444;" onclick="deleteCourse(${c.id})">Delete</button>
          </div>
        </div>

        ${c.lessons && c.lessons.length > 0 ? `
          <div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--border-glass);">
            <div style="font-size: 12px; font-weight: 700; color: var(--text-muted); margin-bottom: 8px;">PLAYLIST VIDEOS:</div>
            ${c.lessons.map((l, idx) => `
              <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px; padding: 6px 0;">
                <span>${idx + 1}. ${escHtml(l.title)}</span>
                <button class="btn btn-ghost btn-sm" style="color: #ef4444;" onclick="deleteLesson(${l.id})">Remove</button>
              </div>
            `).join('')}
          </div>
        ` : ''}
      </div>
    `).join('') || '<p style="color: var(--text-muted); padding: 20px;">No playlists created yet.</p>';

    // Render Single Videos Cards
    const singleVideosHtml = (stats.single_videos || []).map(c => `
      <div class="collab-post" style="margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <div style="display: flex; gap: 16px; align-items: center;">
            <img src="${c.thumbnail}" alt="${escHtml(c.title)}" style="width: 70px; height: 70px; border-radius: 12px; object-fit: cover;">
            <div>
              <h4 style="margin:0; font-size: 18px;">🎬 ${escHtml(c.title)}</h4>
              <p style="margin:4px 0 0; font-size: 13px; color: var(--text-dim);">
                👁️ ${c.views_count || 0} Views | 👥 ${c.enrolled_count} Enrollments | ₹${c.price * c.enrolled_count} Revenue | ${c.is_published ? '✅ Published' : '⏸️ Draft'}
              </p>
            </div>
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-outline btn-sm" onclick="togglePublishCourse(${c.id})">${c.is_published ? 'Unpublish' : 'Publish'}</button>
            <button class="btn btn-outline btn-sm" style="color: #ef4444; border-color: #ef4444;" onclick="deleteCourse(${c.id})">Delete</button>
          </div>
        </div>
      </div>
    `).join('') || '<p style="color: var(--text-muted); padding: 20px;">No single videos uploaded yet.</p>';

    if (playlistsList) playlistsList.innerHTML = playlistsHtml;
    if (singleVideosList) singleVideosList.innerHTML = singleVideosHtml;
    if (fullCoursesList) fullCoursesList.innerHTML = playlistsHtml + singleVideosHtml;

    renderLiveSessions(stats.my_sessions || [], liveList, false);
  } catch (e) { console.error(e); }
}

async function loadCreatorRequests() {
  const reqList = document.getElementById('creatorRequestsList');
  try {
    const res = await apiFetch('/requests/creator', 'GET');
    const data = await res.json();

    if (!data.requests || data.requests.length === 0) {
      reqList.innerHTML = `<p style="color: var(--text-muted); padding: 20px;">No 1-on-1 student session requests received.</p>`;
      return;
    }

    reqList.innerHTML = data.requests.map(r => `
      <div class="collab-post" style="margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <div>
            <h4 style="margin:0; font-size: 18px;">Topic: ${escHtml(r.topic)}</h4>
            <p style="font-size: 14px; color: var(--text-muted); margin: 6px 0;">From Student: <strong>${escHtml(r.student_name)}</strong></p>
            <p style="font-size: 13px; color: var(--text-dim); margin-bottom: 12px;">"${escHtml(r.description)}"</p>
            <div style="font-size: 12px; color: var(--secondary);">
              📅 Date: ${r.preferred_date} | ⏰ Time: ${r.preferred_time} (${r.duration_minutes} mins)
            </div>
          </div>
          <div style="text-align: right;">
            <span class="badge ${r.status === 'accepted' ? 'badge-beginner' : (r.status === 'pending' ? 'badge-intermediate' : 'badge-advanced')}">
              ${r.status.toUpperCase()}
            </span>
          </div>
        </div>

        ${r.status === 'pending' ? `
          <div style="margin-top: 16px; display: flex; gap: 10px;">
            <button class="btn btn-primary btn-sm" onclick="actionStudentRequest(${r.id}, 'accept')">Accept Request</button>
            <button class="btn btn-outline btn-sm" onclick="actionStudentRequest(${r.id}, 'decline')">Decline</button>
          </div>
        ` : ''}
      </div>
    `).join('');
  } catch (e) { console.error(e); }
}

async function actionStudentRequest(reqId, action) {
  const res = await apiFetch(`/requests/${reqId}/action`, 'POST', { action });
  if (res.ok) {
    showToast(`Request ${action}ed!`);
    loadCreatorRequests();
  } else {
    showToast('Failed to update request.', 'error');
  }
}

async function loadCreatorAnalytics() {
  const statsEl = document.getElementById('creatorAnalyticsStats');
  const reviewsEl = document.getElementById('creatorReviewsList');
  try {
    const res = await apiFetch('/dashboard/creator', 'GET');
    const stats = await res.json();

    statsEl.innerHTML = `
      <div class="stat-card">
        <span class="stat-lbl">Average Course Rating</span>
        <div class="stat-val">⭐ ${stats.avg_rating || '0.0'}</div>
      </div>
      <div class="stat-card">
        <span class="stat-lbl">Active Enrolled Students</span>
        <div class="stat-val">${stats.total_students || 0}</div>
      </div>
    `;

    reviewsEl.innerHTML = (stats.recent_reviews || []).map(r => `
      <div class="collab-post" style="margin-bottom: 12px;">
        <div style="display:flex; justify-content:space-between; margin-bottom: 6px;">
          <strong>${escHtml(r.user_name)}</strong>
          <span style="color: var(--gold)">⭐ ${r.rating}/5</span>
        </div>
        <p style="font-size: 13px; color: var(--text-muted);">${escHtml(r.comment)}</p>
      </div>
    `).join('') || '<p style="color: var(--text-muted);">No student reviews submitted yet.</p>';

  } catch (e) { console.error(e); }
}

async function loadCreatorProfile() {
  const profileEl = document.getElementById('creatorProfileCard');
  if (!currentUser) return;
  const pts = currentUser.points || 0;

  let googleHtml = '';
  try {
    const gRes = await apiFetch('/auth/google/status', 'GET');
    const gData = await gRes.json();
    const isConnected = gData.is_connected || gData.google_calendar_connected || currentUser.is_google_connected;

    if (isConnected) {
      const googleEmail = gData.google_email || currentUser.email;
      const lastSynced = gData.last_synced ? new Date(gData.last_synced).toLocaleString() : new Date().toLocaleString();

      googleHtml = `
        <div style="margin-top: 20px; padding: 20px; background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.25); border-radius: 16px;">
          <div style="color: #10b981; font-weight: 700; font-size: 15px; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
            <span>✓ Google Calendar Connected</span>
          </div>
          <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 4px;"><strong>Connected as:</strong> ${escHtml(googleEmail)}</p>
          <p style="font-size: 12px; color: var(--text-dim); margin-bottom: 14px;"><strong>Last synced:</strong> ${escHtml(lastSynced)}</p>
          <button class="btn btn-outline btn-sm" style="color: #ef4444; border-color: rgba(239,68,68,0.4);" onclick="disconnectGoogleCalendar()">Disconnect Google Calendar</button>
        </div>
      `;
    } else {
      googleHtml = `
        <div style="margin-top: 20px; padding: 20px; background: var(--bg-deep); border: 1px solid var(--border-glass); border-radius: 16px;">
          <div style="font-weight: 700; font-size: 15px; margin-bottom: 6px;">Google Calendar & Meet Integration</div>
          <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 14px;">Connect your Google Calendar to automatically generate Google Meet links for every scheduled session.</p>
          <button class="btn btn-primary btn-sm" onclick="connectGoogleCalendar()">Connect Google Calendar 📅</button>
        </div>
      `;
    }
  } catch (e) {
    console.error('Error fetching Google status:', e);
  }

  profileEl.innerHTML = `
    <h4 style="font-size: 20px; margin-bottom: 12px;">${escHtml(currentUser.name)}</h4>
    <p style="color: var(--text-muted); margin-bottom: 8px;"><strong>Email:</strong> ${escHtml(currentUser.email)}</p>
    <p style="color: var(--text-muted); margin-bottom: 8px;"><strong>Role:</strong> Verified Creator</p>
    <p style="color: var(--gold); margin-bottom: 8px;"><strong>Creator Points:</strong> 🪙 ${pts} Points</p>
    <p style="color: var(--text-dim); font-size: 12px; margin-bottom: 12px;">Joined: ${currentUser.joined_at ? new Date(currentUser.joined_at).toLocaleDateString() : 'N/A'}</p>
    ${googleHtml}
  `;
}

async function connectGoogleCalendar() {
  try {
    const res = await apiFetch('/auth/google/url', 'GET');
    const data = await res.json();
    const url = data.url || data.auth_url;
    if (url) {
      window.location.href = url;
    } else {
      showToast(data.error || 'Google OAuth credentials missing in configuration', 'error');
    }
  } catch (e) {
    showToast('Failed to initiate Google OAuth flow.', 'error');
  }
}
async function disconnectGoogleCalendar() {
  if (!confirm('Are you sure you want to disconnect Google Calendar?')) return;
  try {
    const res = await apiFetch('/auth/google/disconnect', 'POST');
    const data = await res.json();
    if (res.ok) {
      if (data.user) currentUser = data.user;
      showToast('Disconnected from Google Calendar.');
      await loadCreatorProfile();
    } else {
      showToast(data.error || 'Failed to disconnect.', 'error');
    }
  } catch (e) {
    showToast('Error disconnecting Google Calendar.', 'error');
  }
}


// Course Creation & Upload Handlers
async function createCourseSubmit() {
  const title = document.getElementById('cTitle').value.trim();
  const description = document.getElementById('cDesc').value.trim();
  const category = document.getElementById('cCategory').value;
  const level = document.getElementById('cLevel').value;
  const price = document.getElementById('cPrice').value;
  const points_price = document.getElementById('cPts').value;
  let thumbnail_url = document.getElementById('cThumbnailUrl').value.trim();
  const thumbnailFile = document.getElementById('cThumbnailFile').files[0];

  if (!title || !description) return showToast('Title and description are required.', 'error');

  if (thumbnailFile) {
    const formData = new FormData();
    formData.append('file', thumbnailFile);
    const upRes = await fetch(`${API}/upload/file`, { method: 'POST', body: formData, credentials: 'include' });
    const upData = await upRes.json();
    if (upRes.ok) thumbnail_url = upData.url;
  }

  const res = await apiFetch('/courses', 'POST', {
    title, description, category, level, price, points_price, thumbnail_url, is_published: true
  });

  if (res.ok) {
    showToast('Course created and published!');
    closeModal('addCourseModal');
    loadCreatorDashboard();
  } else {
    showToast('Failed to create course.', 'error');
  }
}

function openAddVideoModal(courseId) {
  document.getElementById('vCourseId').value = courseId;
  openModal('addVideoModal');
}

async function addLessonSubmit() {
  const courseId = document.getElementById('vCourseId').value;
  const title = document.getElementById('vTitle').value.trim();
  const description = document.getElementById('vDesc').value.trim();
  let video_url = document.getElementById('vVideoUrl').value.trim();
  const videoFile = document.getElementById('vVideoFile').files[0];

  if (!title) return showToast('Lesson title is required.', 'error');

  if (videoFile) {
    const formData = new FormData();
    formData.append('file', videoFile);
    showToast('Uploading video file to storage...');
    const upRes = await fetch(`${API}/upload/file`, { method: 'POST', body: formData, credentials: 'include' });
    const upData = await upRes.json();
    if (upRes.ok) video_url = upData.url;
  }

  if (!video_url) return showToast('Please upload a video file or provide a video URL.', 'error');

  const res = await apiFetch(`/courses/${courseId}/lessons`, 'POST', {
    title, description, video_url
  });

  if (res.ok) {
    showToast('Lesson video added successfully!');
    closeModal('addVideoModal');
    loadCreatorDashboard();
  } else {
    showToast('Failed to add lesson.', 'error');
  }
}

async function togglePublishCourse(courseId) {
  const res = await apiFetch(`/courses/${courseId}/publish`, 'POST');
  if (res.ok) {
    showToast('Course publish state updated.');
    loadCreatorDashboard();
  }
}

async function deleteCourse(courseId) {
  if (!confirm('Are you sure you want to delete this course?')) return;
  const res = await apiFetch(`/courses/${courseId}`, 'DELETE');
  if (res.ok) {
    showToast('Course deleted.');
    loadCreatorDashboard();
  }
}

async function deleteLesson(lessonId) {
  if (!confirm('Remove this video lesson?')) return;
  const res = await apiFetch(`/lessons/${lessonId}`, 'DELETE');
  if (res.ok) {
    showToast('Lesson removed.');
    loadCreatorDashboard();
  }
}

// Live Session Creation & Management
async function addLiveSessionSubmit() {
  const title = document.getElementById('lTitle').value.trim();
  const topic = document.getElementById('lTopic').value.trim();
  const description = document.getElementById('lDesc').value.trim();
  const scheduled_at = document.getElementById('lTime').value;
  const duration_minutes = document.getElementById('lDuration').value;
  const max_students = document.getElementById('lMax').value;
  const price = document.getElementById('lPrice').value;

  if (!title || !topic || !scheduled_at) return showToast('Title, topic, and date are required.', 'error');

  const res = await apiFetch('/live', 'POST', {
    title, topic, description, scheduled_at, duration_minutes, max_students, price
  });

  if (res.ok) {
    showToast('Live session scheduled with Google Meet link!');
    closeModal('addLiveModal');
    loadCreatorDashboard();
  } else {
    const err = await res.json().catch(() => ({}));
    showToast(err.error || 'Failed to schedule live session.', 'error');
  }
}

async function updateSessionStatus(sessionId, status) {
  const res = await apiFetch(`/live/${sessionId}/status`, 'POST', { status });
  if (res.ok) {
    const data = await res.json();
    showToast(`Session status updated to ${status.toUpperCase()}`);
    if (status === 'live' && data.session && data.session.meeting_link) {
      const link = data.session.meeting_link.trim();
      if (link.startsWith('https://meet.google.com/') || link.startsWith('https://hangouts.google.com/') || link.startsWith('https://tel.meet/')) {
        window.open(link, '_blank');
      } else {
        showToast('Stored meeting URL is invalid.', 'error');
      }
    }
    if (currentUser?.role === 'creator') loadCreatorDashboard();
    loadCourses();
    if (document.getElementById('dash-section-dashboard')?.classList.contains('active')) {
      loadDashboard();
    }
  } else {
    const err = await res.json();
    showToast(err.error || 'Failed to update session status', 'error');
  }
}

async function openEditLiveModal(sessionId) {
  try {
    const res = await apiFetch('/dashboard/creator', 'GET');
    const data = await res.json();
    const sess = (data.my_sessions || []).find(s => s.id === sessionId);
    if (!sess) return showToast('Session not found.', 'error');

    document.getElementById('editLiveId').value = sess.id;
    document.getElementById('elTitle').value = sess.title || '';
    document.getElementById('elTopic').value = sess.topic || '';
    document.getElementById('elDesc').value = sess.description || '';
    document.getElementById('elTime').value = sess.scheduled_at ? sess.scheduled_at.slice(0, 16) : '';
    document.getElementById('elDuration').value = sess.duration_minutes || 60;
    document.getElementById('elMax').value = sess.max_students || 50;
    document.getElementById('elPrice').value = sess.price || 0;
    document.getElementById('elLink').value = sess.meeting_link || '';

    openModal('editLiveModal');
  } catch (e) {
    showToast('Failed to load session details.', 'error');
  }
}

async function submitEditLiveSession() {
  const id = document.getElementById('editLiveId').value;
  const title = document.getElementById('elTitle').value.trim();
  const topic = document.getElementById('elTopic').value.trim();
  const description = document.getElementById('elDesc').value.trim();
  const scheduled_at = document.getElementById('elTime').value;
  const duration_minutes = document.getElementById('elDuration').value;
  const max_students = document.getElementById('elMax').value;
  const price = document.getElementById('elPrice').value;
  const meeting_link = document.getElementById('elLink').value.trim();

  if (!title || !topic) return showToast('Title and topic are required.', 'error');

  const res = await apiFetch(`/live/${id}`, 'PUT', {
    title, topic, description, scheduled_at, duration_minutes, max_students, price, meeting_link
  });

  if (res.ok) {
    showToast('Live session updated!');
    closeModal('editLiveModal');
    if (currentUser?.role === 'creator') loadCreatorDashboard();
    loadCourses();
  } else {
    showToast('Failed to update session.', 'error');
  }
}

async function openRegisteredStudentsModal(sessionId) {
  const modalTitle = document.getElementById('registeredStudentsTitle');
  const listEl = document.getElementById('registeredStudentsList');
  listEl.innerHTML = '<p style="color: var(--text-muted); font-size: 13px;">Loading registered students...</p>';
  openModal('registeredStudentsModal');

  try {
    const res = await apiFetch(`/live/${sessionId}/students`, 'GET');
    const data = await res.json();
    const students = data.students || [];
    const sess = data.session || {};

    if (modalTitle) modalTitle.textContent = `Registered Students: ${sess.title || ''}`;

    if (students.length === 0) {
      listEl.innerHTML = '<p style="color: var(--text-muted); padding: 15px; font-size: 13px;">No learners have booked this session yet.</p>';
      return;
    }

    listEl.innerHTML = students.map((st, idx) => `
      <div style="display: flex; justify-content: space-between; align-items: center; background: var(--bg-deep); border: 1px solid var(--border-glass); padding: 12px 16px; border-radius: 12px;">
        <div>
          <strong style="font-size: 14px; display: block;">${idx + 1}. ${escHtml(st.name)}</strong>
          <span style="font-size: 12px; color: var(--text-dim);">${escHtml(st.email)}</span>
        </div>
        <span style="font-size: 11px; color: var(--text-muted);">Booked ${new Date(st.booked_at).toLocaleDateString()}</span>
      </div>
    `).join('');
  } catch (e) {
    listEl.innerHTML = '<p style="color: #ef4444; padding: 15px; font-size: 13px;">Failed to load registered students.</p>';
  }
}

// Interactive Video Player & Timestamp Progress Sync
async function openVideoPlayer(courseId, lessonId = null) {
  if (!currentUser) {
    showToast('Please sign in as a Learner to view this course.', 'error');
    openModal('learnerLoginModal');
    return;
  }
  if (currentUser.role === 'creator') {
    showToast('Creators manage courses inside Creator Studio.', 'error');
    showPage('creator');
    return;
  }

  try {
    const res = await apiFetch(`/courses/${courseId}`, 'GET');
    const data = await res.json();
    activeCourse = data.course;

    if (!activeCourse || !activeCourse.lessons || activeCourse.lessons.length === 0) {
      return showToast('No video lessons available in this course yet.', 'error');
    }

    // Check learner progress
    let startTimestamp = 0;
    if (currentUser) {
      const pRes = await apiFetch(`/progress/${courseId}`, 'GET');
      const pData = await pRes.json();
      if (pData.enrollment) {
        if (!lessonId && pData.enrollment.last_lesson_id) {
          lessonId = pData.enrollment.last_lesson_id;
        }
        startTimestamp = pData.enrollment.last_timestamp || 0;
      }
    }

    activeLesson = activeCourse.lessons.find(l => l.id === lessonId) || activeCourse.lessons[0];

    document.getElementById('playerCourseTitle').textContent = activeCourse.title;
    document.getElementById('playerLessonTitle').textContent = activeLesson.title;
    document.getElementById('playerLessonDesc').textContent = activeLesson.description || '';

    const videoEl = document.getElementById('activeVideoPlayer');
    videoEl.src = activeLesson.video_url;

    // Attach progress tracking events
    videoEl.onloadedmetadata = () => {
      if (startTimestamp > 0 && startTimestamp < videoEl.duration - 2) {
        videoEl.currentTime = startTimestamp;
        showToast(`Resuming from ${Math.floor(startTimestamp)}s`);
      }
    };

    videoEl.ontimeupdate = throttle(() => {
      saveVideoProgress(videoEl.currentTime, false);
    }, 5000);

    videoEl.onended = () => {
      saveVideoProgress(videoEl.currentTime, true);
      showToast('Lesson completed! Progress saved.');
    };

    // Render Lesson Playlist
    const listEl = document.getElementById('playerLessonsList');
    listEl.innerHTML = activeCourse.lessons.map((l, idx) => `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: ${l.id === activeLesson.id ? 'rgba(139,92,246,0.15)' : 'var(--bg-deep)'}; border-radius: 8px; margin-bottom: 6px; cursor: pointer;" onclick="switchVideoLesson(${l.id})">
        <span style="font-size: 14px; font-weight: 600;">${idx + 1}. ${escHtml(l.title)}</span>
        <span style="font-size: 12px; color: var(--text-muted);">${l.id === activeLesson.id ? '▶️ Playing' : 'Watch'}</span>
      </div>
    `).join('');

    // Setup 1-on-1 Request Button
    const reqBtn = document.getElementById('btnRequestLiveFromPlayer');
    reqBtn.onclick = () => openRequestLiveModal(activeCourse.created_by);

    openModal('videoPlayerModal');
  } catch (e) { console.error(e); }
}

function switchVideoLesson(lessonId) {
  openVideoPlayer(activeCourse.id, lessonId);
}

async function saveVideoProgress(currentTime, isCompleted) {
  if (!currentUser || !activeLesson) return;
  try {
    await apiFetch('/progress/update', 'POST', {
      lesson_id: activeLesson.id,
      timestamp: Math.floor(currentTime),
      is_completed: isCompleted
    });
  } catch (e) { console.warn('Progress sync failed.'); }
}

// 1-on-1 Live Request Modal Logic
function openRequestLiveModal(creatorId) {
  if (!currentUser) return openModal('learnerLoginModal');
  document.getElementById('reqCreatorId').value = creatorId;
  openModal('requestLiveModal');
}

async function submitLiveRequest() {
  const creator_id = document.getElementById('reqCreatorId').value;
  const topic = document.getElementById('reqTopic').value.trim();
  const description = document.getElementById('reqDesc').value.trim();
  const preferred_date = document.getElementById('reqDate').value;
  const preferred_time = document.getElementById('reqTime').value;

  if (!topic || !description || !preferred_date || !preferred_time) {
    return showToast('Please complete all details.', 'error');
  }

  const res = await apiFetch('/requests/live', 'POST', {
    creator_id, topic, description, preferred_date, preferred_time
  });

  if (res.ok) {
    showToast('1-on-1 Live Session Request submitted!');
    closeModal('requestLiveModal');
  } else {
    showToast('Failed to submit request.', 'error');
  }
}

// Enrollment & Bookings Actions
async function enroll(id) {
  const res = await apiFetch(`/enroll/${id}`, 'POST');
  if (res.ok) { showToast('Enrolled successfully!'); loadCourses(); }
  else { const d = await res.json(); showToast(d.error, 'error'); }
}

async function buyWithPoints(id) {
  const res = await apiFetch(`/purchase-points/${id}`, 'POST');
  const d = await res.json();
  if (res.ok) {
    showToast(`Purchased! Remaining Points: ${d.points}`);
    currentUser.points = d.points;
    updateNavForUser();
    loadCourses();
  } else showToast(d.error, 'error');
}


async function bookSession(sessionId) {
  if (!currentUser) return openModal('learnerLoginModal');
  const res = await apiFetch(`/live/book/${sessionId}`, 'POST');
  if (res.ok) {
    showToast('Seat reserved successfully!');
    await fetchUserBookings();
    loadCourses();
    loadDashboard();
  } else {
    const d = await res.json();
    showToast(d.error || 'Failed to book session.', 'error');
  }
}

// Collaboration Hub
async function loadCollaboration() {
  const feed = document.getElementById('collabFeed');
  if (!currentUser) return openModal('learnerLoginModal');
  try {
    const res = await apiFetch('/collaboration', 'GET');
    const data = await res.json();

    if (!data.posts || data.posts.length === 0) {
      feed.innerHTML = `<p style="color: var(--text-muted); padding: 20px;">No collaboration posts found.</p>`;
      return;
    }

    feed.innerHTML = data.posts.map(p => `
      <div class="collab-post">
        <div class="post-header">
          <div class="post-user">
            <div class="user-avatar">🚀</div>
            <div class="user-info">
              <strong>${escHtml(p.author_name)}</strong>
              <small>${new Date(p.created_at).toLocaleDateString()}</small>
            </div>
          </div>
        </div>
        <div class="post-content">
          <h4>${escHtml(p.title)}</h4>
          <p>${escHtml(p.description)}</p>
          <div class="skills-list">
            ${p.required_skills.map(s => `<span class="skill-badge">${escHtml(s)}</span>`).join('')}
          </div>
        </div>
        <div class="post-footer">
          <div class="post-meta">
            <span>👥 Needs ${p.members_needed} members</span>
          </div>
          <div style="font-size: 13px; font-weight: 700; color: var(--gold);">${escHtml(p.contact_info)}</div>
        </div>
      </div>
    `).join('');
  } catch (e) { feed.innerHTML = 'Error loading feed.'; }
}

async function addCollabPost() {
  const title = document.getElementById('colTitle').value.trim();
  const description = document.getElementById('colDesc').value.trim();
  const required_skills = document.getElementById('colSkills').value.trim();
  const members_needed = document.getElementById('colMembers').value;
  const contact_info = document.getElementById('colContact').value.trim();

  if (!title || !description || !required_skills || !contact_info) return showToast('Please complete all fields.', 'error');

  const res = await apiFetch('/collaboration', 'POST', { title, description, required_skills, members_needed, contact_info });
  if (res.ok) {
    showToast('Project request posted!');
    closeModal('addCollabModal');
    loadCollaboration();
  } else {
    showToast('Failed to post project request.', 'error');
  }
}

// UI Utilities & Modal Helpers
function openModal(id) { 
  const modalEl = document.getElementById(id);
  if (modalEl) {
    modalEl.classList.add('active');
    document.body.style.overflow = 'hidden';
  }
}
function closeModal(id) { 
  const modalEl = document.getElementById(id);
  if (modalEl) {
    modalEl.classList.remove('active');
    const activeModals = document.querySelectorAll('.modal-overlay.active');
    if (activeModals.length === 0) {
      document.body.style.overflow = '';
    }
  }
}
function switchModal(f, t) { closeModal(f); setTimeout(() => openModal(t), 200); }
function showToast(m, type = 'success') {
  const t = document.getElementById('toast');
  t.textContent = m; t.className = `toast active ${type}`;
  setTimeout(() => t.className = 'toast', 3000);
}

// Global modal handlers: Click outside backdrop & Escape key to dismiss
document.addEventListener('click', (e) => {
  if (e.target && e.target.classList && e.target.classList.contains('modal-overlay')) {
    closeModal(e.target.id);
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const activeModals = document.querySelectorAll('.modal-overlay.active');
    activeModals.forEach(m => closeModal(m.id));
  }
});

async function apiFetch(e, m = 'GET', b = null) {
  const o = { method: m, credentials: 'include', headers: { 'Content-Type': 'application/json' } };
  if (b) o.body = JSON.stringify(b);
  return fetch(`${API}${e}`, o);
}

function escHtml(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

function filterCourses() {
  const s = document.getElementById('searchInput').value.toLowerCase();
  const f = allCourses.filter(x => !s || x.title.toLowerCase().includes(s) || (x.category || '').toLowerCase().includes(s) || (x.instructor || '').toLowerCase().includes(s));
  renderCourses(f, document.getElementById('coursesGrid'), true);
}

function throttle(func, limit) {
  let inThrottle;
  return function() {
    const args = arguments;
    const context = this;
    if (!inThrottle) {
      func.apply(context, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

// ─── Content Upload & Progress Bar Handlers ─────────────────────────────────────

function uploadFileWithProgress(file, progressWrapId, progressBarId, progressTextId, statusText = 'Uploading File...') {
  return new Promise((resolve, reject) => {
    if (!file) return resolve('');

    const wrapEl = document.getElementById(progressWrapId);
    const barEl = document.getElementById(progressBarId);
    const textEl = document.getElementById(progressTextId);

    if (wrapEl) wrapEl.style.display = 'block';
    if (barEl) barEl.style.width = '0%';
    if (textEl) textEl.textContent = '0%';

    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('file', file);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        if (barEl) barEl.style.width = `${percent}%`;
        if (textEl) textEl.textContent = `${percent}%`;
      }
    };

    xhr.onload = () => {
      if (wrapEl) wrapEl.style.display = 'none';
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const res = JSON.parse(xhr.responseText);
          resolve(res.url || '');
        } catch (err) {
          resolve('');
        }
      } else {
        reject(new Error('Upload failed'));
      }
    };

    xhr.onerror = () => {
      if (wrapEl) wrapEl.style.display = 'none';
      reject(new Error('Network error during upload'));
    };

    xhr.withCredentials = true;
    xhr.open('POST', `${API}/upload/file`);
    xhr.send(formData);
  });
}

function togglePriceField(prefix) {
  const isPaid = document.getElementById(`${prefix}IsPaid`).value === 'paid';
  const priceGroup = document.getElementById(`${prefix}PriceGroup`);
  if (priceGroup) priceGroup.style.display = isPaid ? 'block' : 'none';
}

function openUploadChoiceModal() {
  openModal('uploadChoiceModal');
}

async function submitSingleVideoUpload() {
  const title = document.getElementById('svTitle').value.trim();
  const description = document.getElementById('svDesc').value.trim();
  const category = document.getElementById('svCategory').value;
  const level = document.getElementById('svLevel').value;
  const tags = document.getElementById('svTags').value.trim();
  const isPaid = document.getElementById('svIsPaid').value === 'paid';
  const price = isPaid ? parseInt(document.getElementById('svPrice').value || 0) : 0;
  const is_published = document.getElementById('svPublish').checked;

  let thumbnail_url = document.getElementById('svThumbnailUrl').value.trim();
  let video_url = document.getElementById('svVideoUrl').value.trim();

  const thumbFile = document.getElementById('svThumbnailFile').files[0];
  const videoFile = document.getElementById('svVideoFile').files[0];

  if (!title || !description) return showToast('Title and description are required.', 'error');
  if (!videoFile && !video_url) return showToast('Please select a video file or enter a Video URL.', 'error');

  try {
    if (thumbFile) {
      thumbnail_url = await uploadFileWithProgress(thumbFile, 'svProgressWrap', 'svProgressBar', 'svProgressText', 'Uploading Thumbnail Image...');
    }
    if (videoFile) {
      video_url = await uploadFileWithProgress(videoFile, 'svProgressWrap', 'svProgressBar', 'svProgressText', 'Uploading Video File...');
    }

    const res = await apiFetch('/upload/single-video', 'POST', {
      title, description, category, level, tags, price, thumbnail_url, video_url, is_published
    });

    if (res.ok) {
      showToast('Single video uploaded and published!');
      closeModal('uploadSingleVideoModal');
      loadCreatorDashboard();
    } else {
      const errData = await res.json();
      showToast(errData.error || 'Failed to upload video.', 'error');
    }
  } catch (e) {
    showToast('File upload failed. Please try again.', 'error');
  }
}

async function submitCreatePlaylist() {
  const title = document.getElementById('plTitle').value.trim();
  const description = document.getElementById('plDesc').value.trim();
  const category = document.getElementById('plCategory').value;
  const level = document.getElementById('plLevel').value;
  const tags = document.getElementById('plTags').value.trim();
  const isPaid = document.getElementById('plIsPaid').value === 'paid';
  const price = isPaid ? parseInt(document.getElementById('plPrice').value || 0) : 0;
  const is_published = document.getElementById('plPublish').checked;

  let thumbnail_url = document.getElementById('plThumbnailUrl').value.trim();
  const thumbFile = document.getElementById('plThumbnailFile').files[0];

  if (!title || !description) return showToast('Playlist title and description are required.', 'error');

  try {
    if (thumbFile) {
      thumbnail_url = await uploadFileWithProgress(thumbFile, 'plProgressWrap', 'plProgressBar', 'plProgressText', 'Uploading Playlist Thumbnail...');
    }

    const res = await apiFetch('/playlists', 'POST', {
      title, description, category, level, tags, price, thumbnail_url, is_published, is_single_video: false
    });

    if (res.ok) {
      const data = await res.json();
      showToast('Playlist created! Add your first video lesson.');
      closeModal('createPlaylistModal');
      await loadCreatorDashboard();
      openAddVideoToPlaylistModal(data.course.id);
    } else {
      const errData = await res.json();
      showToast(errData.error || 'Failed to create playlist.', 'error');
    }
  } catch (e) {
    showToast('Upload failed.', 'error');
  }
}

async function openAddVideoToPlaylistModal(targetPlaylistId = null) {
  const selectEl = document.getElementById('vpPlaylistSelect');
  selectEl.innerHTML = '<option value="">Loading playlists...</option>';
  openModal('addVideoToPlaylistModal');

  try {
    const res = await apiFetch('/dashboard/creator', 'GET');
    const data = await res.json();
    const playlists = data.playlists || [];

    if (playlists.length === 0) {
      selectEl.innerHTML = '<option value="">No playlists created yet. Create a playlist first.</option>';
      return;
    }

    selectEl.innerHTML = playlists.map(p => `
      <option value="${p.id}" ${targetPlaylistId && p.id === targetPlaylistId ? 'selected' : ''}>${escHtml(p.title)} (${p.lessons_count} videos)</option>
    `).join('');
  } catch (e) {
    selectEl.innerHTML = '<option value="">Failed to load playlists.</option>';
  }
}

async function submitAddVideoToPlaylist() {
  const playlistId = document.getElementById('vpPlaylistSelect').value;
  const title = document.getElementById('vpTitle').value.trim();
  const description = document.getElementById('vpDesc').value.trim();
  let video_url = document.getElementById('vpVideoUrl').value.trim();
  const videoFile = document.getElementById('vpVideoFile').files[0];

  if (!playlistId) return showToast('Please select a target playlist.', 'error');
  if (!title) return showToast('Video title is required.', 'error');
  if (!videoFile && !video_url) return showToast('Please select a video file or enter a Video URL.', 'error');

  try {
    if (videoFile) {
      video_url = await uploadFileWithProgress(videoFile, 'vpProgressWrap', 'vpProgressBar', 'vpProgressText', 'Uploading Video File...');
    }

    const res = await apiFetch(`/courses/${playlistId}/lessons`, 'POST', {
      title, description, video_url
    });

    if (res.ok) {
      showToast('Video added to playlist successfully!');
      closeModal('addVideoToPlaylistModal');
      loadCreatorDashboard();
    } else {
      const errData = await res.json();
      showToast(errData.error || 'Failed to add video.', 'error');
    }
  } catch (e) {
    showToast('Failed to upload video to playlist.', 'error');
  }
}

// ─── Playlist Video Reordering (Drag and Drop) ─────────────────────────
let currentManagingPlaylistId = null;
let currentPlaylistLessons = [];

async function openManagePlaylistModal(playlistId) {
  currentManagingPlaylistId = playlistId;
  const modalTitle = document.getElementById('managePlaylistTitle');

  try {
    const res = await apiFetch(`/courses/${playlistId}`, 'GET');
    const data = await res.json();
    const playlist = data.course;
    currentPlaylistLessons = playlist.lessons || [];

    if (modalTitle) modalTitle.textContent = `Manage Playlist: ${playlist.title}`;
    renderManageVideosList();
    openModal('managePlaylistModal');
  } catch (e) {
    showToast('Failed to load playlist videos.', 'error');
  }
}

function renderManageVideosList() {
  const listEl = document.getElementById('manageVideosList');
  if (currentPlaylistLessons.length === 0) {
    listEl.innerHTML = '<p style="color: var(--text-muted); padding: 20px;">No videos in this playlist yet.</p>';
    return;
  }

  listEl.innerHTML = currentPlaylistLessons.map((l, idx) => `
    <div class="draggable-item" data-id="${l.id}" data-index="${idx}" draggable="true" style="display: flex; align-items: center; justify-content: space-between; background: var(--bg-deep); border: 1px solid var(--border-glass); padding: 12px 16px; border-radius: 12px; cursor: move;">
      <div style="display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 18px; color: var(--text-dim);">☰</span>
        <div>
          <strong style="font-size: 14px;">${idx + 1}. ${escHtml(l.title)}</strong>
          <div style="font-size: 12px; color: var(--text-dim);">${l.duration_seconds ? Math.round(l.duration_seconds/60) + ' mins' : 'Video lesson'}</div>
        </div>
      </div>
      <button class="btn btn-ghost btn-sm" style="color: #ef4444;" onclick="deleteLesson(${l.id})">Delete</button>
    </div>
  `).join('');

  attachDragAndDropListeners();
}

function attachDragAndDropListeners() {
  const listEl = document.getElementById('manageVideosList');
  let draggedItem = null;

  listEl.querySelectorAll('.draggable-item').forEach(item => {
    item.addEventListener('dragstart', (e) => {
      draggedItem = item;
      item.style.opacity = '0.5';
    });

    item.addEventListener('dragend', () => {
      if (draggedItem) draggedItem.style.opacity = '1';
      draggedItem = null;
    });

    item.addEventListener('dragover', (e) => {
      e.preventDefault();
    });

    item.addEventListener('drop', (e) => {
      e.preventDefault();
      if (!draggedItem || draggedItem === item) return;

      const fromIndex = parseInt(draggedItem.dataset.index);
      const toIndex = parseInt(item.dataset.index);

      const movedItem = currentPlaylistLessons.splice(fromIndex, 1)[0];
      currentPlaylistLessons.splice(toIndex, 0, movedItem);

      renderManageVideosList();
    });
  });
}

async function saveReorderedPlaylist() {
  if (!currentManagingPlaylistId) return;
  const lessonIds = currentPlaylistLessons.map(l => l.id);

  const res = await apiFetch(`/playlists/${currentManagingPlaylistId}/reorder`, 'PUT', { lesson_ids: lessonIds });
  if (res.ok) {
    showToast('Video order saved successfully!');
    closeModal('managePlaylistModal');
    loadCreatorDashboard();
  } else {
    showToast('Failed to save video order.', 'error');
  }
}
