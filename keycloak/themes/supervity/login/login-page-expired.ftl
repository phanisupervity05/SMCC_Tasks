<#import "template.ftl" as layout>
<@layout.registrationLayout displayInfo=false; section>

    <#if section = "header">
        Session expired
    </#if>

    <#if section = "form">
        <p class="sv-subtitle">Your session has expired. Please sign in again to continue.</p>
        
        <a href="${url.loginRestartFlowUrl}" class="sv-button" style="display: block; text-align: center; text-decoration: none;">
            Continue to Sign In
        </a>
    </#if>

</@layout.registrationLayout>

