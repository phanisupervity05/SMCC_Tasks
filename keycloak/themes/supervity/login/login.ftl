<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username','password') displayInfo=true; section>

    <#if section = "header">
        Sign in to your account
    </#if>

    <#if section = "form">
        <form id="kc-form-login" action="${url.loginAction}" method="post">
            <div class="sv-field">
                <label for="username" class="sv-label">
                    <#if !realm.loginWithEmailAllowed>${msg("username")}<#elseif !realm.registrationEmailAsUsername>${msg("usernameOrEmail")}<#else>Email</#if>
                </label>
                <input 
                    id="username" 
                    name="username" 
                    value="${(login.username!'')}" 
                    type="text" 
                    class="sv-input" 
                    autofocus 
                    autocomplete="username"
                    placeholder="Enter your email"
                />
                <#if messagesPerField.existsError('username','password')>
                    <span class="sv-error">${kcSanitize(messagesPerField.getFirstError('username','password'))?no_esc}</span>
                </#if>
            </div>

            <div class="sv-field">
                <label for="password" class="sv-label">Password</label>
                <input 
                    id="password" 
                    name="password" 
                    type="password" 
                    class="sv-input" 
                    autocomplete="current-password"
                    placeholder="Enter your password"
                />
            </div>

            <div class="sv-options">
                <#if realm.rememberMe && !usernameHidden??>
                    <label class="sv-checkbox">
                        <input id="rememberMe" name="rememberMe" type="checkbox" <#if login.rememberMe??>checked</#if>>
                        <span>Remember me</span>
                    </label>
                <#else>
                    <div></div>
                </#if>
                
                <#if realm.resetPasswordAllowed>
                    <a href="${url.loginResetCredentialsUrl}" class="sv-link">Forgot password?</a>
                </#if>
            </div>

            <button type="submit" class="sv-button" name="login" id="kc-login">
                Sign In
            </button>
        </form>
    </#if>

    <#if section = "info">
        <div class="sv-register-link">
            <span>Don't have an account?</span>
            <a href="javascript:void(0)" onclick="redirectToRegister()" class="sv-link">Create Account</a>
        </div>
        <script>
            function redirectToRegister() {
                // Get the redirect_uri from the current URL to determine the app's base URL
                // The redirect_uri should already include the base path (e.g., https://example.com/app1/api/auth/callback/keycloak)
                const urlParams = new URLSearchParams(window.location.search);
                const redirectUri = urlParams.get('redirect_uri');
                if (redirectUri) {
                    try {
                        const url = new URL(redirectUri);
                        // Extract base path from redirect_uri by looking for /api/auth pattern
                        const pathParts = url.pathname.split('/api/auth');
                        const basePath = pathParts[0] || '';
                        window.location.href = url.origin + basePath + '/auth/register';
                    } catch (e) {
                        // Fallback to localhost if parsing fails
                        window.location.href = 'http://localhost:3001/auth/register';
                    }
                } else {
                    // Fallback
                    window.location.href = 'http://localhost:3001/auth/register';
                }
            }
        </script>
    </#if>

    <#if section = "socialProviders">
        <#if realm.password && social.providers??>
            <div class="sv-divider"><span>or</span></div>
            <div class="sv-social">
                <#list social.providers as p>
                    <a href="${p.loginUrl}" class="sv-social-btn">
                        Continue with ${p.displayName}
                    </a>
                </#list>
            </div>
        </#if>
    </#if>

</@layout.registrationLayout>
