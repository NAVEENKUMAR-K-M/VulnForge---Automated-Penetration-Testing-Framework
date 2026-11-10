"""
Writeup sources.

Phase 2 ships a small **seed corpus** of original, generically-worded security
knowledge (NOT copied from any specific disclosed report) so the retrieval
pipeline is useful out of the box without scraping anything. Real external
sources (HackerOne Hacktivity, public PoC repos) are added later and MUST
respect each source's ToS and only index disclosed, redistributable content,
always storing provenance.
"""

from __future__ import annotations

from app.models.writeup import WriteupSource
from app.schemas.writeup import WriteupIngestInput


def get_seed_writeups() -> list[WriteupIngestInput]:
    """Return the built-in seed knowledge corpus (original content)."""
    return [
        WriteupIngestInput(
            title="SQL injection via unparameterised search parameter",
            vuln_class="sqli",
            cwe_id="CWE-89",
            severity="high",
            source=WriteupSource.MANUAL,
            tech_stack=["mysql", "php", "laravel"],
            tags=["injection", "database"],
            content=(
                "A search endpoint concatenated the user-supplied query string "
                "directly into a SQL statement. Supplying a single quote broke the "
                "query and revealed a database error, confirming injection. Using a "
                "UNION-based payload, the number of columns was enumerated and the "
                "database version and current user were extracted. Boolean- and "
                "time-based blind techniques work when errors are suppressed. "
                "Remediation: use parameterised queries / prepared statements and an "
                "allow-list for sortable columns; never build SQL by string "
                "concatenation. ORMs help but raw queries must still bind parameters."
            ),
        ),
        WriteupIngestInput(
            title="Stored XSS through an unescaped profile field",
            vuln_class="xss",
            cwe_id="CWE-79",
            severity="medium",
            source=WriteupSource.MANUAL,
            tech_stack=["react", "node", "express"],
            tags=["xss", "client-side"],
            content=(
                "A profile 'bio' field was rendered without output encoding, allowing "
                "a script payload to execute in the context of any viewer. Because the "
                "value was persisted, it was stored (persistent) XSS affecting other "
                "users. The payload stole session cookies by sending document.cookie to "
                "an attacker host. Remediation: contextually encode output, set "
                "HttpOnly and SameSite on session cookies, and apply a strict "
                "Content-Security-Policy. Framework auto-escaping must not be bypassed "
                "with constructs like dangerouslySetInnerHTML."
            ),
        ),
        WriteupIngestInput(
            title="SSRF in a URL-preview feature reaching cloud metadata",
            vuln_class="ssrf",
            cwe_id="CWE-918",
            severity="critical",
            source=WriteupSource.MANUAL,
            tech_stack=["aws", "python", "flask"],
            tags=["ssrf", "cloud"],
            content=(
                "A link-preview feature fetched any URL the user submitted. Pointing it "
                "at the cloud instance metadata endpoint (169.254.169.254) returned IAM "
                "credentials, enabling privilege escalation into the cloud account. "
                "Internal-only services were also reachable. Remediation: validate and "
                "allow-list destinations, resolve and block link-local / private ranges, "
                "disable unused redirects, and prefer IMDSv2 with hop-limit on cloud "
                "hosts. Treat any server-side fetch of user input as SSRF-prone."
            ),
        ),
        WriteupIngestInput(
            title="IDOR exposing other users' records via sequential IDs",
            vuln_class="idor",
            cwe_id="CWE-639",
            severity="high",
            source=WriteupSource.MANUAL,
            tech_stack=["rest", "api"],
            tags=["access-control", "authorization"],
            content=(
                "An API returned an invoice by numeric id without checking that the "
                "invoice belonged to the authenticated user. Decrementing the id "
                "returned other customers' invoices — an insecure direct object "
                "reference. The flaw is an access-control failure, not an "
                "authentication one. Remediation: enforce per-object authorization on "
                "every request server-side, scope queries by the caller's identity, and "
                "prefer unguessable identifiers as defence in depth (not as the only "
                "control)."
            ),
        ),
        WriteupIngestInput(
            title="Exposed .git directory leaking source and secrets",
            vuln_class="info-disclosure",
            cwe_id="CWE-538",
            severity="medium",
            source=WriteupSource.MANUAL,
            tech_stack=["nginx", "apache"],
            tags=["recon", "misconfiguration"],
            content=(
                "A publicly served .git directory allowed reconstructing the full "
                "source tree from pack files and loose objects. The history contained "
                "hard-coded API keys and database credentials that had never been "
                "rotated. Directory listing was not even required — well-known paths "
                "like /.git/HEAD and /.git/config confirmed exposure. Remediation: "
                "block access to VCS metadata at the web server, deploy build artifacts "
                "rather than working trees, and rotate any secret that was ever "
                "committed."
            ),
        ),
        WriteupIngestInput(
            title="Jenkins script console RCE from weak authentication",
            vuln_class="rce",
            cwe_id="CWE-284",
            severity="critical",
            source=WriteupSource.MANUAL,
            tech_stack=["jenkins", "java", "groovy"],
            tags=["rce", "ci-cd"],
            content=(
                "An internet-exposed Jenkins instance allowed access to the Groovy "
                "script console with weak/!default access control. The script console "
                "runs arbitrary Groovy on the controller, giving remote code execution "
                "and access to stored CI credentials, which pivot into connected "
                "systems. Remediation: require authentication, enable matrix "
                "authorization, keep Jenkins and plugins updated, never expose the "
                "controller to the internet, and restrict the script console to "
                "trusted admins only."
            ),
        ),
    ]
