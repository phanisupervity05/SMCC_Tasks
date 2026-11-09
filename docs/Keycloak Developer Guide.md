# Pluggable Authorization Engine: Developer Guide

## 1. The Philosophy: Focus on Logic, Not Security Plumbing

As an application developer, your primary goal is to build business features. You should not be burdened with writing complex, repetitive, and error-prone security code inside every API endpoint. This engine is designed to completely externalize authorization logic.

### How Your Job Becomes Simpler

- **You write business logic, period.** The engine handles the "Is this user allowed?" question before your code even runs.
- **Your endpoint code is cleaner and more readable.** Gone are the nested `if/else` statements checking for roles and permissions.
- **Security policies are managed in one place.** Instead of hunting through code, all access rules are in the human-readable `authz.map.json`.
- **Policies can be updated without redeploying your service.** Security becomes more agile and responsive.

## 2. The `authz.map` Policy Language

Think of `authz.map.json` not as a config file, but as a script written in a declarative "Policy Language." It defines, in plain JSON, exactly who can access what, and under which conditions.

### Pluggable Engine Architecture

The core of the system is the `AuthzEngine` class located in `app/authz.py`. It is instantiated once in `app/security.py` and used as a single FastAPI dependency on the main API router in `app/main.py`. This design makes security a pluggable component rather than scattered logic.

**Key Principle:** Secure by Default. If you add a new API endpoint, it is automatically protected. Access will be denied unless you explicitly add a rule for it in `authz.map.json`.

### The Core Operators

Operators determine the logic for evaluating a rule. A rule can be a simple role check, or a complex, nested combination of operators.

| Operator | Purpose | Syntax |
|----------|---------|--------|
| **Role Check** | Checks if a user has a specific role | `"role-name"` |
| **ANY** | Succeeds if **at least one** of the sub-rules is true (Logical OR) | `{ "ANY": [ rule1, rule2, ... ] }` |
| **ALL** | Succeeds only if **all** of the sub-rules are true (Logical AND) | `{ "ALL": [ rule1, rule2, ... ] }` |
| **NOT** | Succeeds if the sub-rule is false (Logical NOT) | `{ "NOT": rule }` |

#### Example: Combining Logical Operators

**Rule:** Allow access if the user is an `admin` OR (is both a `manager` AND NOT a `trainee`).

```json
{
  "ANY": [
    "admin",
    { "ALL": [ "manager", { "NOT": "trainee" } ] }
  ]
}
```

### The Value & Comparison Operators

These operators allow you to perform checks against data from the user's token (claims) and the request context.

| Operator | Purpose | Syntax |
|----------|---------|--------|
| **claims** | Checks for exact equality between a user/context value and an expected value | `{ "claims": { "key_placeholder": "value_placeholder" } }` |
| **claims_lte** | Checks if a numerical value is **Less Than or Equal To** another | `{ "claims_lte": { "key_placeholder": "value_placeholder" } }` |
| **claims_gte** | Checks if a numerical value is **Greater Than or Equal To** another | `{ "claims_gte": { "key_placeholder": "value_placeholder" } }` |
| **claims_contains** | Checks if a value exists within a list | `{ "claims_contains": { "list_placeholder": "value_placeholder" } }` |
| **claims_timediff_lte** | Checks if a Unix timestamp claim is recent (within N seconds) | `{ "claims_timediff_lte": { "timestamp_claim_name": N } }` |

### Placeholder Syntax: The Key to Dynamic Rules

Placeholders allow your static rules to be evaluated against dynamic, runtime data.

| Placeholder | Resolves To | Example |
|-------------|-------------|---------|
| `{user.<claim>}` | A claim from the user's JWT | `{user.sub}`, `{user.approval_limit}` |
| `{path.<param>}` | A parameter from the URL path | `{path.user_id}` |
| `{context.<...>}` | A value from the custom context object built by your endpoint | `{context.resource.owner_id}` |

### Role-Based Access Control (RBAC)

The engine provides powerful role-based control using the `ANY` and `ALL` operators.

