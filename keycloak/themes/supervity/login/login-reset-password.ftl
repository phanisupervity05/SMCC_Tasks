<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username') displayInfo=true; section>

    <#if section = "header">
        Reset your password
    </#if>

    <#if section = "form">
        <p class="sv-subtitle">Enter your email address and we'll send you a link to reset your password.</p>
        
        <form id="kc-reset-password-form" action="${url.loginAction}" method="post">
            <div class="sv-field">
                <label for="username" class="sv-label">Email</label>
                <input 
                    type="text" 
                    id="username" 
                    name="username" 
                    class="sv-input" 
                    autofocus
                    autocomplete="email"
                    placeholder="Enter your email"
                    value="${(auth.attemptedUsername!'')}"
                />
                <#if messagesPerField.existsError('username')>
                    <span class="sv-error">${kcSanitize(messagesPerField.get('username'))?no_esc}</span>
                </#if>
            </div>

            <button type="submit" class="sv-button">
                Send Reset Link
            </button>
        </form>
    </#if>

    <#if section = "info">
        <div class="sv-back-link">
            <a href="${url.loginUrl}" class="sv-link">&larr; Back to sign in</a>
        </div>
    </#if>

</@layout.registrationLayout>

