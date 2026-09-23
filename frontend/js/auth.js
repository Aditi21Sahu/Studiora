/**
 * STUDIORA — Auth Page Handlers
 * Handles login, registration, password reset, and auth state redirection.
 */

document.addEventListener('DOMContentLoaded', () => {
  // If already logged in, redirect away from login/register pages
  const token = api.getToken();
  const currentPath = window.location.pathname;
  if (token && (currentPath.includes('login.html') || currentPath.includes('register.html'))) {
    window.location.href = '/dashboard.html';
    return;
  }

  // Handle Login Form
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
      const errorMsg = document.getElementById('error-message');
      const submitBtn = document.getElementById('submit-btn');

      if (errorMsg) errorMsg.style.display = 'none';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerText = 'Signing in...';
      }

      try {
        const data = await api.post('/auth/login', { email, password });
        api.setToken(data.access_token);
        api.setUser({
          id: data.user_id,
          full_name: data.full_name,
          email: data.email
        });
        window.location.href = '/dashboard.html';
      } catch (err) {
        if (errorMsg) {
          errorMsg.textContent = err.message || 'Invalid email or password.';
          errorMsg.style.display = 'block';
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerText = 'Sign In';
        }
      }
    });
  }

  // Handle Register Form
  const registerForm = document.getElementById('register-form');
  if (registerForm) {
    registerForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fullName = document.getElementById('full_name').value.trim();
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
      const confirmPassword = document.getElementById('confirm_password').value;
      const errorMsg = document.getElementById('error-message');
      const submitBtn = document.getElementById('submit-btn');

      if (password !== confirmPassword) {
        if (errorMsg) {
          errorMsg.textContent = 'Passwords do not match.';
          errorMsg.style.display = 'block';
        }
        return;
      }

      if (errorMsg) errorMsg.style.display = 'none';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerText = 'Creating account...';
      }

      try {
        const data = await api.post('/auth/register', {
          full_name: fullName,
          email,
          password,
          confirm_password: confirmPassword
        });
        api.setToken(data.access_token);
        api.setUser({
          id: data.user_id,
          full_name: data.full_name,
          email: data.email
        });
        window.location.href = '/dashboard.html';
      } catch (err) {
        if (errorMsg) {
          errorMsg.textContent = err.message || 'Registration failed. Please try again.';
          errorMsg.style.display = 'block';
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerText = 'Create Account';
        }
      }
    });
  }

  // Handle Forgot Password Form
  const forgotForm = document.getElementById('forgot-password-form');
  if (forgotForm) {
    forgotForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('email').value.trim();
      const errorMsg = document.getElementById('error-message');
      const successMsg = document.getElementById('success-message');
      const submitBtn = document.getElementById('submit-btn');

      if (errorMsg) errorMsg.style.display = 'none';
      if (successMsg) successMsg.style.display = 'none';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerText = 'Sending link...';
      }

      try {
        const data = await api.post('/auth/forgot-password', { email });
        if (successMsg) {
          successMsg.textContent = data.message || 'Password reset link sent to your email.';
          successMsg.style.display = 'block';
        }
      } catch (err) {
        if (errorMsg) {
          errorMsg.textContent = err.message || 'Failed to request reset.';
          errorMsg.style.display = 'block';
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerText = 'Send Reset Link';
        }
      }
    });
  }

  // Password Visibility Toggle
  const toggleBtns = document.querySelectorAll('.toggle-password-btn');
  toggleBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-target');
      const input = document.getElementById(targetId);
      if (input) {
        input.type = input.type === 'password' ? 'text' : 'password';
      }
    });
  });
});
