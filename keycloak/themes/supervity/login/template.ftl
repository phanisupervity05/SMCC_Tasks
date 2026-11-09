<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="robots" content="noindex, nofollow">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Sign in | Supervity</title>
    <link rel="icon" href="${url.resourcesPath}/img/favicon.ico" />
    <link href="${url.resourcesPath}/css/styles.css" rel="stylesheet" />
</head>
<body>
    <div class="sv-login-page">
        <div class="sv-login-container">
        <!-- Logo and Brand -->
        <div class="sv-header">
            <div class="sv-logo">
                <img src="${url.resourcesPath}/img/logo.svg" alt="Supervity" width="40" height="40" />
            </div>
            <span class="sv-brand">Supervity</span>
        </div>
            
            <!-- Card -->
            <div class="sv-card">
                <h1 class="sv-title"><#nested "header"></h1>
                
                <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
                    <div class="sv-alert sv-alert-${message.type}">
                        ${kcSanitize(message.summary)?no_esc}
                    </div>
                </#if>
                
                <#nested "form">
                
                <#if auth?has_content && auth.showTryAnotherWayLink()>
                    <form id="kc-select-try-another-way-form" action="${url.loginAction}" method="post">
                        <input type="hidden" name="tryAnotherWay" value="on"/>
                        <a href="#" class="sv-link" onclick="document.forms['kc-select-try-another-way-form'].submit();return false;">
                            ${msg("doTryAnotherWay")}
                        </a>
                    </form>
                </#if>
                
                <#nested "socialProviders">
            </div>
            
            <#if displayInfo>
                <div class="sv-info">
                    <#nested "info">
                </div>
            </#if>
        </div>
    </div>
</body>
</html>
</#macro>
