/**
 * Enterprise Authentication & Firebase Identity Controller (auth.js)
 * Manages Firebase Web Client SDK, Email/Password auth, Google Popup sign-in,
 * One-Click Role Simulations, and Flask backend JWT session bridge.
 */

document.addEventListener("DOMContentLoaded", () => {
    // --------------------------------------------------------------------------
    // 1. DOM Elements
    // --------------------------------------------------------------------------
    const tabSignIn = document.getElementById("tabSignIn");
    const tabSignUp = document.getElementById("tabSignUp");
    const authFormHeading = document.getElementById("authFormHeading");
    const authFormSubheading = document.getElementById("authFormSubheading");
    const groupFullName = document.getElementById("groupFullName");
    const inputFullName = document.getElementById("inputFullName");
    const groupRole = document.getElementById("groupRole");
    const selectRole = document.getElementById("selectRole");
    const inputEmail = document.getElementById("inputEmail");
    const inputPassword = document.getElementById("inputPassword");
    const btnTogglePassword = document.getElementById("btnTogglePassword");
    const checkRemember = document.getElementById("checkRemember");
    const btnSubmitAuth = document.getElementById("btnSubmitAuth");
    const btnSubmitText = document.getElementById("btnSubmitText");
    const btnSubmitSpinner = document.getElementById("btnSubmitSpinner");
    const btnGoogleSignIn = document.getElementById("btnGoogleSignIn");
    const authAlertBanner = document.getElementById("authAlertBanner");
    const authAlertIcon = document.getElementById("authAlertIcon");
    const authAlertMessage = document.getElementById("authAlertMessage");
    const btnSimulateDirector = document.getElementById("btnSimulateDirector");
    const btnSimulateRequester = document.getElementById("btnSimulateRequester");
    const toastContainer = document.getElementById("toastContainer");

    let currentMode = "signin"; // 'signin' or 'signup'
    let isSubmitting = false;

    // Configuration from window context
    const config = window.PROCUREAI_CONFIG || {};
    const projectId = config.projectId || "procureai-c4588";
    const apiKey = config.apiKey || "AIzaSyAWoCv5PuugDdGQiBkEv32BDKi15jJWDuc";
    const appId = config.appId || "1:377887502646:web:123249e49f82ab7e1b4397";
    const nextUrl = config.nextUrl || "/dashboard";

    // --------------------------------------------------------------------------
    // 2. Firebase Client SDK Initialization
    // --------------------------------------------------------------------------
    let firebaseAuth = null;
    let googleProvider = null;

    try {
        if (typeof firebase !== "undefined") {
            const firebaseConfig = {
                apiKey: apiKey,
                authDomain: `${projectId}.firebaseapp.com`,
                projectId: projectId,
                storageBucket: `${projectId}.firebasestorage.app`,
                appId: appId
            };

            if (!firebase.apps || firebase.apps.length === 0) {
                firebase.initializeApp(firebaseConfig);
            }
            firebaseAuth = firebase.auth();
            googleProvider = new firebase.auth.GoogleAuthProvider();
            googleProvider.addScope("email");
            googleProvider.addScope("profile");

            // Check if user was redirected back from Google authentication
            firebaseAuth.getRedirectResult().then(async (result) => {
                if (result && result.user) {
                    setFormLoading(true, "Verifying Google account...");
                    const idToken = await result.user.getIdToken(true);
                    await exchangeTokenWithFlask(idToken, true);
                }
            }).catch(err => {
                if (err.code !== "auth/null-user") {
                    console.warn("Google redirect notice:", err);
                }
            });
        } else {
            console.warn("Firebase SDK script not loaded from CDN.");
        }
    } catch (fbInitErr) {
        console.warn("Firebase client initialization notice:", fbInitErr.message);
    }

    // --------------------------------------------------------------------------
    // 3. UI Helpers: Alerts, Spinners, Toasts
    // --------------------------------------------------------------------------
    function showAlert(message, type = "danger") {
        authAlertBanner.classList.remove("d-none", "alert-danger", "alert-success", "alert-warning", "alert-info");
        authAlertBanner.classList.add(`alert-${type}`);
        const icons = { danger: "⛔", warning: "⚠️", success: "✓", info: "ℹ️" };
        authAlertIcon.textContent = icons[type] || "⚠️";
        authAlertMessage.textContent = message;
        authAlertBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function hideAlert() {
        authAlertBanner.classList.add("d-none");
    }

    function showToast(message, type = "info") {
        if (!toastContainer) return;
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        const icons = { success: "✓", warning: "⚠️", danger: "⛔", info: "ℹ️" };
        toast.innerHTML = `<span>${icons[type] || "ℹ️"}</span><span>${message}</span>`;
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(12px)";
            toast.style.transition = "all 0.3s ease";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    function setFormLoading(loading, loadingText = "Verifying Credentials...") {
        isSubmitting = loading;
        btnSubmitAuth.disabled = loading;
        btnGoogleSignIn.disabled = loading;
        if (btnSimulateDirector) btnSimulateDirector.disabled = loading;
        if (btnSimulateRequester) btnSimulateRequester.disabled = loading;

        if (loading) {
            btnSubmitSpinner.classList.remove("d-none");
            btnSubmitText.textContent = loadingText;
            btnSubmitAuth.style.opacity = "0.8";
        } else {
            btnSubmitSpinner.classList.add("d-none");
            btnSubmitText.textContent = currentMode === "signin" ? "Sign In to Gatekeeper →" : "Create Account →";
            btnSubmitAuth.style.opacity = "1";
        }
    }

    // --------------------------------------------------------------------------
    // 4. Tab Switching: Sign In vs Create Account
    // --------------------------------------------------------------------------
    tabSignIn.addEventListener("click", () => {
        if (currentMode === "signin") return;
        currentMode = "signin";
        tabSignIn.classList.add("active");
        tabSignUp.classList.remove("active");
        tabSignIn.setAttribute("aria-selected", "true");
        tabSignUp.setAttribute("aria-selected", "false");

        authFormHeading.textContent = "Sign In to Gatekeeper";
        authFormSubheading.textContent = "Authenticate with your corporate credentials to access the procurement console.";
        groupFullName.classList.add("d-none");
        if (groupRole) groupRole.classList.add("d-none");
        inputFullName.required = false;
        btnSubmitText.textContent = "Sign In to Gatekeeper →";
        const googleSpan = btnGoogleSignIn.querySelector("span");
        if (googleSpan) googleSpan.textContent = "Continue with Google";
        hideAlert();
    });

    tabSignUp.addEventListener("click", () => {
        if (currentMode === "signup") return;
        currentMode = "signup";
        tabSignUp.classList.add("active");
        tabSignIn.classList.remove("active");
        tabSignUp.setAttribute("aria-selected", "true");
        tabSignIn.setAttribute("aria-selected", "false");

        authFormHeading.textContent = "Create Gatekeeper Account";
        authFormSubheading.textContent = "Set up your corporate procurement profile for automated AI requisitions.";
        groupFullName.classList.remove("d-none");
        if (groupRole) groupRole.classList.remove("d-none");
        inputFullName.required = true;
        btnSubmitText.textContent = "Create Account →";
        const googleSpan = btnGoogleSignIn.querySelector("span");
        if (googleSpan) googleSpan.textContent = "Sign Up with Google";
        hideAlert();
    });

    // --------------------------------------------------------------------------
    // 5. Password Visibility Toggle
    // --------------------------------------------------------------------------
    btnTogglePassword.addEventListener("click", () => {
        const isPassword = inputPassword.getAttribute("type") === "password";
        inputPassword.setAttribute("type", isPassword ? "text" : "password");
        btnTogglePassword.textContent = isPassword ? "🙈" : "👁️";
    });

    // --------------------------------------------------------------------------
    // 6. Token Exchange Helper (Firebase Client ID Token -> Flask Session)
    // --------------------------------------------------------------------------
    async function exchangeTokenWithFlask(idToken, remember, clientRole = null) {
        setFormLoading(true, "Establishing Secure Session...");

        try {
            const resp = await fetch("/api/login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({
                    id_token: idToken,
                    remember: remember,
                    role: clientRole
                })
            });

            const result = await resp.json();

            if (resp.ok && result.success) {
                const displayName = result.user ? result.user.name : "User";
                const displayRole = result.user ? result.user.role : "Authenticated";
                showToast(`Welcome, ${displayName}! Signed in as ${displayRole}.`, "success");
                showAlert(`Identity verified as ${displayName} (${displayRole})! Redirecting to command center...`, "success");

                setTimeout(() => {
                    window.location.href = result.redirect_url || nextUrl || "/dashboard";
                }, 600);
            } else {
                setFormLoading(false);
                showAlert(result.error || "Authentication verification failed on server.");
            }
        } catch (err) {
            setFormLoading(false);
            console.error("Token exchange network error:", err);
            showAlert(`Session creation failed: ${err.message}`);
        }
    }

    // --------------------------------------------------------------------------
    // 7. Form Submission: Create Account & Sign In with Hybrid Fallback
    // --------------------------------------------------------------------------
    const authForm = document.getElementById("authForm");
    authForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (isSubmitting) return;

        hideAlert();
        const email = inputEmail.value.trim();
        const password = inputPassword.value;
        const remember = checkRemember.checked;
        const fullName = inputFullName.value.trim();
        const selectedRole = selectRole ? selectRole.value : "Requester";

        if (!email || !password) {
            showAlert("Please enter both your corporate email and password.");
            return;
        }

        if (password.length < 6) {
            showAlert("Password must be at least 6 characters long.");
            return;
        }

        if (currentMode === "signup" && !fullName) {
            showAlert("Please enter your full name to create an account.");
            return;
        }

        // =====================================================================
        // MODE A: CREATE ACCOUNT
        // =====================================================================
        if (currentMode === "signup") {
            setFormLoading(true, "Registering Gatekeeper Profile...");

            // Try Firebase Client Auth in background if enabled
            if (firebaseAuth) {
                firebaseAuth.createUserWithEmailAndPassword(email, password).then(async (cred) => {
                    if (cred && cred.user && fullName) {
                        await cred.user.updateProfile({ displayName: fullName });
                    }
                }).catch(err => {
                    console.log("Client Firebase Auth notice (fallback active):", err.message);
                });
            }

            // Call Backend Enterprise Registration Endpoint (Guaranteed to succeed in Firestore)
            try {
                const regResp = await fetch("/api/auth/register", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    body: JSON.stringify({
                        email: email,
                        password: password,
                        full_name: fullName,
                        role: selectedRole,
                        remember: remember
                    })
                });

                const regResult = await regResp.json();

                if (regResp.ok && regResult.success) {
                    showToast(`Account created! Welcome, ${fullName}.`, "success");
                    showAlert(`Account established successfully as ${selectedRole}! Loading your console...`, "success");

                    setTimeout(() => {
                        window.location.href = regResult.redirect_url || nextUrl || "/dashboard";
                    }, 650);
                    return;
                } else {
                    setFormLoading(false);
                    showAlert(regResult.error || "Registration failed. Please verify credentials.");
                    return;
                }
            } catch (regErr) {
                setFormLoading(false);
                showAlert(`Registration error: ${regErr.message}`);
                return;
            }
        }

        // =====================================================================
        // MODE B: SIGN IN
        // =====================================================================
        setFormLoading(true, "Authenticating...");

        // 1. First attempt Firebase Client Auth if initialized
        if (firebaseAuth) {
            try {
                const userCredential = await firebaseAuth.signInWithEmailAndPassword(email, password);
                const idToken = await userCredential.user.getIdToken(true);
                await exchangeTokenWithFlask(idToken, remember);
                return;
            } catch (fbErr) {
                console.log("Firebase client auth notice (checking backend):", fbErr.code || fbErr.message);
                if (fbErr.code === "auth/wrong-password") {
                    setFormLoading(false);
                    showAlert("Incorrect password. Please verify and try again.");
                    return;
                }
            }
        }

        // 2. Call Backend Enterprise Password Login Endpoint
        try {
            const loginResp = await fetch("/api/auth/login-password", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({
                    email: email,
                    password: password,
                    remember: remember
                })
            });

            const loginResult = await loginResp.json();

            if (loginResp.ok && loginResult.success) {
                showToast(loginResult.message || "Logged in successfully!", "success");
                showAlert("Identity verified! Redirecting to command center...", "success");

                setTimeout(() => {
                    window.location.href = loginResult.redirect_url || nextUrl || "/dashboard";
                }, 600);
            } else {
                setFormLoading(false);
                showAlert(loginResult.error || "Invalid email or password.");
            }
        } catch (serverErr) {
            setFormLoading(false);
            console.error("Login server error:", serverErr);
            showAlert(`Login network error: ${serverErr.message}`);
        }
    });

    // --------------------------------------------------------------------------
    // 8. Google Sign-In with Popup
    // --------------------------------------------------------------------------
    btnGoogleSignIn.addEventListener("click", async () => {
        if (isSubmitting) return;
        hideAlert();

        setFormLoading(true, "Opening Google Sign-In...");

        if (!firebaseAuth || !googleProvider) {
            setFormLoading(false);
            showAlert("Firebase Auth is initializing. Please refresh page and try again.", "warning");
            return;
        }

        try {
            // Force Google account chooser so the user selects their actual account
            googleProvider.setCustomParameters({
                prompt: 'select_account'
            });

            const result = await firebaseAuth.signInWithPopup(googleProvider);
            const user = result.user;
            const idToken = await user.getIdToken(true);

            // Send REAL verified Google token to Flask backend with selected role
            const chosenRole = selectRole ? selectRole.value : "Requester";
            await exchangeTokenWithFlask(idToken, checkRemember.checked, chosenRole);
        } catch (popupErr) {
            console.error("Google popup error:", popupErr);
            setFormLoading(false);

            if (popupErr.code === "auth/popup-closed-by-user") {
                showAlert("Google Sign-In popup was closed before completing. Please select your Google account to proceed.", "warning");
            } else if (popupErr.code === "auth/popup-blocked") {
                showAlert("Popup was blocked by your browser. Redirecting to Google Sign-In...", "info");
                try {
                    await firebaseAuth.signInWithRedirect(googleProvider);
                } catch (redErr) {
                    showAlert("Redirect error: " + redErr.message);
                }
            } else if (popupErr.code === "auth/unauthorized-domain") {
                showAlert(
                    "Domain not authorized in Firebase. Please access via http://localhost:5000/login or http://127.0.0.1:5000/login.",
                    "danger"
                );
            } else if (popupErr.code === "auth/operation-not-allowed") {
                showAlert(
                    "Google Provider is disabled in Firebase Console. Enable 'Google' in Firebase Authentication > Sign-in method.",
                    "warning"
                );
            } else {
                showAlert(`Google Sign-In Error: ${popupErr.message || popupErr.code}`);
            }
        }
    });

    // --------------------------------------------------------------------------
    // 9. Crucial Feature: One-Click Role Simulation
    // --------------------------------------------------------------------------
    async function triggerSimulatedRoleLogin(role) {
        setFormLoading(true, `Activating ${role} Session...`);
        hideAlert();

        try {
            const resp = await fetch("/api/auth/simulate-role", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({ role: role })
            });

            const data = await resp.json();

            if (resp.ok && data.success) {
                showToast(`Signed in as ${role}!`, "success");
                showAlert(`Role activated: ${role}. Loading your procurement console...`, "success");

                setTimeout(() => {
                    window.location.href = data.redirect_url || nextUrl || "/dashboard";
                }, 600);
            } else {
                setFormLoading(false);
                showAlert(data.error || "Role simulation failed on server.");
            }
        } catch (err) {
            setFormLoading(false);
            console.error("Simulation error:", err);
            showAlert(`Role simulation error: ${err.message}`);
        }
    }

    if (btnSimulateDirector) {
        btnSimulateDirector.addEventListener("click", () => {
            triggerSimulatedRoleLogin("Procurement Director");
        });
    }

    if (btnSimulateRequester) {
        btnSimulateRequester.addEventListener("click", () => {
            triggerSimulatedRoleLogin("Requester");
        });
    }
});