- `"ALL": ["role1", "role2"]`: The user must have both `role1` AND `role2`.
- `"ANY": ["role1", "role2"]`: The user must have either `role1` OR `role2`.

**Example from `authz.map.json`:**

```json
{
  "/app1/api/admin.*": {
    "description": "Requires the user to have the 'admin' role.",
    "ALL": ["admin"]
  }
}
```

### Attribute-Based Access Control (ABAC)

Go beyond roles by defining rules based on any attribute (claim) inside the user's JWT. This is accomplished with the `claims` keyword.

**Example:** Grant access only if the user's `department` claim in their token is exactly `"finance"`.

```json
{
  "/app1/api/finance/reports": {
    "ALL": [
      {
        "claims": {
          "{user.department}": "finance"
        }
      }
    ]
  }
}
```

> **Note:** To use this feature, you must add the attribute to the user in Keycloak and then create a "User Attribute" mapper in the client's scope to ensure the attribute is included in the access token.

### Negation / Exception Rules

The `NOT` operator allows you to invert conditions, which is essential for creating exceptions and enforcing policies like Segregation of Duties.

**Example:** Grant access if the user has the `finance-user` role but does **NOT** have the `expense-approver` role.

```json
{
  "/app1/api/expenses/submit": {
    "ALL": [
      "finance-user",
      {
        "NOT": "expense-approver"
      }
    ]
  }
}
```

The `NOT` operator can also contain nested `ANY` or `ALL` blocks for highly complex logic.

## 3. How to Secure a New Backend API

Follow this workflow to protect a new microservice or API with the engine.

1. **Integrate the Engine:** Copy the `app/authz.py` and `app/security.py` files into your new project. Install necessary dependencies (FastAPI, python-jose, etc.).
2. **Create Policy Files:** Create `app/public.map.json` and `app/authz.map.json` for the new service's routes.
3. **Apply the Global Dependency:** In your new service's main file, apply the `verify_access` dependency to your main FastAPI router. This protects all simple endpoints.
4. **Implement Manual Checks:** For any endpoint that requires context-aware authorization, follow the "Pattern B" guide below.

### Pattern A: Simple Authorization (Roles/Static Claims)

For checks that only depend on the user's identity.

**Rule (`authz.map.json`):**

```json
"/app1/api/admin/dashboard": { "ALL": ["admin"] }
```

**Endpoint (`main.py`):**

```python
# The router's dependency handles this automatically. No extra code needed.

@api_router.get("/admin/dashboard", tags=["Simple Scenarios"])
def get_admin_dashboard(user: dict = Depends(get_current_user)):
    """Requires the 'admin' role."""
    return {"message": f"Welcome to the admin dashboard, {user.get('preferred_username')}"}
```

### Pattern B: Context-Aware Authorization

For checks that depend on the resource being accessed or other runtime data.

> **Note:** Requires **explicit calling of authz_engine.check(request, user, context)**, once context is established in the backend code.

**Rule (Ownership Check):**

```json
"/app1/api/documents/{document_id}": {
  "ANY": [ "admin", { "claims": { "sub": "{context.resource.owner_id}" } } ]
}
```

**Endpoint Implementation:**

```python
from .security import get_current_user, authz_engine # Import engine

@api_router.put("/documents/{document_id}")
def update_document(document_id: str, request: Request, user: dict = Depends(get_current_user)):
    # 1. Fetch resource
    doc = db.get_document(document_id)
    # 2. Build context
    context = {"resource": doc}
    # 3. Manually invoke engine
    authz_engine.check(request, user, context)
    # 4. Proceed with logic
    return {"status": "Updated"}
```

## 4. Practical Examples and Testing

This section provides practical examples for the rules defined in `authz.map.json`.

> **Prerequisite:** Before testing, ensure the application is running with `make up`. You will test all endpoints through the frontend application, which provides a user-friendly interface for this purpose.

### Testing the Endpoints

