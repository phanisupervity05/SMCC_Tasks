<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('firstName','lastName','email','username','password','password-confirm') displayInfo=true; section>

    <#if section = "header">
        Create your account
    </#if>

    <#if section = "form">
        <form id="kc-register-form" action="${url.registrationAction}" method="post">
            <div class="sv-field">
                <label for="firstName" class="sv-label">First Name</label>
                <input 
                    id="firstName" 
                    name="firstName" 
                    value="${(register.formData.firstName!'')}" 
                    type="text" 
                    class="sv-input"
                    placeholder="Enter your first name"
                />
                <#if messagesPerField.existsError('firstName')>
                    <span class="sv-error">${kcSanitize(messagesPerField.get('firstName'))?no_esc}</span>
                </#if>
            </div>

            <div class="sv-field">
                <label for="lastName" class="sv-label">Last Name</label>
                <input 
                    id="lastName" 
                    name="lastName" 
                    value="${(register.formData.lastName!'')}" 
                    type="text" 
                    class="sv-input"
                    placeholder="Enter your last name"
                />
                <#if messagesPerField.existsError('lastName')>
                    <span class="sv-error">${kcSanitize(messagesPerField.get('lastName'))?no_esc}</span>
                </#if>
            </div>

            <div class="sv-field">
                <label for="email" class="sv-label">Email</label>
                <input 
                    id="email" 
                    name="email" 
                    value="${(register.formData.email!'')}" 
                    type="email" 
                    class="sv-input"
                    autocomplete="email"
                    placeholder="Enter your email"
                />
                <#if messagesPerField.existsError('email')>
                    <span class="sv-error">${kcSanitize(messagesPerField.get('email'))?no_esc}</span>
                </#if>
            </div>

            <#if !realm.registrationEmailAsUsername>
                <div class="sv-field">
                    <label for="username" class="sv-label">Username</label>
                    <input 
                        id="username" 
                        name="username" 
                        value="${(register.formData.username!'')}" 
                        type="text" 
                        class="sv-input"
                        autocomplete="username"
                        placeholder="Choose a username"
                    />
                    <#if messagesPerField.existsError('username')>
                        <span class="sv-error">${kcSanitize(messagesPerField.get('username'))?no_esc}</span>
                    </#if>
                </div>
            </#if>

            <div class="sv-field">
                <label for="password" class="sv-label">Password</label>
                <input 
                    id="password" 
                    name="password" 
                    type="password" 
                    class="sv-input"
                    autocomplete="new-password"
                    placeholder="Create a password"
                />
                <#if messagesPerField.existsError('password')>
                    <span class="sv-error">${kcSanitize(messagesPerField.get('password'))?no_esc}</span>
                </#if>
            </div>

            <div class="sv-field">
                <label for="password-confirm" class="sv-label">Confirm Password</label>
                <input 
                    id="password-confirm" 
                    name="password-confirm" 
                    type="password" 
                    class="sv-input"
                    autocomplete="new-password"
                    placeholder="Confirm your password"
                />
                <#if messagesPerField.existsError('password-confirm')>
                    <span class="sv-error">${kcSanitize(messagesPerField.get('password-confirm'))?no_esc}</span>
                </#if>
            </div>

            <#if recaptchaRequired??>
                <div class="sv-field">
                    <div class="g-recaptcha" data-size="compact" data-sitekey="${recaptchaSiteKey}"></div>
                </div>
            </#if>

            <button type="submit" class="sv-button">
                Create Account
            </button>
        </form>
    </#if>

    <#if section = "info">
        <span>Already have an account?</span>
        <a href="${url.loginUrl}" class="sv-link">Sign in</a>
    </#if>

</@layout.registrationLayout>
