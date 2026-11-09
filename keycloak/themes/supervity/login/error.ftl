<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false displayInfo=true; section>

    <#if section = "header">
        Something went wrong
    </#if>

    <#if section = "form">
        <p class="sv-subtitle">We encountered an error processing your request.</p>
        
        <div class="sv-alert sv-alert-error">
            ${kcSanitize(message.summary)?no_esc}
        </div>
        
        <#if skipLink??>
        <#else>
            <#if client?? && client.baseUrl?has_content>
                <a href="${client.baseUrl}" class="sv-button" style="display: block; text-align: center; text-decoration: none;">
                    Back to Application
                </a>
            </#if>
        </#if>
    </#if>

    <#if section = "info">
        <div class="sv-back-link">
            <a href="${url.loginUrl}" class="sv-link">&larr; Try signing in again</a>
        </div>
    </#if>

</@layout.registrationLayout>