1.  **Launch the Application:** Navigate to [http://localhost:3001/app1](http://localhost:3001/app1) (or your configured `BASE_PATH`).
2.  **Sign In:** Use the "Sign In" button. You will be redirected to Keycloak.
3.  **Use Test Credentials:**
    *   For **admin** access, sign in with: `admin` / `password`
    *   For a **regular user**, sign in with: `user` / `password`
    *   *(Note: You can create more users with specific roles and attributes in the [Keycloak Admin Console](http://localhost:8080) to test other rules).*
4.  **Trigger API Calls:** Once signed in, the dashboard provides buttons to "Call Protected Endpoint" and "Call Admin-Only Endpoint".
    *   **As `admin`:** Both calls should succeed.
    *   **As `user`:** The protected call should succeed, but the admin-only call will fail with a `403 Forbidden` error, which you can see in your browser's developer console network tab.

The frontend dashboard displays the raw JSON response from the API, allowing you to verify the outcome of each test.

### Rule 1: Admin Access (Simple RBAC)

```json
"/api/admin.*": { "ALL": ["admin"] }
```

**Explanation:** Classic Role-Based Access Control (RBAC) rule. Grants access to any endpoint starting with `/api/admin/` only if the user's JWT contains the realm role `admin`. The pre-configured `admin` user has this role.

### Rule 2: Logical OR with Attribute-Based Access
```json
"/api/test-finance": {
  "description": "check if has admin role OR department attribute for finance user",
  "ANY": [ "admin", { "claims": { "{user.department}": "finance" } }]
}
```
**Explanation:** Uses the `ANY` operator. Access is granted if the user is an `admin` **OR** if their token contains a claim `department` with the value `finance`.

**Keycloak Setup for Attributes:**
1.  Create a new user (e.g., `finance_user`).
2.  In that user's **Attributes** tab, add a new attribute: Key=`department`, Value=`finance`.
3.  Map this attribute to a token claim: Go to **Clients** -> your client -> **Client Scopes** -> `...-dedicated` scope.
4.  Click **Configure a new mapper** -> **User Attribute**. Name it `department`, set User Attribute and Token Claim Name to `department`, and turn ON "Add to access token".

### Rule 3: Ownership Check (Context-Aware)

```json
"/api/documents/{document_id}": {
  "ANY": [ "admin", { "claims": { "sub": "{context.resource.owner_id}" } }]
}
```

**Explanation:** A context-aware rule for resource ownership. Access is granted if the user is an `admin` OR if their user ID (the `sub` claim in their JWT) matches the `owner_id` of the document being requested.

**Setup:**
1. Create a user `alice`. Note her User ID from the Keycloak UI (this is her `sub`).
2. In your `app/main.py`, ensure the mock database has an entry for Alice:
   ```python
   mock_db = { "documents": { "doc_123": {"owner_id": "PASTE_ALICE_USER_ID_HERE"} } }
   ```

### Rule 4: Data-Driven Limits (Context-Aware)

```json
"/api/purchase_orders/approve": {
  "ALL": [ "manager", { "claims_lte": { "approval_limit": "{context.request.amount}" } }]
}
```

**Explanation:** Grants access only if the user has the `manager` role AND their numerical `approval_limit` claim is less than or equal to the `amount` from the request body.

**Keycloak Setup:**
1. Create a realm role `manager`.
2. Create a user `manager_user`, assign the role.
3. In the user's **Attributes**, add `approval_limit` with value `5000`.
4. Map this attribute to a token claim named `approval_limit` with **Claim JSON Type** set to `long` or `integer`.

### Rule 5: Hierarchical Constraint (Context-Aware)

```json
"/api/analytics/{region}": {
  "ALL": [ "regional-manager", { "claims": { "region": "{path.region}" } }]
}
```

**Explanation:** Grants access if the user has the `regional-manager` role AND their `region` claim matches the `region` parameter from the URL path.

**Setup:**
1. Create a realm role `regional-manager`.
2. Create a user `manager_emea`, assign the role.
3. In the user's **Attributes**, add `region` with value `emea`. Map it to the token.

### Rule 6: Status-Based Transition (Context-Aware)

```json
"/api/articles/{article_id}/publish": { 
  "ALL": [ "editor", { "claims": { "{context.resource.status}": "reviewed" } } ] 
}
```

**Explanation:** Allows a user with the `editor` role to publish an article, but only if that article's current status is "reviewed".

### Rule 7: Multi-Tenancy Isolation (Context-Aware)

```json
"/api/tenants/{tenant_id}/customers": { 
  "ALL": [ { "claims": { "tenant_id": "{path.tenant_id}" } } ] 
}
```

**Explanation:** Ensures a user can only see data belonging to their own organization by matching their `tenant_id` claim against the `tenant_id` in the URL.

### Rule 8: Geofencing (Context-Aware)

```json
"/api/secure-asset": { 
  "ALL": [ { "claims": { "{context.environment.source_country}": "US" } } ] 
}
```

**Explanation:** Restricts access to a resource based on the geographic location of the request's source IP address.

### Rule 9: Time-Based Access (Context-Aware)

```json
"/api/contractor/access": {
  "ALL": [ 
    "contractor", 
    { "claims_gte": { "{context.environment.hour_utc}": 9 } }, 
    { "claims_lte": { "{context.environment.hour_utc}": 17 } } 
  ]
}
```

**Explanation:** Allows a user with the `contractor` role to access a resource, but only during business hours (9 AM to 5 PM / 17:00 UTC).

### Rule 10: Step-Up Authentication (Context-Aware)

```json
"/api/projects/{project_id}/delete": {
  "ALL": [ "admin", { "claims_timediff_lte": { "mfa_authenticated_at": 300 } } ]
}
```

**Explanation:** Allows an `admin` to perform a destructive action, but only if they have recently authenticated with a second factor. This is checked by ensuring their `mfa_authenticated_at` timestamp claim is no more than 300 seconds (5 minutes) old.

### Rule 11: Quota/Usage Limit (Context-Aware)

```json
"/api/files/upload": {
  "ALL": [ 
    "premium-user", 
    { "claims_lte": { "{context.usage.total_after_upload}": "{user.storage_quota}" } } 
  ]
}
```

**Explanation:** Allows a `premium-user` to upload a file, but only if their current usage plus the size of the new file does not exceed their personal `storage_quota` claim.

### Rule 12: Relationship-Based Access (Context-Aware)

```json
"/api/records/{record_id}": {
  "ANY": [
    { "claims": { "sub": "{context.resource.patient_id}" } },
    { "claims_contains": { "{context.resource.authorized_practitioners}": "{user.sub}" } }
  ]
}
```

**Explanation:** A complex rule for sensitive data. Access is granted if the user is the patient themselves (ownership check) OR if their user ID is in the list of `authorized_practitioners` for that specific record.

## 5. Best Practices

1. **Start Simple:** Begin with basic role-based rules and gradually add complexity as needed.
2. **Test Thoroughly:** Each rule should be tested with positive and negative test cases.
3. **Document Your Rules:** Add meaningful descriptions to your `authz.map.json` entries.
4. **Use Secure Defaults:** Always default to denying access unless explicitly allowed.
5. **Regular Audits:** Periodically review your authorization rules to ensure they still meet your security requirements.
6. **Performance Considerations:** Complex nested rules can impact performance. Monitor and optimize as needed.

## 6. Troubleshooting

### Common Issues

1. **403 Forbidden Errors:** Check that the user has the required roles and that the rule syntax is correct.
2. **Token Claims Missing:** Ensure that custom attributes are properly mapped to token claims in Keycloak.
3. **Context Not Available:** For context-aware rules, ensure that the endpoint is properly building and passing the context object.
4. **Time-Based Rules Failing:** Verify that server time is properly synchronized and timezone considerations are handled.

### Debugging Tips

1. Enable debug logging in the authorization engine to see rule evaluation details.
2. Use Keycloak's token inspection tools to verify token contents.
3. Test rules in isolation before combining them with complex logic.
4. Verify that placeholder values are resolving correctly in your context.
