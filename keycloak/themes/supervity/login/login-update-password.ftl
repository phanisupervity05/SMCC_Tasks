<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('password','password-confirm') displayInfo=false; section>

    <#if section = "header">
        Update your password
    </#if>

    <#if section = "form">
        <p class="sv-subtitle">Please create a new secure password for your account.</p>
        
        <form id="kc-passwd-update-form" action="${url.loginAction}" method="post">
            <input type="text" id="username" name="username" value="${username}" autocomplete="username" readonly="readonly" style="display:none;"/>
            <input type="password" id="password" name="password" autocomplete="current-password" style="display:none;"/>
            
            <div class="sv-field">
                <label for="password-new" class="sv-label">New Password</label>
                <input 
                    type="password" 
                    id="password-new" 
                    name="password-new" 
                    class="sv-input" 
                    autofocus 
                    autocomplete="new-password"
                    placeholder="Enter your new password"
                />
                <#if messagesPerField.existsError('password')>
                    <span class="sv-error">${kcSanitize(messagesPerField.get('password'))?no_esc}</span>
                </#if>
                <p class="sv-hint">Min 12 characters with uppercase, lowercase, number, and special character</p>
            </div>

            <div class="sv-field">
                <label for="password-confirm" class="sv-label">Confirm Password</label>
                <input 
                    type="password" 
                    id="password-confirm" 
                    name="password-confirm" 
                    class="sv-input"
                    autocomplete="new-password"
                    placeholder="Re-enter your new password"
                />
                <#if messagesPerField.existsError('password-confirm')>
                    <span class="sv-error">${kcSanitize(messagesPerField.get('password-confirm'))?no_esc}</span>
                </#if>
            </div>

            <#if isAppInitiatedAction??>
                <div class="sv-options">
                    <label class="sv-checkbox">
                        <input type="checkbox" id="logout-sessions" name="logout-sessions" value="on" checked>
                        <span>Sign out from other devices</span>
                    </label>
                </div>
            </#if>

            <button type="submit" class="sv-button">
                Update Password
            </button>
            
            <#if isAppInitiatedAction??>
                <button type="submit" name="cancel-aia" value="true" class="sv-button-secondary">
                    Skip for now
                </button>
            </#if>
        </form>
    </#if>

</@layout.registrationLayout>
